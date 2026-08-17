"""
Idle self-improvement tasks - run by the worker whenever the inbox is empty.

While the GPU/node is idle these tasks quietly make the system smarter:
  1. Analytics synthesis: compute quick statistics from the local datasets and
     store them as instant-answer knowledge entries.
  2. Conversation mining: extract recurring user questions from past web chat
     conversations and persist the Q&A into the knowledge base.
  3. Q&A generation: use the local LLM to derive factual Q&A pairs from dataset
     chunks (cadence-limited so it never delays a real message for long).

Every task is time-budgeted and failures are non-fatal - the system must always
prioritize answering user messages over self-improvement.
"""
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ai_os.tasks")

DATASETS_ROOT = Path(__file__).resolve().parent.parent / "datasets"
_IDLE_STATE: Dict[str, Any] = {"last_llm_task": 0.0}


class IdleTaskRunner:
    """Round-robin runner over the self-improvement task list."""

    def __init__(self, postgres_client, llm=None, budget_seconds: float = 6.0):
        self.db = postgres_client
        self.llm = llm
        self.budget_seconds = budget_seconds
        self._task_index = 0
        self._task_fns = [
            self.analytics_synthesis,
            self.kapoeta_synthesis,
            self.conversation_mining,
            self.qa_generation,
        ]

    def run_one(self) -> None:
        """Run exactly one task (round-robin), respecting the time budget."""
        fn = self._task_fns[self._task_index % len(self._task_fns)]
        self._task_index += 1
        started = time.time()
        try:
            fn()
        except Exception as e:  # never let self-improvement kill the worker
            logger.error(f"Idle task {fn.__name__} failed: {e}")
        elapsed = time.time() - started
        if elapsed > self.budget_seconds:
            logger.info(f"Idle task {fn.__name__} used {elapsed:.1f}s (over budget)")

    # ------------------------------------------------------------------ tasks

    def analytics_synthesis(self) -> None:
        """Compute lightweight stats from datasets and store knowledge entries."""
        added = 0
        market_file = DATASETS_ROOT / "markets" / "gold_market_intelligence.json"
        if market_file.exists():
            data = json.loads(market_file.read_text())
            spot = data.get("gold_market", {}).get("current_price_usd_per_oz")
            history = data.get("gold_price_history") or []
            prices = [
                float(p.get("price_usd_per_oz"))
                for p in history
                if isinstance(p, dict) and p.get("price_usd_per_oz") is not None
            ]
            if spot:
                self.db.add_knowledge(
                    "market",
                    "What is the current gold price?",
                    f"Current gold spot price is ${spot:,.2f}/oz.",
                    source="datasets/markets/gold_market_intelligence.json",
                    confidence=0.95,
                )
                added += 1
            if prices:
                avg = sum(prices) / len(prices)
                self.db.add_knowledge(
                    "market",
                    "What is the average gold price in the dataset?",
                    f"Average gold price across {len(prices)} data points: ${avg:,.2f}/oz "
                    f"(range ${min(prices):,.2f} - ${max(prices):,.2f}/oz).",
                    source="datasets/markets/gold_market_intelligence.json",
                    confidence=0.9,
                )
                added += 1

        prod_file = DATASETS_ROOT / "production" / "gold_production_data.json"
        if prod_file.exists():
            data = json.loads(prod_file.read_text())
            for entry in (data.get("regional_production_summary") or [])[:8]:
                region = entry.get("region") or entry.get("country")
                tonnes = entry.get("annual_production_tonnes") or entry.get("production_tonnes")
                if region and tonnes is not None:
                    self.db.add_knowledge(
                        "production",
                        f"What is gold production in {region}?",
                        f"{region} annual gold production: {tonnes:,.0f} tonnes.",
                        source="datasets/production/gold_production_data.json",
                        confidence=0.85,
                    )
                    added += 1

        cost_file = DATASETS_ROOT / "finance" / "cost_analysis.json"
        if cost_file.exists():
            data = json.loads(cost_file.read_text())
            models = data.get("financial_models") or {}
            if isinstance(models, dict):
                for name, model in list(models.items())[:3]:
                    self.db.add_knowledge(
                        "finance",
                        f"Tell me about the {name} financial model.",
                        f"{name}: {json.dumps(model)[:200]}",
                        source="datasets/finance/cost_analysis.json",
                        confidence=0.8,
                    )
                    added += 1
        if added:
            logger.info(f"Analytics synthesis added {added} knowledge entries")

    def kapoeta_synthesis(self) -> None:
        """Seed instant-answer knowledge entries for the Kapoeta gold district
        from datasets/regions/kapoeta_gold.json."""
        kapoeta_file = DATASETS_ROOT / "regions" / "kapoeta_gold.json"
        if not kapoeta_file.exists():
            return
        source = "datasets/regions/kapoeta_gold.json"
        entries = [
            ("kapoeta",
             "Where is the Kapoeta claim area and what are its coordinates?",
             "The claim lies in the Greater Kapoeta gold district, Eastern Equatoria State, "
             "South Sudan, about 35 km southwest of Kapoeta town. Boundary corners in UTM 36N: "
             "LEFT E540003 N492860 (4.458881N, 33.360579E) and RIGHT E539515 N492768 "
             "(4.458051N, 33.356179E); roughly 488 m by 92 m (about 5 hectares).",
             0.95),
            ("kapoeta",
             "What is the geology of the Kapoeta gold area?",
             "Kapoeta lies in the Neoproterozoic Karasuk Supergroup mobile belt (40 km wide here), "
             "a metavolcano-sedimentary assemblage of amphibolite and greenschist facies including "
             "andesite, basalt, amphibolite, biotite-hornblende gneiss, marble, quartzite, "
             "chlorite/garnet/graphite schist, alaskite, ultrabasic rock and gabbro, with main "
             "structural trends N-S, NNW-SSE, NW-SE and NE-SW.",
             0.9),
            ("kapoeta",
             "What type of gold deposit is found in Kapoeta?",
             "Orogenic gold with a strong epigenetic character, hosted in metavolcano-sedimentary "
             "sequences and NW-SE quartz-sulphide veins (pyrite, chalcopyrite). Placer gold is "
             "mined from stream and river gravels at 0.3-1.5 g/m3 with garnet, magnetite and "
             "ilmenite as the associated heavy minerals. Cu, Co, Cr and Ni are the pathfinder "
             "elements; N-S and NNW-SSE shears control mineralization.",
             0.9),
            ("kapoeta",
             "What is the history of gold mining in Kapoeta?",
             "Kapoeta post was established by Captain Knollys in January 1927; gold has been "
             "documented since at least the 1950s. Hunting Technical Services surveyed the area "
             "in 1976 and 1980, the Belgian Geological Survey in 1983 and 1985. A gold rush "
             "peaked around 2019-2022; licenses were suspended in late 2019. New Kush and "
             "Equator Gold were the first national companies pre-2012 Mining Act.",
             0.85),
            ("kapoeta",
             "How much gold does Kapoeta and South Sudan produce?",
             "No official statistics exist. Estimates for all of South Sudan range from 1-2 "
             "tonnes/month (Enough Project 2020), to about 5 tonnes/year (SWISSAID's most "
             "plausible estimate), with up to 60,000 miners at ~80 sites in Greater Kapoeta. "
             "The Kapoeta government buys ~10 kg/month from miners but only ~1 kg/year reaches "
             "the Bank of South Sudan.",
             0.8),
            ("kapoeta",
             "Which companies operate at Kapoeta?",
             "National: New Kush Exploration, Equator Gold, Blackstone, Gold Leaf, ASWA, "
             "Nakere Gold Mining Company, Eastern Equatoria Mining Corporation, Prudential "
             "Holdings. Foreign: Natura (Turkey), Al-Cardinal (Sudan), Manaji (UAE), Shino "
             "Minerals (China), plus Australian NUCO whose license was revoked.",
             0.8),
        ]
        for topic, question, answer, confidence in entries:
            self.db.add_knowledge(
                topic, question, answer, source=source, confidence=confidence
            )
        logger.info(f"Kapoeta synthesis seeded {len(entries)} knowledge entries")

    def conversation_mining(self) -> None:
        """Extract recurring user questions from recent conversations."""
        conversations = self.db.get_recent_conversations(limit=25) or []
        mined = 0
        for conv in conversations:
            session_id = conv.get("session_id", "")
            messages = conv.get("messages")
            if not messages:
                continue
            if isinstance(messages, str):
                try:
                    messages = json.loads(messages)
                except Exception:
                    continue
            if not isinstance(messages, list):
                continue
            for msg in messages:
                role = msg.get("role") if isinstance(msg, dict) else None
                content = msg.get("content") if isinstance(msg, dict) else None
                if role != "user" or not isinstance(content, str):
                    continue
                content = content.strip()
                if not content or not content.endswith("?"):
                    continue
                self.db.add_knowledge(
                    "conversations",
                    content,
                    "Asked by a user before - the answer was handled through the "
                    "normal pipeline and the exchange is saved in the conversation log.",
                    source=f"conversation:{session_id}",
                    confidence=0.5,
                )
                mined += 1
        if mined:
            logger.info(f"Conversation mining captured {mined} user questions")

    def qa_generation(self) -> None:
        """Use the local LLM to generate factual Q&A pairs from dataset chunks."""
        if not self.llm:
            return
        now = time.time()
        if now - _IDLE_STATE["last_llm_task"] < 30.0:  # cadence gate
            return
        files = sorted(DATASETS_ROOT.rglob("*.json"))
        if not files:
            return
        f = random.choice(files)
        try:
            text = f.read_text()
        except Exception:
            return
        mid = len(text) // 2
        sample = text[mid: mid + 1200]
        prompt = (
            "You are a mining operations expert. From this dataset excerpt, produce "
            "EXACTLY ONE concise question a mine manager would ask, and the one-line "
            "answer, strictly in this format:\nQ: <question>\nA: <answer>\n\n" + sample
        )
        from langchain_core.messages import HumanMessage

        _IDLE_STATE["last_llm_task"] = now
        response = self.llm.invoke([HumanMessage(content=prompt)])
        raw = (getattr(response, "content", "") or "").strip()
        q, a = _parse_qa(raw)
        if q and a:
            self.db.add_knowledge(
                "qa_auto", q, a, source=f.name, confidence=0.6
            )
            logger.info(f"Q&A generation stored: {q}")
        else:
            logger.debug("Q&A generation produced no parseable pair")


def _parse_qa(raw: str) -> tuple:
    """Parse 'Q: ...\\nA: ...' from LLM output, tolerating noise."""
    q = a = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("Q:") or line.startswith("Question:"):
            q = line.split(":", 1)[1].strip()
        elif line.startswith("A:") or line.startswith("Answer:"):
            a = line.split(":", 1)[1].strip()
    return q, a
