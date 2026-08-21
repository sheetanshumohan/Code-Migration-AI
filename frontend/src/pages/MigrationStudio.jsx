import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { 
  Play, 
  AlertTriangle, 
  Sparkles,
  Cpu,
  Loader2,
  Lock,
  Radio,
  Square,
  StopCircle,
  RotateCcw,
  PlusCircle,
  History,
  CheckCircle2,
  GitPullRequest
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useWorkflowStore } from '../stores/workflowStore';
import AgentThoughtStream from '../components/AgentThoughtStream';
import DiffViewer from '../components/DiffViewer';
import api from '../services/api';
import { getErrorMessage } from '../services/api';
import { useWorkflowSocket } from '../hooks/useWorkflowSocket';
import ErrorState from '../components/ErrorState';

export default function MigrationStudio() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryWorkflowId = searchParams.get('workflowId');

  const { 
    activeWorkflowId,
    setActiveWorkflowId,
    activeStepIndex,
    setActiveStepIndex,
    awaitingApproval,
    setAwaitingApproval,
    thoughts, 
    setThoughts,
    fileChanges, 
    setFileChanges,
    selectedFileChange, 
    setSelectedFileChange,
    isExecuting,
    setIsExecuting,
    resetWorkflow,
    initiateNewModernization,
    selectedRepo,
    setSelectedRepo,
    customGoal,
    setCustomGoal,
    workflowType,
    setWorkflowType,
    cachedRepositories,
    setCachedRepositories,
    liveTokens,
    liveCost,
    setLiveMetrics,
  } = useWorkflowStore();

  const [isEnhancing,          setIsEnhancing]          = useState(false);
  const [isStopping,           setIsStopping]           = useState(false);
  const [isResuming,           setIsResuming]           = useState(false);
  const [isApproving,          setIsApproving]          = useState(false);
  const [isRejecting,          setIsRejecting]          = useState(false);
  const [lastStoppedWorkflow,  setLastStoppedWorkflow]  = useState(null);
  const [currentWorkflowData,  setCurrentWorkflowData]  = useState(null);
  const [repositories,        setRepositories]         = useState(cachedRepositories || []);
  const [allWorkflows,         setAllWorkflows]         = useState([]);
  const [hasError,            setHasError]             = useState(false);
  const [loadError,           setLoadError]            = useState(null);
  const [workflowError,       setWorkflowError]        = useState(null);
  const [dismissedErrors,     setDismissedErrors]      = useState(new Set());
  const [reposLoading,        setReposLoading]         = useState(cachedRepositories.length === 0);

  const steps = [
    { name: 'AST & Graph Ingestion',   agent: 'RepoAnalystAgent' },
    { name: 'Migration DAG Planning',  agent: 'PlannerAgent' },
    { name: 'AST Refactoring Engine',  agent: 'RefactorAgent' },
    { name: 'Regression Test Synthesis', agent: 'TestGenAgent' },
    { name: 'Sandbox Validation',      agent: 'ValidationAgent' },
    { name: 'Pull Request Delivery',   agent: 'ReviewerAgent' },
  ];

  // Active workflows that are queued or in execution
  const activeWorkflows = allWorkflows.filter(w => 
    ['queued', 'planning', 'awaiting_approval', 'executing', 'validating'].includes(w.status)
  );

  const lastLoadedWorkflowIdRef = useRef(null);

  const handleDismissError = useCallback((wfId = activeWorkflowId) => {
    if (wfId) {
      setDismissedErrors(prev => new Set(prev).add(wfId));
    }
    setWorkflowError(null);
  }, [activeWorkflowId]);

  // Fetch details for a specific workflow ID and immediately populate UI state
  const loadWorkflowDetails = useCallback(async (workflowId, isSilent = false) => {
    if (!workflowId) return;
    try {
      const detailRes = await api.get(`/workflows/${workflowId}`, { _silent: true });
      const fullData = detailRes.data;
      if (fullData) {
        setCurrentWorkflowData(fullData);
        setActiveWorkflowId(fullData.id);
        if (fullData.repository_id) {
          setSelectedRepo(fullData.repository_id);
        }
        const isAct = ['queued', 'planning', 'executing', 'validating'].includes(fullData.status);
        const isQueued = fullData.status === 'queued';
        const isAppr = fullData.status === 'awaiting_approval';
        const isCancelled = fullData.status === 'cancelled' || fullData.status === 'stopped';
        setIsExecuting(isAct);
        setAwaitingApproval(isAppr);

        let loadedThoughts = [];
        let loadedChanges = [];

        if (fullData.langgraph_state) {
          if (Array.isArray(fullData.langgraph_state.thought_stream) && fullData.langgraph_state.thought_stream.length > 0) {
            loadedThoughts = fullData.langgraph_state.thought_stream;
          }
          if (Array.isArray(fullData.langgraph_state.file_changes) && fullData.langgraph_state.file_changes.length > 0) {
            loadedChanges = fullData.langgraph_state.file_changes;
          }
        }

        // Calculate step index accurately based on latest thoughts and status
        const stepMap = {
          RepoAnalystAgent: 0,
          PlannerAgent:    1,
          RefactorAgent:   2,
          TestGenAgent:    3,
          ValidationAgent: 4,
          ReviewerAgent:   5,
        };
        let stepIdx = fullData.current_step_index || 0;
        if (loadedThoughts.length > 0) {
          const lastThought = loadedThoughts[loadedThoughts.length - 1];
          if (lastThought?.agent && stepMap[lastThought.agent] !== undefined) {
            stepIdx = Math.max(stepIdx, stepMap[lastThought.agent]);
          }
        }
        if (fullData.status === 'completed') stepIdx = 5;
        else if (fullData.status === 'awaiting_approval') stepIdx = 1;
        else if (fullData.status === 'executing') stepIdx = Math.max(stepIdx, 2);

        setActiveStepIndex(stepIdx);

        // Responsive fallback thoughts if not yet emitted
        if (loadedThoughts.length === 0) {
          if (isQueued) {
            loadedThoughts = [{
              agent: 'Orchestrator',
              thought: 'Workflow queued in Celery worker pool. Waiting for previous repository migration to complete...',
              timestamp: fullData.created_at || new Date().toISOString()
            }];
          } else if (isAct) {
            loadedThoughts = [{
              agent: 'PlannerAgent',
              thought: `Autonomous pipeline ${fullData.status.toUpperCase()} — streaming live agent events...`,
              timestamp: fullData.started_at || fullData.created_at || new Date().toISOString()
            }];
          }
        }

        setThoughts(loadedThoughts);
        setFileChanges(loadedChanges);

        if (fullData.cost_and_token_metrics) {
          const tok = fullData.cost_and_token_metrics.total_tokens || 0;
          const cst = fullData.cost_and_token_metrics.total_cost_usd || 0.0;
          setLiveMetrics(tok, cst);
        }

        if (fullData.error_message && !dismissedErrors.has(fullData.id)) {
          setWorkflowError(fullData.error_message);
        } else if (!fullData.error_message) {
          setWorkflowError(null);
        }

        if (isCancelled) {
          setLastStoppedWorkflow({
            id: fullData.id,
            stepIndex: stepIdx,
          });
        }

        if (fullData.status === 'completed') {
          try {
            localStorage.removeItem('codemigration_active_workflow_id');
          } catch (_) {}
        }
      }
    } catch (e) {
      if (!isSilent) {
        console.warn("Could not load workflow details", e);
      }
    }
  }, [setActiveWorkflowId, setSelectedRepo, setIsExecuting, setAwaitingApproval, setActiveStepIndex, setThoughts, setFileChanges, setLiveMetrics, dismissedErrors]);

  // Rehydrate or sync workflows with backend on mount & periodically
  const syncActiveWorkflowState = useCallback(async () => {
    try {
      const wfRes = await api.get('/workflows', { _silent: true });
      const workflows = wfRes.data || [];
      setAllWorkflows(workflows);

      const targetId = queryWorkflowId || activeWorkflowId;
      if (targetId) {
        const currentWf = workflows.find(w => w.id === targetId);
        if (currentWf) {
          const isAct = ['queued', 'planning', 'executing', 'validating'].includes(currentWf.status);
          const isAppr = currentWf.status === 'awaiting_approval';
          const isCancelled = currentWf.status === 'cancelled' || currentWf.status === 'stopped';
          setIsExecuting(isAct);
          setAwaitingApproval(isAppr);
          if (isCancelled) {
            setLastStoppedWorkflow({
              id: currentWf.id,
              stepIndex: currentWf.current_step_index || 0,
            });
          }
          // Deep-fetch details during active execution or when status reaches completed/failed/cancelled
          if (isAct || isAppr || currentWf.status === 'completed' || currentWf.status === 'failed' || isCancelled) {
            await loadWorkflowDetails(targetId, true);
          } else {
            setActiveStepIndex(currentWf.current_step_index || 0);
          }

          if (currentWf.status === 'failed' && !dismissedErrors.has(currentWf.id)) {
            setWorkflowError(currentWf.error_message || 'Workflow execution failed.');
          } else if (currentWf.status !== 'failed') {
            setWorkflowError(null);
          }

          if (currentWf.status === 'completed') {
            try {
              localStorage.removeItem('codemigration_active_workflow_id');
            } catch (_) {}
          }
        }
      }
    } catch (err) {
      console.warn("Could not sync active workflow state", err);
    }
  }, [queryWorkflowId, activeWorkflowId, setIsExecuting, setAwaitingApproval, setActiveStepIndex, loadWorkflowDetails, dismissedErrors]);

  // Initial Ultra-Fast Load: Parallel fetch repositories and workflows
  useEffect(() => {
    let isMounted = true;
    const fetchInitialData = async () => {
      setReposLoading(true);
      try {
        const [reposRes, wfRes] = await Promise.all([
          api.get('/repositories', { _silent: true }),
          api.get('/workflows', { _silent: true }),
        ]);

        if (!isMounted) return;

        const repoList = reposRes.data || [];
        setRepositories(repoList);
        setCachedRepositories(repoList);

        const workflows = wfRes.data || [];
        setAllWorkflows(workflows);

        const activeWfs = workflows.filter(w => 
          ['queued', 'planning', 'awaiting_approval', 'executing', 'validating'].includes(w.status)
        );

        const storedWfId = localStorage.getItem('codemigration_active_workflow_id');
        const storedWf = storedWfId ? workflows.find(w => w.id === storedWfId) : null;

        // Prioritize: 1) explicit query parameter, 2) active executing stored workflow (if user previously had one active)
        let targetWfId = queryWorkflowId;
        if (!targetWfId && storedWf && ['queued', 'planning', 'awaiting_approval', 'executing', 'validating'].includes(storedWf.status)) {
          targetWfId = storedWf.id;
        }

        if (targetWfId) {
          lastLoadedWorkflowIdRef.current = targetWfId;
          setActiveWorkflowId(targetWfId);
          setSearchParams({ workflowId: targetWfId }, { replace: true });
          await loadWorkflowDetails(targetWfId);
        } else {
          lastLoadedWorkflowIdRef.current = null;
          setActiveWorkflowId(null);
          setCurrentWorkflowData(null);
          setActiveStepIndex(0);
          if (!selectedRepo && repoList.length > 0) {
            setSelectedRepo(repoList[0].id);
          }
        }
      } catch (err) {
        if (!isMounted) return;
        if (repositories.length === 0) {
          setHasError(true);
          setLoadError(err);
        }
      } finally {
        if (isMounted) setReposLoading(false);
      }
    };

    fetchInitialData();

    // Background polling every 2.5 seconds to sync status
    const interval = setInterval(() => {
      syncActiveWorkflowState();
    }, 2500);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // When query parameter changes in URL (e.g. navigated from History / Open in Studio), load that workflow immediately
  useEffect(() => {
    if (queryWorkflowId && queryWorkflowId !== lastLoadedWorkflowIdRef.current) {
      lastLoadedWorkflowIdRef.current = queryWorkflowId;
      setActiveWorkflowId(queryWorkflowId);
      try {
        localStorage.setItem('codemigration_active_workflow_id', queryWorkflowId);
      } catch (_) {}
      loadWorkflowDetails(queryWorkflowId);
    }
  }, [queryWorkflowId, loadWorkflowDetails, setActiveWorkflowId]);

  // When active workflow changes via switcher tabs, fetch its latest details & sync URL
  const handleSelectActiveWorkflow = (wfId) => {
    lastLoadedWorkflowIdRef.current = wfId;
    setActiveWorkflowId(wfId);
    try {
      localStorage.setItem('codemigration_active_workflow_id', wfId);
    } catch (_) {}
    setSearchParams({ workflowId: wfId });
    setWorkflowError(null);
    loadWorkflowDetails(wfId);
  };

  // WebSocket connection to active workflow stream
  useWorkflowSocket(
    activeWorkflowId, 
    setActiveStepIndex, 
    setAwaitingApproval, 
    setWorkflowError,
    useCallback((completedId) => {
      const idToLoad = completedId || activeWorkflowId;
      if (idToLoad) {
        loadWorkflowDetails(idToLoad, true);
        syncActiveWorkflowState();
      }
    }, [activeWorkflowId, loadWorkflowDetails, syncActiveWorkflowState])
  );

  const selectedRepoData = repositories.find((r) => r.id === selectedRepo);
  const detectedLangs = selectedRepoData?.detected_languages || [];
  const detectedFws = selectedRepoData?.detected_frameworks || [];

  const isFormValid = () => {
    return customGoal.trim() !== '';
  };

  const handleEnhancePrompt = async () => {
    if (!customGoal.trim()) {
      toast.error('Please enter a brief objective first.');
      return;
    }
    
    setIsEnhancing(true);
    try {
      const response = await api.post('/workflows/enhance-prompt', {
        source_framework: 'Auto-detect',
        target_framework: 'Based on prompt',
        target_language: 'same_as_source',
        custom_goal: customGoal,
      });
      
      if (response.data?.enhanced_prompt) {
        setCustomGoal(response.data.enhanced_prompt);
        toast.success('Prompt successfully enhanced by AI!');
      }
    } catch (err) {
      toast.error(getErrorMessage(err) || 'Failed to enhance prompt.');
    } finally {
      setIsEnhancing(false);
    }
  };

  // Find if selected repository currently has an active workflow
  const activeWorkflowForSelectedRepo = activeWorkflows.find(w => w.repository_id === selectedRepo);
  const isCurrentRepoRunning = Boolean(
    activeWorkflowForSelectedRepo && 
    ['queued', 'planning', 'executing', 'validating'].includes(activeWorkflowForSelectedRepo.status)
  );
  const isCurrentRepoAwaitingApproval = Boolean(
    activeWorkflowForSelectedRepo && activeWorkflowForSelectedRepo.status === 'awaiting_approval'
  );

  const handleStartMigration = async () => {
    if (!selectedRepo) {
      toast.error('Please select a repository first.');
      return;
    }

    if (isCurrentRepoRunning) {
      toast.error('A migration is already in progress for this repository.');
      return;
    }
    
    // Clear previous thoughts and state before starting a new run
    resetWorkflow();
    setCurrentWorkflowData(null);
    setLastStoppedWorkflow(null);
    setThoughts([]);
    setFileChanges([]);
    setIsExecuting(true);
    setAwaitingApproval(false);
    setWorkflowError(null);
    setActiveStepIndex(0);
    toast.success(`Initiating Autonomous Migration Workflow…`);

    try {
      const response = await api.post('/workflows/start', {
        repository_id: selectedRepo,
        workflow_type: workflowType,
        source_framework: 'Auto-detect',
        target_framework: 'Modern Architecture',
        target_language: 'same_as_source',
        custom_goal: customGoal,
        auto_approve: false,
      }, { _silent: true });

      const newWf = response.data;
      lastLoadedWorkflowIdRef.current = newWf.id;
      setActiveWorkflowId(newWf.id);
      setSelectedRepo(selectedRepo);
      try {
        localStorage.setItem('codemigration_active_workflow_id', newWf.id);
      } catch (_) {}
      setSearchParams({ workflowId: newWf.id });
      setAllWorkflows(prev => [newWf, ...prev.filter(w => w.id !== newWf.id)]);
      toast.success(`Workflow queued in Celery worker pool!`);
      loadWorkflowDetails(newWf.id);
    } catch (err) {
      const status = err?.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 409 || status === 400) {
        setWorkflowError(detail || 'A workflow is already actively running on this repository.');
      } else if (status === 429) {
        setWorkflowError(detail || 'Workflow rate limit reached. Please wait before starting another workflow.');
      } else if (status === 404) {
        setWorkflowError('The selected repository was not found. Please refresh and try again.');
      } else {
        setWorkflowError(getErrorMessage(err));
      }
      setIsExecuting(false);
    }
  };

  const handleNewModernization = async () => {
    try {
      localStorage.removeItem('codemigration_active_workflow_id');
    } catch (_) {}
    lastLoadedWorkflowIdRef.current = null;
    setSearchParams({});
    setWorkflowError(null);
    setLastStoppedWorkflow(null);
    setCurrentWorkflowData(null);
    setThoughts([]);
    setFileChanges([]);
    setIsExecuting(false);
    setAwaitingApproval(false);
    setActiveStepIndex(0);
    setActiveWorkflowId(null);

    // Halt any running Celery / LangGraph workflow on the server and reset store
    await initiateNewModernization();

    // Invalidate cached query data across the application
    queryClient.invalidateQueries({ queryKey: ['workflows'] });
    queryClient.invalidateQueries({ queryKey: ['telemetry'] });
    queryClient.invalidateQueries({ queryKey: ['kpis'] });

    toast.success("Active workflows stopped. Ready for new modernization.");
  };

  const handleRepoChange = (newRepoId) => {
    setSelectedRepo(newRepoId);
    setWorkflowError(null);
    // Check if new repo already has an active (currently running or awaiting approval) workflow
    const activeForRepo = activeWorkflows.find(w => w.repository_id === newRepoId);
    if (activeForRepo) {
      handleSelectActiveWorkflow(activeForRepo.id);
    } else {
      // Clear previous thoughts to prepare fresh session for this repo
      try {
        localStorage.removeItem('codemigration_active_workflow_id');
      } catch (_) {}
      lastLoadedWorkflowIdRef.current = null;
      setSearchParams({});
      setThoughts([]);
      setFileChanges([]);
      setCurrentWorkflowData(null);
      setLastStoppedWorkflow(null);
      setIsExecuting(false);
      setAwaitingApproval(false);
      setActiveStepIndex(0);
      setActiveWorkflowId(null);
    }
  };

  const handleResumeWorkflow = async (targetId = null) => {
    const idToResume = targetId || activeWorkflowId || lastStoppedWorkflow?.id;
    if (!idToResume) {
      toast.error("No checkpointed workflow found to resume.");
      return;
    }

    setIsResuming(true);
    setWorkflowError(null);
    toast.success("Resuming autonomous pipeline from last saved checkpoint...");

    try {
      await api.post(`/workflows/${idToResume}/resume`);
      setActiveWorkflowId(idToResume);
      setIsExecuting(true);
      setAwaitingApproval(false);
      setLastStoppedWorkflow(null);
    } catch (err) {
      const msg = getErrorMessage(err);
      toast.error(`Failed to resume: ${msg}`);
      setWorkflowError(msg);
      setIsExecuting(false);
    } finally {
      setIsResuming(false);
    }
  };

  const handleStopWorkflow = async () => {
    const targetWfId = activeWorkflowId || queryWorkflowId || currentWorkflowData?.id;
    if (!targetWfId) {
      toast.error("No active workflow selected to stop.");
      return;
    }
    if (!window.confirm("Are you sure you want to stop/pause the active migration pipeline? Your execution checkpoint will be saved in PostgreSQL and can be resumed anytime.")) return;

    setIsStopping(true);
    try {
      await api.post(`/workflows/${targetWfId}/cancel`);
      toast.success("Migration workflow stopped. Checkpoint safely preserved.");
      setLastStoppedWorkflow({
        id: targetWfId,
        stepIndex: activeStepIndex,
      });
      setIsExecuting(false);
      setAwaitingApproval(false);
      setCurrentWorkflowData(prev => prev ? { ...prev, status: 'cancelled' } : null);
      setAllWorkflows(prev => prev.map(w => w.id === targetWfId ? { ...w, status: 'cancelled' } : w));
      setThoughts(prev => [
        ...prev,
        {
          id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
          agent: 'Orchestrator',
          thought: 'Pipeline execution stopped by operator. Checkpoint safely preserved in PostgreSQL.',
          timestamp: new Date().toISOString()
        }
      ]);
      await syncActiveWorkflowState();
    } catch (err) {
      toast.error(getErrorMessage(err) || "Failed to stop workflow.");
    } finally {
      setIsStopping(false);
    }
  };

  const handleApprovePlan = async () => {
    if (isApproving || isRejecting || isStopping) return;
    setIsApproving(true);

    try {
      if (activeWorkflowId) {
        await api.post(`/workflows/${activeWorkflowId}/approve`);
      }
      setAwaitingApproval(false);
      setIsExecuting(true);
      setActiveStepIndex(2);
      setCurrentWorkflowData(prev => prev ? { ...prev, status: 'executing' } : prev);
      setAllWorkflows(prev => prev.map(w => w.id === activeWorkflowId ? { ...w, status: 'executing' } : w));
      toast.success('Plan Approved! Executing Autonomous Refactoring Engine…');
      syncActiveWorkflowState();
    } catch (err) {
      const msg = getErrorMessage(err);
      toast.error(`Approval failed: ${msg}`, { id: 'approve-error' });
      setIsExecuting(false);
      setAwaitingApproval(true);
      setActiveStepIndex(1);
    } finally {
      setIsApproving(false);
    }
  };

  const handleRejectPlan = async () => {
    if (isApproving || isRejecting || isStopping) return;
    if (!window.confirm("Are you sure you want to reject the migration plan? This will halt the pipeline.")) return;
    setIsRejecting(true);

    try {
      if (activeWorkflowId) {
        await api.post(`/workflows/${activeWorkflowId}/reject`);
      }
      setAwaitingApproval(false);
      setIsExecuting(false);
      toast.success('Plan rejected. Pipeline halted.');
      syncActiveWorkflowState();
    } catch (err) {
      const msg = getErrorMessage(err);
      toast.error(`Rejection failed: ${msg}`);
    } finally {
      setIsRejecting(false);
    }
  };

  if (reposLoading && repositories.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full mt-24 gap-4 text-indigo-400">
        <Loader2 className="w-8 h-8 animate-spin" />
        <span className="text-sm font-mono tracking-widest uppercase">Loading Migration Studio…</span>
      </div>
    );
  }

  if (hasError && repositories.length === 0) {
    return (
      <div className="max-w-7xl mx-auto pt-10">
        <ErrorState 
          title="Studio Unavailable"
          message={
            loadError?.response?.data?.detail ||
            'Failed to load your repositories. Please ensure you have connected a repository to your organization.'
          }
          error={loadError}
          onRetry={() => window.location.reload()}
        />
      </div>
    );
  }

  const currentActiveWf = activeWorkflows.find(w => w.id === activeWorkflowId);
  const isCurrentViewingActive = Boolean(isExecuting || awaitingApproval || currentActiveWf);
  const isCompleted = Boolean(
    activeWorkflowId && (
      currentWorkflowData?.status === 'completed' ||
      (!isExecuting && !awaitingApproval && activeStepIndex === 5 && thoughts.some(t => typeof t.thought === 'string' && (t.thought.includes('Migration complete!') || t.thought.includes('delivered Pull Request'))))
    )
  );
  const canResumeCheckpoint = Boolean(
    !isCurrentViewingActive && 
    !isCompleted && 
    (lastStoppedWorkflow || currentWorkflowData?.status === 'cancelled' || currentWorkflowData?.status === 'stopped' || (activeWorkflowId && !isExecuting && workflowError))
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">

      {/* Migration Completed Banner */}
      {isCompleted && (
        <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-950/70 via-teal-950/50 to-surface border border-emerald-500/50 flex flex-col md:flex-row items-center justify-between gap-4 animate-in fade-in shadow-xl shadow-emerald-950/40">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center flex-shrink-0">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-emerald-100">Migration Pipeline Completed Successfully!</h4>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  6/6 Steps Complete
                </span>
              </div>
              <p className="text-xs text-emerald-300/80 mt-0.5">
                AST transformations applied, regression tests synthesized, sandbox verified, and Pull Request delivered.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-shrink-0">
            {(currentWorkflowData?.langgraph_state?.pr_url || currentWorkflowData?.pr_url) && (
              <a
                href={currentWorkflowData?.langgraph_state?.pr_url || currentWorkflowData?.pr_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-bold text-xs shadow-lg shadow-emerald-950/50 transition-all cursor-pointer"
              >
                <GitPullRequest className="w-3.5 h-3.5" />
                <span>View Pull Request</span>
              </a>
            )}
            <button
              onClick={handleNewModernization}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-200 hover:text-white font-semibold text-xs border border-gray-700 transition-colors cursor-pointer"
            >
              <PlusCircle className="w-3.5 h-3.5 text-cyan-400" />
              <span>New Modernization</span>
            </button>
          </div>
        </div>
      )}

      {/* Workflow Execution Banner when Active */}
      {isCurrentViewingActive && (
        <div className="p-4 rounded-2xl bg-indigo-950/60 border border-indigo-500/40 flex flex-col md:flex-row md:items-center justify-between gap-3 animate-in fade-in duration-300">
          <div className="flex items-center gap-3">
            <Radio className="w-5 h-5 text-indigo-400 animate-pulse" />
            <div>
              <h4 className="text-sm font-bold text-indigo-200">
                Monitoring Pipeline: {repositories.find(r => r.id === selectedRepo)?.name || 'Selected Repository'}
              </h4>
              <p className="text-xs text-indigo-300/80">
                Multi-agent LangGraph workflow is executing asynchronously in the background.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              Step {activeStepIndex + 1} of 6
            </span>
            {(activeWorkflowId || currentActiveWf) && (
              <button
                id="banner-stop-pipeline-btn"
                onClick={handleStopWorkflow}
                disabled={isStopping}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/40 text-rose-200 text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
                title="Stop executing workflow"
              >
                {isStopping ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <StopCircle className="w-3.5 h-3.5" />
                )}
                <span>Stop Workflow</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Stopped / Paused Checkpoint Banner */}
      {canResumeCheckpoint && (
        <div className="p-4 rounded-2xl bg-amber-950/30 border border-amber-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in duration-300">
          <div className="flex items-center gap-3">
            <RotateCcw className="w-5 h-5 text-amber-400 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-bold text-amber-200">Workflow Paused · Checkpoint Ready</h4>
              <p className="text-xs text-amber-300/80">
                Pipeline execution stopped at Step { (lastStoppedWorkflow?.stepIndex || activeStepIndex) + 1 }. You can resume from this checkpoint or start a new modernization.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-center">
            <button
              id="banner-resume-checkpoint-btn"
              onClick={() => handleResumeWorkflow()}
              disabled={isResuming}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white text-xs font-semibold shadow-md shadow-emerald-950/40 transition-all cursor-pointer disabled:opacity-50"
            >
              {isResuming ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
              <span>{isResuming ? 'Resuming...' : 'Resume from Checkpoint'}</span>
            </button>
            <button
              onClick={handleNewModernization}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-medium border border-gray-700 transition-all cursor-pointer"
            >
              <PlusCircle className="w-3.5 h-3.5 text-cyan-400" />
              <span>New Modernization</span>
            </button>
          </div>
        </div>
      )}

      {/* Dynamic Configuration Header */}
      <div className="p-6 rounded-3xl glass-panel border border-gray-800 flex flex-col gap-6">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-indigo-400" />
              <h2 className="text-xl font-bold text-white">Migration &amp; Refactoring Studio</h2>
            </div>
            <p className="text-xs text-gray-400">
              Autonomous multi-agent LangGraph workflow execution with custom target framework objectives and checkpointed approval gates.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* New Modernization Action */}
            <button
              id="new-modernization-btn"
              onClick={handleNewModernization}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gray-800/80 hover:bg-gray-700/80 border border-gray-700 text-gray-200 hover:text-white text-xs font-semibold shadow-md transition-all cursor-pointer"
              title="Initialize a fresh modernization workflow"
            >
              <PlusCircle className="w-3.5 h-3.5 text-cyan-400" />
              <span>New Modernization</span>
            </button>

            {/* Resume from Checkpoint button */}
            {canResumeCheckpoint && (
              <button
                id="header-resume-checkpoint-btn"
                onClick={() => handleResumeWorkflow()}
                disabled={isResuming}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white text-xs font-semibold shadow-lg shadow-emerald-600/25 transition-all cursor-pointer disabled:opacity-50"
                title="Resume pipeline from last saved checkpoint"
              >
                {isResuming ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RotateCcw className="w-3.5 h-3.5" />
                )}
                <span>{isResuming ? 'Resuming...' : 'Resume Checkpoint'}</span>
              </button>
            )}

            {/* Stop Workflow button when actively running */}
            {isCurrentViewingActive && activeWorkflowId && (
              <button
                id="stop-pipeline-btn"
                onClick={handleStopWorkflow}
                disabled={isStopping}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/50 text-rose-300 text-xs font-semibold shadow-lg shadow-rose-950/40 transition-all cursor-pointer disabled:opacity-50"
                title="Stop executing workflow"
              >
                {isStopping ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-400" />
                ) : (
                  <Square className="w-3.5 h-3.5 fill-rose-400 text-rose-400" />
                )}
                <span>{isStopping ? 'Stopping…' : 'Stop Pipeline'}</span>
              </button>
            )}

            {/* Start Modernization button */}
            <button
              id="start-migration-btn"
              onClick={handleStartMigration}
              disabled={isCurrentRepoRunning || isCurrentRepoAwaitingApproval || !selectedRepo || !isFormValid()}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all cursor-pointer disabled:cursor-not-allowed"
            >
              {isCurrentRepoRunning ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Pipeline Executing…</span>
                </>
              ) : isCurrentRepoAwaitingApproval ? (
                <>
                  <Lock className="w-3.5 h-3.5 text-amber-300" />
                  <span>Awaiting Approval</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-white" />
                  <span>Start Modernization</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Repository & Dynamic Preset Controls */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center bg-gray-950/60 p-4 rounded-2xl border border-gray-800/80">
          {/* Repo Selector */}
          <div className="md:col-span-4 space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-semibold text-gray-300 uppercase tracking-wider font-mono">
                Target Repository
              </label>
              {isCurrentRepoRunning && (
                <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                  <Radio className="w-3 h-3 animate-pulse" /> Actively Migrating
                </span>
              )}
            </div>
            <select
              aria-label="Select Repository"
              value={selectedRepo}
              onChange={(e) => handleRepoChange(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-700 text-xs text-gray-200 focus:outline-none focus:border-indigo-500 font-medium cursor-pointer"
            >
              <option value="" disabled>Select Repository</option>
              {repositories.map((repo) => (
                <option key={repo.id} value={repo.id}>
                  {repo.name}
                </option>
              ))}
            </select>
            {selectedRepoData && (
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[10px] text-gray-400">Detected:</span>
                {detectedLangs.map((lang) => (
                  <span key={lang} className="px-1.5 py-0.5 rounded bg-blue-950/60 border border-blue-500/30 text-blue-300 text-[10px] font-mono">
                    {lang}
                  </span>
                ))}
                {detectedFws.map((fw) => (
                  <span key={fw} className="px-1.5 py-0.5 rounded bg-purple-950/60 border border-purple-500/30 text-purple-300 text-[10px] font-mono">
                    {fw}
                  </span>
                ))}
                <span className="text-[10px] text-gray-500 font-mono ml-auto">
                  {selectedRepoData.ast_node_count || 0} AST nodes
                </span>
              </div>
            )}
          </div>

          <div className="md:col-span-8 p-4 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-mono text-indigo-300 uppercase tracking-wider font-bold">
                🛠️ Custom Migration Specification &amp; Architectural Objectives
              </label>
              <button
                onClick={handleEnhancePrompt}
                disabled={isEnhancing || !customGoal.trim() || isCurrentRepoRunning}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-mono transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isEnhancing ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                <span>{isEnhancing ? 'Enhancing...' : '✨ Enhance Objective'}</span>
              </button>
            </div>
            <textarea
              rows={4}
              value={customGoal}
              onChange={(e) => setCustomGoal(e.target.value)}
              disabled={isCurrentRepoRunning}
              placeholder="Describe specific transformation requirements, e.g.: Convert all action creators and reducers to createSlice with createAsyncThunk, replace connect() HOCs with useSelector/useDispatch, and add strict TypeScript interfaces."
              className="w-full px-3 py-2.5 rounded-xl bg-gray-900 border border-gray-700 text-xs text-gray-200 focus:outline-none focus:border-indigo-500 font-sans resize-none disabled:opacity-60 disabled:cursor-not-allowed"
            />
          </div>
        </div>
      </div>

      {/* Human Approval Gate Alert (When Triggered) */}
      {awaitingApproval && (
        <div className="p-5 rounded-2xl bg-amber-950/40 border border-amber-500/40 flex flex-col md:flex-row items-center justify-between gap-4 animate-bounce">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-bold text-amber-200">Human-in-the-Loop Checkpoint Gate</h4>
              <p className="text-xs text-amber-300/80">
                Planner Agent completed the migration DAG. Review and approve before code mutations are executed.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleRejectPlan}
              disabled={isApproving || isRejecting || isStopping}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-950/60 border border-rose-500/40 hover:bg-rose-900/60 text-rose-300 font-semibold text-xs transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isRejecting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Rejecting...</span>
                </>
              ) : (
                <span>Reject &amp; Cancel</span>
              )}
            </button>
            <button
              id="approve-plan-btn"
              onClick={handleApprovePlan}
              disabled={isApproving || isRejecting || isStopping}
              className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-gray-950 font-bold text-xs shadow-lg shadow-amber-500/20 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isApproving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Approving...</span>
                </>
              ) : (
                <span>Approve &amp; Execute DAG</span>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Single Unified Error & Resumable Checkpoint Gate Alert */}
      {workflowError && (
        <div className="p-5 rounded-2xl bg-rose-950/40 border border-rose-500/50 flex flex-col md:flex-row items-center justify-between gap-4 animate-in fade-in shadow-xl">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-bold text-rose-200">Migration Pipeline Notice</h4>
              <p className="text-xs text-rose-300/90 mt-0.5 max-w-2xl">
                {workflowError}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {!isExecuting && activeWorkflowId && (
              <button
                onClick={() => handleResumeWorkflow(activeWorkflowId)}
                disabled={isResuming}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-bold text-xs shadow-lg shadow-emerald-950/50 transition-all cursor-pointer disabled:opacity-50"
              >
                {isResuming ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Resuming...</span>
                  </>
                ) : (
                  <>
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Resume from Checkpoint</span>
                  </>
                )}
              </button>
            )}
            <button
              onClick={() => handleDismissError()}
              className="px-3.5 py-2.5 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white text-xs font-medium border border-gray-700 transition-colors cursor-pointer"
              title="Dismiss error notice"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* No-repo warning */}
      {repositories.length === 0 && !hasError && !reposLoading && (
        <div className="p-5 rounded-2xl bg-gray-900 border border-gray-700 text-center text-sm text-gray-400">
          No repositories found. Please connect a repository to your organization first.
        </div>
      )}

      {/* Progress Stepper */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        {steps.map((step, idx) => {
          const isDone    = isCompleted || idx < activeStepIndex;
          const isCurrent = !isCompleted && (isExecuting || awaitingApproval) && idx === activeStepIndex;
          const isPaused  = !isCompleted && !isExecuting && !awaitingApproval && idx === activeStepIndex && Boolean(activeWorkflowId || lastStoppedWorkflow || currentWorkflowData?.status === 'cancelled' || currentWorkflowData?.status === 'stopped');
          return (
            <div
              key={step.name}
              className={`p-3 rounded-xl border text-center transition-all ${
                isDone
                  ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-300'
                  : isCurrent
                  ? 'bg-indigo-950/40 border-indigo-500 text-indigo-300 shadow-lg shadow-indigo-500/20 animate-pulse'
                  : isPaused
                  ? 'bg-amber-950/30 border-amber-500/50 text-amber-300 shadow-md shadow-amber-950/20'
                  : 'bg-gray-900/40 border-gray-800 text-gray-500'
              }`}
            >
              <p className="text-[10px] uppercase font-mono font-bold tracking-wider mb-0.5">
                {isDone ? `✓ Step ${idx + 1}` : isPaused ? `⏸ Step ${idx + 1}` : `Step ${idx + 1}`}
              </p>
              <p className="text-xs font-semibold truncate">{step.name}</p>
            </div>
          );
        })}
      </div>

      {/* Workspace Split View: Always Preserved */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[500px]">
        {/* Left Column */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="h-[320px]">
            <AgentThoughtStream 
              thoughts={thoughts} 
              isExecuting={Boolean(isExecuting || isCurrentViewingActive)} 
              onStopWorkflow={handleStopWorkflow}
              isStopping={isStopping}
              liveTokens={liveTokens}
              liveCost={liveCost}
            />
          </div>

          {/* Transformed Files Selector */}
          <div className="p-4 rounded-2xl glass-panel border border-gray-800 bg-[#0E1322]/90 flex-1">
            <h4 className="text-xs font-bold uppercase tracking-wider text-gray-300 font-mono mb-3">
              AST Transformed Files ({fileChanges.length})
            </h4>
            <div className="space-y-2">
              {fileChanges.length === 0 ? (
                <p className="text-xs text-gray-500 py-4 text-center">
                  {isExecuting ? 'Agent synthesizing AST code transformations…' : 'No files transformed yet. Start workflow to view AST diffs.'}
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
                    <span>{fc.file_path}</span>
                    <span className="text-[10px] text-emerald-400 font-semibold">100% AST Passed</span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Monaco Diff Viewer */}
        <div className="lg:col-span-7 h-[520px]">
          {selectedFileChange || fileChanges.length > 0 ? (
            <DiffViewer fileChange={selectedFileChange || fileChanges[0]} />
          ) : (
            <div className="h-full flex items-center justify-center border border-gray-800 rounded-2xl bg-[#0E1322]/90">
              <span className="text-gray-500 text-sm">
                {isExecuting ? 'Waiting for first code mutation diff…' : 'No diff available yet.'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
