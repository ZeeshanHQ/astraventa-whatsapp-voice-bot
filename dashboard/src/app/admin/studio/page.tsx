'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Room,
  RoomEvent,
  Track,
  RemoteTrack,
  RemoteTrackPublication,
  RemoteParticipant,
  ConnectionState,
} from 'livekit-client';
import {
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  PhoneCall,
  Sparkles,
  Volume2,
  Building2,
  Globe,
  Settings2,
  Play,
  RotateCw,
  CheckCircle2,
  AlertCircle,
  Radio,
  Zap,
  Cpu,
  Layers,
  ChevronDown,
  ChevronUp,
  Database,
  History,
  Calendar,
  Send,
  Loader2,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.engine.astraventa.com';

interface VoiceItem {
  id: string;
  name: string;
  gender: string;
  provider: string;
  accent: string;
  description: string;
}

interface CallLogItem {
  id: string;
  room_name: string;
  destination_phone: string;
  status: string;
  duration_seconds: number;
  created_at: string;
  transcript?: any;
}

export default function VoiceAIStudioPage() {
  // Astraventa Voice Agent Core State
  const [businessName, setBusinessName] = useState('Astraventa');
  const [industry, setIndustry] = useState('tech_agency');
  const [websiteUrl, setWebsiteUrl] = useState('https://astraventa.com');
  const [customGreeting, setCustomGreeting] = useState(
    'Hello! Thanks for calling Astraventa. How can I assist you with your AI automation or engineering needs today?'
  );
  const [customRules, setCustomRules] = useState(
    '• Focus strictly on Astraventa capabilities: Custom AI Voice Agents, Agentic Backend Pipelines, Modern Web Engineering (Next.js/React), and WhatsApp Automations.\n• Keep voice responses conversational, natural, and under 20 words.\n• Offer 15-minute consultation via Calendly when caller wants to schedule.\n• If caller asks to speak to Zeeshan or human, offer instant transfer.'
  );
  const [selectedVoice, setSelectedVoice] = useState('25679595-ec67-4228-97fb-0309993bdc71');
  const [transferPhoneNumber, setTransferPhoneNumber] = useState('+19255040101');
  const [calendarLink, setCalendarLink] = useState(
    'https://calendly.com/astraventaai/15-min-technical-walkthrough-astraventa'
  );
  const [callError, setCallError] = useState<string | null>(null);

  // Catalogs
  const [voices, setVoices] = useState<VoiceItem[]>([]);
  const [recentCalls, setRecentCalls] = useState<CallLogItem[]>([]);
  const [showSettings, setShowSettings] = useState(false);

  // In-Browser Call Simulation & WebRTC
  const [isCalling, setIsCalling] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [callDuration, setCallDuration] = useState(0);
  const [agentStatus, setAgentStatus] = useState<
    'idle' | 'connecting' | 'speaking' | 'listening' | 'processing'
  >('idle');
  const [latencyMs, setLatencyMs] = useState(260);
  const [transcripts, setTranscripts] = useState<
    { speaker: 'caller' | 'agent'; text: string; time: string }[]
  >([]);

  // Outbound Phone Modal
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [outboundPhone, setOutboundPhone] = useState('');
  const [dialingPhone, setDialingPhone] = useState(false);
  const [phoneDialSuccess, setPhoneDialSuccess] = useState<string | null>(null);

  // Audio Visualizer Refs
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const livekitRoomRef = useRef<Room | null>(null);
  const remoteAudioElementsRef = useRef<HTMLAudioElement[]>([]);

  // Fetch initial catalog & call history
  useEffect(() => {
    async function loadData() {
      try {
        const vRes = await fetch(`${API_BASE}/api/studio/voices`);
        if (vRes.ok) {
          const vData = await vRes.json();
          setVoices(vData.voices || []);
        }
      } catch (err) {
        // Fallback default voice list
        setVoices([
          {
            id: '25679595-ec67-4228-97fb-0309993bdc71',
            name: 'Sarah (Warm & Conversational)',
            gender: 'female',
            provider: 'cartesia',
            accent: 'US American',
            description: 'Ultra-fast natural female receptionist for Astraventa.',
          },
          {
            id: '694f9389-aac1-45b6-b726-9d9369183238',
            name: 'Michael (Confident & Technical)',
            gender: 'male',
            provider: 'cartesia',
            accent: 'US American',
            description: 'Authoritative male tone for engineering and discovery.',
          },
          {
            id: '79a125e8-cd45-4c13-8a67-188112f4dd22',
            name: 'Emma (Polished & Professional)',
            gender: 'female',
            provider: 'cartesia',
            accent: 'British',
            description: 'Refined UK accent for executive client intake.',
          },
          {
            id: 'aura-asteria-en',
            name: 'Asteria (Deepgram Natural)',
            gender: 'female',
            provider: 'deepgram',
            accent: 'US American',
            description: 'Deepgram direct native telephony voice.',
          },
        ]);
      }

      try {
        const sessRes = await fetch(`${API_BASE}/api/kb/call-sessions`);
        if (sessRes.ok) {
          const sessData = await sessRes.json();
          setRecentCalls(sessData.sessions || []);
        }
      } catch (e) {
        console.warn('Call sessions fetch error:', e);
      }
    }
    loadData();
  }, []);

  // Timer for active call
  useEffect(() => {
    let interval: any = null;
    if (isCalling) {
      interval = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      setCallDuration(0);
    }
    return () => clearInterval(interval);
  }, [isCalling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      handleEndCall();
    };
  }, []);

  // Visualizer Loop
  const startVisualizer = async (customStream?: MediaStream) => {
    try {
      let activeStream = customStream;
      if (!activeStream) {
        activeStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      micStreamRef.current = activeStream;

      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioCtx;

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64;
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(activeStream);
      source.connect(analyser);

      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const renderWaveform = () => {
        animationFrameRef.current = requestAnimationFrame(renderWaveform);
        analyser.getByteFrequencyData(dataArray);

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const barWidth = (canvas.width / bufferLength) * 1.8;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const barHeight = (dataArray[i] / 255) * canvas.height * 0.9 + 4;
          const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
          gradient.addColorStop(0, '#06b6d4');
          gradient.addColorStop(1, '#a855f7');

          ctx.fillStyle = gradient;
          ctx.beginPath();
          ctx.roundRect(x, (canvas.height - barHeight) / 2, barWidth - 2, barHeight, 4);
          ctx.fill();

          x += barWidth;
        }
      };

      renderWaveform();
    } catch (e) {
      console.warn('Microphone permission error', e);
    }
  };

  const stopVisualizer = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
  };

  const toggleMute = async () => {
    const nextMute = !isMuted;
    setIsMuted(nextMute);
    if (livekitRoomRef.current?.localParticipant) {
      try {
        await livekitRoomRef.current.localParticipant.setMicrophoneEnabled(!nextMute);
      } catch (err) {
        console.warn('Error toggling microphone track:', err);
      }
    }
  };

  const handleEndCall = () => {
    setIsCalling(false);
    setAgentStatus('idle');
    stopVisualizer();

    remoteAudioElementsRef.current.forEach((el) => {
      try {
        el.pause();
        el.remove();
      } catch (e) {}
    });
    remoteAudioElementsRef.current = [];

    if (livekitRoomRef.current) {
      try {
        livekitRoomRef.current.disconnect();
      } catch (e) {}
      livekitRoomRef.current = null;
    }
  };

  // Connect In-Browser Live Call
  const handleStartBrowserCall = async () => {
    setCallError(null);
    setAgentStatus('connecting');
    setTranscripts([]);

    try {
      const res = await fetch(`${API_BASE}/api/studio/create-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_name: businessName,
          industry: industry,
          website_url: websiteUrl,
          custom_rules: customRules,
          voice_id: selectedVoice,
          transfer_phone_number: transferPhoneNumber,
          calendar_link: calendarLink,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || 'Failed to initialize LiveKit room session.');
      }

      const session = await res.json();
      const livekitUrl = session.livekit_url;
      const token = session.token;

      // Add initial greeting to transcript
      setTranscripts([
        {
          speaker: 'agent',
          text: session.greeting || customGreeting,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });
      livekitRoomRef.current = room;

      room.on(
        RoomEvent.TrackSubscribed,
        (track: RemoteTrack, publication: RemoteTrackPublication, participant: RemoteParticipant) => {
          if (track.kind === Track.Kind.Audio) {
            const audioElement = track.attach();
            remoteAudioElementsRef.current.push(audioElement);
            setAgentStatus('speaking');
          }
        }
      );

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const isAgentSpeaking = speakers.some((s) => s.identity.includes('agent'));
        if (isAgentSpeaking) {
          setAgentStatus('speaking');
        } else if (speakers.length > 0) {
          setAgentStatus('listening');
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        handleEndCall();
      });

      await room.connect(livekitUrl, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      await startVisualizer();

      setIsCalling(true);
      setAgentStatus('listening');
    } catch (err: any) {
      console.error('Call connection error:', err);
      setCallError(err.message || 'Could not connect live audio session.');
      setAgentStatus('idle');
      handleEndCall();
    }
  };

  // Trigger Outbound Phone Call
  const handleOutboundCall = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!outboundPhone.trim()) return;
    setDialingPhone(true);
    setPhoneDialSuccess(null);

    try {
      const res = await fetch(`${API_BASE}/api/studio/outbound-call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_phone: outboundPhone.trim(),
          business_name: businessName,
          industry: industry,
          voice_id: selectedVoice,
          transfer_phone_number: transferPhoneNumber,
          calendar_link: calendarLink,
          custom_rules: customRules,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setPhoneDialSuccess(`Call dispatched successfully to ${outboundPhone}!`);
        setTimeout(() => {
          setShowPhoneModal(false);
          setPhoneDialSuccess(null);
          setOutboundPhone('');
        }, 2000);
      } else {
        alert(data.detail || 'Failed to dispatch phone call.');
      }
    } catch (err: any) {
      alert('Error triggering outbound call: ' + err.message);
    } finally {
      setDialingPhone(false);
    }
  };

  const formatDuration = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remainder.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Hero Control Card */}
      <div className="bg-[#0b101b] border border-zinc-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        {/* Subtle Ambient Glow */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 relative z-10">
          {/* Inbound Line Details */}
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              <span className="text-[11px] font-mono font-semibold tracking-wider uppercase text-emerald-400">
                Astraventa Inbound Voice Gateway Active
              </span>
            </div>

            <h1 className="text-2xl md:text-3xl font-extrabold text-white font-mono tracking-tight flex items-center gap-3">
              <PhoneCall className="w-7 h-7 text-emerald-400" />
              <span>+1 (925) 504-0101</span>
            </h1>

            <p className="text-xs text-zinc-400 max-w-xl">
              When anyone calls this number, the Astraventa AI Receptionist answers instantly with{' '}
              <span className="text-cyan-400 font-mono font-medium">Deepgram Nova-3</span>,{' '}
              <span className="text-emerald-400 font-mono font-medium">Groq Llama-3.3-70B</span>,{' '}
              and <span className="text-pink-400 font-mono font-medium">Cartesia Sonic</span> in under{' '}
              <span className="text-white font-mono font-bold">400 milliseconds</span>.
            </p>

            {/* Telemetry Pills */}
            <div className="flex flex-wrap items-center gap-2 pt-1 font-mono text-[10px]">
              <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-700/80 text-zinc-300">
                STT: Nova-3 WebSockets
              </span>
              <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-700/80 text-cyan-300">
                LLM: Groq LPU (~120ms)
              </span>
              <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-700/80 text-pink-300">
                TTS: Cartesia Sonic (~100ms)
              </span>
              <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-700/80 text-violet-300">
                RAG: pgvector Synced
              </span>
            </div>
          </div>

          {/* Primary Action Buttons */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full lg:w-auto">
            {isCalling ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleMute}
                  className={`p-3 rounded-xl border transition-all ${
                    isMuted
                      ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                      : 'bg-zinc-800 border-zinc-700 text-zinc-300 hover:text-white'
                  }`}
                  title={isMuted ? 'Unmute Mic' : 'Mute Mic'}
                >
                  {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </button>
                <button
                  onClick={handleEndCall}
                  className="flex items-center justify-center space-x-2 bg-red-600 hover:bg-red-500 text-white font-mono text-xs font-bold px-6 py-3 rounded-xl shadow-lg shadow-red-900/30 transition-all"
                >
                  <PhoneOff className="w-4 h-4" />
                  <span>End Live Call ({formatDuration(callDuration)})</span>
                </button>
              </div>
            ) : (
              <button
                onClick={handleStartBrowserCall}
                disabled={agentStatus === 'connecting'}
                className="flex items-center justify-center space-x-2.5 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 text-black font-mono font-bold text-xs px-6 py-3.5 rounded-xl shadow-lg shadow-cyan-950/40 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                {agentStatus === 'connecting' ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Connecting WebRTC...</span>
                  </>
                ) : (
                  <>
                    <Mic className="w-4 h-4" />
                    <span>Test Voice Agent Now (Live Mic)</span>
                  </>
                )}
              </button>
            )}

            <button
              onClick={() => setShowPhoneModal(true)}
              className="flex items-center justify-center space-x-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs font-mono font-medium px-4 py-3.5 rounded-xl transition-all"
            >
              <Phone className="w-4 h-4 text-cyan-400" />
              <span>Dial Any Phone</span>
            </button>
          </div>
        </div>

        {/* Live Audio Visualizer Banner (When Call is Active) */}
        <AnimatePresence>
          {isCalling && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-6 pt-6 border-t border-zinc-800/80 space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div
                    className={`px-3 py-1 rounded-full text-xs font-mono font-semibold flex items-center gap-2 ${
                      agentStatus === 'speaking'
                        ? 'bg-pink-500/20 text-pink-300 border border-pink-500/40'
                        : agentStatus === 'listening'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                    }`}
                  >
                    <span className="w-2 h-2 rounded-full bg-current animate-ping" />
                    <span className="capitalize">{agentStatus}...</span>
                  </div>
                  <span className="text-zinc-500 font-mono text-xs">
                    Speak into your microphone naturally to talk to Astraventa AI
                  </span>
                </div>

                <div className="flex items-center space-x-3 font-mono text-xs text-zinc-400">
                  <span>RTT Latency: <span className="text-emerald-400 font-bold">{latencyMs}ms</span></span>
                  <span>Duration: <span className="text-white font-bold">{formatDuration(callDuration)}</span></span>
                </div>
              </div>

              {/* Dynamic Waveform Canvas */}
              <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 flex items-center justify-center">
                <canvas ref={canvasRef} width={640} height={70} className="w-full max-w-2xl h-16" />
              </div>

              {/* In-Call Live Transcript Stream */}
              <div className="bg-zinc-950/60 border border-zinc-800 rounded-xl p-4 max-h-48 overflow-y-auto space-y-2">
                <div className="text-[10px] font-mono uppercase text-zinc-500 tracking-wider font-semibold mb-2">
                  Live Conversation Transcript
                </div>
                {transcripts.length === 0 ? (
                  <p className="text-xs text-zinc-500 italic">Listening for conversation turns...</p>
                ) : (
                  transcripts.map((t, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span
                        className={`font-mono text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                          t.speaker === 'agent'
                            ? 'bg-cyan-500/20 text-cyan-300'
                            : 'bg-emerald-500/20 text-emerald-300'
                        }`}
                      >
                        {t.speaker === 'agent' ? 'Astraventa AI' : 'Caller'}
                      </span>
                      <span className="text-zinc-300 flex-1">{t.text}</span>
                      <span className="text-[10px] text-zinc-600 font-mono">{t.time}</span>
                    </div>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {callError && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center space-x-2 text-xs text-red-300 font-mono">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span>{callError}</span>
          </div>
        )}
      </div>

      {/* Accordion: Customize Agent Persona, Voice & Routing */}
      <div className="bg-[#0b101b] border border-zinc-800 rounded-xl overflow-hidden">
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-zinc-900/40 transition-colors"
        >
          <div className="flex items-center space-x-3">
            <Settings2 className="w-4 h-4 text-cyan-400" />
            <div>
              <h2 className="text-sm font-bold text-white font-mono">
                Voice Agent Persona & Routing Rules
              </h2>
              <p className="text-xs text-zinc-400">
                Configure greeting, selected voice model, forwarding phone number, and Calendly link.
              </p>
            </div>
          </div>
          {showSettings ? (
            <ChevronUp className="w-4 h-4 text-zinc-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-400" />
          )}
        </button>

        {showSettings && (
          <div className="p-5 border-t border-zinc-800/80 space-y-5 bg-zinc-950/40">
            {/* Initial Greeting */}
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1.5 font-semibold">
                Initial Greeting Spoken on Call Pickup:
              </label>
              <input
                type="text"
                value={customGreeting}
                onChange={(e) => setCustomGreeting(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono"
              />
            </div>

            {/* Voice Model Selector */}
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1.5 font-semibold">
                AI Voice Persona (Cartesia Sonic & Deepgram Aura):
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {voices.map((v) => (
                  <div
                    key={v.id}
                    onClick={() => setSelectedVoice(v.id)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all flex flex-col justify-between gap-1 ${
                      selectedVoice === v.id
                        ? 'bg-cyan-500/10 border-cyan-500 text-white shadow-sm'
                        : 'bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-center justify-between font-mono text-xs">
                      <span className="font-bold text-zinc-200">{v.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 uppercase">
                        {v.provider}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 font-sans">{v.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Telephony Targets: Forwarding & Calendly */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] font-mono text-zinc-400 mb-1.5 font-semibold">
                  Human Transfer Phone Number (Zeeshan's Direct Line):
                </label>
                <input
                  type="text"
                  value={transferPhoneNumber}
                  onChange={(e) => setTransferPhoneNumber(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono text-zinc-400 mb-1.5 font-semibold">
                  Calendly Booking Walkthrough Link (Sent via Instant SMS):
                </label>
                <input
                  type="text"
                  value={calendarLink}
                  onChange={(e) => setCalendarLink(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>
            </div>

            {/* System Prompt Guidelines */}
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1.5 font-semibold">
                Voice Instructions & Agency Boundaries:
              </label>
              <textarea
                rows={4}
                value={customRules}
                onChange={(e) => setCustomRules(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700/80 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-cyan-500 leading-relaxed font-sans"
              />
            </div>
          </div>
        )}
      </div>

      {/* Recent Inbound Calls & Activity Section */}
      <div className="bg-[#0b101b] border border-zinc-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <History className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-bold text-white font-mono">
              Recent Calls to +1 (925) 504-0101
            </h3>
          </div>
          <span className="text-[10px] font-mono text-zinc-400">
            Realtime Call Logs & Transcripts
          </span>
        </div>

        {recentCalls.length === 0 ? (
          <div className="text-center py-8 text-zinc-500 text-xs font-mono space-y-2">
            <p>No phone calls recorded yet.</p>
            <p className="text-[11px] text-zinc-600">
              Calls received via Telnyx or tested via Live Mic will appear here automatically.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
                  <th className="pb-2.5 font-medium">Session / Room</th>
                  <th className="pb-2.5 font-medium">Caller Phone</th>
                  <th className="pb-2.5 font-medium">Type</th>
                  <th className="pb-2.5 font-medium">Status</th>
                  <th className="pb-2.5 font-medium">Duration</th>
                  <th className="pb-2.5 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                {recentCalls.map((call) => (
                  <tr key={call.id} className="hover:bg-zinc-900/40 transition-colors">
                    <td className="py-2.5 text-cyan-400 font-semibold">{call.room_name}</td>
                    <td className="py-2.5 text-white">{call.destination_phone || 'WebRTC In-Browser'}</td>
                    <td className="py-2.5 text-zinc-400 uppercase text-[10px]">
                      {call.status === 'booked' ? 'Appointment' : 'Inbound'}
                    </td>
                    <td className="py-2.5">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {call.status}
                      </span>
                    </td>
                    <td className="py-2.5 text-zinc-400">{call.duration_seconds}s</td>
                    <td className="py-2.5 text-zinc-500 text-[11px]">
                      {call.created_at ? new Date(call.created_at).toLocaleString() : 'Recent'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Outbound Call Modal */}
      <AnimatePresence>
        {showPhoneModal && (
          <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0e1320] border border-zinc-700 rounded-xl p-6 max-w-md w-full space-y-4 shadow-2xl font-mono"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Phone className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-white">Dial Live Mobile Phone</h3>
                </div>
                <button
                  onClick={() => setShowPhoneModal(false)}
                  className="text-zinc-500 hover:text-zinc-300 text-xs"
                >
                  ✕ Close
                </button>
              </div>

              <p className="text-xs text-zinc-400 font-sans">
                Astraventa Voice Agent will initiate an outbound SIP phone call to the number below with full RAG knowledge enabled.
              </p>

              <form onSubmit={handleOutboundCall} className="space-y-4">
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1.5 font-semibold">
                    Destination Phone Number (E.164):
                  </label>
                  <input
                    type="tel"
                    value={outboundPhone}
                    onChange={(e) => setOutboundPhone(e.target.value)}
                    placeholder="+19255040101 or +923001234567"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3.5 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500"
                    required
                  />
                </div>

                {phoneDialSuccess && (
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs rounded-lg flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{phoneDialSuccess}</span>
                  </div>
                )}

                <div className="flex items-center justify-end space-x-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowPhoneModal(false)}
                    className="px-4 py-2 rounded-lg text-xs text-zinc-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={dialingPhone || !outboundPhone.trim()}
                    className="flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs px-5 py-2 rounded-lg shadow-sm"
                  >
                    {dialingPhone ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Dialing SIP...</span>
                      </>
                    ) : (
                      <>
                        <PhoneCall className="w-3.5 h-3.5" />
                        <span>Dispatch Call</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
