import React, { useState, useRef, useEffect } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  User, 
  Cpu, 
  AlertTriangle, 
  RefreshCw, 
  FolderGit2, 
  Lightbulb, 
  Copy, 
  Check, 
  GitBranch, 
  ArrowRight,
  Code2,
  Trash2,
  Database,
  Layers,
  Network
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { getErrorMessage } from '../services/api';
import toast from 'react-hot-toast';

const initialMessages = [
  {
    sender: 'agent',
    agentName: 'ArchitectureCopilot',
    text: `### 👋 Welcome to the Repository AI Architecture Copilot!
I am connected directly to your codebase's **Neo4j AST Knowledge Graph** and multi-model intelligence gateway.

You can ask me to:
* 🏛️ **Analyze architecture & dependencies**: Inspect module coupling, afferent/efferent stability ($I$), and package graphs.
* 🎯 **Calculate blast radius**: Determine exactly which downstream files break if a function, class, or module changes.
* 🔄 **Resolve circular dependencies**: Get step-by-step decoupling patterns (Dependency Inversion, Event Mediator, Interface Segregation).
* ⚡ **Propose SOLID refactorings**: Get clean code patterns, dependency injection templates, and framework migration blueprints.`,
    time: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true }),
    isError: false,
  },
];

const PROMPT_SUGGESTIONS = [
  { label: '🏛️ Analyze Dependencies', text: 'Analyze the architectural dependencies and module coupling of this repository.' },
  { label: '🎯 Calculate Blast Radius', text: 'What is the blast radius and impact if we modify the main entry points?' },
  { label: '🔄 Resolve Circular Dependencies', text: 'What is the recommended migration strategy for circular dependencies?' },
  { label: '⚡ SOLID Refactoring', text: 'Recommend a SOLID refactoring strategy with Dependency Injection for this codebase.' },
  { label: '🚀 Migration Pipeline', text: 'Explain the automated multi-agent migration pipeline and validation steps.' },
];

