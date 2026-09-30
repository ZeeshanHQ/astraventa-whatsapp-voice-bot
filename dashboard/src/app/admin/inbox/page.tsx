'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { Bot, User, Send, Plus, ToggleLeft, ToggleRight, MessageSquare, Phone, X, Loader2, ArrowLeft } from 'lucide-react';

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
}

interface NewConversationForm {
  wa_id: string;
  text: string;
  contact_name: string;
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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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

  const fetchHistory = useCallback(async (wa_id: string) => {
    setLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE}/api/contacts/${wa_id}/history?limit=60`);
      const data = await res.json();
      setMessages(data.messages || []);
    } catch (e) {
      console.error('Failed to fetch history', e);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    fetchContacts();
    const interval = setInterval(fetchContacts, 15000); // Auto-refresh every 15s
    return () => clearInterval(interval);
  }, [fetchContacts]);

  useEffect(() => {
    if (selected) {
      fetchHistory(selected.wa_id);
      const interval = setInterval(() => fetchHistory(selected.wa_id), 10000);
      return () => clearInterval(interval);
    }
  }, [selected, fetchHistory]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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
        prev.map(c => c.wa_id === selected.wa_id ? { ...c, ai_enabled: newStatus } : c)
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
      setMessages(prev => [...prev, { role: 'assistant', content: text }]);
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

  const formatTime = (iso: string) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex h-[calc(100vh-2rem)] overflow-hidden rounded-xl border border-zinc-800 bg-[#0c1019]">

      {/* ── Left: Contact List ─────────────────────────────── */}
      <div className="w-72 flex-shrink-0 border-r border-zinc-800 flex flex-col">
        {/* Header */}
        <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-emerald-400" />
            <span className="text-[13px] font-semibold text-white font-mono">Inbox</span>
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
        <div className="flex-1 overflow-y-auto">
          {contacts.length === 0 ? (
            <div className="p-4 text-center text-zinc-500 text-[12px] font-mono">No contacts yet</div>
          ) : (
            contacts.map(contact => (
              <button
                key={contact.wa_id}
                onClick={() => selectContact(contact)}
                className={`w-full text-left p-3 border-b border-zinc-800/50 hover:bg-zinc-800/40 transition-colors ${
                  selected?.wa_id === contact.wa_id ? 'bg-zinc-800/60 border-l-2 border-l-emerald-500' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-zinc-700 flex items-center justify-center flex-shrink-0">
                      <Phone className="w-3 h-3 text-zinc-400" />
                    </div>
                    <span className="text-[12px] font-medium text-zinc-200 truncate max-w-[110px]">
                      {contact.contact_name}
                    </span>
                  </div>
                  {/* AI indicator */}
                  <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                    contact.ai_enabled
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
                  }`}>
                    {contact.ai_enabled ? 'AI' : 'MAN'}
                  </span>
                </div>
                <p className="text-[11px] text-zinc-500 truncate pl-9">
                  {contact.last_message_role === 'assistant' ? '↗ ' : ''}{contact.last_message || 'No messages yet'}
                </p>
              </button>
            ))
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
        <div className="flex-1 flex flex-col min-w-0">
          {/* Conversation Header */}
          <div className="p-3 border-b border-zinc-800 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              <button onClick={() => setSelected(null)} className="md:hidden text-zinc-400 hover:text-white">
                <ArrowLeft className="w-4 h-4" />
              </button>
              <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center">
                <Phone className="w-3.5 h-3.5 text-zinc-400" />
              </div>
              <div>
                <div className="text-[13px] font-semibold text-white">{selected.contact_name}</div>
                <div className="text-[11px] text-zinc-500 font-mono">+{selected.wa_id}</div>
              </div>
            </div>

            {/* AI Toggle */}
            <button
              onClick={toggleAI}
              disabled={toggling}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[11px] font-mono font-medium transition-all ${
                selected.ai_enabled
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
                  : 'bg-orange-500/10 text-orange-400 border-orange-500/30 hover:bg-orange-500/20'
              }`}
            >
              {toggling ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : selected.ai_enabled ? (
                <ToggleRight className="w-3.5 h-3.5" />
              ) : (
                <ToggleLeft className="w-3.5 h-3.5" />
              )}
              {selected.ai_enabled ? 'AI ON' : 'AI OFF — Manual Mode'}
            </button>
          </div>

          {/* AI Status Banner */}
          {selected.ai_enabled ? (
            <div className="mx-4 mt-3 px-3 py-2 rounded-lg bg-emerald-500/5 border border-emerald-500/15 text-[11px] text-emerald-400 font-mono flex items-center gap-2 flex-shrink-0">
              <Bot className="w-3.5 h-3.5 flex-shrink-0" />
              AI is automatically handling this conversation. Toggle OFF to take over manually.
            </div>
          ) : (
            <div className="mx-4 mt-3 px-3 py-2 rounded-lg bg-orange-500/5 border border-orange-500/15 text-[11px] text-orange-400 font-mono flex items-center gap-2 flex-shrink-0">
              <User className="w-3.5 h-3.5 flex-shrink-0" />
              Manual mode — AI is paused. Replies below go directly to the contact's WhatsApp.
            </div>
          )}

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {loadingHistory ? (
              <div className="flex justify-center pt-8">
                <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center text-zinc-600 text-[12px] font-mono pt-8">No messages yet</div>
            ) : (
              messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'assistant' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`flex items-end gap-2 max-w-[75%] ${msg.role === 'assistant' ? 'flex-row-reverse' : ''}`}>
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
                      msg.role === 'assistant' ? 'bg-emerald-500/20' : 'bg-zinc-700'
                    }`}>
                      {msg.role === 'assistant'
                        ? <Bot className="w-3 h-3 text-emerald-400" />
                        : <User className="w-3 h-3 text-zinc-400" />
                      }
                    </div>
                    <div className={`px-3 py-2 rounded-xl text-[12px] leading-relaxed ${
                      msg.role === 'assistant'
                        ? 'bg-emerald-500/10 text-emerald-100 border border-emerald-500/20 rounded-br-sm'
                        : 'bg-zinc-800 text-zinc-200 border border-zinc-700 rounded-bl-sm'
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Manual Reply Box — only shown when AI is OFF */}
          {!selected.ai_enabled && (
            <div className="p-3 border-t border-zinc-800 flex-shrink-0">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={manualText}
                  onChange={e => setManualText(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  placeholder="Type a message… (Enter to send)"
                  className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-[12px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 font-mono transition-all"
                />
                <button
                  onClick={sendMessage}
                  disabled={sending || !manualText.trim()}
                  className="px-3 py-2 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1.5"
                >
                  {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
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
                  placeholder="971501234567"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-[13px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50 font-mono"
                />
                <p className="text-[10px] text-zinc-600 mt-1 font-mono">No + prefix needed. Example: 971501234567</p>
              </div>
              <div>
                <label className="block text-[11px] font-mono text-zinc-400 mb-1.5">Contact Name (optional)</label>
                <input
                  type="text"
                  value={newForm.contact_name}
                  onChange={e => setNewForm({ ...newForm, contact_name: e.target.value })}
                  placeholder="John Smith"
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
