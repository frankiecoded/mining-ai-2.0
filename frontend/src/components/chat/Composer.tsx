import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Paperclip, ArrowUp, Loader2, X, FileText } from 'lucide-react';
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
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = (text.trim().length > 0 || !!file) && !disabled;
  const isImage = file ? isImageMime(file.type, file.name) : false;

  // Replace the object URL whenever a (different) file is picked, and revoke
  // the live one when the preview unmounts.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const resize = () => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    resize();
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    onSend(text.trim(), file ?? undefined);
    setText('');
    setFile(null);
    setPreviewUrl(null);
    if (areaRef.current) areaRef.current.style.height = 'auto';
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit(e);
    }
  };

  const removeFile = () => {
    setFile(null);
    setPreviewUrl(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  };

  return (
    <div className="relative">
      <input
        type="file"
        ref={fileRef}
        className="hidden"
        accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.geotiff,.tif,.tiff,.shp,.kml,.kmz"
        onChange={onFileChange}
      />

      <motion.form
        onSubmit={submit}
        animate={{ scale: focused ? 1.004 : 1 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        className={`glass-strong rounded-con-24 sm:rounded-con-28 flex items-end p-1.5 sm:p-2 pl-2 sm:pl-2.5 shadow-float transition-shadow duration-300 ${
          focused ? 'shadow-[0_0_0_4px_rgba(91,156,255,0.12),0_20px_56px_rgba(3,4,12,0.65)]' : ''
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
            {file && previewUrl && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.18, ease: 'easeOut' }}
                className="overflow-hidden"
              >
                <div className="flex items-center gap-3 px-1 pt-1.5 pb-1">
                  {isImage ? (
                    <img
                      src={previewUrl}
                      alt={file.name}
                      className="w-11 h-11 rounded-con-12 object-cover border border-sky-400/30"
                    />
                  ) : (
                    <div className="w-11 h-11 rounded-con-12 bg-white/[0.06] border border-white/10 flex items-center justify-center">
                      <FileText className="w-5 h-5 text-zinc-400" />
                    </div>
                  )}
                  <div className="flex flex-col min-w-0">
                    <span className="text-[12px] font-medium text-zinc-200 truncate max-w-[180px]">{file.name}</span>
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

          <textarea
            ref={areaRef}
            value={text}
            onChange={handleChange}
            onKeyDown={handleKey}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            rows={1}
            placeholder={file ? 'Add a message about this file…' : 'Message Intelligence Core…'}
            className="w-full resize-none bg-transparent border-none outline-none px-2 py-[10px] text-base md:text-[15px] leading-[1.45] text-white placeholder:text-zinc-600 max-h-32 thin-scrollbar"
            aria-label="Message"
          />
        </div>

        <motion.button
          whileTap={canSend ? { scale: 0.9 } : undefined}
          type="submit"
          disabled={!canSend}
          aria-label={disabled ? 'Working…' : 'Send message'}
          title={disabled ? 'Working…' : 'Send'}
          className={`shrink-0 w-11 h-11 rounded-full inline-flex items-center justify-center transition-all duration-200 ${
            disabled
              ? 'bg-white/[0.07] text-sky-300'
              : canSend
                ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-[0_6px_16px_rgba(59,110,246,0.45)] hover:brightness-110'
                : 'bg-white/[0.06] text-zinc-600'
          }`}
        >
          {disabled ? (
            <Loader2 className="w-[18px] h-[18px] animate-spin" />
          ) : (
            <ArrowUp className="w-[18px] h-[18px]" strokeWidth={2.5} />
          )}
        </motion.button>
      </motion.form>

      {/* Foot caption — desktop only; the field owns the mobile bottom edge */}
      <div className="hidden sm:flex items-center justify-between px-2 pt-2 text-[10px] font-medium uppercase tracking-[0.14em]">
        <span className="flex items-center gap-2">
          <span className={`w-1.5 h-1.5 rounded-full ${disabled ? 'bg-amber-400' : 'bg-emerald-400'}`} />
          <span className={disabled ? 'text-amber-300/70' : 'text-zinc-600'}>Intelligence Core</span>
          <span className="text-zinc-700">·</span>
          <span className="text-zinc-600">Medium thinking</span>
        </span>
        <span className="text-zinc-700">Enter to send</span>
      </div>
    </div>
  );
}