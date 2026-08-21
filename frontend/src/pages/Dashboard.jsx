import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Cpu,
  GitPullRequest,
  ShieldCheck,
  Sparkles,
  Zap,
  Layers,
  GitBranch,
  BarChart3,
  PlusCircle,
  Coins,
  FileText,
  ArrowRight,
  TrendingUp,
  CheckCircle2,
  Clock,
  RotateCcw,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useTelemetry, useKpis } from '../services/useTelemetry';
import { useWorkflowStore } from '../stores/workflowStore';
import ErrorState from '../components/ErrorState';

/** Skeleton shimmer card for loading state */
function KpiSkeleton() {
  return (
    <div className="p-6 rounded-2xl glass-panel border border-gray-800 space-y-3 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="h-3 bg-gray-700 rounded w-24" />
        <div className="w-9 h-9 rounded-lg bg-gray-700" />
      </div>
      <div className="h-7 bg-gray-700 rounded w-16" />
      <div className="h-2.5 bg-gray-800 rounded w-32" />
    </div>
  );
}

const formatLocalTime = (isoString, fallback) => {
  if (!isoString) return fallback || 'Recent';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return fallback || isoString;
    return d.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return fallback || isoString;
  }
};

const formatShortTime = (isoString, fallback) => {
  if (!isoString) return fallback || '00:00 AM';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return fallback || isoString;
    return d.toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return fallback || isoString;
  }
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { initiateNewModernization } = useWorkflowStore();
  const [chartMetric, setChartMetric] = useState('tokens'); // 'tokens' | 'cost'

  const {
    data: rawTelemetryData = [],
    isLoading: telemetryLoading,
    isError: telemetryError,
    error: telemetryErr,
    refetch: refetchTelemetry,
  } = useTelemetry();

  const {
    data: kpiData,
    isLoading: kpiLoading,
    isError: kpiError,
    error: kpiErr,
    refetch: refetchKpis,
  } = useKpis();

  const telemetryData = React.useMemo(() => {
    return (rawTelemetryData || []).map((d) => ({
      ...d,
      displayTime: d.timestamp ? formatLocalTime(d.timestamp, d.time) : d.time,
      displayTimeShort: d.timestamp ? formatShortTime(d.timestamp, d.time_short) : d.time_short,
    }));
  }, [rawTelemetryData]);

  const isLoading = telemetryLoading || kpiLoading;
  const isError   = telemetryError   || kpiError;

  if (isError) {
    return (
      <div className="mt-8">
        <ErrorState
          title="Dashboard Unavailable"
          message={
            (telemetryErr || kpiErr)?.response?.data?.detail ||
            'Failed to fetch telemetry and KPI metrics. The service may be offline.'
          }
          error={telemetryErr || kpiErr}
          onRetry={() => { refetchTelemetry(); refetchKpis(); }}
        />
      </div>
    );
  }

  const activeWorkflows = kpiData?.active_workflows ?? 0;
  const astNodes        = kpiData?.ast_nodes        ?? 0;
  const generatedPrs    = kpiData?.generated_prs    ?? 0;
  const totalTokens     = kpiData?.total_tokens     ?? 0;
  const totalCostUsd    = kpiData?.total_cost_usd   ?? 0;
  const sandboxScore    = kpiData?.sandbox_score    ?? null;
  const totalRepos      = kpiData?.total_repositories ?? 0;

  const hasWorkflowData = telemetryData.length > 0;

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Top Banner */}
      <div className="relative rounded-3xl p-8 overflow-hidden glass-panel border border-indigo-500/20 bg-gradient-to-r from-indigo-950/40 via-surface to-background shadow-2xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-900/60 border border-indigo-500/30 text-indigo-300 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Multi-Agent Autonomous Modernization Platform</span>
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight text-white font-sans">
              Autonomous Software Engineering Cockpit
            </h1>
            <p className="text-sm text-gray-400 leading-relaxed">
              Refactor legacy codebases, execute zero-downtime framework migrations, and generate AST-verified pull requests with mathematical precision.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              id="new-modernization-dashboard-btn"
              onClick={() => {
                initiateNewModernization();
                navigate('/migration-studio');
              }}
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white font-semibold text-xs shadow-lg shadow-indigo-500/25 transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
            >
              <PlusCircle className="w-4 h-4" />
              <span>New Modernization</span>
            </button>
            <button
              id="launch-migration-btn"
              onClick={() => navigate('/repositories')}
              className="inline-flex items-center gap-2 px-4 py-3 rounded-xl bg-gray-900/80 hover:bg-gray-800 border border-gray-700 text-gray-200 hover:text-white font-medium text-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
            >
              <Zap className="w-4 h-4 text-amber-400" />
              <span>Connect Repo</span>
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {/* Active Workflows */}
        {kpiLoading ? <KpiSkeleton /> : (
          <div className="p-5 rounded-2xl glass-panel glass-panel-hover border border-gray-800 space-y-2">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-semibold uppercase tracking-wider">Active Pipelines</span>
              <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400">
                <Cpu className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white font-mono">{activeWorkflows}</span>
              <span className={`text-[10px] font-semibold ${activeWorkflows > 0 ? 'text-emerald-400' : 'text-gray-500'}`}>
                {activeWorkflows > 0 ? 'Running' : 'Idle'}
              </span>
            </div>
            <p className="text-[10px] text-gray-500 truncate">Concurrent worker jobs</p>
          </div>
        )}

        {/* AST Nodes */}
        {kpiLoading ? <KpiSkeleton /> : (
          <div className="p-5 rounded-2xl glass-panel glass-panel-hover border border-gray-800 space-y-2">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-semibold uppercase tracking-wider">AST Nodes</span>
              <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400">
                <Layers className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white font-mono">{astNodes.toLocaleString()}</span>
              <span className={`text-[10px] font-semibold ${astNodes > 0 ? 'text-cyan-400' : 'text-gray-500'}`}>
                {totalRepos} Repos
              </span>
            </div>
            <p className="text-[10px] text-gray-500 truncate">Classes, methods, call trees</p>
          </div>
        )}

        {/* Generated PRs / Migrations */}
        {kpiLoading ? <KpiSkeleton /> : (
          <div className="p-5 rounded-2xl glass-panel glass-panel-hover border border-gray-800 space-y-2">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-semibold uppercase tracking-wider">Completed PRs</span>
              <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                <GitPullRequest className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white font-mono">{generatedPrs}</span>
              <span className={`text-[10px] font-semibold ${generatedPrs > 0 ? 'text-emerald-400' : 'text-gray-500'}`}>
                {generatedPrs > 0 ? 'Delivered' : 'None yet'}
              </span>
            </div>
            <p className="text-[10px] text-gray-500 truncate">Modernized repositories</p>
          </div>
        )}

        {/* Sandbox Pass Rate */}
        {kpiLoading ? <KpiSkeleton /> : (
          <div className="p-5 rounded-2xl glass-panel glass-panel-hover border border-gray-800 space-y-2">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-semibold uppercase tracking-wider">Quality Gate</span>
              <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400">
                <ShieldCheck className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white font-mono">
                {sandboxScore !== null ? `${sandboxScore}%` : '100%'}
              </span>
              <span className="text-[10px] font-semibold text-emerald-400">Verified</span>
            </div>
            <p className="text-[10px] text-gray-500 truncate">AST &amp; regression pass rate</p>
          </div>
        )}

        {/* Total LLM Tokens */}
        {kpiLoading ? <KpiSkeleton /> : (
          <div className="p-5 rounded-2xl glass-panel glass-panel-hover border border-gray-800 space-y-2">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-semibold uppercase tracking-wider">LLM Tokens</span>
              <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400">
                <TrendingUp className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white font-mono">
                {totalTokens > 0 ? `${(totalTokens / 1000).toFixed(1)}k` : '0'}
              </span>
              <span className="text-[10px] font-semibold text-purple-400">Tokens</span>
            </div>
            <p className="text-[10px] text-gray-500 truncate">Total processed by agents</p>
          </div>
        )}

        {/* Estimated AI Cost */}
        {kpiLoading ? <KpiSkeleton /> : (
          <div className="p-5 rounded-2xl glass-panel glass-panel-hover border border-gray-800 space-y-2">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-semibold uppercase tracking-wider">AI Spend</span>
              <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                <Coins className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white font-mono">
                ${Number(totalCostUsd).toFixed(3)}
              </span>
              <span className="text-[10px] font-semibold text-emerald-400">USD</span>
            </div>
            <p className="text-[10px] text-gray-500 truncate">Cumulative pipeline cost</p>
          </div>
        )}
      </div>

      {/* LLM Token Consumption & Cost Telemetry Chart */}
      <div className="p-6 rounded-3xl glass-panel border border-gray-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-white">LLM Token Consumption &amp; Cost Telemetry</h3>
            <p className="text-xs text-gray-400">Real-time telemetry tracking across migration pipelines</p>
          </div>
          <div className="flex items-center gap-2 bg-gray-900/80 p-1 rounded-xl border border-gray-800">
            <button
              onClick={() => setChartMetric('tokens')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all cursor-pointer ${
                chartMetric === 'tokens'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Tokens ({telemetryData.reduce((acc, d) => acc + (d.tokens || 0), 0).toLocaleString()})
            </button>
            <button
              onClick={() => setChartMetric('cost')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all cursor-pointer ${
                chartMetric === 'cost'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Cost ($ {telemetryData.reduce((acc, d) => acc + (d.cost || 0), 0).toFixed(3)})
            </button>
          </div>
        </div>

        {telemetryLoading ? (
          <div className="h-64 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : !hasWorkflowData ? (
          <div className="h-64 flex flex-col items-center justify-center gap-3 text-center border border-dashed border-gray-800 rounded-2xl bg-gray-900/20">
            <BarChart3 className="w-10 h-10 text-gray-700" />
            <p className="text-sm font-semibold text-gray-400">No workflow telemetry yet</p>
            <p className="text-xs text-gray-600 max-w-xs">
              Run your first migration workflow to start tracking LLM token consumption and cost metrics.
            </p>
            <button
              onClick={() => navigate('/migration-studio')}
              className="mt-2 px-4 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-400 text-xs font-semibold transition-colors cursor-pointer"
            >
              Start First Migration
            </button>
          </div>
        ) : (
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={telemetryData}>
                <defs>
                  <linearGradient id="tokenGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={chartMetric === 'tokens' ? '#6366F1' : '#10B981'} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={chartMetric === 'tokens' ? '#6366F1' : '#10B981'} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="displayTimeShort" stroke="#4B5563" fontSize={11} />
                <YAxis stroke="#4B5563" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#111827',
                    borderColor: '#374151',
                    borderRadius: '12px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                  formatter={(value) => [
                    chartMetric === 'tokens' ? `${Number(value).toLocaleString()} tokens` : `$${Number(value).toFixed(4)}`,
                    chartMetric === 'tokens' ? 'Tokens' : 'Cost (USD)',
                  ]}
                  labelFormatter={(label, payload) => {
                    const item = payload?.[0]?.payload;
                    return item ? `${item.repo_name} · ${item.target_framework} (${item.displayTime})` : label;
                  }}
                />
                <Area
                  type="monotone"
                  dataKey={chartMetric}
                  stroke={chartMetric === 'tokens' ? '#6366F1' : '#10B981'}
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#tokenGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Recent Telemetry & Migration History Quick List */}
      {hasWorkflowData && (
        <div className="p-6 rounded-3xl glass-panel border border-gray-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                Recent Migration Telemetry &amp; Runs (Latest 5)
              </h3>
            </div>
            <button
              onClick={() => navigate('/reports')}
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium transition-colors cursor-pointer"
            >
              <span>View All Reports &amp; Audits</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 uppercase tracking-wider text-[10px]">
                  <th className="pb-3 font-semibold">Repository</th>
                  <th className="pb-3 font-semibold">Target Architecture</th>
                  <th className="pb-3 font-semibold">Tokens</th>
                  <th className="pb-3 font-semibold">Cost</th>
                  <th className="pb-3 font-semibold">Status</th>
                  <th className="pb-3 font-semibold text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {[...telemetryData].reverse().slice(0, 5).map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-900/40 transition-colors">
                    <td className="py-3 text-gray-200 font-semibold">{row.repo_name}</td>
                    <td className="py-3 text-indigo-300">{row.target_framework}</td>
                    <td className="py-3 text-purple-300 font-bold">{row.tokens.toLocaleString()}</td>
                    <td className="py-3 text-emerald-400">${Number(row.cost).toFixed(4)}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                        row.status === 'completed' 
                          ? 'bg-emerald-950/60 border-emerald-700/60 text-emerald-300'
                          : row.status === 'failed'
                          ? 'bg-rose-950/60 border-rose-700/60 text-rose-300'
                          : 'bg-indigo-950/60 border-indigo-700/60 text-indigo-300 animate-pulse'
                      }`}>
                        {row.status}
                      </span>
                    </td>
                    <td className="py-3 text-gray-400 text-right">{row.displayTime || row.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
