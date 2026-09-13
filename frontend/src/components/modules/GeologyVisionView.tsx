import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Camera,
  Mic,
  X,
  Volume2,
  VolumeX,
  Upload,
  ScanLine,
  AlertTriangle,
  Type,
  Sparkles,
} from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { SectionLabel } from '../ui/SectionLabel';
import { Badge } from '../ui/Badge';
import { Spinner } from '../ui/Spinner';
import type { VisionDetection, VisionAnalysisResult, VisionTalkTurn } from '../../types';

type Tab = 'live' | 'analyze';
type LiveMode = 'idle' | 'starting' | 'live' | 'camerror';

interface LogLine {
  id: number;
  role: 'user' | 'assistant';
  text: string;
}

let uid = 0;
const nextId = () => ++uid;

// ── Spoken-phrase helpers ──────────────────────────────────────────────
const ACK_PHRASES = ['mm hm', 'uh huh', 'right', 'interesting', 'yeah', 'go on', 'sure'];
let ackIdx = 0;

function pickAck(): string {
  ackIdx = (ackIdx + 1) % ACK_PHRASES.length;
  return ACK_PHRASES[ackIdx];
}

function browserVoices(): SpeechSynthesisVoice[] {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return [];
  return window.speechSynthesis.getVoices() ?? [];
}

function pickBrowserVoice(): SpeechSynthesisVoice | null {
  const all = browserVoices();
  return (
    all.find((v) => /en/i.test(v.lang) && /natural|neural/i.test(v.name)) ??
    all.find((v) => /en(-US|-GB|-AU)?\b/i.test(v.lang) && /female|premium|improved/i.test(v.name)) ??
    all.find((v) => /^en(-US|-GB|-AU)?/i.test(v.lang)) ??
    null
  );
}

function speakWeb(text: string, muted: boolean): void {
  if (muted || !text.trim() || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.05;
    u.pitch = 1.02;
    u.volume = 1;
    const v = pickBrowserVoice();
    if (v) u.voice = v;
    window.speechSynthesis.speak(u);
  } catch {
    /* ignore */
  }
}

/** Returns the first complete sentence prefix of `text`, or null when none yet. */
function takeSentence(text: string): { sentence: string; rest: string } | null {
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if ((ch === '.' || ch === '!' || ch === '?') && (i + 1 >= text.length || text[i + 1] === ' ' || text[i + 1] === '\n')) {
      return { sentence: text.slice(0, i + 1).trim(), rest: text.slice(i + 1) };
    }
    if (ch === '\n') {
      return { sentence: text.slice(0, i + 1).trim(), rest: text.slice(i + 1) };
    }
  }
  return null;
}

