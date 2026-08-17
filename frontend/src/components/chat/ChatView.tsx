import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, ArrowUpRight, BarChart3, FolderKanban, BookOpen } from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { MessageBubble } from './MessageBubble';
import { Composer } from './Composer';
import type { ChatEvent, ChatMessage } from '../../types';

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'system',
  content: 'Welcome back. Your local Intelligence Core is online — ask about mining operations, markets, geology, or upload documents to expand the knowledge base.',
};

const SUGGESTIONS: Array<{ icon: typeof BarChart3; label: string; prompt: string }> = [
  { icon: BarChart3, label: 'Current market prices', prompt: 'Give me the latest gold, silver, and platinum market prices.' },
  { icon: FolderKanban, label: 'Operations breakdown', prompt: 'Summarise the current operations queue.' },
  { icon: BookOpen, label: 'Knowledge base summary', prompt: 'What documents are in the knowledge base?' },
];

interface ChatViewProps {
  activeSessionId: string | null;
  onSessionCreated: (id: string) => void;
  onActivity: () => void;
}

export function ChatView({ activeSessionId, onSessionCreated, onActivity }: ChatViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streaming, scrollToBottom]);

  useEffect(() => {
    let cancelled = false;
    if (!activeSessionId) {
      setMessages([WELCOME]);
      return;
    }

    setLoading(true);
    void (async () => {
      try {
        const data = await ChatAPI.fetchChatHistory(activeSessionId);
        if (!cancelled) {
          const history = (data.messages ?? []).map((m, i) => ({
            ...m,
            id: m.id ?? `${activeSessionId}_${i}`,
          }));
          setMessages(history.length > 0 ? history : [WELCOME]);
        }
      } catch {
        if (!cancelled) setMessages([{ id: 'err', role: 'system', content: 'Unable to load this session. Check the backend connection.' }]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [activeSessionId]);

  const handleSend = async (text: string, file?: File) => {
    let attachmentId = '';
    let fileName = file?.name;

    // Upload the file first if attached.
    if (file) {
      try {
        const res = await ChatAPI.uploadDocument(file);
        attachmentId = res.file_id ?? '';
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'system', content: `Failed to upload ${file.name}: ${err instanceof Error ? err.message : 'Unknown error'}` },
        ]);
        return;
      }
    }

    const content = fileName ? (text ? `${text}\n\n[Attached: ${fileName}]` : `[Attached: ${fileName}]`) : text;
    if (!content.trim()) return;

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content };
    const assistantId = crypto.randomUUID();

    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);

    const sessionId = activeSessionId ?? `sess_${crypto.randomUUID().slice(0, 9)}`;
    if (!activeSessionId) onSessionCreated(sessionId);

    const pruneEmptyAssistant = () => {
      setMessages((prev) =>
        prev.filter((m) => !(m.role === 'assistant' && m.content === '' && (m.toolCalls?.length ?? 0) === 0)),
      );
    };

    try {
      await ChatAPI.streamChat(content, sessionId, (event: ChatEvent) => {
        if (event.type === 'start') {
          setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '', toolCalls: [] }]);
        } else if (event.type === 'message') {
          setMessages((prev) =>
            prev.some((m) => m.id === assistantId)
              ? prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + event.content } : m))
              : [...prev, { id: assistantId, role: 'assistant', content: event.content, toolCalls: [] }],
          );
        } else if (event.type === 'tool_call') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, toolCalls: [...(m.toolCalls ?? []), { name: event.name, args: event.args }] }
                : m,
            ),
          );
        } else if (event.type === 'error') {
          setMessages((prev) => [
            ...prev,
            { id: crypto.randomUUID(), role: 'system', content: `Connection issue: ${event.message}` },
          ]);
        }
        // 'end' handled implicitly by the finally block below.
      }, attachmentId || undefined);
    } finally {
      // Always release the composer and refresh the session list, even if the
      // stream threw or the connection dropped — never leave the UI "processing".
      setStreaming(false);
      pruneEmptyAssistant();
      onActivity();
    }
  };

  return (
    <div className="h-full flex flex-col relative">
      <div className="flex-1 overflow-y-auto thin-scrollbar px-4 md:px-8 py-6">
        <div className="max-w-3xl mx-auto flex flex-col gap-5 pb-40">
          <AnimatePresence initial={false}>
            {messages.map((m) => <MessageBubble key={m.id} message={m} />)}
          </AnimatePresence>

          {streaming && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-2.5 pl-10 text-zinc-500"
            >
              <span className="flex gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-bounce [animation-delay:-0.3s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:-0.15s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-bounce" />
              </span>
              <span className="text-xs font-medium text-zinc-500">Thinking…</span>
            </motion.div>
          )}

          {loading && (
            <div className="flex justify-center py-10">
              <div className="glass-faint rounded-full px-4 py-2 text-xs text-zinc-400">
                Loading session…
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {messages.length === 1 && !streaming && !loading && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, type: 'spring', stiffness: 260, damping: 26 }}
          className="absolute inset-x-0 top-[16%] flex flex-col items-center pointer-events-none"
        >
          <motion.div
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 300, damping: 20 }}
            className="relative mb-6"
          >
            <motion.div
              className="absolute -inset-6 rounded-full bg-sky-500/20 blur-2xl"
              animate={{ scale: [1, 1.15, 1], opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 3.2, repeat: Infinity, ease: 'easeInOut' }}
            />
            <div className="relative w-14 h-14 rounded-[18px] bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_16px_40px_rgba(59,110,246,0.5)]">
              <Sparkles className="w-7 h-7 text-white" />
            </div>
          </motion.div>

          <h3 className="text-lg font-semibold text-white tracking-tight mb-1.5 text-center">
            Ask your Intelligence Core
          </h3>
          <p className="text-[13px] text-zinc-500 max-w-sm text-center mb-7">
            Markets, operations, geology, or documents — the core knows it all.
          </p>

          <div className="flex flex-col sm:flex-row gap-2.5 pointer-events-auto w-full max-w-xl px-4">
            {SUGGESTIONS.map((s, i) => (
              <motion.button
                key={s.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 + i * 0.08 }}
                whileHover={{ y: -3 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => void handleSend(s.prompt)}
                className="glass-faint rounded-2xl px-4 py-3 flex items-center gap-2.5 text-left text-[13px] font-medium text-zinc-200 hover:text-white hover:border-sky-400/40 transition-colors group flex-1 min-w-0"
              >
                <s.icon className="w-4 h-4 text-sky-300 shrink-0" />
                <span className="truncate min-w-0">{s.label}</span>
                <ArrowUpRight className="w-3.5 h-3.5 text-zinc-600 group-hover:text-sky-300 transition-colors ml-auto shrink-0" />
              </motion.button>
            ))}
          </div>
        </motion.div>
      )}

      <div className="absolute bottom-0 inset-x-0 z-20 px-4 pb-6 md:px-8 md:pb-8 bg-gradient-to-t from-[#06060c] via-[#06060c]/80 to-transparent pt-12">
        <div className="max-w-3xl mx-auto">
          <Composer disabled={streaming} onSend={(t, f) => void handleSend(t, f)} />
        </div>
      </div>
    </div>
  );
}
