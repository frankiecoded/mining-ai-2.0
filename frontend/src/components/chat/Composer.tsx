import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Paperclip, Send, X, Loader2, FileText } from 'lucide-react';
import { isImageMime } from './ImageViewer';

interface ComposerProps {
  disabled: boolean;
  onSend: (text: string, file?: File) => void;
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [focused, setFocused] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const canSend = (text.trim().length > 0 || !!file) && !disabled;
  const isImage = file ? isImageMime(file.type, file.name) : false;

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    onSend(text.trim(), file ?? undefined);
    setText('');
    setFile(null);
    setPreviewUrl(null);
  };

  const removeFile = () => {
    setFile(null);
    setPreviewUrl(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  return (
    <div className="relative">
      <input
        type="file"
        ref={fileRef}
        className="hidden"
        accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.geotiff,.tif,.tiff,.shp,.kml,.kmz"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />

      <motion.form
        onSubmit={submit}
        animate={{ scale: focused ? 1.005 : 1 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className={`glass-strong rounded-con-24 flex items-end gap-1 p-2 pl-3 shadow-float transition-shadow duration-300 ${
          focused ? 'shadow-[0_0_0_4px_rgba(91,156,255,0.12),0_16px_48px_rgba(3,4,12,0.6)]' : ''
        }`}
      >
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          aria-label="Attach file"
          className={`shrink-0 w-11 h-11 rounded-full inline-flex items-center justify-center transition-colors ${
            file
              ? 'text-sky-300 bg-sky-400/10 border border-sky-400/20'
              : 'text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.07]'
          }`}
        >
          <Paperclip className="w-[18px] h-[18px]" />
        </button>

        <div className="flex-1 min-w-0">
          {/* Attachment preview chip */}
          <AnimatePresence>
            {file && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.18, ease: 'easeOut' }}
                className="overflow-hidden"
              >
                <div className="flex items-center gap-3 px-1.5 pt-2 pb-1.5">
                  {isImage && previewUrl ? (
                    <img
                      src={previewUrl}
                      alt={file.name}
                      className="w-12 h-12 rounded-con-12 object-cover border border-sky-400/30"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-con-12 bg-white/[0.06] border border-white/10 flex items-center justify-center">
                      <FileText className="w-5 h-5 text-zinc-400" />
                    </div>
                  )}
                  <div className="flex flex-col min-w-0">
                    <span className="text-[12px] font-medium text-zinc-200 truncate max-w-[200px]">{file.name}</span>
                    <span className="text-[10px] text-zinc-500">
                      {file.size ? `${Math.max(1, Math.round(file.size / 1024))} KB` : 'Ready'}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={removeFile}
                    className="text-zinc-500 hover:text-white p-2.5 rounded-full hover:bg-white/[0.08] transition-colors"
                    aria-label="Remove file"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={file ? 'Add a message about this file…' : 'Ask your Intelligence Core…'}
            className="w-full bg-transparent border-none outline-none px-2 py-3 text-[15px] text-white placeholder-zinc-600"
            autoFocus={false}
            aria-label="Message"
          />
        </div>

        <motion.button
          whileTap={canSend ? { scale: 0.9 } : undefined}
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          title="Send"
          className={`shrink-0 w-11 h-11 rounded-full inline-flex items-center justify-center transition-all duration-200 ${
            canSend
              ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-[0_6px_16px_rgba(59,110,246,0.45)] hover:brightness-110 hover:shadow-[0_8px_24px_rgba(59,110,246,0.55)]'
              : 'bg-white/[0.06] text-zinc-600'
          }`}
        >
          {disabled ? <Loader2 className="w-[18px] h-[18px] animate-spin text-sky-300" /> : <Send className="w-[18px] h-[18px]" />}
        </motion.button>
      </motion.form>

      {/* Status caption — reclaimed on phones so the field owns the bottom edge;
          the send button already signals streaming there. */}
      <div className="hidden sm:flex items-center justify-between px-2 pt-1.5 text-[10px] font-medium uppercase tracking-[0.16em]">
        <span className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${disabled ? 'bg-amber-400' : 'bg-emerald-400'}`} />
          <span className={disabled ? 'text-amber-300/70' : 'text-zinc-600'}>
            {disabled ? 'Processing…' : 'AI OS is ready'}
          </span>
        </span>
        <span className="hidden sm:inline text-zinc-700 tracking-[0.12em]">Enter to send</span>
      </div>
    </div>
  );
}