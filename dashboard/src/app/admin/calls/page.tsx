'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  PhoneCall,
  PhoneIncoming,
  PhoneForwarded,
  Clock,
  User,
  Bot,
  RefreshCw,
  Search,
  Filter,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ChevronRight,
  MessageSquare,
  ShieldCheck,
  Zap,
} from 'lucide-react';

interface CallTranscriptTurn {
  speaker: 'caller' | 'agent';
  text: string;
  time?: string;
}

interface CallSession {
  id: string;
  room_name: string;
  session_type: string;
  destination_phone: string;
  status: string;
  duration_seconds: number;
  transcript: CallTranscriptTurn[] | any;
  created_at: string;
}

export default function InboundCallsPage() {
  const [sessions, setSessions] = useState<CallSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedCall, setSelectedCall] = useState<CallSession | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');

  const fetchCalls = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.engine.astraventa.com';
      const res = await fetch(`${apiUrl}/api/kb/call-sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
        setLastRefreshed(new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.error('Error fetching call sessions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
    if (!autoRefresh) return;
    const interval = setInterval(fetchCalls, 5000); // 5s live polling
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const filteredSessions = sessions.filter((session) => {
    const phone = session.destination_phone || '';
    const room = session.room_name || '';
    const matchesSearch =
      searchTerm === '' ||
      phone.toLowerCase().includes(searchTerm.toLowerCase()) ||
      room.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === 'all' || session.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  // KPI calculations
  const totalCalls = sessions.length;
  const completedCalls = sessions.filter((s) => s.status === 'completed').length;
  const transferredCalls = sessions.filter((s) => s.status === 'transferred').length;
  const avgDuration =
    totalCalls > 0
      ? Math.round(
          sessions.reduce((acc, s) => acc + (s.duration_seconds || 0), 0) /
            totalCalls
        )
      : 0;

  const formatDuration = (seconds: number) => {
    if (!seconds) return '0s';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
              <PhoneIncoming className="w-6 h-6 text-emerald-400" />
              Inbound Call Logs
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              ● REALTIME LIVE
            </span>
          </div>
          <p className="text-xs text-zinc-400 font-sans">
            Live inbound voice calls received on Astraventa company line{' '}
            <span className="text-white font-mono font-semibold">+1 (925) 504-0101</span>, with complete conversational transcripts and durations.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all flex items-center space-x-1.5 border ${
              autoRefresh
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-zinc-800 border-zinc-700 text-zinc-400'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500'}`} />
            <span>Auto-Refresh (5s)</span>
          </button>

          <button
            onClick={fetchCalls}
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
            title="Refresh now"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#0b101b] border border-zinc-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-[11px] font-mono uppercase">Total Inbound Calls</span>
            <PhoneIncoming className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">{totalCalls}</div>
          <div className="text-[10px] text-zinc-500 mt-1">Direct to +1 (925) 504-0101</div>
        </div>

        <div className="bg-[#0b101b] border border-zinc-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-[11px] font-mono uppercase">Completed Calls</span>
            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">{completedCalls}</div>
          <div className="text-[10px] text-cyan-400/80 mt-1">Fully handled by AI Agent</div>
        </div>

        <div className="bg-[#0b101b] border border-zinc-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-[11px] font-mono uppercase">Transferred to Human</span>
            <PhoneForwarded className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">{transferredCalls}</div>
          <div className="text-[10px] text-amber-400/80 mt-1">Forwarded to Zeeshan</div>
        </div>

        <div className="bg-[#0b101b] border border-zinc-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-[11px] font-mono uppercase">Avg Talk Time</span>
            <Clock className="w-4 h-4 text-violet-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">{formatDuration(avgDuration)}</div>
          <div className="text-[10px] text-zinc-500 mt-1">Updated {lastRefreshed || 'now'}</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#0b101b] border border-zinc-800 p-3 rounded-xl">
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by phone number..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500 font-mono"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <Filter className="w-3.5 h-3.5 text-zinc-400" />
          <span className="text-xs text-zinc-400">Status:</span>
          {['all', 'completed', 'in_progress', 'transferred'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-mono capitalize transition-colors ${
                statusFilter === st
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {st.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Main Calls Table */}
      <div className="bg-[#0b101b] border border-zinc-800 rounded-xl overflow-hidden shadow-sm">
        {filteredSessions.length === 0 ? (
          <div className="text-center py-16 space-y-3">
            <PhoneIncoming className="w-10 h-10 text-zinc-600 mx-auto" />
            <div className="text-zinc-300 font-semibold text-sm">No Inbound Calls Yet</div>
            <p className="text-xs text-zinc-500 max-w-md mx-auto">
              Any call made to <span className="text-emerald-400 font-mono">+1 (925) 504-0101</span> will automatically appear here with caller phone number, duration, and dialogue transcript.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-zinc-800/80 bg-zinc-900/50 text-zinc-400 font-mono text-[11px] uppercase tracking-wider">
                  <th className="py-3 px-4">Caller Number</th>
                  <th className="py-3 px-4">Call ID</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Duration</th>
                  <th className="py-3 px-4">Turns</th>
                  <th className="py-3 px-4">Date / Time</th>
                  <th className="py-3 px-4 text-right">Transcript</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {filteredSessions.map((call) => {
                  const turnsCount = Array.isArray(call.transcript) ? call.transcript.length : 0;
                  return (
                    <tr
                      key={call.id}
                      className="hover:bg-zinc-900/40 transition-colors group cursor-pointer"
                      onClick={() => setSelectedCall(call)}
                    >
                      <td className="py-3 px-4 font-mono font-semibold text-white flex items-center space-x-2">
                        <PhoneCall className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                        <span>{call.destination_phone || 'Private / In-Browser'}</span>
                      </td>
                      <td className="py-3 px-4 font-mono text-cyan-400">
                        {call.room_name}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-medium border ${
                            call.status === 'completed'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : call.status === 'transferred'
                              ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                              : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20 animate-pulse'
                          }`}
                        >
                          {call.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-zinc-300">
                        {formatDuration(call.duration_seconds)}
                      </td>
                      <td className="py-3 px-4 font-mono text-zinc-400">
                        {turnsCount} turns
                      </td>
                      <td className="py-3 px-4 text-zinc-400 text-[11px] font-mono">
                        {call.created_at ? new Date(call.created_at).toLocaleString() : 'Recent'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedCall(call);
                          }}
                          className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 group-hover:text-white transition-colors text-xs font-mono inline-flex items-center space-x-1"
                        >
                          <MessageSquare className="w-3 h-3 text-cyan-400" />
                          <span>View Dialogue</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Transcript Detail Modal */}
      <AnimatePresence>
        {selectedCall && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0e1320] border border-zinc-700/80 rounded-2xl p-6 max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl"
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-4">
                <div className="flex items-center space-x-3">
                  <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                    <PhoneIncoming className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white font-mono flex items-center gap-2">
                      <span>{selectedCall.destination_phone || 'Caller'}</span>
                      <span className="text-xs font-normal text-zinc-400 font-sans">
                        ({selectedCall.room_name})
                      </span>
                    </h3>
                    <div className="flex items-center space-x-3 text-xs text-zinc-400 mt-0.5 font-mono">
                      <span>Duration: {formatDuration(selectedCall.duration_seconds)}</span>
                      <span>•</span>
                      <span className="capitalize text-emerald-400">{selectedCall.status}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => setSelectedCall(null)}
                  className="text-zinc-500 hover:text-white text-sm p-1 rounded-lg hover:bg-zinc-800 transition-colors"
                >
                  ✕ Close
                </button>
              </div>

              {/* Transcript Scroll Area */}
              <div className="flex-1 overflow-y-auto space-y-3 pr-2 my-2">
                {!selectedCall.transcript || selectedCall.transcript.length === 0 ? (
                  <div className="text-center py-10 text-zinc-500 text-xs">
                    No speech recorded during this call session.
                  </div>
                ) : (
                  selectedCall.transcript.map((turn: CallTranscriptTurn, idx: number) => {
                    const isAgent = turn.speaker === 'agent';
                    return (
                      <div
                        key={idx}
                        className={`flex gap-3 ${isAgent ? 'justify-start' : 'justify-end'}`}
                      >
                        {isAgent && (
                          <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center flex-shrink-0 text-cyan-400">
                            <Bot className="w-4 h-4" />
                          </div>
                        )}

                        <div
                          className={`max-w-[78%] rounded-xl px-4 py-2.5 text-xs ${
                            isAgent
                              ? 'bg-zinc-800/90 text-zinc-100 border border-zinc-700/60'
                              : 'bg-emerald-600/90 text-white font-medium'
                          }`}
                        >
                          <div className="flex items-center justify-between text-[10px] opacity-75 mb-1 gap-2 font-mono">
                            <span>{isAgent ? 'Astraventa Voice Agent' : 'Caller'}</span>
                            {turn.time && <span>{turn.time}</span>}
                          </div>
                          <p className="leading-relaxed">{turn.text}</p>
                        </div>

                        {!isAgent && (
                          <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center flex-shrink-0 text-emerald-400">
                            <User className="w-4 h-4" />
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

              {/* Modal Footer */}
              <div className="border-t border-zinc-800 pt-3 mt-2 flex items-center justify-between text-xs text-zinc-500">
                <span className="font-mono">
                  Recorded via Deepgram Nova-3 & Astraventa Speech Pipeline
                </span>
                <button
                  onClick={() => setSelectedCall(null)}
                  className="px-4 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-xs font-mono transition-colors"
                >
                  Done
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
