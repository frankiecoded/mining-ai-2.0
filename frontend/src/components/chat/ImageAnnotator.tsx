import { useCallback, useEffect, useRef, useState } from 'react';
import { Type, Square, Circle, ArrowUpRight, Minus, PenLine, Eraser, Download, X } from 'lucide-react';

type Tool = 'label' | 'box' | 'circle' | 'arrow' | 'line' | 'pen' | 'eraser';

interface ImageAnnotatorProps {
  src: string;
  alt?: string;
  onClose: () => void;
  onSave: (dataUrl: string) => void;
}

const COLORS = ['#ff3b30', '#34c759', '#007aff', '#ffcc00', '#ff2d55', '#af52de', '#ffffff'];

export function ImageAnnotator({ src, alt, onClose, onSave }: ImageAnnotatorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const baseRef = useRef<HTMLCanvasElement>(null);
  const [tool, setTool] = useState<Tool>('pen');
  const [color, setColor] = useState('#ffcc00');
  const [drawing, setDrawing] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [textPos, setTextPos] = useState<{ x: number; y: number } | null>(null);
  const lastPosRef = useRef<{ x: number; y: number } | null>(null);
  const draftRef = useRef<{ tool: Tool; sx: number; sy: number; ex: number; ey: number } | null>(null);

  const redrawFromBase = useCallback(() => {
    const canvas = canvasRef.current;
    const base = baseRef.current;
    if (!canvas || !base) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(base, 0, 0);
  }, []);

  const applyBaseLayer = useCallback(() => {
    const canvas = canvasRef.current;
    const base = baseRef.current;
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      if (!canvas || !base) return;
      const scale = Math.min(1, 820 / img.naturalWidth, 560 / img.naturalHeight);
      const w = Math.max(1, Math.round(img.naturalWidth * scale));
      const h = Math.max(1, Math.round(img.naturalHeight * scale));
      canvas.width = w;
      canvas.height = h;
      base.width = w;
      base.height = h;
      const ctx = canvas.getContext('2d');
      const bctx = base.getContext('2d');
      if (ctx) ctx.drawImage(img, 0, 0, w, h);
      if (bctx) bctx.drawImage(img, 0, 0, w, h);
    };
    img.onerror = () => {
      if (!canvas || !base) return;
      canvas.width = 640;
      canvas.height = 480;
      base.width = 640;
      base.height = 480;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(0, 0, 640, 480);
        ctx.fillStyle = '#888';
        ctx.font = '14px system-ui,sans-serif';
        ctx.fillText('Could not load image', 20, 240);
      }
    };
    img.src = src;
  }, [src]);

  useEffect(() => {
    applyBaseLayer();
  }, [applyBaseLayer]);

  const getPos = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const canvas = canvasRef.current!;
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY),
    };
  };

  const drawShape = (d: { tool: Tool; sx: number; sy: number; ex: number; ey: number }) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (d.tool === 'pen' || d.tool === 'eraser') {
      ctx.save();
      if (d.tool === 'eraser') ctx.globalCompositeOperation = 'destination-out';
      ctx.strokeStyle = d.tool === 'pen' ? color : 'rgba(0,0,0,1)';
      ctx.lineWidth = d.tool === 'pen' ? 3 : 22;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(d.sx, d.sy);
      ctx.lineTo(d.ex, d.ey);
      ctx.stroke();
      ctx.restore();
      return;
    }

    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';

    if (d.tool === 'box') {
      ctx.strokeRect(Math.min(d.sx, d.ex), Math.min(d.sy, d.ey), Math.abs(d.ex - d.sx), Math.abs(d.ey - d.sy));
    } else if (d.tool === 'circle') {
      ctx.beginPath();
      ctx.ellipse(d.sx, d.sy, Math.max(1, Math.abs(d.ex - d.sx)), Math.max(1, Math.abs(d.ey - d.sy)), 0, 0, Math.PI * 2);
      ctx.stroke();
    } else if (d.tool === 'arrow') {
      ctx.beginPath();
      ctx.moveTo(d.sx, d.sy);
      ctx.lineTo(d.ex, d.ey);
      ctx.stroke();
      const angle = Math.atan2(d.ey - d.sy, d.ex - d.sx);
      const len = 14;
      ctx.beginPath();
      ctx.moveTo(d.ex, d.ey);
      ctx.lineTo(d.ex - len * Math.cos(angle - 0.4), d.ey - len * Math.sin(angle - 0.4));
      ctx.moveTo(d.ex, d.ey);
      ctx.lineTo(d.ex - len * Math.cos(angle + 0.4), d.ey - len * Math.sin(angle + 0.4));
      ctx.stroke();
    } else if (d.tool === 'line') {
      ctx.beginPath();
      ctx.moveTo(d.sx, d.sy);
      ctx.lineTo(d.ex, d.ey);
      ctx.stroke();
    }
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const pos = getPos(e);
    if (tool === 'label') {
      setTextPos(pos);
      setTextInput('');
      return;
    }
    draftRef.current = { tool, sx: pos.x, sy: pos.y, ex: pos.x, ey: pos.y };
    lastPosRef.current = pos;
    setDrawing(true);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!drawing) return;
    const pos = getPos(e);
    const d = draftRef.current;
    if (!d) return;

    if (d.tool === 'pen' || d.tool === 'eraser') {
      const last = lastPosRef.current ?? d.sx !== 0 ? { x: d.sx, y: d.sy } : { x: d.sx, y: d.sy };
      const seg = { tool: d.tool, sx: last.x, sy: last.y, ex: pos.x, ey: pos.y };
      drawShape(seg);
      lastPosRef.current = pos;
      d.sx = pos.x;
      d.sy = pos.y;
      return;
    }

    d.ex = pos.x;
    d.ey = pos.y;
    redrawFromBase();
    drawShape(d);
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!drawing) return;
    const pos = getPos(e);
    const d = draftRef.current;
    if (d && d.tool !== 'pen' && d.tool !== 'eraser') {
      d.ex = pos.x;
      d.ey = pos.y;
      redrawFromBase();
      // commit final shape so subsequent pen strokes don't get cleared
      drawShape(d);
    }
    draftRef.current = null;
    lastPosRef.current = null;
    setDrawing(false);
  };

  const commitLabel = () => {
    if (!textPos || !textInput.trim()) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const size = Math.max(12, Math.round(canvas.width / 32));
    ctx.font = `bold ${size}px system-ui, sans-serif`;
    ctx.fillStyle = 'rgba(0,0,0,0.72)';
    const tw = ctx.measureText(textInput).width;
    ctx.fillRect(textPos.x - 3, textPos.y - size + 3, tw + 10, size + 8);
    ctx.fillStyle = color;
    ctx.fillText(textInput, textPos.x, textPos.y + 4);
    setTextInput('');
    setTextPos(null);
  };

  const handleClear = () => {
    redrawFromBase();
    draftRef.current = null;
  };

  const handleSave = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    onSave(canvas.toDataURL('image/png'));
  };

  return (
    <div className="fixed inset-0 z-[90] bg-black/85 backdrop-blur-md flex items-center justify-center p-3 md:p-8 pt-[max(0.75rem,env(safe-area-inset-top,0px))] pb-[max(0.75rem,env(safe-area-inset-bottom,0px))]">
      <div className="glass-strong rounded-3xl p-3 md:p-6 max-w-5xl w-full max-h-full overflow-y-auto flex flex-col">
        <div className="flex items-center justify-between mb-3 md:mb-4 gap-3">
          <h3 className="text-[13px] font-semibold uppercase tracking-[0.12em] text-zinc-300 truncate">
            Annotate Image{alt ? ` — ${alt}` : ''}
          </h3>
          <button
            onClick={onClose}
            className="p-2.5 rounded-full text-zinc-400 hover:text-white hover:bg-white/[0.07] transition-colors"
            aria-label="Close annotation"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="mb-3 md:mb-4">
          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { id: 'pen' as Tool, icon: PenLine, label: 'Draw' },
              { id: 'label' as Tool, icon: Type, label: 'Text' },
              { id: 'box' as Tool, icon: Square, label: 'Box' },
              { id: 'circle' as Tool, icon: Circle, label: 'Circle' },
              { id: 'arrow' as Tool, icon: ArrowUpRight, label: 'Arrow' },
              { id: 'line' as Tool, icon: Minus, label: 'Line' },
              { id: 'eraser' as Tool, icon: Eraser, label: 'Erase' },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setTool(t.id)}
                className={`inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-2.5 rounded-full text-[12px] font-medium transition-colors min-h-[40px] ${
                  tool === t.id ? 'bg-sky-500/25 text-sky-200' : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.06]'
                }`}
              >
                <t.icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            ))}

            <div className="flex items-center gap-1.5 ml-1">
              {COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => setColor(c)}
                  className={`w-8 h-8 rounded-full border transition-transform ${
                    color === c ? 'scale-110 border-white ring-2 ring-white/30' : 'border-white/20 hover:scale-110'
                  }`}
                  style={{ backgroundColor: c }}
                  aria-label={`Color ${c}`}
                />
              ))}
            </div>

            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={handleClear}
                className="px-3.5 py-2.5 rounded-full text-[12px] font-medium text-zinc-400 hover:text-white hover:bg-white/[0.07] transition-colors min-h-[40px]"
              >
                Clear
              </button>
              <button
                onClick={handleSave}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white text-[12px] font-semibold hover:brightness-110 transition-all min-h-[40px]"
              >
                <Download className="w-3.5 h-3.5" />
                Save image
              </button>
            </div>
          </div>
        </div>

        <div className="relative flex-1 overflow-auto rounded-2xl bg-black/40 border border-white/[0.06] min-h-[200px] sm:min-h-[320px] flex items-center justify-center">
          <canvas
            ref={canvasRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            className="max-w-full max-h-[60dvh] cursor-crosshair"
          />
        </div>

        {textPos && (
          <div className="fixed z-[95] flex items-center gap-1.5" style={{ top: '48%', left: '50%', transform: 'translate(-50%, -50%)' }}>
            <input
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') commitLabel(); }}
              placeholder="Type label…"
              autoFocus
              className="px-3 py-2.5 rounded-lg bg-black/80 border border-sky-400/40 text-white text-sm outline-none w-52"
            />
            <button
              onClick={commitLabel}
              className="px-3.5 py-2.5 rounded-lg bg-sky-500 text-white text-sm font-medium hover:bg-sky-400"
            >
              Add
            </button>
          </div>
        )}
      </div>

      <canvas ref={baseRef} className="hidden" />
    </div>
  );
}