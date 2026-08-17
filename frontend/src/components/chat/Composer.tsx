import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Paperclip, Send, X, Loader2 } from 'lucide-react';

interface ComposerProps {
  disabled: boolean;
  onSend: (text: string, file?: File) => void;
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const canSend = (text.trim().length > 0 || !!file) && !disabled;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    onSend(text.trim(), file ?? undefined);
    setText('');
    setFile(null);
  };

  return (
    <div className="relative">
      <div className="absolute -top-2 left-1 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-600">
        {disabled ? 'Processing…' : 'AI OS is ready'}
      </div>

      <input
        type="file"
        ref={fileRef}
        className="hidden"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />

      <form
        onSubmit={submit}
        className="glass-strong rounded-[24px] flex items-end gap-1 p-1.5 pl-3 shadow-float"
      >
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          aria-label="Attach file"
          className={`shrink-0 w-9 h-9 rounded-full inline-flex items-center justify-center transition-colors ${
            file ? 'text-sky-300 bg-sky-400/10' : 'text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.07]'
          }`}
        >
          <Paperclip className="w-[18px] h-[18px]" />
        </button>

        <div className="flex-1 min-w-0">
          {file && (
            <div className="flex items-center gap-2 px-2 pt-1.5">
              <span className="text-[11px] text-sky-200 bg-sky-400/10 rounded-md px-2 py-0.5 truncate max-w-[220px]">
                {file.name}
              </span>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="text-zinc-500 hover:text-white"
                aria-label="Remove file"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask the Intelligence Core…"
            className="w-full bg-transparent border-none outline-none px-2 py-2.5 text-[15px] text-white placeholder-zinc-600"
            autoFocus={false}
          />
        </div>

        <motion.button
          whileTap={canSend ? { scale: 0.92 } : undefined}
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          className={`shrink-0 w-10 h-10 rounded-full inline-flex items-center justify-center transition-all ${
            canSend
              ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-[0_6px_16px_rgba(59,110,246,0.4)]'
              : 'bg-white/[0.06] text-zinc-600'
          }`}
        >
          {disabled ? <Loader2 className="w-[18px] h-[18px] animate-spin" /> : <Send className="w-[18px] h-[18px]" />}
        </motion.button>
      </form>
    </div>
  );
}
