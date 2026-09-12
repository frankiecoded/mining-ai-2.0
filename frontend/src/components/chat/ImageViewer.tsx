import { useEffect, useState } from 'react';
import * as React from 'react';
import { Plus } from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { ImageAnnotator } from './ImageAnnotator';

// ─── Helpers ──────────────────────────────────────────────────────────────

export const isImageMime = (mime?: string, name?: string): boolean => {
  const m = (mime ?? '').toLowerCase();
  const n = (name ?? '').toLowerCase();
  return m.startsWith('image/') || /\.(png|jpe?g|gif|webp|tiff?|bmp|geotiff?|svg)$/.test(n);
};

export const absoluteUrl = (url: string): string => {
  if (!url) return '';
  if (url.startsWith('http') || url.startsWith('data:')) return url;
  return `${import.meta.env.VITE_API_URL || ''}${url}`;
};

export interface ImageStackItem {
  filename?: string;
  file_url?: string;
  mime_type?: string;
  size_bytes?: number;
  /** For markdown images — a raw src string. */
  fromMarkdown?: string;
}

export const resolveImageUrl = (item: ImageStackItem): string =>
  absoluteUrl(item.fromMarkdown || item.file_url || '');

// ─── ImageStrip: inline Gemini-style image row loaded into message content ─

const urlCache = new Map<string, string>();

/** Fetch an image as a data URL with auth headers, then return the cached data URL. */
export async function ensureLoadableUrl(src: string): Promise<string> {
  if (!src) return '';
  if (src.startsWith('data:')) return src;
  if (urlCache.has(src)) return urlCache.get(src)!;
  try {
    const res = await fetch(src, { headers: ChatAPI.authHeaders(false) });
    if (!res.ok) return src;
    const blob = await res.blob();
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    urlCache.set(src, dataUrl);
    return dataUrl;
  } catch {
    return src;
  }
}

export function ImageStrip({ images }: { images: ImageStackItem[] }) {
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null);
  const [loadable, setLoadable] = useState<Record<number, string>>({});

  useEffect(() => {
    let cancelled = false;
    images.forEach(async (img, idx) => {
      const src = resolveImageUrl(img);
      if (src.startsWith('data:')) return;
      const resolved = src.startsWith('http') ? src : `${import.meta.env.VITE_API_URL || ''}${src}`;
      const dataUrl = await ensureLoadableUrl(resolved);
      if (!cancelled) setLoadable((prev) => ({ ...prev, [idx]: dataUrl }));
    });
    return () => { cancelled = true; };
  }, [images]);

  return (
    <React.Fragment>
      <div className="flex flex-wrap gap-2.5">
        {images.map((img, idx) => {
          const src = loadable[idx] || resolveImageUrl(img);
          return (
            <div key={idx} className="group relative rounded-con-16 overflow-hidden border border-white/[0.07] bg-black/30">
              <button
                type="button"
                onClick={() => setLightboxIdx(idx)}
                className="block cursor-zoom-in"
                aria-label={`Open image ${img.filename || 'preview'}`}
              >
                <img
                  src={src}
                  alt={img.filename || `Image ${idx + 1}`}
                  loading="lazy"
                  className="max-h-52 max-w-[240px] object-contain rounded-con-12 hover:opacity-90 transition-opacity"
                />
              </button>
              <div className="absolute top-1.5 right-1.5 flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 max-md:opacity-100 transition-opacity">
                <button
                  type="button"
                  onClick={() => {
                    const a = document.createElement('a');
                    a.href = src;
                    a.download = img.filename || `image-${idx + 1}.png`;
                    a.target = '_blank';
                    a.rel = 'noopener noreferrer';
                    a.click();
                  }}
                  className="p-2.5 rounded-lg bg-black/70 text-white hover:bg-sky-500/80 transition-colors"
                  aria-label="Download image"
                  title="Download"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                </button>
              </div>
            </div>
          );
        })}
      </div>
      {lightboxIdx !== null && (
        <Lightbox
          images={images}
          index={lightboxIdx}
          onIndexChange={setLightboxIdx}
          onClose={() => setLightboxIdx(null)}
        />
      )}
    </React.Fragment>
  );
}

// ─── Lightbox: full-screen presentation view ──────────────────────────────

