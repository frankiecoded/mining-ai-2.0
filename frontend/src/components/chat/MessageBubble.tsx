import { useState } from 'react';
import { motion } from 'framer-motion';
import { Bot, User, Loader2, FileDown, FileText, ImageIcon, CheckCheck } from 'lucide-react';
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

export function MessageBubble({ message, isFirst = true, isLast = true, isStreaming = false, timestamp }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  if (isSystem) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full flex justify-center my-2"
      >
        <div className="chat-divider w-full max-w-[560px] flex items-center justify-center py-5">
          <div className="glass-faint rounded-full px-4 py-1.5 relative">
            <span className="text-[11px] font-medium text-zinc-400 whitespace-pre-line">
              {message.content}
            </span>
          </div>
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
  const hasPack = previewImages.length > 0 || otherAttachments.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 420, damping: 34 }}
      className={`flex w-full gap-2.5 sm:gap-3 ${isUser ? 'justify-end' : 'justify-start'} ${isFirst ? 'mt-6 sm:mt-7' : 'mt-2 sm:mt-2.5'}`}
    >
      {!isUser && (
        <div className="w-7 shrink-0 mt-1.5">
          {isFirst ? (
            <motion.div
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="w-7 h-7 rounded-full bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_4px_12px_rgba(59,110,246,0.4)] border border-white/10"
            >
              <Bot className="w-3.5 h-3.5 text-white" />
            </motion.div>
          ) : (
            <div className="w-7 h-7" />
          )}
        </div>
      )}

      <div className={`flex flex-col gap-1.5 min-w-0 max-w-[85%] md:max-w-[74%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Sender meta row (only at group start so a run reads as one block) */}
        {isFirst && (
          <div className={`flex items-center gap-1.5 px-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
            isUser ? 'text-sky-300/70 justify-end' : 'text-zinc-500'
          }`}>
            {isUser ? (
              <>
                <User className="w-3 h-3" /> You
              </>
            ) : (
              <>
                <Bot className="w-3 h-3" /> AI OS
              </>
            )}
          </div>
        )}

        {/* Image previews (inline, presentation-style) */}
        {previewImages.length > 0 && (
          <div className={`min-w-0 max-w-full ${isUser ? 'self-end' : 'self-start w-full'}`}>
            <ImageStrip images={previewImages} />
          </div>
        )}

        {hasText && (
          <div
            className={`px-3.5 sm:px-4 py-2.5 sm:py-3 text-[14px] leading-relaxed tracking-[-0.01em] break-words ${
              isUser
                ? 'rounded-con-22 rounded-br-[6px] bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-[0_8px_20px_rgba(59,110,246,0.35)]'
                : 'rounded-con-22 rounded-bl-[6px] glass'
            } ${hasPack ? 'mt-1' : ''}`}
          >
            <div className={`ai-markdown ${isUser ? 'text-white [&_strong]:text-white [&_h1]:text-white [&_h2]:text-white [&_h3]:text-white [&_th]:text-white [&_li::marker]:text-sky-300 [&_a]:text-sky-200 [&_code:not(pre_code)]:text-sky-200 [&_blockquote]:text-sky-100/80' : ''}`}>
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
                {message.content}
              </ReactMarkdown>
            </div>
            {isStreaming && <span className="chat-caret" />}
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
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass-faint border border-violet-300/10"
              >
                {isStreaming ? (
                  <Loader2 className="w-3 h-3 text-violet-300 animate-spin" />
                ) : (
                  <CheckCheck className="w-3 h-3 text-emerald-300" />
                )}
                <span className="text-[10px] font-semibold text-violet-200 uppercase tracking-wider">
                  {tool.name}
                </span>
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
              const fullUrl = file.file_url.startsWith('http') || file.file_url.startsWith('data:') || file.file_url.startsWith('blob:')
                ? file.file_url
                : `${import.meta.env.VITE_API_URL || ''}${file.file_url}`;
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-3 self-start rounded-con-16 glass-faint px-3.5 sm:px-4 py-2.5 sm:py-3 group w-full sm:w-auto sm:min-w-[280px]"
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

        {/* Timestamp (only closes the group — keeps the stream clean) */}
        {isLast && (timestamp || isStreaming) && (
          <span className="px-1 mt-0.5 text-[10px] font-mono text-zinc-600 tabular">
            {isStreaming ? 'Streaming…' : timestamp}
          </span>
        )}
      </div>
    </motion.div>
  );
}

/** Renders a markdown-embedded image as a clickable preview. */
function MiniImage({ src, alt }: { src: string; alt: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="inline-block">
      <button
        type="button"
        className="group relative inline-block rounded-lg overflow-hidden align-middle cursor-zoom-in"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
      >
        <img
          src={src}
          alt={alt}
          loading="lazy"
          className="max-h-40 max-w-[220px] object-contain rounded-lg border border-white/[0.08] hover:opacity-90 transition-opacity"
        />
        <span className="absolute bottom-1 right-1 p-1 rounded-md bg-black/70 text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
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