/** An inline error bubble shown inside the chat thread */
function ErrorBubble({ message, onRetry }) {
  return (
    <div className="flex gap-3 justify-start">
      <div className="w-8 h-8 rounded-xl bg-red-900/60 border border-red-500/40 flex items-center justify-center flex-shrink-0">
        <AlertTriangle className="w-4 h-4 text-red-400" />
      </div>
      <div className="max-w-2xl rounded-2xl rounded-bl-none p-4 text-xs leading-relaxed bg-red-950/40 border border-red-500/20 text-red-300 shadow-md space-y-2">
        <p className="font-semibold text-red-200">Copilot Temporarily Unavailable</p>
        <p>{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-1 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-900/60 hover:bg-red-900 border border-red-500/30 text-red-200 text-xs font-medium transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

/** Formats simple markdown with headers, lists, tables, and code blocks */
function FormattedMessage({ text }) {
  const [copiedIndex, setCopiedIndex] = useState(null);

  const copyToClipboard = (snippet, index) => {
    navigator.clipboard.writeText(snippet);
    setCopiedIndex(index);
    toast.success('Code copied to clipboard!');
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  // Split by code blocks
  const parts = text.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-2.5 text-xs leading-relaxed text-gray-200">
      {parts.map((part, i) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const lines = part.slice(3, -3).trim().split('\n');
          const lang = lines[0].trim().match(/^[a-zA-Z0-9_-]+$/) ? lines[0].trim() : '';
          const code = (lang ? lines.slice(1) : lines).join('\n');

          return (
            <div key={i} className="my-3 rounded-xl overflow-hidden border border-indigo-950/80 bg-[#080B14] shadow-md">
              <div className="flex items-center justify-between px-3 py-1.5 bg-gray-900/90 border-b border-gray-800 text-[11px] font-mono text-gray-400">
                <span className="flex items-center gap-1.5 text-indigo-300 font-semibold">
                  <Code2 className="w-3.5 h-3.5 text-indigo-400" />
                  {lang || 'code'}
                </span>
                <button
                  onClick={() => copyToClipboard(code, i)}
                  className="flex items-center gap-1 hover:text-white px-2 py-0.5 rounded hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  {copiedIndex === i ? (
                    <span className="flex items-center gap-1 text-emerald-400">
                      <Check className="w-3.5 h-3.5" /> Copied
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <Copy className="w-3.5 h-3.5" /> Copy Code
                    </span>
                  )}
                </button>
              </div>
              <pre className="p-3.5 overflow-x-auto text-[11px] font-mono text-cyan-200 leading-relaxed scrollbar-thin scrollbar-thumb-slate-700">
                <code>{code}</code>
              </pre>
            </div>
          );
        }

        // Check for Markdown table lines
        if (part.includes('|') && part.includes('\n|')) {
          const tableLines = part.split('\n').filter((l) => l.trim().startsWith('|') && l.trim().endsWith('|'));
          if (tableLines.length >= 2) {
            const parseRow = (line) => line.split('|').slice(1, -1).map((c) => c.trim());
            const headers = parseRow(tableLines[0]);
            const isSeparator = (line) => line.includes('---');
            const dataRows = tableLines.slice(1).filter((l) => !isSeparator(l)).map(parseRow);

            return (
              <div key={i} className="my-3 overflow-x-auto rounded-xl border border-gray-800 bg-[#0B0F19]">
                <table className="w-full text-left text-[11px] border-collapse">
                  <thead>
                    <tr className="bg-slate-900/90 border-b border-gray-800 text-indigo-300">
                      {headers.map((h, hi) => (
                        <th key={hi} className="px-3 py-2 font-semibold">
                          {h.replace(/\*\*/g, '')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60">
                    {dataRows.map((row, ri) => (
                      <tr key={ri} className="hover:bg-slate-800/40 transition-colors">
                        {row.map((cell, ci) => (
                          <td key={ci} className="px-3 py-2 text-slate-300">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }
        }

        return (
          <div key={i} className="whitespace-pre-line leading-relaxed space-y-1">
            {part}
          </div>
        );
      })}
    </div>
  );
}

export default function AIChat() {
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [selectedRepoId, setSelectedRepoId] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastInput, setLastInput] = useState('');
  const bottomRef = useRef(null);

  // Fetch connected repositories
  const { data: repos = [] } = useQuery({
    queryKey: ['repositories'],
    queryFn: async () => {
      const res = await api.get('/repositories');
      return res.data;
    },
  });

  // Set default selected repository
  useEffect(() => {
    if (repos.length > 0 && !selectedRepoId) {
      setSelectedRepoId(repos[0].id);
    }
  }, [repos, selectedRepoId]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  const sendMessage = async (text) => {
    if (!text.trim() || isGenerating) return;

    // Remove any previous error bubble before retry
    setMessages((prev) => prev.filter((m) => !m.isError));

    const userMsg = {
      sender: 'user',
      text,
      time: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLastInput(text);
    setInput('');
    setIsGenerating(true);

    try {
      const res = await api.post('/chat', { 
        message: text,
        repository_id: selectedRepoId || undefined,
      });
      setMessages((prev) => [
        ...prev,
        {
          sender: 'agent',
          agentName: res.data.agentName || 'ArchitectureCopilot',
          text: res.data.text,
          time: res.data.time && !isNaN(new Date(res.data.time).getTime())
            ? new Date(res.data.time).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true })
            : new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true }),
          isError: false,
        },
      ]);
    } catch (error) {
      const msg = getErrorMessage(error);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'system',
          isError: true,
          text: msg,
        },
      ]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSend = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleRetry = () => {
    sendMessage(lastInput);
  };

  const handleClearChat = () => {
    setMessages(initialMessages);
    toast.success('Conversation reset');
  };

  const selectedRepo = repos.find((r) => r.id === selectedRepoId);

  return (
    <div className="space-y-4 max-w-5xl mx-auto pb-6 h-[calc(100vh-6.5rem)] flex flex-col">
      {/* Header */}
      <div className="p-4 rounded-3xl glass-panel border border-gray-800 flex flex-wrap items-center justify-between gap-3 flex-shrink-0 bg-[#0E1322]/90 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shadow-md shadow-indigo-500/10">
            <Cpu className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Repository AI Architecture Copilot
              <span className="px-2 py-0.5 text-[10px] font-mono rounded-md bg-indigo-950 text-indigo-300 border border-indigo-700/50">
                v2.5 Enterprise
              </span>
            </h2>
            <p className="text-xs text-gray-400">Context-grounded with real-time Neo4j AST knowledge graph &amp; multi-model gateway.</p>
          </div>
        </div>

        {/* Controls & Repository Selector */}
        <div className="flex items-center gap-2 flex-wrap">
          {selectedRepo && (
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-xl bg-slate-900/80 border border-slate-800 text-[11px] text-slate-400">
              <span className="flex items-center gap-1 text-cyan-300">
                <Layers className="w-3 h-3 text-cyan-400" />
                {selectedRepo.detected_languages?.join(', ') || 'Mixed'}
              </span>
              <span className="text-slate-600">|</span>
              <span className="flex items-center gap-1 text-emerald-300">
                <Network className="w-3 h-3 text-emerald-400" />
                {selectedRepo.ast_node_count || 0} AST nodes
              </span>
            </div>
          )}

          {repos.length > 0 ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700 text-xs text-slate-300">
              <FolderGit2 className="w-3.5 h-3.5 text-indigo-400" />
              <select
                value={selectedRepoId}
                onChange={(e) => setSelectedRepoId(e.target.value)}
                className="bg-transparent text-white font-medium focus:outline-none cursor-pointer"
              >
                {repos.map((r) => (
                  <option key={r.id} value={r.id} className="bg-slate-900 text-white">
                    {r.name} ({r.primary_language || 'Repo'})
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <span className="px-3 py-1 text-[10px] font-mono text-slate-400 bg-slate-800/60 rounded-xl border border-slate-700">
              No Repos Connected
            </span>
          )}

          <button
            onClick={handleClearChat}
            title="Reset Conversation"
            className="p-2 rounded-xl bg-slate-800/70 hover:bg-slate-800 text-slate-400 hover:text-rose-300 border border-slate-700/60 transition-colors cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>

          <span className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider rounded-xl bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Live AST Graph
          </span>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 p-5 rounded-3xl glass-panel border border-gray-800 bg-[#0A0E1A]/80 shadow-inner">
        {messages.map((m, idx) => {
          if (m.isError) {
            return (
              <ErrorBubble
                key={idx}
                message={m.text}
                onRetry={lastInput ? handleRetry : undefined}
              />
            );
          }

          return (
            <div
              key={idx}
              className={`flex gap-3 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {m.sender === 'agent' && (
                <div className="w-8 h-8 rounded-xl bg-indigo-900/60 border border-indigo-500/40 flex items-center justify-center flex-shrink-0 mt-1 shadow-md shadow-indigo-500/10">
                  <Bot className="w-4 h-4 text-indigo-300" />
                </div>
              )}

              <div
                className={`max-w-3xl rounded-2xl p-4 text-xs leading-relaxed ${
                  m.sender === 'user'
                    ? 'bg-indigo-600 text-white rounded-br-none shadow-lg shadow-indigo-600/20 font-medium'
                    : 'bg-gray-900/90 border border-gray-800 text-gray-200 rounded-bl-none shadow-md'
                }`}
              >
                {m.agentName && (
                  <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-gray-800/80">
                    <span className="font-mono font-bold text-[10px] text-indigo-400 uppercase tracking-wider flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />
                      {m.agentName}
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono">{m.time}</span>
                  </div>
                )}
                <FormattedMessage text={m.text} />
              </div>

              {m.sender === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-cyan-900/60 border border-cyan-500/40 flex items-center justify-center flex-shrink-0 mt-1">
                  <User className="w-4 h-4 text-cyan-300" />
                </div>
              )}
            </div>
          );
        })}

        {/* Typing indicator */}
        {isGenerating && (
          <div className="flex items-center gap-2.5 text-xs text-indigo-400 font-mono pl-11 py-2">
            <Sparkles className="w-4 h-4 animate-spin text-indigo-400" />
            <span>ArchitectureCopilot is traversing AST graph &amp; synthesizing architectural solution…</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Suggestion Chips */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 px-1 scrollbar-none">
        <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1 shrink-0">
          <Lightbulb className="w-3 h-3 text-amber-400" /> Quick Ask:
        </span>
        {PROMPT_SUGGESTIONS.map((item, idx) => (
          <button
            key={idx}
            onClick={() => sendMessage(item.text)}
            disabled={isGenerating}
            className="shrink-0 px-3 py-1 rounded-full bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 hover:border-indigo-500/50 text-[11px] text-slate-300 hover:text-white transition-all disabled:opacity-50 cursor-pointer shadow-sm"
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* Input Box */}
      <form onSubmit={handleSend} className="relative flex-shrink-0">
        <input
          id="chat-input"
          type="text"
          placeholder={
            selectedRepo
              ? `Ask about ${selectedRepo.name} (e.g. 'How to resolve circular dependencies?', 'Show blast radius of entry point')`
              : "Ask ArchitectureCopilot anything about codebase architecture, blast radius, SOLID patterns, or refactoring..."
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isGenerating}
          className="w-full pl-5 pr-14 py-4 rounded-2xl bg-gray-900/90 border border-gray-800 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 shadow-xl disabled:opacity-60 transition-colors"
        />
        <button
          id="chat-send-btn"
          type="submit"
          disabled={!input.trim() || isGenerating}
          className="absolute right-3 top-3 p-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white shadow-md shadow-indigo-600/30 transition-all cursor-pointer"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}

