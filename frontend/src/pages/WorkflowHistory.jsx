import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  History, 
  GitBranch, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Cpu,
  Coins,
  ArrowRight,
  Code2,
  FileCode2,
  Loader2,
  AlertTriangle,
  Trash2,
  RefreshCw,
  Radio,
  Square,
  Ban,
  RotateCcw,
  PlusCircle,
  Play,
  FolderGit2
} from 'lucide-react';
import api from '../services/api';
import { useWorkflowStore } from '../stores/workflowStore';
import AgentThoughtStream from '../components/AgentThoughtStream';
import DiffViewer from '../components/DiffViewer';
import ErrorState from '../components/ErrorState';
import { format } from 'date-fns';
import toast from 'react-hot-toast';

const formatDateSafe = (dateStr, formatPattern = 'MMM dd, yyyy, hh:mm a') => {
  if (!dateStr) return 'Recent';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return 'Recent';
    return format(d, formatPattern);
  } catch {
    return 'Recent';
  }
};

export default function WorkflowHistory() {
  const navigate = useNavigate();
  const { 
    initiateNewModernization, 
    setActiveWorkflowId: setStoreActiveWorkflowId,
    setIsExecuting,
    setAwaitingApproval,
    activeWorkflowId,
    cachedRepositories,
    setCachedRepositories
  } = useWorkflowStore();

  const [workflows, setWorkflows] = useState([]);
  const [repositories, setRepositories] = useState(cachedRepositories || []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState(null);
  const [workflowDetails, setWorkflowDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [selectedFileChange, setSelectedFileChange] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [deletingIds, setDeletingIds] = useState(new Set());
  const [stoppingIds, setStoppingIds] = useState(new Set());
  const [resumingIds, setResumingIds] = useState(new Set());

  const fetchWorkflows = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      const [wfRes, repoRes] = await Promise.allSettled([
        api.get('/workflows', { _silent: true }),
        api.get('/repositories', { _silent: true })
      ]);

      if (repoRes.status === 'fulfilled' && repoRes.value?.data) {
        const repoList = Array.isArray(repoRes.value.data) ? repoRes.value.data : [];
        setRepositories(repoList);
        setCachedRepositories(repoList);
      }

      if (wfRes.status === 'fulfilled') {
        const list = Array.isArray(wfRes.value?.data) ? wfRes.value.data : [];
        // Deduplicate by ID
        const uniqueList = Array.from(new Map(list.map(item => [item.id, item])).values());
        setWorkflows(uniqueList);
        
        // Auto-select latest workflow if none is currently selected or current is not in list
        if (uniqueList.length > 0) {
          setSelectedWorkflowId(prev => {
            if (!prev || !uniqueList.some(w => w.id === prev)) {
              return uniqueList[0].id;
            }
            return prev;
          });
        }
      } else if (wfRes.status === 'rejected') {
        throw wfRes.reason;
      }
    } catch (err) {
      if (!isSilent) setError(err);
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, [setCachedRepositories]);

  const fetchWorkflowDetails = useCallback(async (id, isSilent = false) => {
    if (!id) return;
    if (!isSilent) setDetailsLoading(true);
    try {
      const res = await api.get(`/workflows/${id}`, { _silent: true });
      setWorkflowDetails(res.data);
      const changes = res.data?.langgraph_state?.file_changes;
      if (changes && changes.length > 0) {
        setSelectedFileChange(prev => {
          if (prev && changes.some(c => c.file_path === prev.file_path)) {
            return prev;
          }
          return changes[0];
        });
      } else {
        setSelectedFileChange(null);
      }
    } catch (err) {
      console.warn("Failed to fetch workflow details", err);
      if (!isSilent) setWorkflowDetails(null);
    } finally {
      if (!isSilent) setDetailsLoading(false);
    }
  }, []);

  // Mount: Immediate fetch + snappy 2-second polling for instant live updates
  useEffect(() => {
    fetchWorkflows(false);

    const interval = setInterval(() => {
      fetchWorkflows(true);
      if (selectedWorkflowId) {
        fetchWorkflowDetails(selectedWorkflowId, true);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [fetchWorkflows, fetchWorkflowDetails, selectedWorkflowId]);

  // When selected workflow changes, fetch details immediately
  useEffect(() => {
    if (selectedWorkflowId) {
      fetchWorkflowDetails(selectedWorkflowId, false);
    }
  }, [selectedWorkflowId, fetchWorkflowDetails]);

  const handleDeleteWorkflow = async (e, id) => {
    e.stopPropagation();
    if (deletingIds.has(id)) return;
    if (!window.confirm("Are you sure you want to delete this migration history? This action cannot be undone.")) return;
    
    setDeletingIds(prev => new Set(prev).add(id));
    try {
      await api.delete(`/workflows/${id}`);
      setWorkflows(prev => prev.filter(w => w.id !== id));
      if (selectedWorkflowId === id) {
        setSelectedWorkflowId(null);
        setWorkflowDetails(null);
      }
      toast.success("Migration history deleted");
    } catch (err) {
      toast.error("Failed to delete workflow history");
      console.error(err);
    } finally {
      setDeletingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleStopWorkflow = async (e, id) => {
    if (e && e.stopPropagation) e.stopPropagation();
    const targetId = id || selectedWorkflowId;
    if (!targetId) return;
    if (stoppingIds.has(targetId)) return;
    if (!window.confirm("Are you sure you want to stop this running migration?")) return;

    setStoppingIds(prev => new Set(prev).add(targetId));
    try {
      await api.post(`/workflows/${targetId}/cancel`);
      toast.success("Workflow stopped successfully");
      setIsExecuting(false);
      setAwaitingApproval(false);
      setWorkflows(prev => prev.map(w => w.id === targetId ? { ...w, status: 'cancelled' } : w));
      setWorkflowDetails(prev => prev && prev.id === targetId ? { ...prev, status: 'cancelled' } : prev);
      await fetchWorkflows(true);
      if (selectedWorkflowId === targetId) {
        await fetchWorkflowDetails(targetId, true);
      }
    } catch (err) {
      toast.error("Failed to stop workflow");
      console.error(err);
    } finally {
      setStoppingIds(prev => {
        const next = new Set(prev);
        next.delete(targetId);
        return next;
      });
    }
  };

  const handleNewModernization = (repoId = null) => {
    initiateNewModernization(repoId);
    navigate('/migration-studio');
  };

  const handleResumeWorkflow = async (e, id) => {
    if (e) e.stopPropagation();
    if (resumingIds.has(id)) return;

    setResumingIds(prev => new Set(prev).add(id));
    try {
      await api.post(`/workflows/${id}/resume`);
      setStoreActiveWorkflowId(id);
      toast.success("Resuming workflow from last saved checkpoint...");
      navigate(`/migration-studio?workflowId=${id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to resume workflow");
      console.error(err);
    } finally {
      setResumingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleOpenInStudio = (id) => {
    if (!id) return;
    setStoreActiveWorkflowId(id);
    navigate(`/migration-studio?workflowId=${id}`);
  };

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await fetchWorkflows(true);
    if (selectedWorkflowId) {
      await fetchWorkflowDetails(selectedWorkflowId, true);
    }
    setIsRefreshing(false);
    toast.success("Migration history refreshed");
  };

  if (loading && workflows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full mt-24 gap-4 text-indigo-400">
        <Loader2 className="w-8 h-8 animate-spin" />
        <span className="text-sm font-mono tracking-widest uppercase">Loading Migration History…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto pt-10">
        <ErrorState 
          title="History Unavailable"
          message="Failed to load migration history. Please check your backend connection."
          error={error}
          onRetry={() => fetchWorkflows(false)}
        />
      </div>
    );
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" /> Completed
          </span>
        );
      case 'cancelled':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Ban className="w-3.5 h-3.5" /> Cancelled
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <XCircle className="w-3.5 h-3.5" /> Failed
          </span>
        );
      case 'executing':
      case 'planning':
      case 'validating':
      case 'awaiting_approval':
      case 'queued':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse">
            <Radio className="w-3.5 h-3.5 animate-spin" /> {status.replace('_', ' ').toUpperCase()}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-gray-500/10 text-gray-400 border border-gray-500/20">
            <Clock className="w-3.5 h-3.5" /> {status}
          </span>
        );
    }
  };

  const thoughts = workflowDetails?.langgraph_state?.thought_stream || [];
  const fileChanges = workflowDetails?.langgraph_state?.file_changes || [];
  const isSelectedRunning = ['planning', 'executing', 'awaiting_approval', 'queued', 'validating'].includes(workflowDetails?.status);
  const isSelectedResumable = ['cancelled', 'stopped', 'failed', 'awaiting_approval'].includes(workflowDetails?.status);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <History className="w-6 h-6 text-indigo-400" />
          <div>
            <h2 className="text-xl font-bold text-white">Migration History &amp; Audits</h2>
            <p className="text-xs text-gray-400">
              Live inspection of autonomous agent workflow executions, thought transcripts, and AST mutation diffs.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            id="history-new-modernization-btn"
            onClick={() => handleNewModernization()}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-md shadow-indigo-500/20 transition-all cursor-pointer"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>New Modernization</span>
          </button>
          <button
            onClick={handleManualRefresh}
            disabled={isRefreshing}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-900 border border-gray-700 hover:border-gray-600 text-gray-300 text-xs font-medium transition-all cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Main Grid: History List (Left) + Detail View (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
        {/* Left Column: Workflows List */}
        <div className="lg:col-span-4 space-y-3">
          {workflows.length === 0 ? (
            <div className="p-8 rounded-2xl glass-panel border border-gray-800 text-center text-gray-500 text-xs font-mono">
              No migration runs recorded yet. Initiate your first migration in the Studio.
            </div>
          ) : (
            workflows.map((wf) => {
              const isSelected = selectedWorkflowId === wf.id;
              const isDeleting = deletingIds.has(wf.id);
              const isStopping = stoppingIds.has(wf.id);
              const isRunning = ['planning', 'executing', 'awaiting_approval', 'queued', 'validating'].includes(wf.status);
              const repo = Array.isArray(repositories) ? repositories.find(r => r.id === wf.repository_id) : null;
              const repoName = wf.repository_name || (repo ? repo.name : `Repo ${wf.repository_id ? wf.repository_id.slice(0, 6) : 'Unknown'}`);

              return (
                <div
                  key={wf.id}
                  onClick={() => setSelectedWorkflowId(wf.id)}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer relative group ${
                    isSelected
                      ? 'bg-indigo-950/40 border-indigo-500/80 shadow-lg shadow-indigo-500/10'
                      : 'glass-panel border-gray-800 hover:border-gray-700 bg-[#0E1322]/80'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <FolderGit2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                        <span className="text-xs font-bold text-white font-mono truncate max-w-[180px]" title={repoName}>
                          {repoName}
                        </span>
                      </div>
                      <span className="text-[10px] text-gray-400 font-mono ml-6 truncate">
                        {wf.target_framework || 'Modern Architecture'}
                      </span>
                    </div>
                    {getStatusBadge(wf.status)}
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-gray-400 font-mono mt-3 pt-2 border-t border-gray-800/60">
                    <span>
                      {formatDateSafe(wf.created_at)}
                    </span>
                    <div className="flex items-center gap-2">
                      <span>Step {(wf.current_step_index || 0) + 1}/{wf.total_steps || 6}</span>

                      {/* Resume button for resumable workflows */}
                      {['cancelled', 'stopped', 'failed', 'awaiting_approval'].includes(wf.status) && (
                        <button
                          onClick={(e) => handleResumeWorkflow(e, wf.id)}
                          disabled={resumingIds.has(wf.id)}
                          className="text-emerald-400 hover:text-emerald-300 p-1 rounded transition-all inline-flex items-center gap-1"
                          title="Resume this workflow from its last saved checkpoint"
                        >
                          {resumingIds.has(wf.id) ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                          ) : (
                            <RotateCcw className="w-3.5 h-3.5 text-emerald-400" />
                          )}
                        </button>
                      )}

                      {/* Stop Workflow button for running workflows */}
                      {isRunning && (
                        <button
                          onClick={(e) => handleStopWorkflow(e, wf.id)}
                          disabled={isStopping}
                          className="text-rose-400 hover:text-rose-300 p-1 rounded transition-all"
                          title="Stop this running workflow"
                        >
                          {isStopping ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-400" />
                          ) : (
                            <Square className="w-3.5 h-3.5 fill-rose-400" />
                          )}
                        </button>
                      )}

                      {/* Delete button */}
                      <button
                        onClick={(e) => handleDeleteWorkflow(e, wf.id)}
                        disabled={isDeleting}
                        className={`p-1 rounded transition-all ${
                          isDeleting 
                            ? 'opacity-100 cursor-not-allowed text-rose-400' 
                            : 'text-gray-500 hover:text-rose-400 opacity-0 group-hover:opacity-100'
                        }`}
                        title={isDeleting ? "Deleting record…" : "Delete record"}
                      >
                        {isDeleting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-400" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Execution Workspace Inspection */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          {detailsLoading && !workflowDetails ? (
            <div className="h-full flex flex-col items-center justify-center border border-gray-800 rounded-2xl bg-[#0E1322]/90 text-indigo-400 gap-3">
              <Loader2 className="w-6 h-6 animate-spin" />
              <span className="text-xs font-mono tracking-wider">Loading Execution Transcript…</span>
            </div>
          ) : !selectedWorkflowId ? (
            <div className="h-full flex items-center justify-center border border-gray-800 rounded-2xl bg-[#0E1322]/90 text-gray-500 text-xs font-mono">
              Select a migration workflow from the history list to inspect its execution.
            </div>
          ) : (
            <>
              {/* Selected Workflow Repository Header */}
              <div className="p-4 rounded-2xl glass-panel border border-gray-800 bg-[#0E1322]/90 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-md">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-indigo-600/10 border border-indigo-500/30 text-indigo-400">
                    <FolderGit2 className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-bold text-white font-mono">
                        {(Array.isArray(repositories) ? repositories.find(r => r.id === workflowDetails?.repository_id)?.name : null) || workflowDetails?.repository_name || `Repo ${workflowDetails?.repository_id ? workflowDetails.repository_id.slice(0, 8) : 'Unknown'}`}
                      </h3>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-indigo-950/60 text-indigo-300 border border-indigo-800/40">
                        {workflowDetails?.target_framework || 'Modern Architecture'}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-400 font-mono mt-0.5">
                      Workflow ID: <span className="text-gray-300">{workflowDetails?.id ? workflowDetails.id.slice(0, 18) : ''}...</span> · Created: {formatDateSafe(workflowDetails?.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(workflowDetails?.status)}
                </div>
              </div>

              {/* Top Details Action Bar when running */}
              {isSelectedRunning && (
                <div className="p-3.5 rounded-2xl bg-indigo-950/60 border border-indigo-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-xs font-mono text-indigo-200">
                    <Radio className="w-4 h-4 text-indigo-400 animate-pulse" />
                    <span>Workflow is actively executing</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleOpenInStudio(selectedWorkflowId)}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-200 text-xs font-semibold transition-all cursor-pointer"
                      title="View live stream in Migration Studio"
                    >
                      <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Open in Studio</span>
                    </button>
                    <button
                      onClick={(e) => handleStopWorkflow(e, selectedWorkflowId)}
                      disabled={stoppingIds.has(selectedWorkflowId)}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/40 text-rose-200 text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
                    >
                      {stoppingIds.has(selectedWorkflowId) ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Square className="w-3.5 h-3.5 fill-rose-400 text-rose-400" />
                      )}
                      <span>Stop Execution</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Resumable Checkpoint Action Bar for paused/failed workflows */}
              {isSelectedResumable && !isSelectedRunning && (
                <div className="p-3.5 rounded-2xl bg-amber-950/30 border border-amber-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in">
                  <div className="flex items-center gap-2 text-xs font-mono text-amber-200">
                    <RotateCcw className="w-4 h-4 text-amber-400" />
                    <span>Checkpoint saved at Step {(workflowDetails?.current_step_index || 0) + 1}. You can resume execution from where it stopped.</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => handleResumeWorkflow(e, selectedWorkflowId)}
                      disabled={resumingIds.has(selectedWorkflowId)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white text-xs font-semibold shadow-md shadow-emerald-950/40 transition-all cursor-pointer disabled:opacity-50"
                    >
                      {resumingIds.has(selectedWorkflowId) ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="w-3.5 h-3.5" />
                      )}
                      <span>Resume Checkpoint</span>
                    </button>
                    <button
                      onClick={() => handleOpenInStudio(selectedWorkflowId)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-950/60 hover:bg-indigo-900/60 border border-indigo-500/40 text-indigo-200 text-xs font-medium transition-all cursor-pointer"
                      title="Inspect workflow in Migration Studio"
                    >
                      <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Studio</span>
                    </button>
                    <button
                      onClick={() => handleNewModernization(workflowDetails?.repository_id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-medium border border-gray-700 transition-all cursor-pointer"
                    >
                      <PlusCircle className="w-3.5 h-3.5 text-cyan-400" />
                      <span>New Run</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Completed / Inspected non-running action bar */}
              {!isSelectedRunning && !isSelectedResumable && (
                <div className="p-3 rounded-2xl bg-gray-900/60 border border-gray-800 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-mono text-gray-400">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Inspection Mode</span>
                  </div>
                  <button
                    onClick={() => handleOpenInStudio(selectedWorkflowId)}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 text-xs font-medium transition-all cursor-pointer"
                  >
                    <Cpu className="w-3.5 h-3.5" />
                    <span>Open in Migration Studio</span>
                  </button>
                </div>
              )}

              {/* Agent Thought Stream for the selected historical/live workflow */}
              <div className="h-[280px]">
                <AgentThoughtStream 
                  thoughts={thoughts} 
                  isExecuting={isSelectedRunning} 
                  onStopWorkflow={isSelectedRunning ? (e) => handleStopWorkflow(e, selectedWorkflowId) : null}
                  isStopping={stoppingIds.has(selectedWorkflowId)}
                />
              </div>

              {/* Bottom Split: Transformed Files list + Monaco Diff Viewer */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-4 flex-1">
                {/* File List */}
                <div className="md:col-span-4 p-4 rounded-2xl glass-panel border border-gray-800 bg-[#0E1322]/90 flex flex-col">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-gray-300 font-mono mb-3 flex items-center justify-between">
                    <span>Mutated Files</span>
                    <span className="text-[10px] text-indigo-400">{fileChanges.length}</span>
                  </h4>
                  <div className="space-y-2 flex-1 overflow-y-auto max-h-[300px]">
                    {fileChanges.length === 0 ? (
                      <p className="text-xs text-gray-500 py-6 text-center">
                        {isSelectedRunning 
                          ? 'Agent actively formulating AST mutations…' 
                          : 'No file diffs recorded for this run.'}
                      </p>
                    ) : (
                      fileChanges.map((fc) => (
                        <button
                          key={fc.file_path}
                          onClick={() => setSelectedFileChange(fc)}
                          className={`w-full text-left p-2.5 rounded-xl border text-xs font-mono transition-all flex items-center justify-between ${
                            selectedFileChange?.file_path === fc.file_path
                              ? 'bg-indigo-600/20 border-indigo-500 text-indigo-200'
                              : 'bg-gray-900/60 border-gray-800 text-gray-300 hover:border-gray-700'
                          }`}
                        >
                          <span className="truncate">{fc.file_path}</span>
                        </button>
                      ))
                    )}
                  </div>
                </div>

                {/* Diff Viewer */}
                <div className="md:col-span-8 min-h-[350px]">
                  {selectedFileChange || fileChanges.length > 0 ? (
                    <DiffViewer fileChange={selectedFileChange || fileChanges[0]} />
                  ) : (
                    <div className="h-full flex items-center justify-center border border-gray-800 rounded-2xl bg-[#0E1322]/90">
                      <span className="text-gray-500 text-xs font-mono">No diff available for this step.</span>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
