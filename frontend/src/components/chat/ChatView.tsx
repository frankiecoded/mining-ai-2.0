import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, ArrowDown, ArrowUpRight, BarChart3, FolderKanban, BookOpen, Terminal } from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { MessageBubble } from './MessageBubble';
import { Composer } from './Composer';
import { useAuth } from '../../contexts/AuthContext';
import type { ChatEvent, ChatMessage } from '../../types';

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'system',
  content: 'Welcome back. Your local Intelligence Core is online — ask about mining operations, markets, geology, or upload documents to expand the knowledge base.',
};

const SUGGESTIONS: Array<{ icon: typeof BarChart3; label: string; hint: string; prompt: string }> = [
  { icon: BarChart3, label: 'Market prices', hint: 'Gold, silver & platinum', prompt: 'Give me the latest gold, silver, and platinum market prices.' },
  { icon: FolderKanban, label: 'Operations', hint: 'Live task breakdown', prompt: 'Summarise the current operations queue.' },
  { icon: BookOpen, label: 'Knowledge base', hint: 'What’s documented', prompt: 'What documents are in the knowledge base?' },
  { icon: Terminal, label: 'Field report', hint: 'Write from findings', prompt: 'Help me draft a field report on this week’s site findings.' },
];

const bucketOf = (role: ChatMessage['role']) => (role === 'user' ? 'user' : role === 'system' ? 'system' : 'assistant');

interface ChatViewProps {
  activeSessionId: string | null;
  onSessionCreated: (id: string) => void;
  onActivity: () => void;
}

