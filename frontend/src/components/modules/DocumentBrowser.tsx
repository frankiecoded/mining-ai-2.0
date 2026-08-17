import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, Download, X, FileText, FileSpreadsheet, FileImage,
  FileCode, Eye, FolderOpen, ChevronRight, Loader2, Presentation,
  ExternalLink,
} from 'lucide-react';
import { ChatAPI } from '../../services/api';

type DocEntry = {
  name: string;
  type: 'file' | 'folder';
  path: string;
  size?: number;
  mime?: string;
  children?: DocEntry[];
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function fileIcon(name: string, size = 20) {
  const ext = name.split('.').pop()?.toLowerCase() || '';
  const cls = `w-${size < 24 ? '5' : '6'} h-${size < 24 ? '5' : '6'}`;
  if (ext === 'pdf') return <FileText className={`${cls} text-rose-400`} />;
  if (['pptx', 'ppt'].includes(ext)) return <Presentation className={`${cls} text-orange-400`} />;
  if (['xlsx', 'xls', 'csv'].includes(ext)) return <FileSpreadsheet className={`${cls} text-emerald-400`} />;
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return <FileImage className={`${cls} text-violet-400`} />;
  if (['json', 'xml', 'geojson'].includes(ext)) return <FileCode className={`${cls} text-amber-400`} />;
  if (['docx', 'doc'].includes(ext)) return <FileText className={`${cls} text-sky-400`} />;
  return <FileText className={`${cls} text-zinc-400`} />;
}

function fileColor(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return 'bg-rose-400/10 text-rose-300 border-rose-400/20';
  if (['pptx', 'ppt'].includes(ext)) return 'bg-orange-400/10 text-orange-300 border-orange-400/20';
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'bg-emerald-400/10 text-emerald-300 border-emerald-400/20';
  if (['png', 'jpg', 'jpeg'].includes(ext)) return 'bg-violet-400/10 text-violet-300 border-violet-400/20';
  if (['json', 'xml'].includes(ext)) return 'bg-amber-400/10 text-amber-300 border-amber-400/20';
  return 'bg-zinc-400/10 text-zinc-300 border-zinc-400/20';
}

function isPreviewable(mime?: string, name?: string): boolean {
  if (!mime && !name) return false;
  const m = (mime || '').toLowerCase();
  const ext = (name || '').split('.').pop()?.toLowerCase() || '';
  if (m === 'application/pdf' || ext === 'pdf') return true;
  if (m === 'image/png' || m === 'image/jpeg' || m === 'image/gif' || m === 'image/webp' || m === 'image/svg+xml') return true;
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return true;
  return false;
}

function isPdf(mime?: string, name?: string): boolean {
  const m = (mime || '').toLowerCase();
  const ext = (name || '').split('.').pop()?.toLowerCase() || '';
  return m === 'application/pdf' || ext === 'pdf';
}

function isImage(mime?: string, name?: string): boolean {
  const m = (mime || '').toLowerCase();
  const ext = (name || '').split('.').pop()?.toLowerCase() || '';
  return m.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext);
}

