import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Camera,
  Play,
  Square,
  Volume2,
  VolumeX,
  Upload,
  ImageIcon,
  ScanLine,
  AlertTriangle,
  Mic,
  Type,
} from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { SectionLabel } from '../ui/SectionLabel';
import { Badge } from '../ui/Badge';
import { Spinner } from '../ui/Spinner';
import { SpotlightCard } from '../ui/SpotlightCard';
import { EmptyState } from '../ui/EmptyState';
import type { VisionDetection, VisionAnalysisResult } from '../../types';

type Tab = 'live' | 'analyze';

interface FeedItem {
  id: number;
  narration: string;
  detections?: VisionDetection[];
  time: string;
}

let uid = 0;
const nextId = () => ++uid;

function speak(text: string, muted: boolean): void {
  if (muted || !text.trim()) return;
  if (!('speechSynthesis' in window)) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.04;
    u.pitch = 1.0;
    const voices = window.speechSynthesis.getVoices();
    const preferred =
      voices.find((v) => /en(-(US|GB))?/i.test(v.lang) && /natural|neural/i.test(v.name)) ??
      voices.find((v) => /^en/i.test(v.lang));
    if (preferred) u.voice = preferred;
    window.speechSynthesis.speak(u);
  } catch {
    /* TTS unavailable on this device — narration still shown as text. */
  }
}

function detectChips(detections: VisionDetection[] | undefined): VisionDetection[] {
  return (detections ?? []).filter((d) => (d.confidence ?? 0) >= 0.3);
}

