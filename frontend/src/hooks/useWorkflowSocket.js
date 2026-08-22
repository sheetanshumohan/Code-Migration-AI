import { useEffect, useRef, useCallback } from 'react';
import toast from 'react-hot-toast';
import { useWorkflowStore } from '../stores/workflowStore';
import { getWebSocketUrl } from '../services/api';

const RECONNECT_DELAY_MS  = 3000;
const MAX_RECONNECT_TRIES = 5;

/**
 * useWorkflowSocket — connects to the workflow WebSocket and handles:
 *   - Step progression  (type: "thought" or thought payload with timestamps)
 *   - File change diffs (type: "file_change" or file_change payload)
 *   - Plan-ready gate   (type: "plan_ready", awaiting_approval, or DAG tasks)
 *   - Error events      (type: "workflow_failed", "error", or status: "failed")
 *   - Completion events (type: "workflow_completed", agent: "ReviewerAgent", or status: "completed")
 *   - Connection loss   → auto-reconnect
 */
export function useWorkflowSocket(activeWorkflowId, setActiveStepIndex, setAwaitingApproval, setWorkflowError, onWorkflowCompleted) {
  const { addThought, addFileChange, setIsExecuting, setLiveMetrics } = useWorkflowStore();
  const socketRef     = useRef(null);
  const reconnectRef  = useRef(0);
  const unmountedRef  = useRef(false);

  const connect = useCallback(() => {
    if (!activeWorkflowId || unmountedRef.current) return;

    if (socketRef.current) {
      try {
        socketRef.current.close();
      } catch (_) {}
    }

    const token = localStorage.getItem('codemigration_token') || '';
    const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
    const wsUrl = getWebSocketUrl(activeWorkflowId, tokenQuery);

    let socket;
    try {
      socket = new WebSocket(wsUrl);
      socketRef.current = socket;
    } catch (wsErr) {
      console.warn('[WorkflowSocket] WebSocket instantiation failed:', wsErr);
      return;
    }

    // ── Message handler ──────────────────────────────────────────────────────
    socket.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (err) {
        console.error('[WorkflowSocket] Failed to parse message:', event.data, err);
        return;
      }

      // 0. Process explicit step progression & live token metrics
      if (data.total_tokens !== undefined || data.total_cost_usd !== undefined || data.cost_metrics) {
        const tok = data.total_tokens ?? data.cost_metrics?.total_tokens ?? 0;
        const cst = data.total_cost_usd ?? data.cost_metrics?.total_cost_usd ?? 0.0;
        if (tok > 0 || cst > 0) {
          setLiveMetrics(tok, cst);
        }
      }

      if (data.type === 'step_progress' || typeof data.current_step_index === 'number' || typeof data.step_index === 'number') {
        const stepNum = typeof data.current_step_index === 'number' ? data.current_step_index : data.step_index;
        if (typeof setActiveStepIndex === 'function' && stepNum >= 0) {
          setActiveStepIndex(stepNum);
        }
      }

      // 1. Process agent thought stream with emission timestamps
      if (data.thought) {
        addThought({ 
          agent: data.agent, 
          thought: data.thought,
          timestamp: data.timestamp || new Date().toISOString()
        });

        const stepMap = {
          RepoAnalystAgent: 0,
          PlannerAgent:    1,
          RefactorAgent:   2,
          TestGenAgent:    3,
          ValidationAgent: 4,
          ReviewerAgent:   5,
        };
        if (stepMap[data.agent] !== undefined && typeof setActiveStepIndex === 'function') {
          setActiveStepIndex(stepMap[data.agent]);
        }
      }

      // 2. Process file AST diff mutations
      if (data.type === 'file_change' || data.file_change) {
        const change = data.file_change || data;
        if (change?.file_path) {
          addFileChange(change);
        }
      }

      // 2b. Explicit step progress updates
      if (data.type === 'step_progress' && typeof data.current_step_index === 'number') {
        if (typeof setActiveStepIndex === 'function') {
          setActiveStepIndex(data.current_step_index);
        }
      }

      // 3. Human-in-the-loop approval gate
      if (
        data.type === 'plan_ready' || 
        data.status === 'awaiting_approval'
      ) {
        if (typeof setAwaitingApproval === 'function') {
          setAwaitingApproval(true);
        }
        setIsExecuting(false);
        if (typeof setActiveStepIndex === 'function') {
          setActiveStepIndex(1);
        }
      }

      // 3b. Plan approved / execution resumed
      if (
        data.type === 'plan_approved' ||
        data.type === 'workflow_resumed' ||
        (data.status === 'executing' && data.type !== 'plan_ready') ||
        ['RefactorAgent', 'TestGenAgent', 'ValidationAgent', 'ReviewerAgent'].includes(data.agent)
      ) {
        if (typeof setAwaitingApproval === 'function') {
          setAwaitingApproval(false);
        }
        setIsExecuting(true);
        if (typeof data.current_step_index === 'number' && typeof setActiveStepIndex === 'function') {
          setActiveStepIndex(data.current_step_index);
        }
      }

      // 4. Workflow completion
      if (
        data.type === 'workflow_completed' || 
        data.status === 'completed' || 
        (data.agent === 'ReviewerAgent' && data.pr_url) ||
        (typeof data.thought === 'string' && (data.thought.includes('Migration complete!') || data.thought.includes('delivered Pull Request')))
      ) {
        setIsExecuting(false);
        if (typeof setAwaitingApproval === 'function') {
          setAwaitingApproval(false);
        }
        if (typeof setActiveStepIndex === 'function') {
          setActiveStepIndex(5);
        }
        if (typeof onWorkflowCompleted === 'function') {
          onWorkflowCompleted(activeWorkflowId);
        }
        toast.success('Migration pipeline completed successfully!');
      }

      // 5. Workflow stopped / paused by operator
      if (data.status === 'cancelled' || data.type === 'workflow_stopped') {
        setIsExecuting(false);
        if (typeof setAwaitingApproval === 'function') {
          setAwaitingApproval(false);
        }
        if (typeof data.current_step_index === 'number' && typeof setActiveStepIndex === 'function') {
          setActiveStepIndex(data.current_step_index);
        }
      }

      // 6. Backend-emitted error or failure (except intentional operator cancellation)
      if ((data.type === 'workflow_failed' || data.type === 'error' || data.status === 'failed') && data.status !== 'cancelled') {
        const msg = data.message || data.error || 'The migration workflow encountered an error.';
        toast.error(msg, { duration: 8000 });
        setIsExecuting(false);
        if (typeof setAwaitingApproval === 'function') {
          setAwaitingApproval(false);
        }
        if (typeof setWorkflowError === 'function') {
          setWorkflowError(msg);
        }
      }
    };

    socket.onopen = () => {
      reconnectRef.current = 0;
    };

    socket.onerror = (err) => {
      console.warn('[WorkflowSocket] Connection error:', err);
    };

    socket.onclose = (event) => {
      if (unmountedRef.current) return;
      if (!event.wasClean && reconnectRef.current < MAX_RECONNECT_TRIES) {
        reconnectRef.current += 1;
        setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };
  }, [activeWorkflowId, addThought, addFileChange, setIsExecuting, setActiveStepIndex, setAwaitingApproval, setWorkflowError]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connect]);
}
