import { motion } from 'framer-motion';
import { Bot, User, Wrench, CheckCircle2, FileDown, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../../types';

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  if (isSystem) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full flex justify-center my-3"
      >
        <div className="glass-faint rounded-full px-4 py-1.5 text-center">
          <span className="text-[11px] font-medium text-zinc-400 whitespace-pre-line">
            {message.content}
          </span>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 400, damping: 32 }}
      className={`flex w-full gap-2.5 ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      {!isUser && (
        <div className="w-7 h-7 shrink-0 mt-1 rounded-full bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_4px_12px_rgba(59,110,246,0.4)]">
          <Bot className="w-3.5 h-3.5 text-white" />
        </div>
      )}

      <div className={`flex flex-col gap-1.5 max-w-[82%] md:max-w-[72%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.12em] ${
          isUser ? 'text-sky-300/70' : 'text-zinc-500'
        }`}>
          {isUser ? (
            <>
              <User className="w-3 h-3" /> You
            </>
          ) : (
            <>
              <CheckCircle2 className="w-3 h-3" /> AI OS
            </>
          )}
        </div>

        {message.content && (
          <div
            className={`px-4 py-3 text-[14px] leading-relaxed tracking-[-0.01em] break-words ${
              isUser
                ? 'rounded-[20px] rounded-br-md bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-[0_8px_20px_rgba(59,110,246,0.35)]'
                : 'rounded-[20px] rounded-bl-md glass'
            }`}
          >
            <div className={`ai-markdown ${isUser ? 'text-white [&_strong]:text-white [&_h1]:text-white [&_h2]:text-white [&_h3]:text-white [&_th]:text-white [&_li::marker]:text-sky-300 [&_a]:text-sky-200 [&_code:not(pre_code)]:text-sky-200 [&_blockquote]:text-sky-100/80' : ''}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          </div>
        )}

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-col gap-1.5 mt-1 w-full">
            {message.toolCalls.map((tool, idx) => (
              <div key={idx} className="self-start inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass-faint">
                <Wrench className="w-3 h-3 text-violet-300" />
                <span className="text-[10px] font-semibold text-violet-200 uppercase tracking-wider">
                  {tool.name}
                </span>
              </div>
            ))}
          </div>
        )}

        {message.attachments && message.attachments.length > 0 && (
          <div className="flex flex-col gap-2 mt-2 w-full">
            {message.attachments.map((file, idx) => {
              const isPdf = file.mime_type === 'application/pdf' || file.filename.endsWith('.pdf');
              const sizeKb = file.size_bytes ? Math.round(file.size_bytes / 1024) : null;
              const fullUrl = file.file_url.startsWith('http') ? file.file_url : `${import.meta.env.VITE_API_URL || ''}${file.file_url}`;
              return (
                <div key={idx} className="flex items-center gap-3 self-start rounded-xl glass-faint px-4 py-3 group">
                  {isPdf ? (
                    <FileText className="w-5 h-5 text-sky-300 shrink-0" />
                  ) : (
                    <FileDown className="w-5 h-5 text-sky-300 shrink-0" />
                  )}
                  <div className="flex flex-col min-w-0">
                    <span className="text-[13px] font-medium text-zinc-200 truncate max-w-[220px]">{file.filename}</span>
                    {sizeKb !== null && <span className="text-[10px] text-zinc-500">{sizeKb} KB</span>}
                  </div>
                  <a
                    href={fullUrl}
                    download={file.filename}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/20 text-sky-300 text-[11px] font-semibold hover:bg-sky-500/30 transition-colors"
                  >
                    <FileDown className="w-3.5 h-3.5" />
                    Download
                  </a>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </motion.div>
  );
}
