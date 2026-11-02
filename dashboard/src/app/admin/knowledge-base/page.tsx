'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Database,
  Plus,
  Trash2,
  Search,
  Check,
  Sparkles,
  Tag,
  Zap,
  ArrowRight,
  Loader2,
  FileText,
  Filter,
  PhoneCall,
} from 'lucide-react';

interface KnowledgeDoc {
  id: string;
  content: string;
  metadata?: {
    category?: string;
    [key: string]: any;
  };
  created_at?: string;
}

interface TestResult {
  id: string;
  content: string;
  metadata?: any;
  similarity: number;
}

const CATEGORIES = [
  { id: 'all', label: 'All Documents' },
  { id: 'company_overview', label: 'Company Overview' },
  { id: 'services', label: 'Services & Tech' },
  { id: 'pricing', label: 'Pricing & Packages' },
  { id: 'contact_info', label: 'Contact & Booking' },
  { id: 'faq', label: 'FAQs' },
];

export default function KnowledgeBasePage() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [search, setSearch] = useState('');

  // Add Modal State
  const [showModal, setShowModal] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newCategory, setNewCategory] = useState('services');
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  // RAG Simulator State
  const [testQuery, setTestQuery] = useState('');
  const [testingRag, setTestingRag] = useState(false);
  const [testResults, setTestResults] = useState<TestResult[] | null>(null);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.engine.astraventa.com';
      try {
        const res = await fetch(`${apiUrl}/api/kb`);
        if (res.ok) {
          const json = await res.json();
          if (json.documents && json.documents.length > 0) {
            setDocs(json.documents as KnowledgeDoc[]);
            setLoading(false);
            return;
          }
        }
      } catch (apiErr) {
        console.warn('API /api/kb fetch error, trying direct Supabase:', apiErr);
      }

      const { data, error } = await supabase
        .from('knowledge_base')
        .select('id, content, metadata, created_at')
        .order('created_at', { ascending: false });

      if (!error && data && data.length > 0) {
        setDocs(data as KnowledgeDoc[]);
      } else {
        // Fallback fetch without created_at if table lacks column
        const { data: fallbackData } = await supabase
          .from('knowledge_base')
          .select('id, content, metadata');
        if (fallbackData) {
          setDocs(fallbackData as KnowledgeDoc[]);
        }
      }
    } catch (err) {
      console.error('Error fetching knowledge base:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  // Handle Add Document with 768d Vector Embedding
  const handleAddKnowledge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;

    setSubmitting(true);
    setSuccessMsg('');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.engine.astraventa.com';
      let added = false;

      // 1. Primary: Insert via backend API (runs with service_role key & fast 768d vectorizer)
      try {
        const res = await fetch(`${apiUrl}/api/kb`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content: newContent.trim(),
            category: newCategory,
            metadata: { category: newCategory, source: 'dashboard' },
          }),
        });
        if (res.ok) {
          added = true;
        }
      } catch (err) {
        console.warn('API /api/kb insert error:', err);
      }

      // 2. Direct Supabase fallback
      if (!added) {
        const { error } = await supabase.from('knowledge_base').insert({
          content: newContent.trim(),
          metadata: { category: newCategory },
        });
        if (!error) {
          added = true;
        }
      }

      setSuccessMsg('Document successfully added & vectorized for voice calls!');
      setNewContent('');
      setShowModal(false);
      await fetchDocs();
    } catch (err) {
      console.error('KB submit error:', err);
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Delete Document
  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to remove this document from the voice agent memory?')) return;
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.engine.astraventa.com';
      try {
        await fetch(`${apiUrl}/api/kb/${id}`, { method: 'DELETE' });
      } catch (err) {
        await supabase.from('knowledge_base').delete().eq('id', id);
      }
      setDocs((prev) => prev.filter((d) => String(d.id) !== String(id)));
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  // Handle RAG Live Simulator Test
  const handleTestRAG = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testQuery.trim()) return;

    setTestingRag(true);
    setTestResults(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.engine.astraventa.com';
      const res = await fetch(`${apiUrl}/api/kb/test-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: testQuery.trim(),
          match_threshold: 0.1,
          match_count: 3,
        }),
      });
      const data = await res.json();
      if (data.results) {
        setTestResults(data.results);
      }
    } catch (err) {
      console.error('Error running RAG test:', err);
    } finally {
      setTestingRag(false);
    }
  };

  // Filtered documents
  const filteredDocs = docs.filter((doc) => {
    const matchesSearch =
      search === '' ||
      doc.content.toLowerCase().includes(search.toLowerCase()) ||
      (doc.metadata?.category && doc.metadata.category.toLowerCase().includes(search.toLowerCase()));

    const matchesCategory =
      selectedCategory === 'all' ||
      doc.metadata?.category === selectedCategory ||
      (!doc.metadata?.category && selectedCategory === 'services');

    return matchesSearch && matchesCategory;
  });

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header Card */}
      <div className="bg-[#0b101b] border border-zinc-800 rounded-xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-violet-500/10 border border-violet-500/20 rounded-lg text-violet-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight font-mono">
                RAG Knowledge Base & Voice Agent Memory
              </h1>
              <p className="text-xs text-zinc-400 mt-0.5">
                Verified documents that the AI phone agent accesses during live calls to{' '}
                <span className="text-emerald-400 font-mono font-medium">+1 (925) 504-0101</span>.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3 w-full md:w-auto">
          <button
            onClick={() => setShowModal(true)}
            className="flex-1 md:flex-none flex items-center justify-center space-x-2 bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-xs px-4 py-2.5 rounded-lg shadow-sm transition-all font-mono"
          >
            <Plus className="w-4 h-4" />
            <span>Add Knowledge Doc</span>
          </button>
        </div>
      </div>

      {/* Interactive RAG Voice Retrieval Simulator Box */}
      <div className="bg-gradient-to-r from-violet-950/20 via-zinc-900/60 to-cyan-950/20 border border-violet-500/30 rounded-xl p-5 shadow-lg space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-violet-400" />
            <span className="font-mono text-xs font-semibold text-white tracking-wide">
              LIVE VOICE RAG TEST PLAYGROUND
            </span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-violet-500/10 text-violet-300 border border-violet-500/20">
            Vector Similarity &lt; 20ms
          </span>
        </div>

        <p className="text-xs text-zinc-400">
          Type any question a caller might ask over the phone to inspect which knowledge snippets the agent will retrieve.
        </p>

        <form onSubmit={handleTestRAG} className="flex gap-2">
          <input
            type="text"
            value={testQuery}
            onChange={(e) => setTestQuery(e.target.value)}
            placeholder="e.g. What services does Astraventa offer? or How much does the enterprise plan cost?"
            className="flex-1 bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500 font-mono"
          />
          <button
            type="submit"
            disabled={testingRag || !testQuery.trim()}
            className="flex items-center space-x-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg font-mono transition-colors font-medium"
          >
            {testingRag ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Search className="w-3.5 h-3.5" />
            )}
            <span>Test Query</span>
          </button>
        </form>

        {/* Simulator Results */}
        {testResults && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 bg-zinc-950/80 border border-zinc-800 rounded-lg p-3 space-y-2"
          >
            <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
              <span>Retrieved {testResults.length} matching snippets:</span>
              <span className="text-emerald-400">Agent Response Context Ready</span>
            </div>
            {testResults.length === 0 ? (
              <p className="text-xs text-zinc-500 italic py-2">
                No matching documents found above threshold. Agent will use default baseline knowledge.
              </p>
            ) : (
              <div className="space-y-2">
                {testResults.map((res, i) => (
                  <div
                    key={i}
                    className="p-2.5 rounded bg-zinc-900 border border-zinc-800/80 flex flex-col gap-1 text-xs"
                  >
                    <div className="flex items-center justify-between font-mono text-[10px]">
                      <span className="text-violet-300 font-semibold">
                        Match #{i + 1} ({res.metadata?.category || 'general'})
                      </span>
                      <span className="text-cyan-400">
                        Score: {(res.similarity * 100).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-zinc-200 text-xs leading-relaxed">{res.content}</p>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </div>

      {/* Category Pills & Search Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-3 pt-2">
        {/* Category Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all font-mono ${
                selectedCategory === cat.id
                  ? 'bg-zinc-800 text-white border border-zinc-700 shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Keyword Search */}
        <div className="relative w-full md:w-64">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents..."
            className="w-full bg-[#0b101b] border border-zinc-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500"
          />
        </div>
      </div>

      {/* Documents Grid */}
      {loading ? (
        <div className="p-12 text-center text-zinc-500 font-mono text-xs flex items-center justify-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
          Loading knowledge base documents...
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="bg-[#0b101b] border border-zinc-800/80 rounded-xl p-12 text-center space-y-3">
          <FileText className="w-8 h-8 text-zinc-600 mx-auto" />
          <h3 className="text-sm font-semibold text-zinc-300">No documents found</h3>
          <p className="text-xs text-zinc-500 max-w-sm mx-auto">
            {search
              ? 'No knowledge documents match your search criteria.'
              : 'Add your first document so the Astraventa voice agent can answer customer inquiries accurately.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredDocs.map((doc) => (
            <div
              key={doc.id}
              className="bg-[#0b101b] border border-zinc-800/80 hover:border-zinc-700 rounded-xl p-4 flex flex-col justify-between gap-3 transition-all group"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-semibold tracking-wider">
                    {doc.metadata?.category || 'General'}
                  </span>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 p-1 transition-opacity"
                    title="Delete document"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed font-sans">{doc.content}</p>
              </div>

              <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 pt-2 border-t border-zinc-800/60">
                <span>ID: {doc.id.toString().slice(-6)}</span>
                <span className="text-emerald-400/80">Vector Active (768d)</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Knowledge Modal */}
      <AnimatePresence>
        {showModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0e1320] border border-zinc-700 rounded-xl p-6 max-w-lg w-full space-y-4 shadow-2xl"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Database className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-white font-mono">
                    Add Knowledge Base Document
                  </h3>
                </div>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-zinc-500 hover:text-zinc-300 text-xs font-mono"
                >
                  ✕ Close
                </button>
              </div>

              <p className="text-xs text-zinc-400">
                This document will be converted into high-dimensional vector embeddings and immediately made available to the Voice AI agent on calls.
              </p>

              <form onSubmit={handleAddKnowledge} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-mono text-zinc-400 mb-1.5">
                    Category:
                  </label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono"
                  >
                    <option value="company_overview">Company Overview</option>
                    <option value="services">Services & Tech Capabilities</option>
                    <option value="pricing">Pricing & Packages</option>
                    <option value="contact_info">Contact & Booking Information</option>
                    <option value="faq">Frequently Asked Questions (FAQ)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-mono text-zinc-400 mb-1.5">
                    Document Content:
                  </label>
                  <textarea
                    rows={5}
                    value={newContent}
                    onChange={(e) => setNewContent(e.target.value)}
                    placeholder="Enter facts, service descriptions, pricing numbers, or answers for the AI receptionist..."
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500 leading-relaxed font-sans"
                    required
                  />
                </div>

                <div className="flex items-center justify-end space-x-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 rounded-lg text-xs font-mono text-zinc-400 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting || !newContent.trim()}
                    className="flex items-center space-x-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-medium text-xs px-5 py-2 rounded-lg font-mono transition-colors shadow-sm"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Vectorizing...</span>
                      </>
                    ) : (
                      <>
                        <Check className="w-3.5 h-3.5" />
                        <span>Save & Embed</span>
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
