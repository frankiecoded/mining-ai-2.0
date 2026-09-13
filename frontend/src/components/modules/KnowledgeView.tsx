import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Database, UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2, X,
  Search, Satellite, Eye, Map, Layers, BookOpen, ChevronRight,
  Hash, Calendar, HardDrive, Tag, Globe, Cpu, Beaker, Mountain, Upload,
  BarChart3, FileImage, FileSpreadsheet, FileCode, RefreshCw, Download,
  ArrowLeft, Sparkles, Cog, FolderOpen, Maximize2, ExternalLink,
} from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { SectionLabel } from '../ui/SectionLabel';
import { DocumentBrowser } from './DocumentBrowser';
import type {
  KnowledgeDocument,
  KnowledgeStats,
  DocumentReadResult,
} from '../../types';

type Tab = 'documents' | 'satellite' | 'reader' | 'browser';

const CATEGORIES = ['All', 'Geological', 'Operational', 'Environmental', 'Financial', 'Satellite', 'Other'] as const;

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function fileTypeIcon(type: string) {
  const t = type.toLowerCase();
  if (t.includes('pdf')) return <FileText className="w-5 h-5 text-rose-400" />;
  if (t.includes('doc') || t.includes('word')) return <FileText className="w-5 h-5 text-sky-400" />;
  if (t.includes('xls') || t.includes('sheet') || t.includes('csv')) return <FileSpreadsheet className="w-5 h-5 text-emerald-400" />;
  if (t.includes('png') || t.includes('jpg') || t.includes('jpeg') || t.includes('tif') || t.includes('geotiff') || t.includes('image')) return <FileImage className="w-5 h-5 text-violet-400" />;
  if (t.includes('json') || t.includes('xml') || t.includes('geojson')) return <FileCode className="w-5 h-5 text-amber-400" />;
  return <FileText className="w-5 h-5 text-zinc-400" />;
}

function fileTypeColor(type: string): string {
  const t = type.toLowerCase();
  if (t.includes('pdf')) return 'bg-rose-400/10 text-rose-300';
  if (t.includes('doc') || t.includes('word')) return 'bg-sky-400/10 text-sky-300';
  if (t.includes('xls') || t.includes('sheet') || t.includes('csv')) return 'bg-emerald-400/10 text-emerald-300';
  if (t.includes('png') || t.includes('jpg') || t.includes('jpeg') || t.includes('tif') || t.includes('image')) return 'bg-violet-400/10 text-violet-300';
  if (t.includes('json') || t.includes('xml')) return 'bg-amber-400/10 text-amber-300';
  return 'bg-zinc-400/10 text-zinc-300';
}

function categoryColor(cat: string): string {
  const c = cat.toLowerCase();
  if (c === 'geological') return 'bg-emerald-400/10 text-emerald-300 border-emerald-400/20';
  if (c === 'operational') return 'bg-sky-400/10 text-sky-300 border-sky-400/20';
  if (c === 'environmental') return 'bg-amber-400/10 text-amber-300 border-amber-400/20';
  if (c === 'financial') return 'bg-rose-400/10 text-rose-300 border-rose-400/20';
  if (c === 'satellite') return 'bg-violet-400/10 text-violet-300 border-violet-400/20';
  return 'bg-zinc-400/10 text-zinc-300 border-zinc-400/20';
}

const tabItems: { id: Tab; label: string; icon: typeof Database }[] = [
  { id: 'documents', label: 'Documents', icon: Database },
  { id: 'browser', label: 'Browse Files', icon: FolderOpen },
  { id: 'satellite', label: 'Satellite Intelligence', icon: Satellite },
  { id: 'reader', label: 'Document Reader', icon: BookOpen },
];