function Lightbox({
  images,
  index,
  onIndexChange,
  onClose,
}: {
  images: ImageStackItem[];
  index: number;
  onIndexChange: (i: number) => void;
  onClose: () => void;
}) {
  const [annotating, setAnnotating] = useState(false);
  const img = images[index];
  const src = ensureLightboxSrc(img);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight') onIndexChange(Math.min(images.length - 1, index + 1));
      if (e.key === 'ArrowLeft') onIndexChange(Math.max(0, index - 1));
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [onClose, onIndexChange, index, images.length]);

  if (annotating) {
    return <AnnotatorHost src={src} fallbackName={img.filename} onClose={() => setAnnotating(false)} />;
  }

  return (
    <div
      className="fixed inset-0 z-[80] bg-black/90 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-10"
      onClick={onClose}
    >
      <div className="absolute top-[max(1rem,env(safe-area-inset-top,0px))] right-4 left-4 flex items-center justify-end gap-2 flex-wrap">
        {images.length > 1 && (
          <span className="text-[11px] text-zinc-400 mr-1 sm:mr-2">
            {index + 1} / {images.length}
          </span>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onIndexChange(Math.max(0, index - 1)); }}
          disabled={index === 0}
          className="p-3 rounded-full bg-white/[0.08] text-white hover:bg-white/[0.16] disabled:opacity-30 transition-colors"
          aria-label="Previous image"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6" /></svg>
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onIndexChange(Math.min(images.length - 1, index + 1)); }}
          disabled={index >= images.length - 1}
          className="p-3 rounded-full bg-white/[0.08] text-white hover:bg-white/[0.16] disabled:opacity-30 transition-colors"
          aria-label="Next image"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); setAnnotating(true); }}
          className="inline-flex items-center justify-center gap-1.5 w-11 h-11 sm:w-auto sm:h-auto sm:px-3.5 sm:py-2.5 rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white text-[12px] font-semibold hover:brightness-110 transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Annotate</span>
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            const a = document.createElement('a');
            a.href = src;
            a.download = img.filename || `image-${index + 1}.png`;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            a.click();
          }}
          className="inline-flex items-center justify-center gap-1.5 w-11 h-11 sm:w-auto sm:h-auto sm:px-3.5 sm:py-2.5 rounded-full bg-white/[0.1] text-white text-[12px] font-semibold hover:bg-white/[0.18] transition-colors"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
          <span className="hidden sm:inline">Download</span>
        </button>
        <button
          onClick={onClose}
          className="p-3 rounded-full bg-white/[0.08] text-white hover:bg-white/[0.16] transition-colors"
          aria-label="Close viewer"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
        </button>
      </div>

      <img
        src={src}
        alt={img.filename || 'Image'}
        onClick={(e) => e.stopPropagation()}
        className="max-w-full max-h-[82dvh] object-contain rounded-xl shadow-2xl"
      />

      {img.filename && (
        <div className="absolute bottom-[max(1rem,env(safe-area-inset-bottom,0px))] text-[11px] text-zinc-500">
          {img.filename}
        </div>
      )}
    </div>
  );
}

function ensureLightboxSrc(img: ImageStackItem): string {
  const src = resolveImageUrl(img);
  if (src.startsWith('http') || src.startsWith('data:')) return src;
  return `${import.meta.env.VITE_API_URL || ''}${src}`;
}

// ─── Annotator host: annotate → download / persist annotated copy ─────────

function AnnotatorHost({ src, fallbackName, onClose }: { src: string; fallbackName?: string; onClose: () => void }) {
  const [done, setDone] = React.useState<string | null>(null);

  const handleSave = async (dataUrl: string) => {
    try {
      const base = fallbackName?.replace(/\.(\w+)$/i, '') || 'annotated';
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], `${base}_annotated.png`, { type: 'image/png' });
      const res = await ChatAPI.renderUploadedImage(file);
      setDone(res.file_url);
    } catch (err) {
      setDone(`error:${err instanceof Error ? err.message : 'Failed to save'}`);
    }
  };

  return (
    <React.Fragment>
      <ImageAnnotator src={src} alt={fallbackName} onClose={onClose} onSave={(dataUrl) => void handleSave(dataUrl)} />
      {done && done.startsWith('error') ? (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[95] bg-red-500/90 text-white text-[12px] px-4 py-2 rounded-full">
          {done.slice(6)}
        </div>
      ) : done ? (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[95] bg-emerald-500/90 text-white text-[12px] px-4 py-2 rounded-full flex items-center gap-2">
          <span>Annotated copy saved.</span>
          <button
            onClick={() => {
              const a = document.createElement('a');
              a.href = absoluteUrl(done);
              a.download = 'annotated.png';
              a.target = '_blank';
              a.rel = 'noopener noreferrer';
              a.click();
            }}
            className="underline font-semibold"
          >
            Download
          </button>
        </div>
      ) : null}
    </React.Fragment>
  );
}

export { Lightbox, AnnotatorHost };