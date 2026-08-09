/**
 * WhatsApp front brain + queue relay (Cloudflare Worker, always-on, free tier).
 *
 * This worker is the *always-on brain* - it stays alive even when Colab/GPU is
 * down. For every message it:
 *   1. Tries the instant fast path first (pure-math calculators like /grade).
 *      If it matches, it computes and replies directly to WhatsApp in ~100ms -
 *      no Colab needed, no queue, no "waiting" message.
 *   2. Otherwise sends an instant "*Got it*" receipt so the user is never
 *      staring at a silent queue, then writes the message into the `wa_inbox`
 *      table on Neon PostgreSQL for the deep brain (backend/worker.py on Colab)
 *      to answer on demand.
 *
 * Deploy:
 *   1. npm i -D wrangler
 *   2. npx wrangler login
 *   3. npx wrangler secret put APP_SECRET             (Meta app secret)
 *   4. npx wrangler secret put SUPABASE_URL           (https://<ref>.supabase.co)
 *   5. npx wrangler secret put SUPABASE_SERVICE_KEY   (service_role key from Supabase)
 *   6. npx wrangler secret put WHATSAPP_TOKEN         (Meta permanent access token)
 *   7. set VERIFY_TOKEN and WHATSAPP_PHONE_NUMBER_ID as vars:
 *        npx wrangler var put VERIFY_TOKEN <token>
 *        npx wrangler var put WHATSAPP_PHONE_NUMBER_ID <id>
 *   8. npx wrangler deploy
 *   9. Create the wa_inbox table once in Supabase SQL editor
 *      (see supabase_schema.sql in this folder).
 *  10. In Meta dashboard, webhook URL = https://<your-worker>.workers.dev/webhook
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/webhook") {
      return handleVerify(request, env);
    }
    if (request.method === "POST" && url.pathname === "/webhook") {
      return handleMessage(request, env);
    }
    return new Response(JSON.stringify({ status: "not_found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  },
};

/** WhatsApp webhook verification (GET). */
async function handleVerify(request, env) {
  const mode = urlParam(request, "hub.mode");
  const challenge = urlParam(request, "hub.challenge");
  const token = urlParam(request, "hub.verify_token");

  if (mode === "subscribe" && token === env.VERIFY_TOKEN) {
    return new Response(challenge, { status: 200 });
  }
  return new Response("Verification failed", { status: 403 });
}

/** WhatsApp message webhook (POST) - validate signature, fast-path or enqueue. */
async function handleMessage(request, env) {
  if (!env.APP_SECRET || !env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) {
    return json({ status: "error", detail: "Relay not configured (APP_SECRET/SUPABASE_URL/SUPABASE_SERVICE_KEY)" }, 503);
  }

  const body = await request.arrayBuffer();
  const signature = request.headers.get("X-Hub-Signature-256") || "";

  const valid = await verifySignature(body, signature, env.APP_SECRET);
  if (!valid) {
    return json({ status: "error", detail: "Invalid signature" }, 401);
  }

  let payload;
  try {
    payload = JSON.parse(new TextDecoder().decode(body));
  } catch {
    return json({ status: "error", detail: "Invalid JSON" }, 400);
  }

  if (!payload.entry || !payload.entry[0] || !payload.entry[0].changes) {
    return json({ status: "ignored" }, 200);
  }

  const value = payload.entry[0].changes[0]?.value || {};
  if (!value.messages || value.messages.length === 0) {
    return json({ status: "ignored" }, 200); // statuses / read receipts
  }

  const msg = value.messages[0];
  const sender = msg.from;
  const type = msg.type;
  if (!sender || !type) {
    return json({ status: "ignored" }, 200);
  }

  const { text, mediaUri, mediaMime, mediaName } = parseMessage(msg);

  // ---- Fast path: pure math, answered by the always-on brain, zero waiting ----
  if (type === "text") {
    const instant = fastAnswer(text);
    if (instant) {
      await sendWhatsApp(env, sender, instant);
      return json({ status: "instant", sender }, 200);
    }
  }

  // ---- Receipt + deep path: acknowledge now, answer comes from Colab shortly ----
  try {
    await sendWhatsApp(
      env,
      sender,
      "*Got it* \u2014 running the full analysis now. I\u2019ll reply in a second."
    );
  } catch {
    // receipt is best-effort; the queued message still gets answered
  }

  try {
    const { data, error } = await supabaseInsert(env, {
      phone_number: sender,
      msg_type: type,
      text,
      media_uri: mediaUri,
      media_mime: mediaMime,
      media_name: mediaName,
      status: "pending",
    });
    if (error) throw error;
    return json({ status: "queued", message_id: data?.[0]?.id }, 200);
  } catch (e) {
    return json({ status: "error", detail: "Queue write failed" }, 500);
  }
}

/**
 * Fast path - pure-math calculators the always-on brain answers instantly.
 * Mirrors backend/commands/mining_commands.py (`/grade`). Returns null when
 * the message needs the deep brain instead.
 */