// ── Speech recognition feature-detect ──────────────────────────────────
interface SpeechRecog {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((ev: {
    results: ArrayLike<{ isFinal: boolean; [i: number]: { transcript: string } }>;
  }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  onend: (() => void) | null;
}
type SpeechRecogCtor = new () => SpeechRecog;

function getRecognitionCtor(): SpeechRecogCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecogCtor;
    webkitSpeechRecognition?: SpeechRecogCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function GeologyVisionView() {
  const [tab, setTab] = useState<Tab>('live');
  const [mode, setMode] = useState<LiveMode>('idle');
  const [muted, setMuted] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [ambient, setAmbient] = useState('');
  const [showAmbient, setShowAmbient] = useState(false);

  // Spoken conversation state
  const [userTalking, setUserTalking] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [caption, setCaption] = useState('');
  const [yr, setYr] = useState('');
  const [log, setLog] = useState<LogLine[]>([]);
  const [liveDetectionChips, setLiveDetectionChips] = useState<VisionDetection[]>([]);

  // Analyze tab
  const [analyzingImage, setAnalyzingImage] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [result, setResult] = useState<VisionAnalysisResult | null>(null);
  const [prevUrl, setPrevUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Refs that survive the render loop
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const vadTimerRef = useRef<number | null>(null);
  const sceneTimerRef = useRef<number | null>(null);
  const proactiveTimerRef = useRef<number | null>(null);
  const ackTimerRef = useRef<number | null>(null);
  const speechGenRef = useRef(0);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const userTurnRef = useRef(false);
  const userHeldRef = useRef(0);
  const sceneNotesRef = useRef<string[]>([]);
  const sceneDetectionsRef = useRef<VisionDetection[]>([]);
  const sceneStatsRef = useRef<{ brightness?: number; green_ratio?: number }>({});
  const ambRef = useRef('');
  const mutedRef = useRef(false);
  const historyRef = useRef<VisionTalkTurn[]>([]);
  const lastProactiveRef = useRef(0);
  const ttsBrokenRef = useRef(false);
  const sttFinalBufRef = useRef('');
  const sttMarkRef = useRef(0);
  const recognitionRef = useRef<SpeechRecog | null>(null);
  const replyingRef = useRef(false);

  useEffect(() => {
    ambRef.current = ambient.trim();
  }, [ambient]);

  // ── Media: camera + microphone ───────────────────────────────────────
  const captureFrameBytes = useCallback(async (): Promise<string | null> => {
    const video = videoRef.current;
    if (!video || video.readyState < 2 || !video.videoWidth) return null;
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 640;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    const side = Math.min(vw, vh);
    try {
      ctx.drawImage(video, (vw - side) / 2, (vh - side) / 2, side, side, 0, 0, 640, 640);
    } catch {
      return null;
    }
    return canvas.toDataURL('image/jpeg', 0.72).split(',')[1];
  }, []);

  const refreshScene = useCallback(async () => {
    const b64 = await captureFrameBytes();
    if (!b64) return;
    try {
      const res = await ChatAPI.analyzeVisionFrame(b64, ambRef.current, false);
      const dets = (res.detections ?? []).filter((d) => (d.confidence ?? 0) >= 0.3);
      sceneDetectionsRef.current = dets;
      sceneStatsRef.current = res.stats ?? {};
      setLiveDetectionChips(dets);
      if (res.speakable?.trim()) {
        sceneNotesRef.current = [...sceneNotesRef.current.slice(-4), res.speakable.trim()];
      }
    } catch {
      /* transient */
    }
  }, [captureFrameBytes]);

  // ── Stop everything ──────────────────────────────────────────────────
  const stopCurrentSpeech = useCallback(() => {
    speechGenRef.current += 1;
    try {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    } catch {
      /* ignore */
    }
    const el = audioElRef.current;
    if (el) {
      try {
        el.pause();
        el.currentTime = 0;
        el.src = '';
      } catch {
        /* ignore */
      }
      audioElRef.current = null;
    }
  }, []);

  useEffect(() => {
    mutedRef.current = muted;
    if (muted) stopCurrentSpeech();
  }, [muted, stopCurrentSpeech]);

  const stopAll = useCallback(() => {
    if (vadTimerRef.current) window.clearInterval(vadTimerRef.current);
    if (sceneTimerRef.current) window.clearInterval(sceneTimerRef.current);
    if (proactiveTimerRef.current) window.clearTimeout(proactiveTimerRef.current);
    if (ackTimerRef.current) window.clearTimeout(ackTimerRef.current);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.abort();
      } catch {
        /* ignore */
      }
      recognitionRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (audioCtxRef.current) {
      try {
        void audioCtxRef.current.close();
      } catch {
        /* ignore */
      }
      audioCtxRef.current = null;
    }
    analyserRef.current = null;
    audioElRef.current = null;
    stopCurrentSpeech();
    setUserTalking(false);
    setMicLevel(0);
    setMode('idle');
  }, [stopCurrentSpeech]);

  useEffect(() => () => stopAll(), [stopAll]);

  // ── Spoken reply pipeline ────────────────────────────────────────────
  const playSentence = useCallback(
    async (sentence: string, gen: number) => {
      // Neural server voice when healthy; graceful browser fallback.
      if (!ttsBrokenRef.current) {
        try {
          const blob = await ChatAPI.tts(sentence, 'en-US-JennyNeural');
          if (gen !== speechGenRef.current) return;
          const url = URL.createObjectURL(blob);
          const el = new Audio(url);
          audioElRef.current = el;
          el.volume = 1;
          await el.play();
          await new Promise<void>((resolve) => {
            el.onended = () => resolve();
            el.onerror = () => resolve();
          });
          URL.revokeObjectURL(url);
          audioElRef.current = null;
          if (gen !== speechGenRef.current) return;
          return;
        } catch {
          ttsBrokenRef.current = true;
        }
      }
      if (gen === speechGenRef.current && !mutedRef.current) {
        speakWeb(sentence, mutedRef.current);
      }
    },
    [],
  );

  const respond = useCallback(
    async (transcript: string, opts: { proactive?: boolean; reason?: string } = {}) => {
      if (!opts.proactive) {
        const clean = transcript.trim();
        if (!clean || replyingRef.current) return;
        replyingRef.current = true;
        historyRef.current = [...historyRef.current.slice(-6), { role: 'user', text: clean }];
        setLog((l) => [...l.slice(-3), { id: nextId(), role: 'user', text: clean }]);
        try {
          await refreshScene();
          const scenePayload = {
            detections: sceneDetectionsRef.current,
            stats: sceneStatsRef.current,
            notes: sceneNotesRef.current,
          };
          const gen = ++speechGenRef.current;
          setYr(clean);
          setCaption('');
          let buf = '';
          const out: string[] = [];
          try {
            for await (const chunk of ChatAPI.talkVision(clean, {
              ambient: ambRef.current,
              scene: scenePayload,
              history: historyRef.current,
              proactive: false,
            })) {
              if (gen !== speechGenRef.current) return;
              buf += chunk;
              let taken;
              while ((taken = takeSentence(buf)) !== null) {
                buf = taken.rest;
                if (taken.sentence) void playSentence(taken.sentence, gen);
                out.push(taken.sentence);
                setCaption(taken.sentence);
              }
            }
            if (buf.trim()) {
              void playSentence(buf.trim(), gen);
              out.push(buf.trim());
              setCaption(buf.trim());
            }
            const full = out.join(' ').trim();
            if (full) {
              historyRef.current = [...historyRef.current.slice(-6), { role: 'assistant', text: full }];
              setLog((l) => [...l.slice(-3), { id: nextId(), role: 'assistant', text: full }]);
              setCaption('');
            }
          } finally {
            replyingRef.current = false;
          }
        } catch {
          replyingRef.current = false;
          setCaption('Sorry — the voice line dropped. Try again.');
          void playSentence('Sorry, my voice connection just dropped. Ask me again.', ++speechGenRef.current);
        }
      } else {
        // Proactive opener — brief, once, only when idle.
        if (replyingRef.current || userTurnRef.current) return;
        const now = Date.now();
        if (now - lastProactiveRef.current < 20_000) return;
        lastProactiveRef.current = now;
        replyingRef.current = true;
        try {
          await refreshScene();
          const gen = ++speechGenRef.current;
          let buf = '';
          const out: string[] = [];
          for await (const chunk of ChatAPI.talkVision('', {
            ambient: ambRef.current,
            scene: { detections: sceneDetectionsRef.current, stats: sceneStatsRef.current, notes: sceneNotesRef.current },
            history: historyRef.current,
            proactive: true,
          })) {
            if (gen !== speechGenRef.current) return;
            buf += chunk;
            let taken;
            while ((taken = takeSentence(buf)) !== null) {
              buf = taken.rest;
              if (taken.sentence) void playSentence(taken.sentence, gen);
              out.push(taken.sentence);
              setCaption(taken.sentence);
            }
          }
          if (buf.trim()) {
            void playSentence(buf.trim(), gen);
            out.push(buf.trim());
            setCaption(buf.trim());
          }
          const full = out.join(' ').trim();
          if (full) {
            historyRef.current = [...historyRef.current.slice(-6), { role: 'assistant', text: full }];
            setLog((l) => [...l.slice(-3), { id: nextId(), role: 'assistant', text: full }]);
            setCaption('');
          }
        } catch {
          /* leave quiet */
        } finally {
          replyingRef.current = false;
        }
      }
    },
    [playSentence, refreshScene],
  );

  // ── Back-channel acknowledgements (the "mmh") ────────────────────────
  const startAckLoop = useCallback(() => {
    if (ackTimerRef.current) window.clearTimeout(ackTimerRef.current);
    const tick = () => {
      if (!userTurnRef.current) return;
      if (userHeldRef.current > 2.4) speakWeb(pickAck(), mutedRef.current);
      ackTimerRef.current = window.setTimeout(tick, 3600);
    };
    ackTimerRef.current = window.setTimeout(tick, 2400);
  }, []);

  const clearAckLoop = useCallback(() => {
    if (ackTimerRef.current) window.clearTimeout(ackTimerRef.current);
    ackTimerRef.current = null;
  }, []);

  // ── Voice activity detection ─────────────────────────────────────────
  const startVAD = useCallback(() => {
    if (vadTimerRef.current) window.clearInterval(vadTimerRef.current);
    let wasSpeaking = false;
    let hotTicks = 0;
    let coldTicks = 0;
    let turnStartAt = 0;

    vadTimerRef.current = window.setInterval(() => {
      const analyser = analyserRef.current;
      if (!analyser) return;
      const bufLen = analyser.fftSize;
      const data = new Uint8Array(bufLen);
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < bufLen; i++) {
        const v = (data[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / bufLen);
      const talking = rms > 0.045;

      if (talking) {
        hotTicks += 1;
        coldTicks = 0;
      } else {
        hotTicks = 0;
        coldTicks += 1;
      }
      const nowSpeaking = hotTicks > 2;

      setMicLevel(Math.min(1, rms * 6));

      if (nowSpeaking && !wasSpeaking) {
        // User started talking → immediately stop the robot.
        wasSpeaking = true;
        userTurnRef.current = true;
        turnStartAt = Date.now();
        stopCurrentSpeech();
        setUserTalking(true);
        startAckLoop();
      } else if (userTurnRef.current) {
        userHeldRef.current = (Date.now() - turnStartAt) / 1000;
      }

      if (!nowSpeaking && wasSpeaking && coldTicks >= 6) {
        // User finished talking → we may answer.
        wasSpeaking = false;
        userTurnRef.current = false;
        userHeldRef.current = 0;
        clearAckLoop();
        setUserTalking(false);
        const mark = sttMarkRef.current;
        const turn = sttFinalBufRef.current.slice(mark).trim();
        sttMarkRef.current = sttFinalBufRef.current.length;
        void respond(turn || pickupWarmHandoff(), {});
      }
    }, 120);
  }, [clearAckLoop, respond, startAckLoop, stopCurrentSpeech]);

  const pickupWarmHandoff = () => 'Go on.';

  // ── Speech recognition ───────────────────────────────────────────────
  const startSTT = useCallback(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return;
    try {
      const rec = new Ctor();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = navigator.language?.startsWith('en') ? (navigator.language || 'en-US').length > 2 ? 'en-US' : 'en-US' : 'en-US';
      rec.onresult = (ev) => {
        for (let i = 0; i < ev.results.length; i++) {
          const r = ev.results[i];
          if (r.isFinal && r[0]?.transcript) {
            sttFinalBufRef.current += ' ' + r[0].transcript.trim();
          }
        }
      };
      rec.onerror = () => {
        try { rec.abort(); } catch { /* ignore */ }
      };
      rec.onend = () => {
        if (mode === 'live') {
          try { rec.start(); } catch { /* ignore */ }
        }
      };
      recognitionRef.current = rec;
      rec.start();
    } catch {
      recognitionRef.current = null;
    }
  }, [mode]);

  // ── Begin the immersive voice experience ─────────────────────────────
  const startLive = useCallback(async () => {
    setMode('starting');
    setCameraError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
      } catch {
        setCameraError('Camera is blocked or unavailable. Allow camera + microphone access, then retry.');
        setMode('camerror');
        return;
      }
    }
    streamRef.current = stream;
    const audioTracks = stream.getAudioTracks();

    // Attach camera
    const video = videoRef.current;
    if (video) {
      video.muted = true;
      video.playsInline = true;
      video.srcObject = stream;
      try {
        await video.play();
      } catch {
        /* autoplay quirk — ignore, rAF/play on loadstar */
      }
      video.onloadeddata = () => { try { void video.play(); } catch { /* ignore */ } };
      video.onerror = () => { /* surface nothing; frames still flow */ };
    }

    // Mic + analyser for VAD
    if (audioTracks.length > 0) {
      try {
        audioCtxRef.current = new AudioContext();
        const src = audioCtxRef.current.createMediaStreamSource(stream);
        const analyser = audioCtxRef.current.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.5;
        src.connect(analyser);
        analyserRef.current = analyser;
        await audioCtxRef.current.resume();
        startVAD();
      } catch {
        analyserRef.current = null;
      }
    }

    setMode('live');
    setLiveDetectionChips([]);

    // Scene observation loop (every 5s, only when the user isn't holding the mic).
    sceneTimerRef.current = window.setInterval(() => {
      if (!userTurnRef.current && !replyingRef.current) void refreshScene();
    }, 5000);

    // Fullscreen attempt (mobile feels truly immersive)
    if (containerRef.current?.requestFullscreen) {
      containerRef.current.requestFullscreen().catch(() => undefined);
    }

    // Speech-to-text (Chrome/Safari).
    try { startSTT(); } catch { /* optional */ }

    // Immediate warm arrival.
    setCaption('I am right here with you. What are we looking at?');
    const greet = 'I am right here with you. What are we looking at?';
    void playSentence(greet, ++speechGenRef.current);

    // One proactive geo note shortly after entering (feels alive immediately).
    proactiveTimerRef.current = window.setTimeout(() => {
      void respond('', { proactive: true });
    }, 4500);
  }, [playSentence, refreshScene, respond, startSTT, startVAD]);

