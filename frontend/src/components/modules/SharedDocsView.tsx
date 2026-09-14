import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  FolderUp,
  Upload,
  Eye,
  Check,
  X,
  Loader2,
  AlertTriangle,
  Trash2,
  Clock,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { SectionLabel } from '../ui/SectionLabel';
import { Badge } from '../ui/Badge';
import { Spinner } from '../ui/Spinner';
import { SpotlightCard } from '../ui/SpotlightCard';
import { EmptyState } from '../ui/EmptyState';
import type { SharedDocRecord } from '../../types';

const STATUS_ICON: Record<string, typeof Clock> = {
  pending: Clock,
  committed: CheckCircle2,
  rejected: XCircle,
};
const STATUS_TONE: Record<string, 'amber' | 'emerald' | 'rose'> = {
  pending: 'amber',
  committed: 'emerald',
  rejected: 'rose',
};

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function SharedDocsView() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [docs, setDocs] = useState<SharedDocRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadNote, setUploadNote] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadOk, setUploadOk] = useState(false);

  // Admin action state
  const [committingId, setCommittingId] = useState<number | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [previewId, setPreviewId] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await ChatAPI.fetchSharedDocuments();
      setDocs(res.records ?? []);
    } catch {
      setError('Could not load shared documents.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleUpload = useCallback(async () => {
    if (!uploadFile || uploading) return;
    setUploading(true);
    try {
      await ChatAPI.uploadSharedDocument(uploadFile, uploadNote.trim());
      setUploadFile(null);
      setUploadNote('');
      setUploadOk(true);
      window.setTimeout(() => setUploadOk(false), 2400);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  }, [uploadFile, uploading, uploadNote, load]);

  const commit = useCallback(
    async (id: number) => {
      setCommittingId(id);
      try {
        await ChatAPI.commitSharedDocument(id);
        await load();
      } catch {
        setError('Commit failed.');
      } finally {
        setCommittingId(null);
      }
    },
    [load],
  );

  const reject = useCallback(
    async (id: number) => {
      setRejectingId(id);
      try {
        await ChatAPI.rejectSharedDocument(id);
        await load();
      } catch {
        setError('Reject failed.');
      } finally {
        setRejectingId(null);
      }
    },
    [load],
  );

  const remove = useCallback(
    async (id: number) => {
      setDeleteId(id);
      try {
        await ChatAPI.deleteSharedDocument(id);
        await load();
      } catch {
        setError('Delete failed.');
      } finally {
        setDeleteId(null);
      }
    },
    [load],
  );

  const pending = docs.filter((d) => d.status === 'pending');
  const others = docs.filter((d) => d.status !== 'pending');

  return (
    <div className="h-full overflow-y-auto thin-scrollbar px-4 md:px-8 py-6">
      <div className="max-w-5xl mx-auto space-y-8 pb-8">
        <motion.header
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="flex items-center gap-3.5"
        >
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-amber-500 to-rose-600 flex items-center justify-center shadow-[0_10px_28px_rgba(245,158,11,0.35)]">
            <FolderUp className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white tracking-tight">Documents</h2>
            <p className="text-[13px] text-zinc-500">
              {isAdmin
                ? "Team's shared files — preview and commit each to the knowledge base"
                : 'Share a file to Frank for review and commitment into the knowledge base'}
            </p>
          </div>
        </motion.header>

        {error && (
          <div className="flex items-center gap-2.5 text-[13px] text-rose-300 bg-rose-500/[0.08] border border-rose-500/20 rounded-xl p-3">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
            <button className="ml-auto text-zinc-500 hover:text-white" onClick={() => setError(null)}>
              dismiss
            </button>
          </div>
        )}

        {/* Upload section (all users) */}
        <section>
          <SectionLabel>{isAdmin ? 'Share a File' : 'Share to Frank'}</SectionLabel>
          <SpotlightCard className="glass-faint rounded-2xl">
            <div className="p-4 md:p-5 space-y-4">
              <div className="flex flex-col sm:flex-row gap-3">
                <label
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const f = e.dataTransfer.files?.[0];
                    if (f) setUploadFile(f);
                  }}
                  className="flex-1 cursor-pointer rounded-xl border border-dashed border-white/[0.1] hover:border-sky-400/30 transition-colors"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) setUploadFile(f);
                    }}
                  />
                  <div className="flex items-center gap-3 px-4 py-3">
                    <div className="w-9 h-9 rounded-xl bg-white/[0.06] flex items-center justify-center shrink-0">
                      <Upload className="w-4 h-4 text-sky-300" />
                    </div>
                    <div className="flex-1 min-w-0">
                      {uploadFile ? (
                        <span className="text-[13px] text-white font-medium truncate block">{uploadFile.name}</span>
                      ) : (
                        <span className="text-[13px] text-zinc-400">Drag a file here, or tap to browse</span>
                      )}
                    </div>
                  </div>
                </label>
                <button
                  onClick={() => void handleUpload()}
                  disabled={!uploadFile || uploading}
                  className="rounded-xl btn-primary px-5 py-2.5 text-[13px] font-semibold flex items-center justify-center gap-2 disabled:opacity-50 disabled:pointer-events-none"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Uploading…
                    </>
                  ) : uploadOk ? (
                    <>
                      <Check className="w-4 h-4" /> Uploaded
                    </>
                  ) : (
                    'Upload'
                  )}
                </button>
              </div>
              <input
                value={uploadNote}
                onChange={(e) => setUploadNote(e.target.value)}
                placeholder="Note for Frank (optional)"
                className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-[13px] text-white placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-sky-400/40"
              />
            </div>
          </SpotlightCard>
        </section>

        {loading ? (
          <div className="flex justify-center py-16 text-sky-300">
            <Spinner className="w-6 h-6" />
          </div>
        ) : docs.length === 0 ? (
          <div className="glass-faint rounded-2xl">
            <EmptyState
              icon={<FolderUp className="w-6 h-6" />}
              title="No shared files yet"
              description="Drag a report or photo into the box above — it will appear here for review."
            />
          </div>
        ) : (
          <>
            {isAdmin && pending.length > 0 && (
              <section className="space-y-4">
                <SectionLabel>New — Commit to Knowledge Base</SectionLabel>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {pending.map((d) => {
                    const isCommitting = committingId === d.id;
                    const isRejecting = rejectingId === d.id;
                    return (
                      <motion.div
                        key={d.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                      >
                        <SpotlightCard className="glass-faint rounded-2xl h-full flex flex-col">
                          <div className="p-4 flex-1 flex flex-col">
                            <div className="flex items-center justify-between mb-2.5">
                              <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">
                                {d.file_type}
                              </span>
                              <Badge tone="amber">
                                <Clock className="w-3 h-3 inline -mt-px mr-1" /> pending
                              </Badge>
                            </div>
                            <h3 className="text-sm font-semibold text-white truncate" title={d.original_filename}>
                              {d.original_filename}
                            </h3>
                            <p className="text-[11.5px] text-zinc-500 mt-1">
                              shared by <span className="text-zinc-300 font-medium">{d.sharer_display || d.sharer_username}</span> · {fmtSize(d.size_bytes)}
                            </p>
                            {d.note && (
                              <p className="text-[12px] text-zinc-400 mt-2 line-clamp-2 italic">&ldquo;{d.note}&rdquo;</p>
                            )}
                            <p className="text-[10.5px] text-zinc-600 mt-auto pt-3 font-mono">
                              {d.shared_at
                                ? new Date(d.shared_at).toLocaleString(undefined, {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  })
                                : ''}
                            </p>
                          </div>
                          <div className="grid grid-cols-3 border-t border-white/[0.06]">
                            <button
                              onClick={() => setPreviewId(previewId === d.id ? null : d.id)}
                              className="py-2.5 text-[12px] font-semibold text-sky-300 hover:text-white flex items-center justify-center gap-1.5 transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5" /> Preview
                            </button>
                            <button
                              onClick={() => void commit(d.id)}
                              disabled={isCommitting}
                              className="py-2.5 text-[12px] font-semibold text-emerald-300 hover:text-white flex items-center justify-center gap-1.5 border-x border-white/[0.06] transition-colors disabled:opacity-50"
                            >
                              {isCommitting ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <>
                                  <Check className="w-3.5 h-3.5" /> Commit
                                </>
                              )}
                            </button>
                            <button
                              onClick={() => void reject(d.id)}
                              disabled={isRejecting}
                              className="py-2.5 text-[12px] font-semibold text-rose-300 hover:text-white flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                            >
                              {isRejecting ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <>
                                  <X className="w-3.5 h-3.5" /> Reject
                                </>
                              )}
                            </button>
                          </div>
                          {previewId === d.id && (
                            <div className="border-t border-white/[0.06]">
                              <iframe
                                src={ChatAPI.getSharedDocPreviewUrl(d.id)}
                                className="w-full h-[320px]"
                                sandbox="allow-same-origin allow-scripts"
                                title={`Preview ${d.original_filename}`}
                              />
                            </div>
                          )}
                        </SpotlightCard>
                      </motion.div>
                    );
                  })}
                </div>
              </section>
            )}

            {!isAdmin && pending.length > 0 && (
              <section className="space-y-4">
                <SectionLabel>Pending Review</SectionLabel>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {pending.map((d) => (
                    <SpotlightCard key={d.id} className="glass-faint rounded-2xl">
                      <div className="p-4 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <Badge tone="amber">
                            <Clock className="w-3 h-3 inline -mt-px mr-1" /> pending
                          </Badge>
                          <span className="text-[10.5px] text-zinc-600 font-mono">
                            {d.shared_at
                              ? new Date(d.shared_at).toLocaleString(undefined, {
                                  month: 'short',
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })
                              : ''}
                          </span>
                        </div>
                        <h3 className="text-sm font-semibold text-white truncate">{d.original_filename}</h3>
                        {d.note && <p className="text-[12px] text-zinc-400 italic line-clamp-2">&ldquo;{d.note}&rdquo;</p>}
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            onClick={() => window.open(ChatAPI.getSharedDocPreviewUrl(d.id), '_blank', 'noopener')}
                            className="px-3 py-1.5 rounded-lg text-[12px] font-medium glass-faint text-zinc-300 hover:text-white flex items-center gap-1.5 transition-colors"
                          >
                            <Eye className="w-3.5 h-3.5" /> Preview
                          </button>
                          <button
                            onClick={() => void remove(d.id)}
                            disabled={deleteId === d.id}
                            className="px-3 py-1.5 rounded-lg text-[12px] font-medium text-rose-400 hover:text-white hover:bg-rose-500/[0.06] flex items-center gap-1.5 transition-colors disabled:opacity-50"
                          >
                            {deleteId === d.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <>
                                <Trash2 className="w-3.5 h-3.5" /> Remove
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </SpotlightCard>
                  ))}
                </div>
              </section>
            )}

            {others.length > 0 && (
              <section className="space-y-4">
                <SectionLabel>{isAdmin ? 'All Processed' : 'My History'}</SectionLabel>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {others.map((d) => {
                    const Icon = STATUS_ICON[d.status] ?? Clock;
                    return (
                      <SpotlightCard key={d.id} className="glass-faint rounded-2xl">
                        <div className="p-4 space-y-2.5">
                          <div className="flex items-center justify-between">
                            <Badge tone={STATUS_TONE[d.status] ?? 'amber'}>
                              <Icon className="w-3 h-3 inline -mt-px mr-1" /> {d.status}
                            </Badge>
                            <span className="text-[10.5px] text-zinc-600 font-mono">
                              {d.committed_at
                                ? new Date(d.committed_at).toLocaleString(undefined, {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  })
                                : d.shared_at
                                  ? new Date(d.shared_at).toLocaleString(undefined, {
                                      month: 'short',
                                      day: 'numeric',
                                      hour: '2-digit',
                                      minute: '2-digit',
                                    })
                                  : ''}
                            </span>
                          </div>
                          <h3 className="text-sm font-semibold text-white truncate">{d.original_filename}</h3>
                          {d.status === 'committed' && d.doc_id && (
                            <p className="text-[10.5px] text-emerald-400/80 font-mono">doc: {d.doc_id.slice(0, 16)}…</p>
                          )}
                          <div className="flex items-center gap-2 pt-1">
                            <button
                              onClick={() => window.open(ChatAPI.getSharedDocPreviewUrl(d.id), '_blank', 'noopener')}
                              className="px-3 py-1.5 rounded-lg text-[12px] font-medium glass-faint text-zinc-300 hover:text-white flex items-center gap-1.5 transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5" /> Preview
                            </button>
                            {d.status === 'pending' && (
                              <button
                                onClick={() => void remove(d.id)}
                                disabled={deleteId === d.id}
                                className="px-3 py-1.5 rounded-lg text-[12px] font-medium text-rose-400 hover:text-white hover:bg-rose-500/[0.06] flex items-center gap-1.5 transition-colors disabled:opacity-50"
                              >
                                {deleteId === d.id ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <>
                                    <Trash2 className="w-3.5 h-3.5" /> Remove
                                  </>
                                )}
                              </button>
                            )}
                          </div>
                        </div>
                      </SpotlightCard>
                    );
                  })}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}