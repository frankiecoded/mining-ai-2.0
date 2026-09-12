import { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Check, Copy, Loader2, FileDown, FileText, ImageIcon } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../../types';
import { ImageStrip, Lightbox, isImageMime } from './ImageViewer';
import type { ImageStackItem } from './ImageViewer';

interface MessageBubbleProps {
  message: ChatMessage;
  isFirst?: boolean;
  isLast?: boolean;
  isStreaming?: boolean;
  timestamp?: string;
}

const enter = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { type: 'spring' as const, stiffness: 420, damping: 34 },
};

export function MessageBubble({ message, isFirst = true, isLast = true, isStreaming = false, timestamp }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  // System messages read as quiet margin notes, not bubbles — they never
  // compete with the conversation.
  if (isSystem) {
    return (
      <motion.div {...enter} className="w-full flex justify-center px-6 py-4 sm:py-5">
        <div className="flex items-start gap-2.5 max-w-[560px]">
          <span className="flex-1 h-px mt-2 bg-gradient-to-r from-transparent via-white/8 to-white/12" />
          <span className="text-[11px] sm:text-[12px] leading-relaxed text-zinc-500 text-center whitespace-pre-line">
            {message.content}
          </span>
          <span className="flex-1 h-px mt-2 bg-gradient-to-l from-transparent via-white/8 to-white/12" />
        </div>
      </motion.div>
    );
  }

  // Structured image event attachments (the new `image` SSE type).
  const inlineImages: ImageStackItem[] = (message.images ?? []).map((img) => ({
    filename: img.filename,
    file_url: img.file_url,
    mime_type: img.mime_type,
    size_bytes: img.size_bytes,
  }));

  // Split file attachments into image previews vs. download cards.
  const fileAttachments = message.attachments ?? [];
  const imageFileAttachments = fileAttachments.filter((f) => isImageMime(f.mime_type, f.filename));
  const otherAttachments = fileAttachments.filter((f) => !isImageMime(f.mime_type, f.filename));
  const previewImages: ImageStackItem[] = [
    ...inlineImages,
    ...imageFileAttachments.map((f) => ({
      filename: f.filename,
      file_url: f.file_url,
      mime_type: f.mime_type,
      size_bytes: f.size_bytes,
    })),
  ];

  const hasText = !!message.content;
  const canCopy = hasText && !isUser && isLast && !isStreaming;

  const copyText = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <motion.div
      {...enter}
      className={`flex w-full group ${isUser ? 'justify-end' : 'justify-start'} ${isFirst ? 'mt-5 sm:mt-7' : 'mt-1.5 sm:mt-2'}`}
    >
      {/* Assistant mark — only at the start of a run so a reply reads as one voice */}
      {!isUser && (
        <div className="w-6 sm:w-7 shrink-0 mt-1">
          {isFirst ? (
            <motion.div
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 500, damping: 26 }}
              className="w-6 h-6 sm:w-7 sm:h-7 rounded-con-8 bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center border border-white/10"
            >
              <Sparkles className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-white" />
            </motion.div>
          ) : (
            <div className="w-6 h-6 sm:w-7 sm:h-7" />
          )}
        </div>
      )}

      <div className={`flex flex-col gap-1.5 min-w-0 max-w-[86%] md:max-w-[72%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Image previews (inline, presentation-style) */}
        {previewImages.length > 0 && (
          <div className={`min-w-0 max-w-full ${isUser ? 'self-end' : 'self-start w-full'}`}>
            <ImageStrip images={previewImages} />
          </div>
        )}

        {hasText && (
          <div className={isUser ? '' : 'w-full min-w-0'}>
            {isUser ? (
              <div className="px-4 py-2.5 rounded-con-20 rounded-br-[6px] bg-white/[0.08] border border-white/[0.06] text-white text-[15px] leading-[1.6] tracking-[-0.01em] break-words shadow-[0_2px_10px_rgba(3,4,12,0.25)]">
                <div className="ai-markdown text-white [&_strong]:text-white [&_h1]:text-white [&_h2]:text-white [&_h3]:text-white [&_th]:text-white [&_li::marker]:text-sky-300 [&_a]:text-sky-200 [&_code:not(pre_code)]:text-sky-200 [&_blockquote]:text-sky-100/80">
                  <Markdown content={message.content} />
                </div>
              </div>
            ) : (
              <div className="text-[15px] sm:text-[15.5px] leading-[1.7] tracking-[-0.01em] text-zinc-200 break-words">
                <div className="ai-markdown">
                  <Markdown content={message.content} />
                </div>
                {isStreaming && <span className="chat-caret" />}
              </div>
            )}
          </div>
        )}

        {/* Tool invocation chips */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className={`flex flex-wrap gap-1.5 mt-1 w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
            {message.toolCalls.map((tool, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: idx * 0.04 }}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass-faint border border-sky-300/10"
              >
                {isStreaming ? (
                  <Loader2 className="w-3 h-3 text-sky-300 animate-spin" />
                ) : (
                  <Check className="w-3 h-3 text-emerald-300" />
                )}
                <span className="text-[10px] font-semibold text-sky-200 uppercase tracking-wider">{tool.name}</span>
              </motion.div>
            ))}
          </div>
        )}

        {/* Non-image file cards */}
        {otherAttachments.length > 0 && (
          <div className="flex flex-col gap-2 mt-1 w-full">
            {otherAttachments.map((file, idx) => {
              const isPdf = file.mime_type === 'application/pdf' || file.filename.endsWith('.pdf');
              const sizeKb = file.size_bytes ? Math.round(file.size_bytes / 1024) : null;
              const fullUrl =
                file.file_url.startsWith('http') || file.file_url.startsWith('data:') || file.file_url.startsWith('blob:')
                  ? file.file_url
                  : `${import.meta.env.VITE_API_URL || ''}${file.file_url}`;
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-3 self-start rounded-con-16 glass-faint px-3.5 sm:px-4 py-2.5 sm:py-3 w-full sm:w-auto sm:min-w-[280px]"
                >
                  <div className={`w-9 h-9 shrink-0 rounded-con-12 flex items-center justify-center ${isPdf ? 'bg-sky-500/15 text-sky-300' : 'bg-violet-500/15 text-violet-300'}`}>
                    {isPdf ? <FileText className="w-4 h-4" /> : <FileDown className="w-4 h-4" />}
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-[13px] font-medium text-zinc-200 truncate max-w-[200px]">{file.filename}</span>
                    {sizeKb !== null && <span className="text-[10px] text-zinc-500">{sizeKb} KB</span>}
                  </div>
                  <a
                    href={fullUrl}
                    download={file.filename}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-con-10 bg-sky-500/15 text-sky-300 text-[11px] font-semibold hover:bg-sky-500/25 transition-colors"
                  >
                    <FileDown className="w-3.5 h-3.5" />
                    Download
                  </a>
                </motion.div>
              );
            })}
          </div>
        )}

        {/* Copy affordance — hover on desktop, hidden on touch where there's no hover */}
        {canCopy && (
          <button
            type="button"
            onClick={() => void copyText()}
            className="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-medium text-zinc-500 hover:text-zinc-200 opacity-0 group-hover:opacity-100 transition-opacity px-2 py-1 -ml-1"
          >
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}

        {/* Timestamp closes the group — desktop only, keeps the phone thread clean */}
        {isLast && timestamp && !isStreaming && (
          <span className="hidden sm:block px-2 mt-0.5 text-[10px] font-mono text-zinc-600 tabular">{timestamp}</span>
        )}
      </div>
    </motion.div>
  );
}

