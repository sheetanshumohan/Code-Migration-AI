import React, { useEffect, useRef } from 'react';
import { BrainCircuit, CheckCircle2, Coins, Loader2, Sparkles, StopCircle, Zap } from 'lucide-react';

export default function AgentThoughtStream({ 
  thoughts = [], 
  isExecuting = false, 
  onStopWorkflow = null, 
  isStopping = false,
  liveTokens = 0,
  liveCost = 0.0,
}) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thoughts]);

  const formatTimestamp = (ts) => {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      return isNaN(d.getTime()) 
        ? '' 
        : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true });
    } catch {
      return '';
    }
  };

  return (
    <div className="flex flex-col h-full rounded-2xl glass-panel border border-gray-800 bg-[#0E1322]/90 overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between px-4 py-3 bg-gray-900/80 border-b border-gray-800 gap-2">
        <div className="flex items-center gap-2">
          <BrainCircuit className="w-4 h-4 text-indigo-400 animate-pulse" />
          <span className="text-xs font-semibold tracking-wide text-gray-200 uppercase font-mono">
            Autonomous Agent Thought Stream
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Live Telemetry Pill */}
          {liveTokens > 0 && (
            <div className="flex items-center gap-2 px-2.5 py-0.5 rounded-lg bg-indigo-950/80 border border-indigo-500/30 text-[11px] font-mono">
              <span className="text-purple-300 font-bold flex items-center gap-1">
                <Zap className="w-3 h-3 text-purple-400" />
                {liveTokens.toLocaleString()} tok
              </span>
              <span className="text-gray-500">·</span>
              <span className="text-emerald-400 font-bold flex items-center gap-1">
                <Coins className="w-3 h-3 text-emerald-400" />
                ${Number(liveCost).toFixed(4)}
              </span>
            </div>
          )}

          {isExecuting ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-[11px] text-cyan-400 font-mono">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Reasoning...</span>
              </div>
              {onStopWorkflow && (
                <button
                  type="button"
                  onClick={onStopWorkflow}
                  disabled={isStopping}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/40 text-rose-200 text-[11px] font-mono font-medium transition-all cursor-pointer disabled:opacity-50"
                  title="Stop workflow execution"
                >
                  <StopCircle className="w-3 h-3 text-rose-400" />
                  <span>{isStopping ? 'Stopping...' : 'Stop'}</span>
                </button>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-mono">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Engine Ready</span>
            </div>
          )}
        </div>
      </div>

      {/* Thought Log Body */}
      <div
        ref={scrollRef}
        className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-3.5 scroll-smooth"
      >
        {thoughts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 py-12">
            <Sparkles className="w-8 h-8 text-gray-600 mb-2 opacity-50" />
            <p>Agent thought feed ready. Select a repository to initiate modernization.</p>
          </div>
        ) : (
          thoughts.map((t, idx) => {
            const timeStr = formatTimestamp(t.timestamp) || (t._clientTime ? formatTimestamp(t._clientTime) : '');
            return (
              <div
                key={t.id || `${t.agent}-${idx}`}
                className="p-3 rounded-xl bg-gray-900/60 border border-gray-800/80 hover:border-indigo-500/30 transition-all space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-indigo-950 text-indigo-300 border border-indigo-800/60">
                    {t.agent || 'Orchestrator'}
                  </span>
                  {timeStr && (
                    <span className="text-[10px] text-gray-500 font-sans">
                      {timeStr}
                    </span>
                  )}
                </div>
                <p className="text-gray-300 leading-relaxed pl-1">{t.thought}</p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