  const exitFullscreen = useCallback(() => {
    if (typeof document !== 'undefined' && document.fullscreenElement) {
      document.exitFullscreen().catch(() => undefined);
    }
  }, []);

  const toggleMuted = useCallback(() => {
    setMuted((m) => {
      const next = !m;
      if (next) stopCurrentSpeech();
      return next;
    });
  }, [stopCurrentSpeech]);

  // ── Analyze tab ──────────────────────────────────────────────────────
  const pickFile = (file: File | undefined) => {
    if (!file) return;
    if (prevUrl) URL.revokeObjectURL(prevUrl);
    setPrevUrl(URL.createObjectURL(file));
    setResult(null);
    setAnalyzeError(null);
    setAnalyzingImage(true);
    void ChatAPI.analyzeVisionImage(file)
      .then((res) => setResult(res))
      .catch(() => setAnalyzeError('Analysis failed. The vision backend may be unreachable.'))
      .finally(() => setAnalyzingImage(false));
  };

  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      void window.speechSynthesis.getVoices();
    }
  }, []);

  return (
    <div className="h-full overflow-hidden relative">
      {/* ────────────────────────────────────────────────────────
           LIVE TAB — immersive voice experience
           ──────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {tab === 'live' && (
          <motion.div
            key="live"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0"
          >
            {/* Immersive full-screen layer */}
            {mode !== 'idle' && (
              <motion.div
                ref={containerRef}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.35 }}
                className="fixed inset-0 z-50 bg-black overflow-hidden select-none"
              >
                {/* Camera fills the screen */}
                <video
                  ref={videoRef}
                  muted
                  playsInline
                  autoPlay
                  className="absolute inset-0 w-full h-full object-cover -scale-x-100"
                />
                {/* Legibility wash */}
                <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-transparent to-black/70 pointer-events-none" />

                {/* Top chrome */}
                <div className="absolute top-[max(0.75rem,env(safe-area-inset-top,0px))] left-0 right-0 flex items-center justify-between px-4 pointer-events-none">
                  <button
                    onClick={() => { exitFullscreen(); stopAll(); }}
                    className="pointer-events-auto w-9 h-9 rounded-full bg-black/45 backdrop-blur flex items-center justify-center text-white/90 hover:text-white transition-colors"
                    aria-label="End voice tour"
                  >
                    <X className="w-4 h-4" />
                  </button>
                  <div className="flex items-center gap-2 pointer-events-auto">
                    <button
                      onClick={() => setShowAmbient((s) => !s)}
                      className="h-9 w-9 rounded-full bg-black/45 backdrop-blur flex items-center justify-center text-white/80 hover:text-white transition-colors"
                      aria-label="Context hint"
                    >
                      <Type className="w-4 h-4" />
                    </button>
                    <button
                      onClick={toggleMuted}
                      className="h-9 w-9 rounded-full bg-black/45 backdrop-blur flex items-center justify-center text-white/80 hover:text-white transition-colors"
                      aria-label={muted ? 'Unmute' : 'Mute'}
                    >
                      {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {showAmbient && (
                  <div className="absolute top-[max(4.5rem,env(safe-area-inset-top,0px)+3rem)] left-4 right-4 pointer-events-none">
                    <div className="max-w-md mx-auto pointer-events-auto">
                      <input
                        value={ambient}
                        onChange={(e) => setAmbient(e.target.value)}
                        placeholder="Context hint — 'west pit bench, fresh cut of basalt'"
                        className="w-full rounded-xl border border-white/10 bg-black/55 backdrop-blur px-3.5 py-2.5 text-[13px] text-white placeholder:text-zinc-400 focus:outline-none focus:ring-1 focus:ring-sky-400/40"
                      />
                    </div>
                  </div>
                )}

                {/* Status pill */}
                <div className="absolute top-[max(0.75rem,env(safe-area-inset-top,0px))] left-1/2 -translate-x-1/2">
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/45 backdrop-blur text-[11.5px] font-medium text-zinc-200">
                    {mode === 'starting' ? (
                      <>
                        <Spinner className="w-3.5 h-3.5" /> Connecting…
                      </>
                    ) : userTalking ? (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" /> Listening…
                      </>
                    ) : (
                      <>
                        <span className={`w-1.5 h-1.5 rounded-full ${mode === 'live' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
                        Geology Voice Live
                      </>
                    )}
                  </div>
                </div>

                {/* Camera error */}
                {mode === 'camerror' && (
                  <div className="absolute inset-0 flex items-center justify-center px-6">
                    <div className="max-w-sm w-full rounded-2xl bg-black/60 backdrop-blur p-6 text-center">
                      <div className="mx-auto w-12 h-12 rounded-2xl bg-rose-500/15 flex items-center justify-center mb-3">
                        <AlertTriangle className="w-5 h-5 text-rose-300" />
                      </div>
                      <p className="text-sm text-zinc-200 leading-relaxed">{cameraError}</p>
                      <div className="flex gap-2 mt-5">
                        <button
                          onClick={() => void startLive()}
                          className="flex-1 rounded-xl px-4 py-2.5 text-[13px] font-semibold btn-primary"
                        >
                          Retry
                        </button>
                        <button
                          onClick={() => { exitFullscreen(); stopAll(); }}
                          className="flex-1 rounded-xl px-4 py-2.5 text-[13px] font-semibold glass-faint text-zinc-300 hover:text-white"
                        >
                          Back
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Gemini-style orb */}
                <div className="absolute bottom-[max(7rem,env(safe-area-inset-bottom,0px)+4.5rem)] left-1/2 -translate-x-1/2 flex flex-col items-center">
                  <motion.div
                    animate={{ scale: 1 + micLevel * 0.25 }}
                    transition={{ type: 'spring', stiffness: 260, damping: 18 }}
                    className={`vision-orb ${userTalking ? 'listening' : replyingRef.current ? 'busy' : ''}`}
                  >
                    {userTalking ? (
                      <Mic className="absolute inset-0 m-auto w-6 h-6 text-white/95 drop-shadow" />
                    ) : (
                      <Sparkles className="absolute inset-0 m-auto w-6 h-6 text-white/95 drop-shadow" />
                    )}
                  </motion.div>
                  <span className="mt-3 text-[11px] font-medium text-zinc-300 bg-black/45 rounded-full px-3 py-1">
                    {userTalking ? 'You are talking…' : muted ? 'Voice muted' : 'Tap to interject — just start talking'}
                  </span>
                </div>

                {/* Listener equalizer cue */}
                {userTalking && (
                  <div className="absolute bottom-[max(3.2rem,env(safe-area-inset-bottom,0px)+0.75rem)] left-1/2 -translate-x-1/2 flex items-end gap-1 h-6">
                    {[0, 1, 2, 3, 4, 5].map((i) => (
                      <motion.span
                        key={i}
                        animate={{ scaleY: 0.35 + micLevel * 1.4 + (i % 2) * 0.25 }}
                        transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                        className="w-1 rounded-full bg-sky-400 origin-bottom h-6"
                      />
                    ))}
                  </div>
                )}

                {/* Live caption + recent log */}
                <div className="absolute bottom-[max(0.9rem,env(safe-area-inset-bottom,0px))] left-0 right-0 px-5 pb-2">
                  <div className="max-w-2xl mx-auto space-y-1.5 text-center">
                    <AnimatePresence>
                      {caption && (
                        <motion.p
                          key={caption}
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="text-[15px] md:text-lg font-medium text-white drop-shadow-[0_1px_6px_rgba(0,0,0,0.9)]"
                        >
                          {caption}
                        </motion.p>
                      )}
                    </AnimatePresence>
                    <AnimatePresence initial={false}>
                      {log.length > 0 && (
                        <div className="space-y-1 opacity-80">
                          {log.slice(-2).map((l) => (
                            <motion.p
                              key={l.id}
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              exit={{ opacity: 0 }}
                              className={`text-[12.5px] truncate drop-shadow-[0_1px_4px_rgba(0,0,0,0.9)] ${
                                l.role === 'user' ? 'text-sky-200' : 'text-zinc-300'
                              }`}
                            >
                              {l.role === 'user' ? yr || 'you…' : null}
                              <span className="text-zinc-500">{l.role === 'user' ? '' : ' · '}</span>
                              {l.text}
                            </motion.p>
                          ))}
                        </div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {/* Detection chips */}
                {liveDetectionChips.length > 0 && (
                  <div className="absolute left-4 bottom-[max(9.5rem,env(safe-area-inset-bottom,0px)+7rem)] right-4">
                    <div className="flex flex-wrap justify-center gap-1.5">
                      {liveDetectionChips.slice(0, 8).map((d, i) => (
                        <span
                          key={`${d.class}-${i}`}
                          className="text-[10.5px] font-mono px-2 py-0.5 rounded-full bg-black/45 backdrop-blur text-emerald-200 border border-emerald-400/20"
                        >
                          {d.class} {Math.round((d.confidence ?? 0) * 100)}%
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* Idle / entry CTA (pre-permission) */}
            {mode === 'idle' && (
              <div className="h-full flex flex-col items-center justify-center px-6 text-center relative">
                <motion.div
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, ease: 'easeOut' }}
                  className="flex flex-col items-center max-w-md"
                >
                  <div className="w-20 h-20 rounded-[28px] bg-gradient-to-br from-emerald-400/20 to-sky-500/20 border border-white/10 flex items-center justify-center mb-5">
                    <Camera className="w-9 h-9 text-emerald-300" />
                  </div>
                  <h3 className="text-2xl font-semibold text-white tracking-tight">Voice Tour</h3>
                  <p className="text-[14px] text-zinc-400 mt-2 leading-relaxed">
                    Full-screen camera plus a geologist that talks to you — like Gemini Live. Point it at
                    the rock and just ask out loud.
                  </p>
                  <button
                    onClick={() => void startLive()}
                    className="mt-7 btn-primary rounded-full px-8 py-3.5 text-[15px] font-semibold flex items-center gap-2"
                  >
                    <Sparkles className="w-4 h-4" /> Start Talking
                  </button>
                  <p className="text-[11px] text-zinc-600 mt-4">
                    Your camera and microphone stay on this device — nothing is recorded to the server.
                  </p>
                </motion.div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ────────────────────────────────────────────────────────
           ANALYZE TAB — photo upload + full assessment
           ──────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {tab === 'analyze' && (
          <motion.div
            key="analyze"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 overflow-y-auto thin-scrollbar px-4 md:px-8 py-6"
          >
            <div className="max-w-5xl mx-auto space-y-8 pb-8">
              <motion.header
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-3.5"
              >
                <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-emerald-500 to-sky-600 flex items-center justify-center shadow-[0_10px_28px_rgba(16,185,129,0.35)]">
                  <ScanLine className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white tracking-tight">Analyze a Sample</h2>
                  <p className="text-[13px] text-zinc-500">Upload a rock face or hand sample for a full field report</p>
                </div>
              </motion.header>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="glass-faint rounded-2xl">
                  <div className="p-4 md:p-5 space-y-4">
                    <SectionLabel>Upload</SectionLabel>
                    <label
                      htmlFor="geo-upload"
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        const f = e.dataTransfer.files?.[0];
                        if (f) pickFile(f);
                      }}
                      className="block cursor-pointer rounded-2xl border-2 border-dashed border-white/[0.1] hover:border-sky-400/40 transition-colors"
                    >
                      <div className="py-10 px-6 text-center">
                        <div className="mx-auto w-12 h-12 rounded-2xl bg-white/[0.06] flex items-center justify-center mb-3">
                          <Upload className="w-5 h-5 text-sky-300" />
                        </div>
                        <p className="text-sm text-zinc-300 font-medium">Drop a rock / outcrop photo</p>
                        <p className="text-[12px] text-zinc-600 mt-1">or tap to browse · PNG, JPG, WEBP</p>
                      </div>
                      <input
                        id="geo-upload"
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => pickFile(e.target.files?.[0])}
                      />
                    </label>

                    {prevUrl && (
                      <div className="relative rounded-2xl overflow-hidden bg-black/50 border border-white/[0.06]">
                        <img src={prevUrl} alt="Sample" className="w-full h-auto block" />
                        {result && (
                          <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full">
                            {result.detections
                              .filter((d) => (d.width ?? 0) > 0 && (d.height ?? 0) > 0)
                              .map((d, i) => {
                                const good = (d.confidence ?? 0) >= 0.55;
                                const color = good ? 'rgba(74,222,128,0.95)' : 'rgba(251,191,36,0.95)';
                                return (
                                  <g key={i}>
                                    <rect
                                      x={(d.x ?? 0) * 100}
                                      y={(d.y ?? 0) * 100}
                                      width={(d.width ?? 0) * 100}
                                      height={(d.height ?? 0) * 100}
                                      fill="none"
                                      stroke={color}
                                      strokeWidth={2.5 / 100}
                                    />
                                    <text
                                      x={((d.x ?? 0) + 0.006) * 100}
                                      y={Math.max(0.03, (d.y ?? 0)) * 100}
                                      fontSize={0.052}
                                      fill="#fff"
                                      stroke="#000"
                                      strokeWidth={0.006}
                                      style={{ fontWeight: 600 }}
                                    >
                                      {d.class} {Math.round((d.confidence ?? 0) * 100)}%
                                    </text>
                                  </g>
                                );
                              })}
                          </svg>
                        )}
                        {analyzingImage && (
                          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                            <div className="flex flex-col items-center gap-2 text-sky-300">
                              <Spinner className="w-6 h-6" />
                              <span className="text-[12.5px] text-zinc-300">Analyzing sample…</span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {analyzeError && (
                      <div className="flex items-start gap-2.5 text-[13px] text-rose-300 bg-rose-500/[0.08] border border-rose-500/20 rounded-xl p-3">
                        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                        {analyzeError}
                      </div>
                    )}

                    {!prevUrl && (
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="w-full rounded-xl glass-faint py-3 text-sm font-medium text-zinc-300 hover:text-white transition-colors flex items-center justify-center gap-2"
                      >
                        <Camera className="w-4 h-4" /> Open photo picker
                      </button>
                    )}
                  </div>
                </div>

                <div className="glass-faint rounded-2xl">
                  <div className="p-4 md:p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <SectionLabel>Field Assessment</SectionLabel>
                      {result && (
                        <Badge tone={result.provider === 'roboflow' ? 'sky' : result.provider === 'edge' ? 'violet' : 'emerald'}>
                          {result.provider}·{result.configured ? 'CV+LLM' : 'LLM'}
                        </Badge>
                      )}
                    </div>
                    {result ? (
                      <>
                        <div className="flex flex-wrap gap-2">
                          {result.detections
                            .filter((d) => (d.confidence ?? 0) >= 0.3)
                            .map((d, i) => (
                              <Badge key={i} tone={d.confidence >= 0.55 ? 'emerald' : 'amber'}>
                                {d.class} · {Math.round((d.confidence ?? 0) * 100)}%
                              </Badge>
                            ))}
                        </div>
                        <p className="text-[13.5px] leading-relaxed text-zinc-300 whitespace-pre-wrap">
                          {result.assessment || 'No assessment returned.'}
                        </p>
                        <button
                          onClick={() => void playSentence(result.assessment?.slice(0, 900) || '', ++speechGenRef.current)}
                          className="rounded-full px-4 py-2 text-[12.5px] font-semibold glass-faint text-zinc-200 hover:text-white inline-flex items-center gap-2 self-start"
                        >
                          <Volume2 className="w-3.5 h-3.5" /> Read assessment aloud
                        </button>
                      </>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-16 text-center">
                        <ScanLine className="w-9 h-9 text-zinc-600" />
                        <p className="text-[13px] text-zinc-500 mt-4 max-w-xs leading-relaxed">
                          Upload a photo and the geologist will read the outcrop — lithology, alteration,
                          structure and the next field test.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Module tab switcher (floating, bottom-center) */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[60]">
        <div className="flex items-center gap-1.5 p-1.5 rounded-full bg-black/55 backdrop-blur border border-white/10">
          {(['live', 'analyze'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-full text-[13px] font-medium transition-colors ${
                tab === t ? 'bg-white/20 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t === 'live' ? (
                <span className="inline-flex items-center gap-1.5"><Mic className="w-3.5 h-3.5" /> Live</span>
              ) : (
                <span className="inline-flex items-center gap-1.5"><ScanLine className="w-3.5 h-3.5" /> Analyze</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}