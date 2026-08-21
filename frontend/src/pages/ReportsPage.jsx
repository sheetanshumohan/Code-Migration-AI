import React, { useState } from 'react';
import {
  FileCheck2,
  Lock,
  Clock,
  FileText,
  RefreshCw,
  Download,
  Filter,
  Shield,
  Layers,
  Key,
  GitBranch,
  BarChart2,
  Coins,
  TrendingUp,
  Cpu,
  ExternalLink,
  Eye,
  X,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import ErrorState from '../components/ErrorState';
import toast from 'react-hot-toast';

/** Skeleton shimmer for cards */
function ReportSkeleton() {
  return (
    <div className="p-6 rounded-3xl glass-panel border border-gray-800 space-y-4 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="h-4 bg-gray-700 rounded w-28" />
        <div className="h-5 bg-gray-700 rounded-full w-20" />
      </div>
      <div className="h-6 bg-gray-700 rounded w-48" />
      <div className="h-3 bg-gray-800 rounded w-36" />
      <div className="grid grid-cols-3 gap-2 py-3 border-y border-gray-800/80">
        <div className="h-5 bg-gray-800 rounded" />
        <div className="h-5 bg-gray-800 rounded" />
        <div className="h-5 bg-gray-800 rounded" />
      </div>
      <div className="h-4 bg-gray-800 rounded w-full" />
    </div>
  );
}

const ACTION_COLORS = {
  create:  'bg-emerald-950/80 text-emerald-300 border-emerald-700/60 shadow-sm shadow-emerald-950',
  execute: 'bg-indigo-950/80 text-indigo-300 border-indigo-700/60 shadow-sm shadow-indigo-950',
  approve: 'bg-purple-950/80 text-purple-300 border-purple-700/60 shadow-sm shadow-purple-950',
  update:  'bg-blue-950/80 text-blue-300 border-blue-700/60 shadow-sm shadow-blue-950',
  delete:  'bg-red-950/80 text-red-300 border-red-700/60 shadow-sm shadow-red-950',
  login:   'bg-cyan-950/80 text-cyan-300 border-cyan-700/60 shadow-sm shadow-cyan-950',
  logout:  'bg-gray-900 text-gray-400 border-gray-700',
  sync:    'bg-amber-950/80 text-amber-300 border-amber-700/60 shadow-sm shadow-amber-950',
  default: 'bg-gray-900 text-gray-300 border-gray-700',
};

function actionBadgeClass(action = '') {
  return ACTION_COLORS[action.toLowerCase()] || ACTION_COLORS.default;
}

function getResourceIcon(type = '') {
  const t = type.toLowerCase();
  if (t.includes('repo')) return <GitBranch className="w-4 h-4 text-cyan-400" />;
  if (t.includes('workflow')) return <Layers className="w-4 h-4 text-indigo-400" />;
  if (t.includes('auth') || t.includes('session') || t.includes('user')) return <Key className="w-4 h-4 text-emerald-400" />;
  return <Shield className="w-4 h-4 text-purple-400" />;
}

export default function ReportsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('workflows'); // 'workflows' | 'audits'
  const [filterType, setFilterType] = useState('all');
  const [selectedWorkflowReport, setSelectedWorkflowReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);

  // 1. Fetch summarized workflow reports
  const {
    data: workflowReports = [],
    isLoading: isWorkflowsLoading,
    isError: isWorkflowsError,
    error: workflowsError,
    refetch: refetchWorkflows,
    isFetching: isWorkflowsFetching,
  } = useQuery({
    queryKey: ['workflowReports'],
    queryFn: async () => {
      const res = await api.get('/reports/workflows', { _silent: true });
      return res.data;
    },
    refetchInterval: 15000,
  });

  // 2. Fetch cryptographic audit logs
  const {
    data: auditLogs = [],
    isLoading: isAuditsLoading,
    isError: isAuditsError,
    error: auditsError,
    refetch: refetchAudits,
    isFetching: isAuditsFetching,
  } = useQuery({
    queryKey: ['auditLogs'],
    queryFn: async () => {
      const res = await api.get('/reports/audit-logs', { _silent: true });
      return res.data;
    },
    refetchInterval: 15000,
  });

  const filteredLogs = (auditLogs || []).filter((log) => {
    if (filterType === 'all') return true;
    if (filterType === 'repository') return log.resource_type.toLowerCase().includes('repo');
    if (filterType === 'workflow') return log.resource_type.toLowerCase().includes('workflow');
    if (filterType === 'auth') return log.resource_type.toLowerCase().includes('auth') || log.resource_type.toLowerCase().includes('session');
    return true;
  });

  const handleOpenDetailedReport = async (wfId) => {
    setReportLoading(true);
    try {
      const res = await api.get(`/reports/workflows/${wfId}`);
      setSelectedWorkflowReport(res.data);
    } catch (err) {
      toast.error('Failed to load detailed migration report');
    } finally {
      setReportLoading(false);
    }
  };

  const handleExportJson = () => {
    const dataToExport = activeTab === 'workflows' ? workflowReports : auditLogs;
    if (!dataToExport || dataToExport.length === 0) {
      toast.error('No report data to export');
      return;
    }
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(dataToExport, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `${activeTab}_report_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    toast.success('Report exported as JSON');
  };

  const isCurrentFetching = activeTab === 'workflows' ? isWorkflowsFetching : isAuditsFetching;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="p-6 rounded-3xl glass-panel border border-gray-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <FileCheck2 className="w-5 h-5 text-emerald-400" />
            <h2 className="text-xl font-bold text-white">Migration Reports &amp; Cryptographic Audit Trail</h2>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Track token consumption, cost telemetry, AST transformation quality gates, and SHA-256 tamper-evident logs.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleExportJson}
            disabled={activeTab === 'workflows' ? workflowReports.length === 0 : auditLogs.length === 0}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed border border-gray-700 text-gray-300 text-xs font-medium transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-indigo-400" />
            Export JSON
          </button>
          <button
            onClick={() => {
              if (activeTab === 'workflows') refetchWorkflows();
              else refetchAudits();
            }}
            disabled={isCurrentFetching}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 text-xs font-medium transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isCurrentFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Main Section Switcher Tabs */}
      <div className="flex items-center justify-between border-b border-gray-800/80 pb-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab('workflows')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'workflows'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Migration &amp; Telemetry Reports</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-white/20 text-[10px] font-mono">
              {workflowReports.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('audits')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'audits'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
            }`}
          >
            <Lock className="w-4 h-4" />
            <span>Cryptographic Audit Trail</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-white/20 text-[10px] font-mono">
              {auditLogs.length}
            </span>
          </button>
        </div>

        {activeTab === 'audits' && (
          <div className="flex items-center gap-2 overflow-x-auto">
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Filter:
            </span>
            {[
              { id: 'all', label: 'All' },
              { id: 'repository', label: 'Repos' },
              { id: 'workflow', label: 'Workflows' },
              { id: 'auth', label: 'Auth' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setFilterType(tab.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  filterType === tab.id
                    ? 'bg-indigo-600 text-white font-semibold'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── TAB 1: WORKFLOW MIGRATION REPORTS ────────────────────────────── */}
      {activeTab === 'workflows' && (
        <div className="space-y-6">
          {isWorkflowsLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => <ReportSkeleton key={i} />)}
            </div>
          )}

          {isWorkflowsError && (
            <ErrorState
              title="Reports Unavailable"
              message={workflowsError?.response?.data?.detail || 'Failed to fetch migration reports.'}
              error={workflowsError}
              onRetry={refetchWorkflows}
            />
          )}

          {!isWorkflowsLoading && !isWorkflowsError && workflowReports.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 gap-4 text-center border border-dashed border-gray-800 rounded-3xl bg-gray-900/20">
              <FileText className="w-12 h-12 text-gray-700" />
              <h3 className="text-lg font-bold text-gray-300">No Migration Reports Yet</h3>
              <p className="text-sm text-gray-500 max-w-sm">
                Run an autonomous modernization workflow in the Migration Studio to generate comprehensive AST reports, token telemetries, and quality gate logs.
              </p>
              <button
                onClick={() => navigate('/migration-studio')}
                className="mt-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors cursor-pointer"
              >
                Start Migration Workflow
              </button>
            </div>
          )}

          {!isWorkflowsLoading && !isWorkflowsError && workflowReports.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {workflowReports.map((wf) => {
                const isCompleted = wf.status === 'completed';
                const isFailed = wf.status === 'failed';

                return (
                  <div
                    key={wf.workflow_id}
                    className="p-6 rounded-3xl glass-panel glass-panel-hover border border-gray-800 space-y-4 flex flex-col justify-between transition-all hover:border-gray-700"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono text-indigo-400 font-semibold truncate max-w-[140px]" title={wf.workflow_id}>
                          {wf.workflow_id.slice(0, 8)}…
                        </span>
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                          isCompleted
                            ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60'
                            : isFailed
                            ? 'bg-rose-950/80 text-rose-300 border-rose-700/60'
                            : 'bg-indigo-950/80 text-indigo-300 border-indigo-700/60 animate-pulse'
                        }`}>
                          {wf.status}
                        </span>
                      </div>

                      <div>
                        <h3 className="text-base font-bold text-white truncate" title={wf.repository_name}>
                          {wf.repository_name}
                        </h3>
                        <p className="text-xs text-indigo-300 mt-0.5 font-medium">
                          {wf.workflow_type?.replace(/_/g, ' ')} → <span className="text-cyan-300">{wf.target_framework}</span>
                        </p>
                      </div>

                      {/* Telemetry Metrics Bar */}
                      <div className="grid grid-cols-3 gap-2 py-2.5 px-3 bg-gray-900/70 rounded-2xl border border-gray-800/80 text-center font-mono">
                        <div>
                          <p className="text-[9px] text-gray-500 uppercase">Tokens</p>
                          <p className="text-xs font-bold text-purple-300">
                            {wf.total_tokens ? Number(wf.total_tokens).toLocaleString() : '0'}
                          </p>
                        </div>
                        <div>
                          <p className="text-[9px] text-gray-500 uppercase">Est. Cost</p>
                          <p className="text-xs font-bold text-emerald-400">
                            ${Number(wf.total_cost_usd || 0).toFixed(4)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[9px] text-gray-500 uppercase">Progress</p>
                          <p className="text-xs font-bold text-cyan-300">
                            Step {wf.current_step_index}/{wf.total_steps || 5}
                          </p>
                        </div>
                      </div>

                      <div className="text-[11px] text-gray-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>Created {new Date(wf.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short', hour12: true })}</span>
                      </div>
                    </div>

                    <div className="pt-3 border-t border-gray-800/80 flex items-center justify-between gap-2">
                      <button
                        onClick={() => handleOpenDetailedReport(wf.workflow_id)}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 text-xs font-semibold transition-colors cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>View Report</span>
                      </button>
                      <button
                        onClick={() => navigate(`/migration-studio?workflowId=${wf.workflow_id}`)}
                        className="inline-flex items-center justify-center p-2 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 hover:text-white transition-colors cursor-pointer"
                        title="Open in Migration Studio"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: CRYPTOGRAPHIC AUDIT TRAIL ──────────────────────────────── */}
      {activeTab === 'audits' && (
        <div className="space-y-6">
          {isAuditsLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {[1, 2, 3, 4].map((i) => <ReportSkeleton key={i} />)}
            </div>
          )}

          {isAuditsError && (
            <ErrorState
              title="Audit Logs Unavailable"
              message={auditsError?.response?.data?.detail || 'Failed to fetch cryptographic audit logs.'}
              error={auditsError}
              onRetry={refetchAudits}
            />
          )}

          {!isAuditsLoading && !isAuditsError && filteredLogs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 gap-4 text-center border border-dashed border-gray-800 rounded-3xl bg-gray-900/20">
              <FileText className="w-12 h-12 text-gray-700" />
              <h3 className="text-lg font-bold text-gray-300">No Audit Events Found</h3>
              <p className="text-sm text-gray-500 max-w-sm">
                Cryptographic audit logs are automatically recorded when you connect repositories, trigger migration workflows, or log into the platform.
              </p>
            </div>
          )}

          {!isAuditsLoading && !isAuditsError && filteredLogs.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {filteredLogs.map((log) => {
                const meta = log.metadata || {};
                const detailText =
                  meta.repo_name ||
                  meta.workflow_type ||
                  meta.email ||
                  meta.target_framework ||
                  meta.provider ||
                  null;

                return (
                  <div
                    key={log.id}
                    className="p-6 rounded-3xl glass-panel glass-panel-hover border border-gray-800 space-y-4 transition-all hover:border-gray-700"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getResourceIcon(log.resource_type)}
                        <span className="text-xs font-mono font-bold text-indigo-400">
                          {log.id.slice(0, 8)}…
                        </span>
                      </div>
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${actionBadgeClass(log.action)}`}>
                        {log.action}
                      </span>
                    </div>

                    <div>
                      <h3 className="text-base font-bold text-white capitalize flex items-center gap-2">
                        {log.resource_type.replace('_', ' ')}
                        {detailText && (
                          <span className="text-xs font-normal text-indigo-300 font-mono bg-indigo-950/60 px-2 py-0.5 rounded-md border border-indigo-800/40">
                            {detailText}
                          </span>
                        )}
                      </h3>
                      <p className="text-xs text-gray-500 flex items-center gap-1 mt-1">
                        <Clock className="w-3.5 h-3.5" />
                        {new Date(log.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short', hour12: true })}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-2 py-2 border-y border-gray-800/80 text-center">
                      <div>
                        <p className="text-[10px] text-gray-500 uppercase">Resource ID</p>
                        <p className="text-xs font-bold text-white font-mono truncate px-2" title={log.resource_id}>
                          {log.resource_id || '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-gray-500 uppercase">Client IP</p>
                        <p className="text-xs font-bold text-cyan-400 font-mono">
                          {log.ip_address || '127.0.0.1'}
                        </p>
                      </div>
                    </div>

                    {Object.keys(meta).length > 0 && (
                      <div className="text-[11px] text-gray-400 bg-gray-900/60 rounded-xl p-2.5 border border-gray-800/80 space-y-1">
                        {Object.entries(meta).map(([key, val]) => (
                          <div key={key} className="flex justify-between items-center">
                            <span className="text-gray-500 capitalize">{key.replace('_', ' ')}:</span>
                            <span className="font-mono text-gray-300 truncate max-w-[200px]" title={String(val)}>
                              {String(val)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-1">
                      <span className="text-xs text-gray-400 flex items-center gap-1.5">
                        <Lock className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="font-mono text-[10px] text-gray-400 truncate max-w-[260px]" title={log.integrity_hash}>
                          SHA-256: {log.integrity_hash || 'N/A'}
                        </span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── MODAL: DETAILED MIGRATION REPORT VIEWER ───────────────────────── */}
      {selectedWorkflowReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-3xl glass-panel border border-gray-700 shadow-2xl bg-surface overflow-hidden">
            {/* Modal Header */}
            <div className="p-6 border-b border-gray-800 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <FileText className="w-5 h-5 text-indigo-400" />
                  <span>Migration Audit Report</span>
                </h3>
                <p className="text-xs text-gray-400 font-mono mt-0.5">
                  Workflow ID: {selectedWorkflowReport.workflow_id}
                </p>
              </div>
              <button
                onClick={() => setSelectedWorkflowReport(null)}
                className="p-2 rounded-xl text-gray-400 hover:text-white hover:bg-gray-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto space-y-6 font-sans">
              {/* Telemetry Summary Bar */}
              {selectedWorkflowReport.cost_metrics && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-2xl bg-gray-900/80 border border-gray-800 font-mono text-center">
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase block">Total Tokens</span>
                    <span className="text-sm font-bold text-purple-400">
                      {Number(selectedWorkflowReport.cost_metrics.total_tokens || 0).toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase block">AI Cost</span>
                    <span className="text-sm font-bold text-emerald-400">
                      ${Number(selectedWorkflowReport.cost_metrics.total_cost_usd || 0).toFixed(4)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase block">Status</span>
                    <span className="text-sm font-bold text-indigo-400 capitalize">
                      {selectedWorkflowReport.status}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase block">Target Stack</span>
                    <span className="text-sm font-bold text-cyan-300">
                      {selectedWorkflowReport.target_framework || 'Modern'}
                    </span>
                  </div>
                </div>
              )}

              {/* Markdown Document Content */}
              <div className="p-5 rounded-2xl bg-gray-950/60 border border-gray-800 text-gray-200 text-xs font-mono whitespace-pre-wrap leading-relaxed">
                {selectedWorkflowReport.report_markdown}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-800 flex items-center justify-between bg-gray-900/40">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(selectedWorkflowReport.report_markdown);
                  toast.success('Report markdown copied to clipboard');
                }}
                className="px-4 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-semibold transition-colors cursor-pointer"
              >
                Copy Markdown
              </button>
              <button
                onClick={() => navigate(`/migration-studio?workflowId=${selectedWorkflowReport.workflow_id}`)}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors cursor-pointer"
              >
                Open in Migration Studio
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