export function ChatView({ activeSessionId, onSessionCreated, onActivity }: ChatViewProps) {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [showJump, setShowJump] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  // Client-side timestamps for messages created in this session (History does
  // not carry timestamps, so we only show what we genuinely know).
  const tsRef = useRef<Map<string, string>>(new Map());
  // Sessions created locally (not yet persisted) must not trigger a history
  // refetch that would wipe the optimistic messages while the stream runs.
  const locallyCreatedRef = useRef<Set<string>>(new Set());

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streaming, scrollToBottom]);

  useEffect(() => {
    let cancelled = false;
    tsRef.current = new Map();
    if (!activeSessionId) {
      setMessages([WELCOME]);
      return;
    }
    if (locallyCreatedRef.current.has(activeSessionId)) {
      // New session created in this component — keep the optimistic messages;
      // the stream is already rendering into them.
      locallyCreatedRef.current.delete(activeSessionId);
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

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowJump(distanceFromBottom > 180);
  }, []);

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

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      attachments: file
        ? [{ filename: file.name, file_url: URL.createObjectURL(file), mime_type: file.type || 'application/octet-stream', size_bytes: file.size }]
        : undefined,
    };
    const assistantId = crypto.randomUUID();
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    tsRef.current.set(userMsg.id, now);
    tsRef.current.set(assistantId, now);

    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);

    const sessionId = activeSessionId ?? `sess_${crypto.randomUUID().slice(0, 9)}`;
    if (!activeSessionId) {
      locallyCreatedRef.current.add(sessionId);
      onSessionCreated(sessionId);
    }

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
        } else if (event.type === 'file') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, attachments: [...(m.attachments ?? []), { filename: event.filename, file_url: event.file_url, mime_type: event.mime_type, size_bytes: event.size_bytes }] }
                : m,
            ),
          );
        } else if (event.type === 'image') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, images: [...(m.images ?? []), { filename: event.filename, file_url: event.file_url, mime_type: event.mime_type, size_bytes: event.size_bytes }] }
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

  // Compute conversational groups (consecutive same-sender runs render as one unit)
  const grouped = messages.map((m, i) => {
    const prevB = i > 0 ? bucketOf(messages[i - 1].role) : null;
    const nextB = i < messages.length - 1 ? bucketOf(messages[i + 1].role) : null;
    const cur = bucketOf(m.role);
    const isFirst = cur === 'system' || cur !== prevB;
    const isLast = cur === 'system' || cur !== nextB;
    const isStreaming = streaming && i === messages.length - 1 && m.role === 'assistant';
    return { m: { ...m, content: m.content.trimEnd() }, isFirst, isLast, isStreaming, ts: tsRef.current.get(m.id) };
  });

  const isNewChat = messages.length === 1 && !streaming && !loading;

  return (
    <div className="h-full flex flex-col relative app-aurora overflow-hidden">
      {/* Ambient blobs behind the conversation */}
      <div className="aurora-blob w-[340px] h-[340px] top-1/4 -left-32 bg-sky-600/25" />
      <div className="aurora-blob w-[300px] h-[300px] bottom-1/4 -right-24 bg-violet-600/20" style={{ animationDelay: '-10s' }} />

      {/* Message area — hero and conversation swap in flow so nothing ever
          sits behind anything; both scroll independently. */}
      <div className="relative flex-1 min-h-0">
        <AnimatePresence mode="wait" initial={false}>
          {isNewChat ? (
            <motion.div
              key="hero"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="h-full overflow-y-auto overflow-x-hidden thin-scrollbar snap-top"
            >
              <div className="min-h-full flex flex-col items-center justify-center px-4 py-8 sm:py-14">
                <motion.div
                  initial={{ scale: 0.6, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.1, type: 'spring', stiffness: 300, damping: 20 }}
                  className="relative mb-5 sm:mb-6"
                >
                  <motion.div
                    className="absolute -inset-8 rounded-full bg-sky-500/20 blur-2xl"
                    animate={{ scale: [1, 1.18, 1], opacity: [0.55, 1, 0.55] }}
                    transition={{ duration: 3.6, repeat: Infinity, ease: 'easeInOut' }}
                  />
                  <motion.div
                    initial={{ scale: 0.6, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.15, type: 'spring', stiffness: 300, damping: 18 }}
                    className="relative w-14 h-14 sm:w-16 sm:h-16 rounded-con-18 sm:rounded-con-20 bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_16px_40px_rgba(59,110,246,0.5)] border border-white/10"
                  >
                    <Sparkles className="w-7 h-7 sm:w-8 sm:h-8 text-white" />
                  </motion.div>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.22 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full glass-faint mb-4 sm:mb-5"
                >
                  <span className="pulse-dot text-emerald-400" />
                  <span className="text-[11px] font-semibold text-emerald-200/90">Live · Intelligence Core online</span>
                </motion.div>

                <div className="text-center">
                  <h3 className="text-[24px] sm:text-[30px] font-semibold tracking-tight mb-2.5">
                    <span className="text-gradient">Ask your Intelligence Core</span>
                  </h3>
                  <p className="text-[13px] sm:text-[14px] text-zinc-400 max-w-sm mx-auto mb-6 sm:mb-8 leading-relaxed">
                    Markets, operations, geology, or documents — the core knows it all,{' '}
                    {user?.display_name ? `ready for ${user.display_name.split(' ')[0]}` : 'ready when you are'}.
                  </p>
                </div>

                <motion.div
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3, type: 'spring', stiffness: 260, damping: 24 }}
                  className="grid grid-cols-2 gap-2.5 w-full max-w-xl sm:gap-3"
                >
                  {SUGGESTIONS.map((s, i) => (
                    <motion.button
                      key={s.label}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.34 + i * 0.07 }}
                      whileHover={{ y: -3 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => void handleSend(s.prompt)}
                      className="glass-faint rounded-con-16 sm:rounded-con-20 px-3 sm:px-4 py-3 sm:py-3.5 flex items-center gap-2.5 sm:gap-3 text-left text-[13px] font-medium text-zinc-200 hover:text-white hover:border-sky-400/40 hover:bg-white/[0.06] transition-colors group min-w-0"
                    >
                      <span className="w-9 h-9 sm:w-10 sm:h-10 shrink-0 rounded-con-10 sm:rounded-con-12 bg-sky-500/15 text-sky-300 flex items-center justify-center">
                        <s.icon className="w-4 h-4" />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-semibold text-[12px] sm:text-[13px]">{s.label}</span>
                        <span className="block text-[10px] sm:text-[11px] text-zinc-500 group-hover:text-zinc-400 transition-colors truncate">{s.hint}</span>
                      </span>
                      <ArrowUpRight className="w-3.5 h-3.5 text-zinc-600 group-hover:text-sky-300 transition-colors ml-auto shrink-0" />
                    </motion.button>
                  ))}
                </motion.div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="messages"
              ref={scrollRef}
              onScroll={handleScroll}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="h-full overflow-y-auto overflow-x-hidden thin-scrollbar snap-top relative z-10"
            >
              <div className="max-w-3xl mx-auto px-3.5 sm:px-6 md:px-8 pt-5 sm:pt-6 pb-2">
                <div className="flex flex-col">
                  <AnimatePresence initial={false}>
                    {grouped.map(({ m, isFirst, isLast, isStreaming, ts }) => (
                      <MessageBubble
                        key={m.id}
                        message={m}
                        isFirst={isFirst}
                        isLast={isLast}
                        isStreaming={isStreaming}
                        timestamp={ts}
                      />
                    ))}
                  </AnimatePresence>

                  {/* Typing indicator — only while the first assistant placeholder is pending */}
                  {streaming && !grouped.some((g) => g.isStreaming) && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex items-center gap-3 mt-4"
                    >
                      <div className="w-7 h-7 shrink-0 rounded-full bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center border border-white/10">
                        <Sparkles className="w-3.5 h-3.5 text-white" />
                      </div>
                      <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-2xl glass-faint">
                        <span className="flex gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-bounce [animation-delay:-0.3s]" />
                          <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:-0.15s]" />
                          <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-bounce" />
                        </span>
                        <span className="text-xs font-medium text-zinc-400">Thinking…</span>
                      </div>
                    </motion.div>
                  )}

                  {loading && (
                    <div className="flex justify-center py-10">
                      <div className="glass-faint rounded-full px-4 py-2 text-xs text-zinc-400">
                        Loading session…
                      </div>
                    </div>
                  )}

                  <div ref={bottomRef} className="h-1" />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Scroll-to-bottom jump button — floats within the message area above the composer */}
        <AnimatePresence>
          {showJump && !isNewChat && (
            <motion.button
              initial={{ opacity: 0, scale: 0.7, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.7, y: 8 }}
              whileHover={{ scale: 1.06 }}
              whileTap={{ scale: 0.94 }}
              onClick={() => scrollToBottom()}
              aria-label="Jump to latest message"
              className="absolute z-30 right-4 md:right-8 bottom-4 w-11 h-11 rounded-full glass-strong text-sky-300 flex items-center justify-center shadow-float hover:text-white transition-colors"
            >
              <ArrowDown className="w-[18px] h-[18px]" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Composer dock — in flow, so it never covers the last message */}
      <div className="relative z-20 px-3.5 sm:px-6 md:px-8 pt-2.5 sm:pt-3 pb-[calc(1rem+env(safe-area-inset-bottom,0px))] sm:pb-5 bg-gradient-to-t from-[#06060c] via-[#06060c]/70 to-transparent">
        <div className="max-w-3xl mx-auto">
          <Composer disabled={streaming} onSend={(t, f) => void handleSend(t, f)} />
        </div>
      </div>
    </div>
  );
}