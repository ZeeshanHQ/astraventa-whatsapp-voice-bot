'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Bot,
  User,
  Send,
  Plus,
  ToggleLeft,
  ToggleRight,
  MessageSquare,
  Phone,
  X,
  Loader2,
  ArrowLeft,
  Calendar,
  Clock,
  ArrowDown,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.engine.astraventa.com';

interface Contact {
  wa_id: string;
  contact_name: string;
  ai_enabled: boolean;
  last_message: string;
  last_message_role: string;
  last_seen: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
}

interface NewConversationForm {
  wa_id: string;
  text: string;
  contact_name: string;
}

// ── Time & Date Helpers ──────────────────────────────────────────────────────

function formatMessageTime(isoString?: string): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
  } catch {
    return '';
  }
}

function getMessageDateKey(isoString?: string): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '';
    return d.toISOString().split('T')[0];
  } catch {
    return '';
  }
}

function formatMessageDateSeparator(dateKey: string): string {
  if (!dateKey) return '';
  try {
    const [y, m, d] = dateKey.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const isToday =
      date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear();

    const isYesterday =
      date.getDate() === yesterday.getDate() &&
      date.getMonth() === yesterday.getMonth() &&
      date.getFullYear() === yesterday.getFullYear();

    if (isToday) {
      return `Today — ${date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;
    }
    if (isYesterday) {
      return `Yesterday — ${date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;
    }
    return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateKey;
  }
}

function formatContactLastSeen(isoString?: string): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '';
    const now = new Date();
    const isToday =
      d.getDate() === now.getDate() &&
      d.getMonth() === now.getMonth() &&
      d.getFullYear() === now.getFullYear();

    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
    if (isToday) {
      return `Today, ${timeStr}`;
    }
    const yesterday = new Date();
    yesterday.setDate(now.getDate() - 1);
    const isYesterday =
      d.getDate() === yesterday.getDate() &&
      d.getMonth() === yesterday.getMonth() &&
      d.getFullYear() === yesterday.getFullYear();
    if (isYesterday) {
      return `Yesterday, ${timeStr}`;
    }
    return `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} at ${timeStr}`;
  } catch {
    return '';
  }
}