/* ──────────────────────────── Document Tab ──────────────────────────── */
function DocumentsTab({
  onSelectDocument,
}: {
  onSelectDocument: (doc: KnowledgeDocument) => void;
}) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Array<{ document: KnowledgeDocument; score: number }> | null>(null);
  const [searching, setSearching] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('All');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [docsRes, statsRes] = await Promise.all([
        ChatAPI.fetchKnowledgeDocuments(),
        ChatAPI.fetchKnowledgeStats(),
      ]);
      setDocuments(docsRes.documents || []);
      setStats(statsRes.stats || null);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    setSearching(true);
    try {
      const res = await ChatAPI.searchKnowledge(searchQuery, activeCategory === 'All' ? undefined : activeCategory);
      setSearchResults(res.results || []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => { if (searchQuery.trim()) handleSearch(); else setSearchResults(null); }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, activeCategory]);

  const pick = (f: File | null) => { if (!f) return; setFile(f); setStatus('idle'); };

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setStatus('idle');
    try {
      const res = await ChatAPI.uploadDocument(file);
      setStatus('success');
      setMessage(`Indexed ${res.chunks_indexed} chunks from ${res.filename}.`);
      setFile(null);
      loadData();
    } catch (e) {
      setStatus('error');
      setMessage(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const displayDocs = searchResults
    ? searchResults.map((r) => r.document)
    : activeCategory === 'All'
      ? documents
      : documents.filter((d) => d.category?.toLowerCase() === activeCategory.toLowerCase());

  const recentDocs = documents.slice(0, 5);

  const categoryBreakdown = stats?.by_category || {};
  const typeBreakdown = stats?.by_type || {};

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <section className="space-y-4">
        <SectionLabel>Document Ingestion</SectionLabel>
        <input
          type="file"
          ref={fileRef}
          className="hidden"
          accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg,.tif,.tiff,.geotiff,.json,.xml,.geojson"
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
        <motion.div
          animate={{ scale: dragging ? 1.01 : 1, borderColor: dragging ? 'rgba(91,156,255,0.6)' : undefined }}
          transition={{ type: 'spring', stiffness: 300, damping: 24 }}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0] ?? null); }}
          className={`glass rounded-3xl p-8 flex flex-col items-center text-center cursor-pointer transition-colors duration-200 border-2 border-dashed ${
            dragging ? 'border-sky-400/60' : 'border-white/[0.12] hover:border-white/[0.22]'
          }`}
          onClick={() => fileRef.current?.click()}
        >
          {!file ? (
            <>
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500/20 to-violet-600/20 flex items-center justify-center mb-4">
                <UploadCloud className="w-7 h-7 text-sky-300" />
              </div>
              <h3 className="text-[15px] font-semibold text-white">Drop any file here</h3>
              <p className="text-xs text-zinc-500 mt-1.5">
                PDF, DOCX, XLSX, CSV, TXT, PNG, JPG, TIF, GeoTIFF, JSON &middot; up to 50 MB
              </p>
            </>
          ) : (
            <div className="w-full max-w-md flex items-center gap-3.5 glass-faint rounded-2xl p-4 text-left" onClick={(e) => e.stopPropagation()}>
              <div className={`w-11 h-11 rounded-xl inline-flex items-center justify-center shrink-0 ${fileTypeColor(file.name)}`}>
                {fileTypeIcon(file.name)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-white truncate">{file.name}</div>
                <div className="text-[11px] text-zinc-500 font-mono mt-0.5">{formatBytes(file.size)}</div>
              </div>
              <button onClick={() => setFile(null)} className="text-zinc-500 hover:text-white p-1.5 shrink-0" aria-label="Remove">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
          {file && (
            <button
              onClick={(e) => { e.stopPropagation(); void upload(); }}
              disabled={uploading}
              className="btn-primary rounded-full px-6 py-2.5 text-sm font-semibold flex items-center gap-2 mt-5"
            >
              {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {uploading ? 'Indexing…' : 'Upload & Index'}
            </button>
          )}
        </motion.div>
        <AnimatePresence>
          {status !== 'idle' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={`flex items-start gap-2.5 rounded-2xl p-4 text-[13px] ${
                status === 'success' ? 'bg-emerald-400/10 text-emerald-200' : 'bg-rose-400/10 text-rose-200'
              }`}
            >
              {status === 'success' ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" /> : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />}
              {message}
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* Stats Bar */}
      {stats && (
        <section className="glass rounded-2xl p-5">
          <SectionLabel>Collection Overview</SectionLabel>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
            <div className="glass-faint rounded-xl p-3 text-center">
              <div className="text-2xl font-bold text-white break-words">{stats.total_documents}</div>
              <div className="text-[11px] text-zinc-500 mt-0.5">Documents</div>
            </div>
            <div className="glass-faint rounded-xl p-3 text-center">
              <div className="text-2xl font-bold text-white break-words">{formatBytes(stats.total_size_bytes)}</div>
              <div className="text-[11px] text-zinc-500 mt-0.5">Total Size</div>
            </div>
            <div className="glass-faint rounded-xl p-3 text-center">
              <div className="text-2xl font-bold text-white break-words">{stats.total_words?.toLocaleString() || '0'}</div>
              <div className="text-[11px] text-zinc-500 mt-0.5">Total Words</div>
            </div>
            <div className="glass-faint rounded-xl p-3 text-center">
              <div className="text-2xl font-bold text-white break-words">{Object.keys(stats.by_category || {}).length}</div>
              <div className="text-[11px] text-zinc-500 mt-0.5">Categories</div>
            </div>
          </div>
          {(Object.keys(typeBreakdown).length > 0 || Object.keys(categoryBreakdown).length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              {Object.keys(typeBreakdown).length > 0 && (
                <div>
                  <div className="text-[11px] text-zinc-500 mb-2 uppercase tracking-wider font-semibold">By File Type</div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(typeBreakdown).map(([type, count]) => (
                      <span key={type} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium ${fileTypeColor(type)}`}>
                        {fileTypeIcon(type)}
                        {type.toUpperCase()} · {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {Object.keys(categoryBreakdown).length > 0 && (
                <div>
                  <div className="text-[11px] text-zinc-500 mb-2 uppercase tracking-wider font-semibold">By Category</div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(categoryBreakdown).map(([cat, count]) => (
                      <span key={cat} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border ${categoryColor(cat)}`}>
                        {cat} · {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* Search & Filters */}
      <section className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents…"
              className="glass-input w-full pl-10 pr-4 py-2.5 rounded-xl text-sm text-white placeholder:text-zinc-600"
            />
          </div>
          {searching && <Loader2 className="w-4 h-4 text-sky-400 animate-spin" />}
          <button
            onClick={loadData}
            className="glass-faint rounded-xl p-2.5 text-zinc-400 hover:text-white transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3.5 py-2.5 rounded-lg text-[12px] font-medium transition-all min-h-[40px] ${
                activeCategory === cat
                  ? 'bg-sky-400/15 text-sky-300 border border-sky-400/30'
                  : 'glass-faint text-zinc-400 hover:text-zinc-200 border border-transparent'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </section>

      {/* Recent Documents */}
      {!searchQuery && recentDocs.length > 0 && activeCategory === 'All' && (
        <section className="space-y-3">
          <SectionLabel>Recent Uploads</SectionLabel>
          <div className="space-y-2">
            {recentDocs.map((doc) => (
              <motion.div
                key={doc.doc_id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-faint rounded-xl p-3.5 flex items-center gap-3 cursor-pointer hover:bg-white/[0.04] transition-colors"
                onClick={() => onSelectDocument(doc)}
              >
                <div className={`w-10 h-10 rounded-lg inline-flex items-center justify-center shrink-0 ${fileTypeColor(doc.file_type)}`}>
                  {fileTypeIcon(doc.file_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white truncate">{doc.filename}</div>
                  <div className="text-[11px] text-zinc-500 flex items-center gap-2 mt-0.5">
                    <span className="flex items-center gap-1"><HardDrive className="w-3 h-3" />{formatBytes(doc.file_size)}</span>
                    <span>·</span>
                    <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${categoryColor(doc.category || 'Other')}`}>
                  {doc.category || 'Other'}
                </span>
                <ChevronRight className="w-4 h-4 text-zinc-600" />
              </motion.div>
            ))}
          </div>
        </section>
      )}

      {/* All Documents Grid */}
      <section className="space-y-3">
        <SectionLabel>
          {searchQuery ? `Search Results · ${displayDocs.length}` : `All Documents · ${displayDocs.length}`}
        </SectionLabel>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
          </div>
        ) : displayDocs.length === 0 ? (
          <div className="glass rounded-2xl p-12 text-center">
            <Database className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
            <p className="text-sm text-zinc-500">No documents found. Upload files to get started.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <AnimatePresence mode="popLayout">
              {displayDocs.map((doc) => (
                <motion.div
                  key={doc.doc_id}
                  layout
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96 }}
                  className="glass-faint rounded-2xl p-4 cursor-pointer hover:bg-white/[0.04] transition-colors group"
                  onClick={() => onSelectDocument(doc)}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-11 h-11 rounded-xl inline-flex items-center justify-center shrink-0 ${fileTypeColor(doc.file_type)}`}>
                      {fileTypeIcon(doc.file_type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-white truncate group-hover:text-sky-200 transition-colors">
                        {doc.filename}
                      </div>
                      <div className="text-[11px] text-zinc-500 mt-0.5 line-clamp-1">
                        {doc.description || doc.content_summary || 'No description'}
                      </div>
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${categoryColor(doc.category || 'Other')}`}>
                          {doc.category || 'Other'}
                        </span>
                        <span className="text-[10px] text-zinc-600 flex items-center gap-1">
                          <HardDrive className="w-3 h-3" />{formatBytes(doc.file_size)}
                        </span>
                        <span className="text-[10px] text-zinc-600 flex items-center gap-1">
                          <Calendar className="w-3 h-3" />{new Date(doc.created_at).toLocaleDateString()}
                        </span>
                        {doc.word_count > 0 && (
                          <span className="text-[10px] text-zinc-600 flex items-center gap-1">
                            <Hash className="w-3 h-3" />{doc.word_count.toLocaleString()} words
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </section>
    </div>
  );
}

function parseBandInputs(inputs: Record<string, string>): {
  flat: Record<string, number[]>;
  grid: Record<string, number[][]>;
  anyGrid: boolean;
} {
  const flat: Record<string, number[]> = {};
  const grid: Record<string, number[][]> = {};
  let anyGrid = false;
  for (const [key, val] of Object.entries(inputs)) {
    if (!val.trim()) continue;
    const rows = val
      .split(';')
      .map((r) => r.split(',').map((s) => parseFloat(s.trim())).filter((n) => !isNaN(n)))
      .filter((r) => r.length > 0);
    if (rows.length === 0) continue;
    if (rows.length > 1 || rows.some((r) => r.length > 1)) {
      grid[key] = rows;
      anyGrid = true;
    } else {
      const row = rows[0];
      if (row.length > 0) flat[key] = row;
    }
  }
  return { flat, grid, anyGrid };
}

/* ──────────────────────────── Satellite Tab ──────────────────────────── */
function SatelliteTab() {
  const [bands, setBands] = useState<Record<string, string>>({
    B02: '', B03: '', B04: '', B05: '', B06: '', B07: '', B08: '', B8A: '', B11: '', B12: '',
  });
  const [demInput, setDemInput] = useState('');
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [previewUrl, setPreviewUrl] = useState('');
  const [previewIndexUrl, setPreviewIndexUrl] = useState('');

  const handleAnalyze = async () => {
    setRunning(true);
    setError('');
    setResults(null);
    setPreviewUrl('');
    setPreviewIndexUrl('');
    try {
      const { flat, grid, anyGrid } = parseBandInputs(bands);
      let parsedDem: number[][] | undefined;
      if (demInput.trim()) {
        try {
          parsedDem = JSON.parse(demInput);
        } catch {
          setError('Invalid DEM JSON format');
          setRunning(false);
          return;
        }
      }
      const res = await ChatAPI.fullSatelliteAnalysis(flat, parsedDem);
      setResults(res.results as Record<string, unknown>);

      if (anyGrid) {
        const base = import.meta.env.VITE_API_URL || '';
        const dims = grid.B04 ?? grid.B08 ?? grid.B02 ?? grid.B03;
        if (grid.B02 && grid.B03 && grid.B04) {
          try {
            const c = await ChatAPI.renderComposite(
              { B02: grid.B02, B03: grid.B03, B04: grid.B04 },
              'true_color',
            );
            setPreviewUrl(`${base}${c.file_url}`);
          } catch { /* render failures shouldn't block analysis results */ }
        }
        if (grid.B04 && grid.B08) {
          try {
            const idx = await ChatAPI.renderIndex({ B04: grid.B04, B08: grid.B08 }, 'ndvi');
            setPreviewIndexUrl(`${base}${idx.file_url}`);
          } catch { /* render failures shouldn't block analysis results */ }
        }
        if (!grid.B02 && !grid.B03 && !grid.B04 && !grid.B08 && dims) {
          const lastKey = Object.keys(grid)[Object.keys(grid).length - 1];
          if (lastKey) {
            try {
              const gray = await ChatAPI.renderComposite({ gray: grid[lastKey] }, 'true_color');
              setPreviewUrl(`${base}${gray.file_url}`);
            } catch { /* ignore */ }
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
    } finally {
      setRunning(false);
    }
  };

  const bandLabels: Record<string, string> = {
    B02: 'Blue (490nm)', B03: 'Green (560nm)', B04: 'Red (665nm)', B05: 'Red Edge 1 (705nm)',
    B06: 'Red Edge 2 (740nm)', B07: 'Red Edge 3 (783nm)', B08: 'NIR (842nm)', B8A: 'NIR Narrow (865nm)',
    B11: 'SWIR 1 (1610nm)', B12: 'SWIR 2 (1930nm)',
  };

  const r = results && typeof results === 'object' ? (results as Record<string, unknown>) : undefined;
  const pickSection = (keys: string[]): Record<string, unknown> | undefined => {
    for (const k of keys) {
      const v = r?.[k];
      if (v && typeof v === 'object') return v as Record<string, unknown>;
    }
    return undefined;
  };
  const spectralResults = pickSection(['spectral', 'spectral_assessment']);
  const terrainResults = pickSection(['terrain', 'terrain_analysis']);
  const featureResults = pickSection(['features', 'feature_extraction']);
  const annotationsResults = pickSection(['annotations']);
  const reportText = r?.report as string | Record<string, unknown> | undefined;

  return (
    <div className="space-y-6">
      {/* Band Input */}
      <section className="space-y-4">
        <SectionLabel>Spectral Band Input</SectionLabel>
        <div className="glass rounded-2xl p-5 space-y-4">
          <p className="text-xs text-zinc-500">
                Enter reflectance values per band. Single pixel: comma-separated (e.g. <code className="text-sky-300/80 font-mono">0.1, 0.2, 0.3</code>).
                Multiple pixels: separate rows with <code className="text-sky-300/80 font-mono">;</code> to also render an image preview.
              </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(bandLabels).map(([band, label]) => (
              <div key={band} className="glass-faint rounded-xl p-3">
                <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider">{band}</label>
                <div className="text-[10px] text-zinc-600 mb-1.5">{label}</div>
                <input
                  type="text"
                  value={bands[band]}
                  onChange={(e) => setBands((prev) => ({ ...prev, [band]: e.target.value }))}
                  placeholder="e.g. 0.10, 0.12, 0.15 ; 0.11, 0.13, 0.16"
                  className="glass-input w-full px-3 py-1.5 rounded-lg text-xs text-white placeholder:text-zinc-700"
                />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* DEM Input */}
      <section className="space-y-4">
        <SectionLabel>Digital Elevation Model (Optional)</SectionLabel>
        <div className="glass rounded-2xl p-5">
          <textarea
            value={demInput}
            onChange={(e) => setDemInput(e.target.value)}
            placeholder='Paste DEM as JSON array, e.g. [[1200, 1250], [1180, 1220]]'
            rows={4}
            className="glass-input w-full px-4 py-3 rounded-xl text-xs text-white placeholder:text-zinc-700 font-mono resize-y"
          />
        </div>
      </section>

      {/* Run Button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleAnalyze}
          disabled={running}
          className="btn-primary rounded-full px-6 py-2.5 text-sm font-semibold flex items-center gap-2"
        >
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Satellite className="w-4 h-4" />}
          {running ? 'Analyzing…' : 'Run Full Analysis'}
        </button>
        {error && (
          <div className="flex items-center gap-2 text-rose-300 text-[13px]">
            <AlertCircle className="w-4 h-4" />{error}
          </div>
        )}
      </div>

      {/* Results */}
      {results && (
        <div className="space-y-4">
          <SectionLabel>Analysis Results</SectionLabel>

          {(previewUrl || previewIndexUrl) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {previewUrl && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-2xl p-5 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <Satellite className="w-4 h-4 text-sky-400" />True Color Preview
                  </div>
                  <div className="rounded-xl overflow-hidden bg-[#0d0d1a] border border-white/[0.06]">
                    <img src={previewUrl} alt="True color composite" className="w-full max-h-[380px] object-contain" />
                  </div>
                </motion.div>
              )}
              {previewIndexUrl && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass rounded-2xl p-5 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <Map className="w-4 h-4 text-emerald-400" />NDVI Index Preview
                  </div>
                  <div className="rounded-xl overflow-hidden bg-[#0d0d1a] border border-white/[0.06]">
                    <img src={previewIndexUrl} alt="NDVI index" className="w-full max-h-[380px] object-contain" />
                  </div>
                </motion.div>
              )}
            </div>
          )}

          {spectralResults && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Sparkles className="w-4 h-4 text-sky-400" />Spectral Assessment
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {'alteration_score' in spectralResults && (
                  <div className="glass-faint rounded-xl p-3 text-center">
                    <div className="text-xl font-bold text-sky-300">{String(spectralResults.alteration_score)}</div>
                    <div className="text-[10px] text-zinc-500">Alteration Score</div>
                  </div>
                )}
                {'confidence' in spectralResults && (
                  <div className="glass-faint rounded-xl p-3 text-center">
                    <div className="text-xl font-bold text-emerald-300">{String(spectralResults.confidence)}</div>
                    <div className="text-[10px] text-zinc-500">Confidence</div>
                  </div>
                )}
                {'indicators' in spectralResults && Array.isArray(spectralResults.indicators) && (
                  <div className="glass-faint rounded-xl p-3 md:col-span-3">
                    <div className="text-[11px] text-zinc-500 mb-2">Indicators</div>
                    <div className="flex flex-wrap gap-1.5">
                      {(spectralResults.indicators as string[]).map((ind, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-sky-400/10 text-sky-300 text-[11px]">{ind}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {terrainResults && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Mountain className="w-4 h-4 text-emerald-400" />Terrain Analysis
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {'slope_degrees' in terrainResults && (
                  <div className="glass-faint rounded-xl p-3 text-center">
                    <div className="text-xl font-bold text-emerald-300">{String(terrainResults.slope_degrees)}</div>
                    <div className="text-[10px] text-zinc-500">Slope (°)</div>
                  </div>
                )}
                {'zones' in terrainResults && Array.isArray(terrainResults.zones) && (
                  <div className="glass-faint rounded-xl p-3 md:col-span-2">
                    <div className="text-[11px] text-zinc-500 mb-2">Terrain Zones</div>
                    <div className="flex flex-wrap gap-1.5">
                      {(terrainResults.zones as string[]).map((z, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-emerald-400/10 text-emerald-300 text-[11px]">{z}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {featureResults && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Map className="w-4 h-4 text-violet-400" />Feature Extraction
              </div>
              <div className="grid grid-cols-2 gap-3">
                {'lineaments' in featureResults && Array.isArray(featureResults.lineaments) && (
                  <div className="glass-faint rounded-xl p-3">
                    <div className="text-[11px] text-zinc-500 mb-2">Lineaments</div>
                    <div className="text-xl font-bold text-violet-300">{(featureResults.lineaments as unknown[]).length}</div>
                  </div>
                )}
                {'targets' in featureResults && Array.isArray(featureResults.targets) && (
                  <div className="glass-faint rounded-xl p-3">
                    <div className="text-[11px] text-zinc-500 mb-2">Target Areas</div>
                    <div className="text-xl font-bold text-violet-300">{(featureResults.targets as unknown[]).length}</div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {reportText && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Sparkles className="w-4 h-4 text-amber-400" />Exploration Report
              </div>
              <pre className="glass-faint rounded-xl p-4 text-[12px] text-zinc-300 overflow-x-auto font-sans whitespace-pre-wrap max-h-96 overflow-y-auto thin-scrollbar leading-relaxed">
                {typeof reportText === 'string' ? reportText : JSON.stringify(reportText, null, 2)}
              </pre>
            </motion.div>
          )}

          {annotationsResults && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Layers className="w-4 h-4 text-amber-400" />Auto-Generated Annotations
              </div>
              <pre className="glass-faint rounded-xl p-4 text-[11px] text-zinc-400 overflow-x-auto font-mono max-h-64 overflow-y-auto thin-scrollbar">
                {JSON.stringify(annotationsResults, null, 2)}
              </pre>
            </motion.div>
          )}
        </div>
      )}
    </div>
  );
}

/* ──────────────────────────── Reader Tab ──────────────────────────── */
function previewableDoc(doc: KnowledgeDocument | null): { kind: 'image' | 'pdf' | null; url: string } {
  if (!doc) return { kind: null, url: '' };
  const stored = doc.stored_filename || doc.filename || '';
  const ext = (doc.file_type || '').toLowerCase() || ((stored.split('.').pop() || '').toLowerCase());
  const base = import.meta.env.VITE_API_URL || '';
  const url = stored ? `${base}/files/${encodeURIComponent(stored)}` : '';
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) return { kind: 'image', url };
  if (ext === 'pdf') return { kind: 'pdf', url };
  return { kind: null, url: '' };
}

function ReaderTab({
  selectedDoc,
  onBack,
}: {
  selectedDoc: KnowledgeDocument | null;
  onBack: () => void;
}) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [activeDoc, setActiveDoc] = useState<KnowledgeDocument | null>(selectedDoc);
  const [readResult, setReadResult] = useState<DocumentReadResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('');

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPreviewOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const openLightbox = (url: string) => {
    setPreviewUrl(url);
    setPreviewOpen(true);
  };

  useEffect(() => {
    if (selectedDoc) setActiveDoc(selectedDoc);
  }, [selectedDoc]);

  useEffect(() => {
    ChatAPI.fetchKnowledgeDocuments()
      .then((res) => setDocuments(res.documents || []))
      .catch(() => {})
      .finally(() => setLoadingDocs(false));
  }, []);

  const loadDocument = async (doc: KnowledgeDocument) => {
    setActiveDoc(doc);
    setReadResult(null);
    setLoading(true);
    try {
      const res = await ChatAPI.readDocument(doc.doc_id);
      setReadResult(res.result || null);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  const loadDeepUnderstand = async (doc: KnowledgeDocument) => {
    setLoading(true);
    try {
      const res = await ChatAPI.understandDocument(doc.doc_id);
      setReadResult(res.result || null);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  const exportSummary = (doc: KnowledgeDocument, res: DocumentReadResult) => {
    const lines: string[] = [];
    lines.push(`# ${res.filename || doc.filename || 'Document Summary'}`);
    lines.push('');
    lines.push(`- Category: ${doc.category || 'Other'}`);
    lines.push(`- Type: ${res.file_type || doc.file_type || 'unknown'}`);
    lines.push(`- Words: ${res.word_count?.toLocaleString() ?? 0} | Pages: ${res.page_count || '—'} | Mining relevance: ${(res.mining_relevance * 100).toFixed(0)}%`);
    lines.push(`- Uploaded: ${doc.created_at ? new Date(doc.created_at).toDateString() : '—'}`);
    lines.push('');
    if (res.summary) { lines.push('## Summary'); lines.push(res.summary); lines.push(''); }
    if (res.key_findings?.length) {
      lines.push('## Key Findings');
      res.key_findings.forEach((f, i) => lines.push(`${i + 1}. ${f}`));
      lines.push('');
    }
    if (res.entities) {
      const hasEntities = Object.values(res.entities).some((arr) => arr.length > 0);
      if (hasEntities) {
        lines.push('## Extracted Entities');
        if (res.entities.minerals?.length) lines.push(`- Minerals: ${res.entities.minerals.join(', ')}`);
        if (res.entities.equipment?.length) lines.push(`- Equipment: ${res.entities.equipment.join(', ')}`);
        if (res.entities.locations?.length) lines.push(`- Locations: ${res.entities.locations.join(', ')}`);
        if (res.entities.chemicals?.length) lines.push(`- Chemicals: ${res.entities.chemicals.join(', ')}`);
        if (res.entities.processes?.length) lines.push(`- Processes: ${res.entities.processes.join(', ')}`);
        lines.push('');
      }
    }
    if (res.key_terms?.length) { lines.push('## Key Terms'); lines.push(res.key_terms.join(', ')); lines.push(''); }
    if (res.sections?.length) {
      lines.push('## Sections');
      res.sections.forEach((s) => lines.push(`${'#'.repeat(Math.max(1, s.level || 2))} ${s.heading}\n${s.content}`));
      lines.push('');
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(doc.filename || 'document').replace(/[\\/:*?"<>|]+/g, '_')}_summary.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 200);
  };

  useEffect(() => {
    if (activeDoc) loadDocument(activeDoc);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDoc?.doc_id]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        {selectedDoc && (
          <button onClick={onBack} className="glass-faint rounded-lg p-2 text-zinc-400 hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
        )}
        <SectionLabel>Document Reader</SectionLabel>
      </div>

      {/* Document Selector */}
      <div className="glass rounded-2xl p-4">
        <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider block mb-2">Select Document</label>
        <select
          value={activeDoc?.doc_id || ''}
          onChange={(e) => {
            const doc = documents.find((d) => d.doc_id === e.target.value);
            if (doc) setActiveDoc(doc);
          }}
          className="glass-input w-full px-4 py-2.5 rounded-xl text-sm text-white"
        >
          <option value="" disabled>{loadingDocs ? 'Loading…' : 'Choose a document'}</option>
          {documents.map((doc) => (
            <option key={doc.doc_id} value={doc.doc_id}>{doc.filename}</option>
          ))}
        </select>
      </div>

      {!activeDoc && (
        <div className="glass rounded-2xl p-16 text-center">
          <BookOpen className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
          <p className="text-sm text-zinc-500">Select a document to read its contents and extracted intelligence.</p>
        </div>
      )}

      {activeDoc && loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
        </div>
      )}

      {activeDoc && readResult && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Full Text */}
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <FileText className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-semibold text-white">{readResult.filename}</h3>
              </div>

              {previewableDoc(activeDoc).kind === 'image' && (
                <div
                  className="relative rounded-xl overflow-hidden mb-4 bg-[#0d0d1a] border border-white/[0.06] group cursor-zoom-in"
                  onClick={() => openLightbox(previewableDoc(activeDoc).url)}
                >
                  <img
                    src={previewableDoc(activeDoc).url}
                    alt={activeDoc.filename}
                    className="w-full max-h-[520px] object-contain"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                  />
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                    <span className="flex items-center gap-2 text-xs font-medium text-white bg-black/60 border border-white/10 rounded-full px-3 py-1.5 pointer-events-none">
                      <Maximize2 className="w-3.5 h-3.5" /> View full size
                    </span>
                  </div>
                </div>
              )}
              {previewableDoc(activeDoc).kind === 'pdf' && (
                <div className="rounded-xl overflow-hidden mb-4 border border-white/[0.06] h-[520px] relative">
                  <a
                    href={previewableDoc(activeDoc).url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="absolute top-2 right-2 z-10 flex items-center gap-1.5 text-xs font-medium text-white bg-black/60 border border-white/10 rounded-full px-3 py-1.5 hover:bg-black/80 transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" /> Open PDF
                  </a>
                  <iframe
                    src={previewableDoc(activeDoc).url}
                    title={activeDoc.filename}
                    className="w-full h-full border-0 bg-[#0d0d1a]"
                  />
                </div>
              )}

              <div className="glass-faint rounded-xl p-5 max-h-[500px] overflow-y-auto thin-scrollbar">
                <pre className="text-[13px] text-zinc-300 whitespace-pre-wrap font-sans leading-relaxed">
                  {readResult.content_text || 'No content available.'}
                </pre>
              </div>
            </motion.div>

            {/* Summary */}
            {readResult.summary && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  <h3 className="text-sm font-semibold text-white">AI Summary</h3>
                </div>
                <p className="text-[13px] text-zinc-300 leading-relaxed">{readResult.summary}</p>
              </motion.div>
            )}

            {/* Key Findings */}
            {readResult.key_findings?.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="glass rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-3">
                  <Eye className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-semibold text-white">Key Findings</h3>
                </div>
                <ul className="space-y-2">
                  {readResult.key_findings.map((finding, i) => (
                    <li key={i} className="flex items-start gap-2 text-[13px] text-zinc-300">
                      <ChevronRight className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                      {finding}
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}

            {/* Sections */}
            {readResult.sections?.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Layers className="w-4 h-4 text-violet-400" />
                  <h3 className="text-sm font-semibold text-white">Sections</h3>
                </div>
                <div className="space-y-3">
                  {readResult.sections.map((section, i) => (
                    <div key={i} className="glass-faint rounded-xl p-4">
                      <div className={`font-semibold mb-1.5 ${
                        section.level === 1 ? 'text-base text-white' :
                        section.level === 2 ? 'text-sm text-white' :
                        'text-[13px] text-zinc-200'
                      }`}>
                        {section.heading}
                      </div>
                      <p className="text-[12px] text-zinc-400 leading-relaxed line-clamp-4">{section.content}</p>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Metadata */}
            <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <BarChart3 className="w-4 h-4 text-sky-400" />
                <h3 className="text-[12px] font-semibold text-white uppercase tracking-wider">Metadata</h3>
              </div>
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-zinc-500 flex items-center gap-1.5"><FileText className="w-3 h-3" />Type</span>
                  <span className="text-white font-medium">{readResult.file_type?.toUpperCase()}</span>
                </div>
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-zinc-500 flex items-center gap-1.5"><HardDrive className="w-3 h-3" />Size</span>
                  <span className="text-white font-medium">{formatBytes(activeDoc.file_size)}</span>
                </div>
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-zinc-500 flex items-center gap-1.5"><Hash className="w-3 h-3" />Words</span>
                  <span className="text-white font-medium">{readResult.word_count?.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-zinc-500 flex items-center gap-1.5"><BookOpen className="w-3 h-3" />Pages</span>
                  <span className="text-white font-medium">{readResult.page_count || '—'}</span>
                </div>
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-zinc-500 flex items-center gap-1.5"><Mountain className="w-3 h-3" />Relevance</span>
                  <span className={`font-medium ${readResult.mining_relevance > 0.7 ? 'text-emerald-300' : readResult.mining_relevance > 0.4 ? 'text-amber-300' : 'text-zinc-300'}`}>
                    {(readResult.mining_relevance * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-zinc-500 flex items-center gap-1.5"><Calendar className="w-3 h-3" />Uploaded</span>
                  <span className="text-white font-medium">{new Date(activeDoc.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            </motion.div>

            {/* Entities */}
            {readResult.entities && (
              <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }} className="glass rounded-2xl p-5 space-y-3">
                <div className="flex items-center gap-2 mb-1">
                  <Globe className="w-4 h-4 text-violet-400" />
                  <h3 className="text-[12px] font-semibold text-white uppercase tracking-wider">Extracted Entities</h3>
                </div>
                {readResult.entities.minerals?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Beaker className="w-3 h-3" />Minerals
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {readResult.entities.minerals.map((m, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-emerald-400/10 text-emerald-300 text-[11px] border border-emerald-400/20">{m}</span>
                      ))}
                    </div>
                  </div>
                )}
                {readResult.entities.equipment?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Cpu className="w-3 h-3" />Equipment
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {readResult.entities.equipment.map((e, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-sky-400/10 text-sky-300 text-[11px] border border-sky-400/20">{e}</span>
                      ))}
                    </div>
                  </div>
                )}
                {readResult.entities.locations?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Map className="w-3 h-3" />Locations
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {readResult.entities.locations.map((l, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-violet-400/10 text-violet-300 text-[11px] border border-violet-400/20">{l}</span>
                      ))}
                    </div>
                  </div>
                )}
                {readResult.entities.chemicals?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Beaker className="w-3 h-3" />Chemicals
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {readResult.entities.chemicals.map((c, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-amber-400/10 text-amber-300 text-[11px] border border-amber-400/20">{c}</span>
                      ))}
                    </div>
                  </div>
                )}
                {readResult.entities.processes?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Cog className="w-3 h-3" />Processes
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {readResult.entities.processes.map((p, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-rose-400/10 text-rose-300 text-[11px] border border-rose-400/20">{p}</span>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* Key Terms */}
            {readResult.key_terms?.length > 0 && (
              <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }} className="glass rounded-2xl p-5 space-y-3">
                <div className="flex items-center gap-2 mb-1">
                  <Tag className="w-4 h-4 text-amber-400" />
                  <h3 className="text-[12px] font-semibold text-white uppercase tracking-wider">Key Terms</h3>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {readResult.key_terms.map((term, i) => (
                    <span key={i} className="px-2.5 py-1 rounded-lg bg-white/[0.04] text-zinc-300 text-[11px] border border-white/[0.06]">
                      {term}
                    </span>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Actions */}
            <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }} className="glass rounded-2xl p-5 space-y-2">
              <button
                onClick={() => { if (activeDoc) void loadDeepUnderstand(activeDoc); }}
                className="w-full btn-primary rounded-xl py-2.5 text-sm font-semibold flex items-center justify-center gap-2"
              >
                <Sparkles className="w-4 h-4" />Deep Understand
              </button>
              <button
                onClick={() => { if (activeDoc && readResult) exportSummary(activeDoc, readResult); }}
                className="w-full glass-faint rounded-xl py-2.5 text-sm font-medium text-zinc-300 flex items-center justify-center gap-2 hover:text-white transition-colors"
              >
                <Download className="w-4 h-4" />Export Summary
              </button>
            </motion.div>
          </div>
        </div>
      )}

      {previewOpen && previewUrl && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 md:p-8 bg-black/85 backdrop-blur-sm" onClick={() => setPreviewOpen(false)}>
          <div className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2">
            <span className="text-xs font-medium text-zinc-300 bg-black/60 border border-white/10 rounded-full px-4 py-2 max-w-[70vw] truncate">
              {activeDoc?.filename}
            </span>
          </div>
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2">
            <a
              href={previewUrl}
              download={activeDoc?.filename}
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1.5 text-xs font-medium text-white bg-sky-500/90 hover:bg-sky-500 rounded-full px-4 py-2 transition-colors"
            >
              <Download className="w-3.5 h-3.5" /> Download
            </a>
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1.5 text-xs font-medium text-white bg-black/60 border border-white/10 hover:bg-black/80 rounded-full px-4 py-2 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Open
            </a>
            <button
              onClick={(e) => { e.stopPropagation(); setPreviewOpen(false); }}
              className="flex items-center gap-1.5 text-xs font-medium text-white bg-black/60 border border-white/10 hover:bg-black/80 rounded-full px-4 py-2 transition-colors"
            >
              <X className="w-3.5 h-3.5" /> Close
            </button>
          </div>
          <img
            src={previewUrl}
            alt={activeDoc?.filename || 'Preview'}
            className="max-w-full max-h-[82vh] object-contain rounded-xl shadow-2xl border border-white/10"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

/* ──────────────────────────── Main Component ──────────────────────────── */
export function KnowledgeView() {
  const [activeTab, setActiveTab] = useState<Tab>('documents');
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null);

  const handleSelectDocument = (doc: KnowledgeDocument) => {
    setSelectedDoc(doc);
    setActiveTab('reader');
  };

  return (
    <div className="h-full overflow-y-auto thin-scrollbar px-4 md:px-8 py-6">
      <div className="max-w-6xl mx-auto space-y-6 pb-8">
        {/* Header */}
        <header className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_10px_28px_rgba(59,110,246,0.45)]">
            <Database className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white tracking-tight">Knowledge Base</h2>
            <p className="text-[13px] text-zinc-500">Documents, satellite intelligence & document reader</p>
          </div>
        </header>

        {/* Tab Bar */}
        <div className="glass rounded-2xl p-1.5 flex gap-1">
          {tabItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-[13px] font-medium transition-all ${
                activeTab === id
                  ? 'bg-gradient-to-r from-sky-500/20 to-violet-600/20 text-white border border-sky-400/20'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span className="hidden md:inline">{label}</span>
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'documents' && <DocumentsTab onSelectDocument={handleSelectDocument} />}
            {activeTab === 'browser' && <DocumentBrowser />}
            {activeTab === 'satellite' && <SatelliteTab />}
            {activeTab === 'reader' && <ReaderTab selectedDoc={selectedDoc} onBack={() => setActiveTab('documents')} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