function fastAnswer(text) {
  const t = (text || "").trim();
  if (!t.startsWith("/")) return null;
  const parts = t.slice(1).trim().split(/\s+/);
  const cmd = (parts[0] || "").toLowerCase();

  if (cmd === "grade") return gradeCmd(parts.slice(1));
  if (cmd === "help") return helpText();
  return null; // everything else -> deep brain on Colab
}

function helpText() {
  return "*AI Mining OS*\n\nI answer instantly on:\n\n`/grade value <g/t> <tonnes> <recovery%>`\n`/grade cog <mining> <processing> <ga> <price> <recovery%>`\n`/grade conversion <g/t>`\n`/grade dilution <grade> <dilution%>`\n`/grade reconciliation <planned_g/t> <actual_g/t> <planned_t> <actual_t>`\n\nAnything else (reports, geology, cost analysis, images, voice) is processed by the deep brain and replies within seconds.";
}

function gradeCmd(parts) {
  if (parts.length === 0) {
    return "Usage:\n`/grade value <g/t> <tonnes> <recovery%>`\n`/grade cog <mining> <processing> <ga> <gold_price> <recovery%>`\n`/grade conversion <g/t>`\n`/grade dilution <grade> <dilution%>`\n`/grade reconciliation <planned_g/t> <actual_g/t> <planned_t> <actual_t>`";
  }
  const sub = parts[0].toLowerCase();
  const args = parts.slice(1);
  try {
    switch (sub) {
      case "value": return gradeValue(args);
      case "cog": return gradeCog(args);
      case "conversion": return gradeConversion(args);
      case "dilution": return gradeDilution(args);
      case "reconciliation": return gradeReconciliation(args);
      default: return gradeCmd([]);
    }
  } catch {
    return "Invalid numbers \u2014 check the usage with `/grade`.";
  }
}

function gradeValue(parts) {
  if (parts.length < 3) return "Usage: `/grade value <g/t> <tonnes> <recovery%>`\nExample: /grade value 5.2 10000 93";
  const g_t = parseFloat(parts[0]);
  const tonnes = parseFloat(parts[1]);
  const recovery = parseFloat(parts[2]) / 100;
  const goldOz = (g_t * tonnes * recovery) / 31.1035;
  const goldUsd = goldOz * 3250;
  const goldKg = (g_t * tonnes * recovery) / 1000;
  return `*Grade Value*\n\nGrade: ${g_t} g/t\nTonnage: ${tonnes.toLocaleString()} t\nRecovery: ${(recovery * 100).toFixed(1)}%\n\nContained metal: ${goldKg.toFixed(2)} kg (${goldOz.toLocaleString(undefined, { maximumFractionDigits: 1 })} oz)\nGross value: $${goldUsd.toLocaleString()}\nValue per tonne: $${(goldUsd / tonnes).toFixed(2)}/t\n\nFormula: grade \u00d7 tonnes \u00d7 recovery / 31.1035\nAssumed price: $3,250/oz`;
}

function gradeCog(parts) {
  if (parts.length < 5) return "Usage: `/grade cog <mining_cost> <processing_cost> <ga_cost> <gold_price> <recovery%>`\nExample: /grade cog 8 25 5 3250 95";
  const mining = parseFloat(parts[0]);
  const processing = parseFloat(parts[1]);
  const ga = parseFloat(parts[2]);
  const price = parseFloat(parts[3]);
  const recovery = parseFloat(parts[4]) / 100;
  const totalCost = mining + processing + ga;
  const cogOzT = totalCost / (price * recovery);
  const cogGT = cogOzT * 31.1035;
  return `*Cut-Off Grade*\n\nMining: $${mining}/t  Processing: $${processing}/t  G&A: $${ga}/t\nGold: $${price.toLocaleString()}/oz  Recovery: ${(recovery * 100).toFixed(1)}%\n\nTotal cost: $${totalCost}/t\nCOG: ${cogOzT.toFixed(4)} oz/t = ${cogGT.toFixed(3)} g/t\n\nGrades below ${cogGT.toFixed(3)} g/t are sub-economic at these costs.\nFormula: COG (oz/t) = Total Cost / (Recovery \u00d7 Price)`;
}

function gradeConversion(parts) {
  if (parts.length < 1) return "Usage: `/grade conversion <grams_per_tonne>`\nExample: /grade conversion 5.2";
  const g_t = parseFloat(parts[0]);
  const ozT = g_t / 31.1035;
  return `${g_t} g/t = ${ozT.toFixed(4)} oz/t\n= ${(g_t / 10).toFixed(4)}%\n= ${(g_t * 0.00220462).toFixed(6)} lb/t\n\n1 troy oz = 31.1035 g\n1 g/t = 0.032151 oz/t\n1 g/t = 0.1%`;
}

function gradeDilution(parts) {
  if (parts.length < 2) return "Usage: `/grade dilution <grade> <dilution%>`\nExample: /grade dilution 2.5 15";
  const grade = parseFloat(parts[0]);
  const dilution = parseFloat(parts[1]) / 100;
  const diluted = grade * (1 - dilution);
  const wasteRatio = dilution / (1 - dilution);
  return `*Dilution Adjustment*\n\nGrade: ${grade} g/t\nDilution: ${(dilution * 100).toFixed(0)}%\n\nDiluted grade: ${diluted.toFixed(3)} g/t\nWaste-to-ore: ${wasteRatio.toFixed(2)}:1\nLoss: ${(grade - diluted).toFixed(3)} g/t (${(dilution * 100).toFixed(0)}%)\n\nFormula: Diluted = Grade \u00d7 (1 \u2212 Dilution)`;
}