/** Markdown render with dark-app refinements. */
function Markdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        img: (props) => {
          const src = props.src || '';
          return (
            <span className="inline-block">
              <MiniImage src={src} alt={props.alt || 'image'} />
            </span>
          );
        },
        table: ({ children }) => (
          <div className="w-full overflow-x-auto thin-scrollbar chat-table-scroll">
            <table className="w-full border-collapse">{children}</table>
          </div>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

/** Renders a markdown-embedded image as a clickable preview. */
function MiniImage({ src, alt }: { src: string; alt: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="inline-block">
      <button
        type="button"
        className="group relative inline-block rounded-con-12 overflow-hidden align-middle cursor-zoom-in"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
      >
        <img
          src={src}
          alt={alt}
          loading="lazy"
          className="max-h-40 max-w-[220px] object-contain rounded-con-10 border border-white/[0.08] hover:opacity-90 transition-opacity"
        />
        <span className="absolute bottom-1.5 right-1.5 p-1 rounded-md bg-black/70 text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
          <ImageIcon className="w-3 h-3" />
        </span>
      </button>
      {open && (
        <div className="fixed inset-0 z-[100]" onClick={() => setOpen(false)}>
          <Lightbox
            images={[{ fromMarkdown: src, filename: alt || 'image' }]}
            index={0}
            onIndexChange={() => {}}
            onClose={() => setOpen(false)}
          />
        </div>
      )}
    </span>
  );
}