export function GeologyVisionView() {
  const [tab, setTab] = useState<Tab>('live');

  // Live state
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const analyzingRef = useRef(false);
  const liveDetectionsRef = useRef<VisionDetection[]>([]);
  const ambientRef = useRef('');
  const mutedRef = useRef(false);

  const [live, setLive] = useState(false);
  const [muted, setMuted] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [ambient, setAmbient] = useState('');
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [recentDetections, setRecentDetections] = useState<VisionDetection[]>([]);

  // Analyze state
  const [analyzingImage, setAnalyzingImage] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [result, setResult] = useState<VisionAnalysisResult | null>(null);
  const [prevUrl, setPrevUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [caption, setCaption] = useState('');

  useEffect(() => {
    if ('speechSynthesis' in window) {
      void window.speechSynthesis.getVoices();
    }
  }, []);

  const drawOverlay = useCallback(() => {
    const canvas = overlayRef.current;
    if (!canvas) return;
    const d = liveDetectionsRef.current.filter((x) => (x.confidence ?? 0) >= 0.3);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const cw = canvas.width;
    const ch = canvas.height;
    ctx.clearRect(0, 0, cw, ch);
    if (live && d.length > 0) {
      ctx.save();
      ctx.translate(cw, 0);
      ctx.scale(-1, 1);
      for (const det of d) {
        const x = (det.x ?? 0) * cw;
        const y = (det.y ?? 0) * ch;
        const w = (det.width ?? 0) * cw;
        const h = (det.height ?? 0) * ch;
        const tok = det.confidence ?? 0;
        const good = tok >= 0.55;
        ctx.strokeStyle = good ? 'rgba(74, 222, 128, 0.9)' : 'rgba(251, 191, 36, 0.9)';
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
        ctx.font = '600 12px Inter, system-ui, sans-serif';
        const label = `${det.class} ${Math.round(tok * 100)}%`;
        const tw = ctx.measureText(label).width + 10;
        ctx.fillStyle = good ? 'rgba(21, 128, 61, 0.85)' : 'rgba(180, 120, 10, 0.85)';
        const ly = Math.max(0, y - 18);
        ctx.fillRect(x, ly, tw, 18);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(label, x + 5, ly + 13);
      }
      ctx.restore();
    }
  }, [live]);

  useEffect(() => {
    drawOverlay();
  }, [drawOverlay, live, feed]);

  const captureFrame = useCallback(async () => {
    const video = videoRef.current;
    if (analyzingRef.current || !video || video.readyState < 2) return;
    analyzingRef.current = true;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 720;
      canvas.height = 720;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const vw = video.videoWidth || 1280;
      const vh = video.videoHeight || 720;
      const side = Math.min(vw, vh);
      ctx.drawImage(video, (vw - side) / 2, (vh - side) / 2, side, side, 0, 0, 720, 720);
      const b64 = canvas.toDataURL('image/jpeg', 0.72).split(',')[1];

      const res = await ChatAPI.analyzeVisionFrame(b64, ambientRef.current, false);
      liveDetectionsRef.current = res.detections ?? [];
      setRecentDetections(detectChips(res.detections));
      if (res.speakable?.trim()) {
        const item: FeedItem = {
          id: nextId(),
          narration: res.speakable,
          detections: detectChips(res.detections),
          time: new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }),
        };
        setFeed((prev) => [...prev.slice(-24), item]);
        if (!mutedRef.current && !analyzingImage) speak(res.speakable, mutedRef.current);
      }
    } catch {
      /* transient frame failure — continue live loop */
    } finally {
      analyzingRef.current = false;
    }
  }, [analyzingImage]);

  const startLive = useCallback(async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      setLive(true);
      timerRef.current = window.setInterval(() => {
        void captureFrame();
      }, 3600);
    } catch {
      setCameraError('Camera unavailable. Grant camera permission or use the Analyze tab with a photo.');
    }
  }, [captureFrame]);

  const stopLive = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    liveDetectionsRef.current = [];
    setRecentDetections([]);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setLive(false);
  }, []);

  useEffect(() => {
    if (live && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      void videoRef.current.play().catch(() => undefined);
    }
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [live]);

  const toggleLive = async () => {
    if (live) {
      stopLive();
    } else {
      await startLive();
    }
  };

  const handleAmbientCommit = () => {
    ambientRef.current = ambient.trim();
  };

  const toggleMuted = () => {
    const next = !muted;
    setMuted(next);
    mutedRef.current = next;
    if (next) {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    } else {
      const last = feed[feed.length - 1];
      if (last) speak(last.narration, false);
    }
  };

  // ── Analyze tab ──
  const pickFile = (file: File | undefined) => {
    if (!file) return;
    if (prevUrl) URL.revokeObjectURL(prevUrl);
    setPrevUrl(URL.createObjectURL(file));
    setResult(null);
    setAnalyzeError(null);
    setCaption('');
    setAnalyzingImage(true);
    void ChatAPI.analyzeVisionImage(file)
      .then((res) => {
        setResult(res);
        setCaption(res.assessment || '');
        speak(res.assessment || '', mutedRef.current);
      })
      .catch(() => setAnalyzeError('Analysis failed. The vision backend may be unreachable.'))
      .finally(() => setAnalyzingImage(false));
  };

  return (
    <div className="h-full overflow-y-auto thin-scrollbar px-4 md:px-8 py-6">
      <div className="max-w-6xl mx-auto space-y-6 pb-8">
        <motion.header
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="flex items-center justify-between gap-3 flex-wrap"
        >
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-emerald-500 to-sky-600 flex items-center justify-center shadow-[0_10px_28px_rgba(16,185,129,0.35)]">
              <ScanLine className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white tracking-tight">Geology Vision</h2>
              <p className="text-[13px] text-zinc-500">Live AI narration of the ground you walk — Roboflow / NVIDIA feed + vision LLM</p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-1 rounded-full glass-faint">
            {(['live', 'analyze'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-1.5 rounded-full text-[13px] font-medium transition-colors ${
                  tab === t ? 'bg-white/[0.12] text-white' : 'text-zinc-500 hover:text-white'
                }`}
              >
                {t === 'live' ? 'Live on Location' : 'Analyze Sample'}
              </button>
            ))}
          </div>
        </motion.header>

        {tab === 'live' && (
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px] gap-4">
            {/* Camera feed */}
            <SpotlightCard className="glass-faint rounded-2xl">
              <div className="p-4 md:p-5 space-y-4">
                <div className="relative aspect-[4/3] rounded-2xl overflow-hidden bg-black/60 border border-white/[0.06]">
                  {live ? (
                    <>
                      <video
                        ref={videoRef}
                        muted
                        playsInline
                        autoPlay
                        className="absolute inset-0 w-full h-full object-cover -scale-x-100"
                      />
                      <canvas
                        ref={overlayRef}
                        className="absolute inset-0 w-full h-full pointer-events-none"
                      />
                    </>
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="text-center px-6">
                        <div className="mx-auto w-14 h-14 rounded-2xl bg-white/[0.06] flex items-center justify-center mb-3">
                          <Camera className="w-6 h-6 text-zinc-500" />
                        </div>
                        <p className="text-sm text-zinc-400">
                          Point the camera at rock faces, trenches, outcrops or stockpiles.
                        </p>
                        {cameraError && (
                          <p className="mt-2 text-[12.5px] text-amber-300 flex items-center justify-center gap-1.5">
                            <AlertTriangle className="w-3.5 h-3.5" /> {cameraError}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Control / status chrome */}
                  <div className="absolute top-3 left-3 right-3 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[11px] font-medium px-2.5 py-1.5 rounded-lg bg-black/40 backdrop-blur text-zinc-300">
                      <span className={`w-1.5 h-1.5 rounded-full ${live ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500'}`} />
                      {live ? 'Analyzing every ~3s' : 'Camera off'}
                    </div>
                    <button
                      onClick={toggleMuted}
                      className="p-2 rounded-lg bg-black/40 backdrop-blur text-zinc-300 hover:text-white transition-colors"
                      aria-label={muted ? 'Unmute narration' : 'Mute narration'}
                    >
                      {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                    </button>
                  </div>

                  {/* Gemini-Live style orb */}
                  <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex flex-col items-center">
                    <div className={`vision-orb ${live && analyzingRef.current ? 'busy' : ''} ${live && muted ? 'muted' : ''}`}>
                      {live && (
                        <Mic className="absolute inset-0 m-auto w-6 h-6 text-white/90 drop-shadow" />
                      )}
                    </div>
                    {live && muted && (
                      <span className="mt-2 text-[10.5px] text-zinc-400 bg-black/40 rounded-full px-2 py-0.5">muted</span>
                    )}
                  </div>
                </div>

                {/* Live controls + context hint */}
                <div className="flex flex-col sm:flex-row gap-3">
                  <button
                    onClick={() => void toggleLive()}
                    className={`rounded-full px-5 py-2.5 text-sm font-semibold flex items-center justify-center gap-2 transition-all ${
                      live
                        ? 'bg-rose-500/90 hover:bg-rose-500 text-white'
                        : 'btn-primary'
                    }`}
                  >
                    {live ? (
                      <>
                        <Square className="w-4 h-4" /> Stop Live
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" /> Start Live Narration
                      </>
                    )}
                  </button>
                  <div className="flex-1 flex gap-2">
                    <div className="relative flex-1">
                      <Type className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                      <input
                        value={ambient}
                        onChange={(e) => setAmbient(e.target.value)}
                        placeholder="Context hint — e.g. 'west pit bench, fresh cut of basalt'"
                        className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] pl-9 pr-3 py-2.5 text-[13px] text-white placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-sky-400/40"
                      />
                    </div>
                    <button
                      onClick={handleAmbientCommit}
                      className="px-3.5 py-2.5 rounded-xl text-[13px] font-medium glass-faint text-zinc-300 hover:text-white transition-colors"
                    >
                      Set
                    </button>
                  </div>
                </div>

                {/* Detection chips feed */}
                <div className="flex flex-wrap gap-2">
                  {recentDetections.length === 0 ? (
                    <span className="text-[12px] text-zinc-600">Waiting for detections…</span>
                  ) : (
                    recentDetections.slice(0, 12).map((d, i) => (
                      <motion.span
                        key={`${d.class}-${i}`}
                        initial={{ opacity: 0, y: 6, scale: 0.94 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        className="vision-detect-chip"
                      >
                        <Badge tone={d.confidence >= 0.55 ? 'emerald' : 'amber'}>
                          {d.class} · {Math.round(d.confidence * 100)}%
                        </Badge>
                      </motion.span>
                    ))
                  )}
                </div>
              </div>
            </SpotlightCard>

            {/* Narration feed */}
            <SpotlightCard className="glass-faint rounded-2xl flex flex-col">
              <div className="p-4 border-b border-white/[0.06]">
                <SectionLabel>Field Narration Feed</SectionLabel>
              </div>
              <div className="flex-1 min-h-[280px] max-h-[560px] overflow-y-auto no-scrollbar p-4 space-y-3">
                {feed.length === 0 ? (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-[13px] text-zinc-600 leading-relaxed"
                  >
                    Your geologist starts talking the moment the stream is live — rock types,
                    structures, alteration and next field test, spoken aloud exactly like a guide.
                  </motion.p>
                ) : (
                  <AnimatePresence initial={false}>
                    {feed.map((item) => (
                      <motion.div
                        key={item.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-3"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10px] uppercase tracking-wider text-sky-400/80 font-semibold">Geologist</span>
                          <span className="text-[10px] text-zinc-600 font-mono">{item.time}</span>
                        </div>
                        <p className="text-[13px] text-zinc-200 leading-relaxed">{item.narration}</p>
                        {item.detections && item.detections.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2.5">
                            {item.detections.map((d, i) => (
                              <span key={i} className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-emerald-500/10 text-emerald-300">
                                {d.class} {Math.round(d.confidence * 100)}%
                              </span>
                            ))}
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </AnimatePresence>
                )}
              </div>
            </SpotlightCard>
          </div>
        )}

        {tab === 'analyze' && (
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4">
            <SpotlightCard className="glass-faint rounded-2xl">
              <div className="p-4 md:p-5 space-y-4">
                <SectionLabel>Upload a Photo</SectionLabel>
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
                    <ImageIcon className="w-4 h-4" /> Open photo picker
                  </button>
                )}
              </div>
            </SpotlightCard>

            <SpotlightCard className="glass-faint rounded-2xl">
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
                            {d.class} · {Math.round(d.confidence * 100)}%
                          </Badge>
                        ))}
                    </div>
                    <div className="text-[13.5px] leading-relaxed text-zinc-300 whitespace-pre-wrap">
                      {caption}
                    </div>
                    <button
                      onClick={() => speak(caption, false)}
                      className="rounded-full px-4 py-2 text-[12.5px] font-semibold glass-faint text-zinc-200 hover:text-white inline-flex items-center gap-2 self-start"
                    >
                      <Volume2 className="w-3.5 h-3.5" /> Read assessment aloud
                    </button>
                  </>
                ) : (
                  <EmptyState
                    icon={<ScanLine className="w-6 h-6" />}
                    title="No sample yet"
                    description="Upload a photo and Frank's geologist will read the outcrop — lithology, alteration, structure and the next field test."
                  />
                )}
              </div>
            </SpotlightCard>
          </div>
        )}
      </div>
    </div>
  );
}