function gradeReconciliation(parts) {
  if (parts.length < 4) return "Usage: `/grade reconciliation <planned_g/t> <actual_g/t> <planned_t> <actual_t>`\nExample: /grade reconciliation 1.5 1.3 50000 48000";
  const pG = parseFloat(parts[0]);
  const aG = parseFloat(parts[1]);
  const pT = parseFloat(parts[2]);
  const aT = parseFloat(parts[3]);
  const gradeVar = ((aG - pG) / pG) * 100;
  const tonVar = ((aT - pT) / pT) * 100;
  const pMetal = (pG * pT) / 31.1035;
  const aMetal = (aG * aT) / 31.1035;
  const metalVar = ((aMetal - pMetal) / pMetal) * 100;
  const status = Math.abs(metalVar) <= 10 ? "ON TRACK" : "VARIANCE ALERT";
  const gradeNote = Math.abs(gradeVar) <= 5 ? "Grade control model is accurate." : "Investigate grade model \u2014 significant variance.";
  const tonNote = Math.abs(tonVar) <= 10 ? "Tonnage within acceptable range." : "Check blasting/mucking factors.";
  return `*Grade Reconciliation*\n\nGrade:   ${pG.toFixed(3)} g/t \u2192 ${aG.toFixed(3)} g/t (${gradeVar.toFixed(1)}%)\nTonnage: ${pT.toLocaleString()} t \u2192 ${aT.toLocaleString()} t (${tonVar.toFixed(1)}%)\nMetal:   ${pMetal.toLocaleString(undefined, { maximumFractionDigits: 0 })} oz \u2192 ${aMetal.toLocaleString(undefined, { maximumFractionDigits: 0 })} oz (${metalVar.toFixed(1)}%)\n\nStatus: *${status}*\n${gradeNote}\n${tonNote}`;
}

/** Send a WhatsApp text message via the Cloud API (reply from the worker). */
async function sendWhatsApp(env, to, text) {
  if (!env.WHATSAPP_TOKEN || !env.WHATSAPP_PHONE_NUMBER_ID) return;
  const url = `https://graph.facebook.com/v18.0/${env.WHATSAPP_PHONE_NUMBER_ID}/messages`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${env.WHATSAPP_TOKEN}`,
    },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      to,
      type: "text",
      text: { body: text },
    }),
  });
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`WhatsApp send failed (${resp.status}): ${err.slice(0, 200)}`);
  }
}

/** Extract message fields into inbox columns (mirrors backend/main.py). */
function parseMessage(msg) {
  const type = msg.type;
  let text = "";
  let mediaUri = "";
  let mediaMime = "";
  let mediaName = "";

  if (type === "text") {
    text = (msg.text?.body || "").slice(0, 5000);
  } else if (type === "audio") {
    const id = msg.audio?.id || "";
    mediaUri = `whatsapp://media/${id}`;
    mediaMime = msg.audio?.mime_type || "audio/ogg";
    mediaName = `${id}.ogg`;
    text = "[Voice note attached]";
  } else if (type === "image") {
    const id = msg.image?.id || "";
    mediaUri = `whatsapp://media/${id}`;
    mediaMime = msg.image?.mime_type || "image/png";
    mediaName = `image_${id}.png`;
    text = (msg.image?.caption || "Analyze this image").slice(0, 5000);
  } else if (type === "document") {
    const id = msg.document?.id || "";
    mediaUri = `whatsapp://media/${id}`;
    mediaMime = msg.document?.mime_type || "application/pdf";
    mediaName = msg.document?.filename || "document.pdf";
    text = `Analyze document: ${msg.document?.filename || "document"}`.slice(0, 5000);
  }

  return { text, mediaUri, mediaMime, mediaName };
}

/** HMAC-SHA256 verification using Web Crypto (matches X-Hub-Signature-256). */
async function verifySignature(body, signature, secret) {
  if (!signature) return false;
  if (signature.startsWith("sha256=")) signature = signature.slice(7);

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, body);
  const expected = [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");

  if (expected.length !== signature.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ signature.charCodeAt(i);
  return diff === 0;
}

/** Insert a row into wa_inbox via Supabase PostgREST (no SDK dependency). */
async function supabaseInsert(env, row) {
  const resp = await fetch(`${env.SUPABASE_URL}/rest/v1/wa_inbox`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
      Prefer: "return=representation",
    },
    body: JSON.stringify(row),
  });
  if (!resp.ok) {
    const err = await resp.text();
    return { data: null, error: new Error(`Supabase insert failed (${resp.status}): ${err.slice(0, 200)}`) };
  }
  const data = await resp.json();
  return { data, error: null };
}

function urlParam(request, name) {
  return new URL(request.url).searchParams.get(name);
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