/* ──────── Preview Modal (Apple Design) ──────── */
function PreviewModal({
  file,
  onClose,
}: {
  file: DocEntry;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const previewUrl = ChatAPI.getDocumentPreviewUrl(file.path);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="fixed inset-0 z-[9999] flex items-center justify-center"
    >
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/70 backdrop-blur-xl"
        onClick={onClose}
      />

      {/* Modal */}
      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        className="relative z-10 w-[92vw] h-[88vh] max-w-[1200px] bg-[#1a1a2e]/95 backdrop-blur-2xl rounded-[24px] border border-white/[0.08] shadow-[0_40px_100px_rgba(0,0,0,0.6)] flex flex-col overflow-hidden"
      >
        {/* Top Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-10 h-10 rounded-xl inline-flex items-center justify-center shrink-0 border ${fileColor(file.name)}`}>
              {fileIcon(file.name)}
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-white truncate">{file.name}</h3>
              <p className="text-[11px] text-zinc-500">
                {file.size ? formatBytes(file.size) : ''}
                {file.mime ? ` · ${file.mime.split('/').pop()?.toUpperCase()}` : ''}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={previewUrl}
              download
              target="_blank"
              rel="noopener noreferrer"
              className="glass-faint rounded-xl px-3.5 py-2 text-[12px] font-medium text-zinc-300 hover:text-white flex items-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Download
            </a>
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="glass-faint rounded-xl px-3.5 py-2 text-[12px] font-medium text-zinc-300 hover:text-white flex items-center gap-1.5 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Open
            </a>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-white/[0.06] hover:bg-white/[0.12] flex items-center justify-center text-zinc-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Preview Area */}
        <div className="flex-1 relative overflow-hidden">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
                <p className="text-[13px] text-zinc-500">Loading preview…</p>
              </div>
            </div>
          )}

          {isPdf(file.mime, file.name) && (
            <iframe
              src={previewUrl}
              className="w-full h-full border-0"
              onLoad={() => setLoading(false)}
              title={file.name}
            />
          )}

          {isImage(file.mime, file.name) && (
            <div className="w-full h-full flex items-center justify-center p-8 bg-[#0d0d1a]">
              <img
                src={previewUrl}
                alt={file.name}
                className="max-w-full max-h-full object-contain rounded-xl shadow-2xl"
                onLoad={() => setLoading(false)}
              />
            </div>
          )}

          {!isPdf(file.mime, file.name) && !isImage(file.mime, file.name) && (
            <div className="w-full h-full flex flex-col items-center justify-center p-12 text-center">
              <div className={`w-20 h-20 rounded-3xl inline-flex items-center justify-center mb-5 border ${fileColor(file.name)}`}>
                {fileIcon(file.name, 32)}
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{file.name}</h3>
              <p className="text-[13px] text-zinc-500 mb-6 max-w-md">
                This file type can be downloaded but doesn't support in-browser preview.
                Click Download to save a local copy.
              </p>
              <a
                href={previewUrl}
                download
                className="btn-primary rounded-full px-6 py-2.5 text-sm font-semibold flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download File
              </a>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ──────── Document Browser (Apple Finder Style) ──────── */
export function DocumentBrowser() {
  const [docs, setDocs] = useState<DocEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [pathStack, setPathStack] = useState<{ name: string; path: string }[]>([]);
  const [previewFile, setPreviewFile] = useState<DocEntry | null>(null);

  const currentFolder = pathStack.length > 0 ? pathStack[pathStack.length - 1].path : undefined;

  const loadFolder = useCallback(async (folder?: string) => {
    setLoading(true);
    try {
      const res = await ChatAPI.listDocuments(folder);
      setDocs((res.documents || []) as DocEntry[]);
    } catch {
      setDocs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFolder(currentFolder);
  }, [currentFolder, loadFolder]);

  const navigateTo = (entry: DocEntry) => {
    if (entry.type === 'folder') {
      setPathStack((prev) => [...prev, { name: entry.name, path: entry.path }]);
    } else if (isPreviewable(entry.mime, entry.name)) {
      setPreviewFile(entry);
    }
  };

  const goBack = () => {
    setPathStack((prev) => prev.slice(0, -1));
  };

  const goToRoot = () => {
    setPathStack([]);
  };

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <div className="glass rounded-2xl px-4 py-3 flex items-center gap-1.5 overflow-x-auto thin-scrollbar">
        <button
          onClick={goToRoot}
          className={`shrink-0 text-[12px] font-medium px-2 py-1 rounded-lg transition-colors ${
            pathStack.length === 0 ? 'text-white bg-white/[0.06]' : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <FolderOpen className="w-3.5 h-3.5 inline mr-1.5" />
          All Documents
        </button>
        {pathStack.map((p, i) => (
          <span key={p.path} className="flex items-center gap-1.5 shrink-0">
            <ChevronRight className="w-3 h-3 text-zinc-600" />
            <button
              onClick={() => {
                setPathStack((prev) => prev.slice(0, i + 1));
              }}
              className={`text-[12px] font-medium px-2 py-1 rounded-lg transition-colors ${
                i === pathStack.length - 1 ? 'text-white bg-white/[0.06]' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {p.name}
            </button>
          </span>
        ))}
        {pathStack.length > 0 && (
          <button
            onClick={goBack}
            className="ml-2 glass-faint rounded-lg p-1.5 text-zinc-500 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* File Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
        </div>
      ) : docs.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center">
          <FolderOpen className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <p className="text-sm text-zinc-500">This folder is empty.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {docs.map((entry) => (
            <motion.div
              key={entry.path}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => navigateTo(entry)}
              className={`glass-faint rounded-2xl p-4 cursor-pointer transition-all group ${
                entry.type === 'folder'
                  ? 'hover:border-sky-400/20 border border-transparent'
                  : isPreviewable(entry.mime, entry.name)
                    ? 'hover:border-sky-400/20 border border-transparent'
                    : 'border border-transparent hover:bg-white/[0.03]'
              }`}
            >
              {/* Icon */}
              <div className="flex justify-center mb-3">
                {entry.type === 'folder' ? (
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500/15 to-violet-600/15 flex items-center justify-center border border-sky-400/10">
                    <FolderOpen className="w-7 h-7 text-sky-300" />
                  </div>
                ) : (
                  <div className={`w-14 h-14 rounded-2xl flex items-center justify-center border ${fileColor(entry.name)}`}>
                    {fileIcon(entry.name, 28)}
                  </div>
                )}
              </div>

              {/* Name */}
              <div className="text-center">
                <div className="text-[12px] font-medium text-white truncate px-1 group-hover:text-sky-200 transition-colors">
                  {entry.name}
                </div>
                {entry.size != null && (
                  <div className="text-[10px] text-zinc-600 mt-1 font-mono">{formatBytes(entry.size)}</div>
                )}
                {entry.type === 'folder' && entry.children && (
                  <div className="text-[10px] text-zinc-600 mt-1">{entry.children.length} items</div>
                )}
              </div>

              {/* Preview Badge */}
              {entry.type === 'file' && isPreviewable(entry.mime, entry.name) && (
                <div className="flex justify-center mt-2">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-400/10 text-sky-300 text-[10px] font-medium border border-sky-400/15">
                    <Eye className="w-2.5 h-2.5" />
                    Preview
                  </span>
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}

      {/* Preview Modal */}
      <AnimatePresence>
        {previewFile && (
          <PreviewModal
            file={previewFile}
            onClose={() => setPreviewFile(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