export default function InboxPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selected, setSelected] = useState<Contact | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [manualText, setManualText] = useState('');
  const [sending, setSending] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newForm, setNewForm] = useState<NewConversationForm>({ wa_id: '', text: '', contact_name: '' });
  const [startingNew, setStartingNew] = useState(false);
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isAtBottomRef = useRef(true);

  // Smart scrolling handler: preserves position if user scrolled up
  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const isBottom = scrollHeight - scrollTop - clientHeight < 100;
    isAtBottomRef.current = isBottom;
    setShowScrollBottomBtn(!isBottom);
  };

  const scrollToBottom = (smooth = true) => {
    if (!scrollContainerRef.current) return;
    scrollContainerRef.current.scrollTo({
      top: scrollContainerRef.current.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    });
    isAtBottomRef.current = true;
    setShowScrollBottomBtn(false);
  };

  const fetchContacts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/contacts`);
      const data = await res.json();
      setContacts(data.contacts || []);
    } catch (e) {
      console.error('Failed to fetch contacts', e);
    }
  }, []);

  const fetchHistory = useCallback(async (wa_id: string, isInitial = false) => {
    if (isInitial) setLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE}/api/contacts/${wa_id}/history?limit=100`);
      const data = await res.json();
      setMessages(data.messages || []);
    } catch (e) {
      console.error('Failed to fetch history', e);
    } finally {
      if (isInitial) setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    fetchContacts();
    const interval = setInterval(fetchContacts, 15000);
    return () => clearInterval(interval);
  }, [fetchContacts]);

  useEffect(() => {
    if (selected) {
      fetchHistory(selected.wa_id, true);
      const interval = setInterval(() => fetchHistory(selected.wa_id, false), 8000);
      return () => clearInterval(interval);
    }
  }, [selected?.wa_id, fetchHistory]);

  // SMART AUTO-SCROLL: ONLY scroll to bottom if user was already at bottom
  useEffect(() => {
    if (isAtBottomRef.current) {
      scrollToBottom(false);
    }
  }, [messages]);

  // Jump to bottom whenever selecting a new contact
  useEffect(() => {
    isAtBottomRef.current = true;
    setShowScrollBottomBtn(false);
    setTimeout(() => scrollToBottom(false), 80);
  }, [selected?.wa_id]);

  const selectContact = (contact: Contact) => {
    setSelected(contact);
    setManualText('');
  };

  const toggleAI = async () => {
    if (!selected || toggling) return;
    setToggling(true);
    const newStatus = !selected.ai_enabled;
    try {
      await fetch(`${API_BASE}/api/contacts/${selected.wa_id}/toggle`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ai_enabled: newStatus }),
      });
      setSelected({ ...selected, ai_enabled: newStatus });
      setContacts(prev =>
        prev.map(c => (c.wa_id === selected.wa_id ? { ...c, ai_enabled: newStatus } : c))
      );
    } catch (e) {
      console.error('Toggle failed', e);
    } finally {
      setToggling(false);
    }
  };

  const sendMessage = async () => {
    if (!selected || !manualText.trim() || sending) return;
    setSending(true);
    const text = manualText.trim();
    setManualText('');
    try {
      await fetch(`${API_BASE}/api/contacts/${selected.wa_id}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: text, created_at: new Date().toISOString() },
      ]);
      isAtBottomRef.current = true;
      setTimeout(() => scrollToBottom(true), 50);
    } catch (e) {
      console.error('Send failed', e);
    } finally {
      setSending(false);
    }
  };

  const startNewConversation = async () => {
    if (!newForm.wa_id.trim() || !newForm.text.trim() || startingNew) return;
    setStartingNew(true);
    try {
      const res = await fetch(`${API_BASE}/api/contacts/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newForm),
      });
      if (res.ok) {
        setShowNewModal(false);
        setNewForm({ wa_id: '', text: '', contact_name: '' });
        await fetchContacts();
      }
    } catch (e) {
      console.error('New conversation failed', e);
    } finally {
      setStartingNew(false);
    }
  };

  // Reset date key tracker for render
  let lastDateKey = '';

  return (
    <div className="flex h-[calc(100vh-2rem)] overflow-hidden rounded-xl border border-zinc-800 bg-[#0c1019]">
      {/* ── Left: Contact List ─────────────────────────────── */}
      <div className="w-80 flex-shrink-0 border-r border-zinc-800 flex flex-col bg-zinc-950/60">
        {/* Header */}
        <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-emerald-400" />
            <span className="text-[13px] font-semibold text-white font-mono">WhatsApp Inbox</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">
              {contacts.length}
            </span>
          </div>
          <button
            onClick={() => setShowNewModal(true)}
            className="flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors text-[11px] font-mono"
          >
            <Plus className="w-3 h-3" /> New
          </button>
        </div>

        {/* Contact List */}
        <div className="flex-1 overflow-y-auto divide-y divide-zinc-800/40">
          {contacts.length === 0 ? (
            <div className="p-4 text-center text-zinc-500 text-[12px] font-mono">No contacts yet</div>
          ) : (
            contacts.map(contact => {
              const isSelected = selected?.wa_id === contact.wa_id;
              return (
                <button
                  key={contact.wa_id}
                  onClick={() => selectContact(contact)}
                  className={`w-full text-left p-3 hover:bg-zinc-800/40 transition-colors ${
                    isSelected ? 'bg-zinc-800/70 border-l-2 border-l-emerald-500' : ''
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-7 h-7 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center flex-shrink-0">
                        <Phone className="w-3 h-3 text-emerald-400" />
                      </div>
                      <div className="truncate">
                        <span className="text-[12px] font-medium text-zinc-200 block truncate">
                          {contact.contact_name || `+${contact.wa_id}`}
                        </span>
                        {contact.contact_name && (
                          <span className="text-[10px] font-mono text-zinc-500 block">
                            +{contact.wa_id}
                          </span>
                        )}
                      </div>
                    </div>

                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded font-mono flex-shrink-0 ${
                        contact.ai_enabled
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {contact.ai_enabled ? 'AI AUTO' : 'MANUAL'}
                    </span>
                  </div>

                  <p className="text-[11px] text-zinc-400 truncate pl-9 mb-1 font-sans">
                    {contact.last_message_role === 'assistant' ? '↗ ' : '↙ '}{contact.last_message || 'No messages yet'}
                  </p>

                  <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 pl-9">
                    <span className="flex items-center gap-1 text-zinc-500">
                      <Clock className="w-2.5 h-2.5" />
                      {formatContactLastSeen(contact.last_seen) || 'Active recently'}
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* ── Right: Conversation View ───────────────────────── */}
      {!selected ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <MessageSquare className="w-12 h-12 text-zinc-700 mx-auto mb-3" />
            <p className="text-zinc-500 text-[13px] font-mono">Select a contact to view conversation</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-w-0 relative">
          {/* Conversation Header */}
          <div className="p-3 border-b border-zinc-800 flex items-center justify-between flex-shrink-0 bg-zinc-950/70">
            <div className="flex items-center gap-3">
              <button onClick={() => setSelected(null)} className="md:hidden text-zinc-400 hover:text-white">
                <ArrowLeft className="w-4 h-4" />
              </button>
              <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                <Phone className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div>
                <div className="text-[13px] font-semibold text-white">
                  {selected.contact_name || `+${selected.wa_id}`}
                </div>
                <div className="text-[11px] text-zinc-500 font-mono">+{selected.wa_id}</div>
              </div>
            </div>

            {/* AI Auto-Reply Toggle */}
            <button
              onClick={toggleAI}
              disabled={toggling}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[11px] font-mono font-medium transition-all ${
                selected.ai_enabled
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20'
              }`}
            >
              {toggling ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : selected.ai_enabled ? (
                <ToggleRight className="w-3.5 h-3.5" />
              ) : (
                <ToggleLeft className="w-3.5 h-3.5" />
              )}
              {selected.ai_enabled ? 'AI AUTO-REPLY ACTIVE' : 'MANUAL TAKEOVER MODE'}
            </button>
          </div>

          {/* AI Status Banner */}
          {selected.ai_enabled ? (
            <div className="mx-4 mt-3 px-3 py-2 rounded-lg bg-emerald-500/5 border border-emerald-500/15 text-[11px] text-emerald-400 font-mono flex items-center gap-2 flex-shrink-0">
              <Bot className="w-3.5 h-3.5 flex-shrink-0" />
              Astraventa AI is automatically answering this contact. Switch to Manual Mode anytime to reply yourself.
            </div>
          ) : (
            <div className="mx-4 mt-3 px-3 py-2 rounded-lg bg-amber-500/5 border border-amber-500/15 text-[11px] text-amber-400 font-mono flex items-center gap-2 flex-shrink-0">
              <User className="w-3.5 h-3.5 flex-shrink-0" />
              Manual Takeover Mode — AI auto-reply is paused. Replies below go directly to this contact's WhatsApp.
            </div>
          )}

          {/* Messages Stream Viewport with Smart Scroll */}
          <div
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-4 space-y-3 font-sans relative"
          >
            {loadingHistory ? (
              <div className="flex justify-center pt-8">
                <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center text-zinc-600 text-[12px] font-mono pt-8">No messages yet</div>
            ) : (
              messages.map((msg, i) => {
                const isAssistant = msg.role === 'assistant';
                const msgDateKey = getMessageDateKey(msg.created_at);
                const showSeparator = msgDateKey && msgDateKey !== lastDateKey;
                if (msgDateKey) {
                  lastDateKey = msgDateKey;
                }

                return (
                  <div key={i} className="space-y-3">
                    {/* Calendar Date Banner */}
                    {showSeparator && (
                      <div className="flex items-center justify-center my-3">
                        <div className="px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-[10px] font-mono font-medium text-zinc-400 shadow-sm flex items-center gap-1.5">
                          <Calendar className="w-3 h-3 text-cyan-400" />
                          <span>{formatMessageDateSeparator(msgDateKey)}</span>
                        </div>
                      </div>
                    )}

                    <div className={`flex ${isAssistant ? 'justify-end' : 'justify-start'}`}>
                      <div className={`flex items-end gap-2 max-w-[78%] ${isAssistant ? 'flex-row-reverse' : ''}`}>
                        <div
                          className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] ${
                            isAssistant ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-zinc-800 text-cyan-400 border border-zinc-700'
                          }`}
                        >
                          {isAssistant ? <Bot className="w-3 h-3" /> : <User className="w-3 h-3" />}
                        </div>

                        <div
                          className={`px-3.5 py-2.5 rounded-xl text-[12px] leading-relaxed shadow-sm ${
                            isAssistant
                              ? 'bg-emerald-950/40 text-emerald-100 border border-emerald-500/20 rounded-br-sm'
                              : 'bg-zinc-900 text-zinc-100 border border-zinc-700/80 rounded-bl-sm'
                          }`}
                        >
                          <div className="whitespace-pre-wrap font-sans">{msg.content}</div>

                          {/* Message Time and Role Badge */}
                          <div className="flex items-center justify-between mt-1.5 pt-1 border-t border-zinc-800/40 text-[9px] font-mono gap-4">
                            <span className={isAssistant ? 'text-emerald-400 font-semibold' : 'text-cyan-400 font-semibold'}>
                              {isAssistant ? (selected.ai_enabled ? 'Astraventa AI' : 'Manual Operator') : `User (+${selected.wa_id})`}
                            </span>
                            <span className="text-zinc-400 flex items-center gap-1">
                              <Clock className="w-2.5 h-2.5 text-zinc-500" />
                              {formatMessageTime(msg.created_at) || 'Just now'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Floating Jump to Latest Button */}
          {showScrollBottomBtn && (
            <button
              onClick={() => scrollToBottom(true)}
              className="absolute bottom-16 right-6 z-20 px-3 py-1.5 rounded-full bg-zinc-900 border border-cyan-500/40 text-cyan-400 text-[11px] font-mono shadow-lg flex items-center gap-1.5 hover:bg-zinc-800 transition-all"
            >
              <ArrowDown className="w-3.5 h-3.5 animate-bounce" />
              <span>Jump to latest</span>
            </button>
          )}

          {/* Manual Reply Box — available to take over manual reply */}
          {!selected.ai_enabled && (
            <div className="p-3 border-t border-zinc-800 flex-shrink-0 bg-zinc-950/60">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={manualText}
                  onChange={e => setManualText(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  placeholder="Type a manual reply to send to WhatsApp... (Enter to send)"
                  className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-[12px] text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 font-mono transition-all"
                />
                <button
                  onClick={sendMessage}
                  disabled={sending || !manualText.trim()}
                  className="px-3.5 py-2 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1.5 text-xs font-mono font-medium"
                >
                  {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  <span>Send</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── New Conversation Modal ─────────────────────────── */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0c1019] border border-zinc-800 rounded-xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <Plus className="w-4 h-4 text-emerald-400" />
                <span className="text-[14px] font-semibold text-white font-mono">New Conversation</span>
              </div>
              <button onClick={() => setShowNewModal(false)} className="text-zinc-500 hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-[11px] font-mono text-zinc-400 mb-1.5">Phone Number (with country code)</label>
                <input
                  type="text"
                  value={newForm.wa_id}
                  onChange={e => setNewForm({ ...newForm, wa_id: e.target.value })}
                  placeholder="923001234567"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-[13px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50 font-mono"
                />
                <p className="text-[10px] text-zinc-600 mt-1 font-mono">No + prefix needed. Example: 923001234567 or 19255040101</p>
              </div>
              <div>
                <label className="block text-[11px] font-mono text-zinc-400 mb-1.5">Contact Name (optional)</label>
                <input
                  type="text"
                  value={newForm.contact_name}
                  onChange={e => setNewForm({ ...newForm, contact_name: e.target.value })}
                  placeholder="Client Name"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-[13px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50 font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] font-mono text-zinc-400 mb-1.5">First Message</label>
                <textarea
                  value={newForm.text}
                  onChange={e => setNewForm({ ...newForm, text: e.target.value })}
                  placeholder="Hi! I'm reaching out from Astraventa..."
                  rows={3}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-[13px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50 font-mono resize-none"
                />
              </div>
              <div className="flex gap-3 pt-1">
                <button
                  onClick={() => setShowNewModal(false)}
                  className="flex-1 px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-600 text-[12px] font-mono transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={startNewConversation}
                  disabled={startingNew || !newForm.wa_id.trim() || !newForm.text.trim()}
                  className="flex-1 px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 disabled:opacity-40 disabled:cursor-not-allowed text-[12px] font-mono transition-all flex items-center justify-center gap-2"
                >
                  {startingNew ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  Send Message
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
