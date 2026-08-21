import { create } from 'zustand';
import api from '../services/api';

export const useWorkflowStore = create((set, get) => ({
  activeWorkflowId: null,
  activeWorkflow: null,
  activeStepIndex: 0,
  awaitingApproval: false,
  activeStep: 'init',
  thoughts: [],
  plan: [],
  fileChanges: [],
  validationResults: null,
  isExecuting: false,
  selectedFileChange: null,
  selectedRepo: '',
  customGoal: '',
  workflowType: 'custom_modernization',
  cachedRepositories: [],
  liveTokens: 0,
  liveCost: 0.0,

  setCachedRepositories: (repos) => set({ cachedRepositories: Array.isArray(repos) ? repos : [] }),
  setActiveWorkflowId: (id) => set({ activeWorkflowId: id }),
  setActiveWorkflow: (workflow) => set({ activeWorkflow: workflow }),
  setActiveStepIndex: (index) => set({ activeStepIndex: index }),
  setAwaitingApproval: (status) => set({ awaitingApproval: status }),
  setSelectedRepo: (repoId) => set({ selectedRepo: repoId }),
  setCustomGoal: (goal) => set({ customGoal: goal }),
  setWorkflowType: (type) => set({ workflowType: type }),
  setLiveMetrics: (tokens, cost) => set({ liveTokens: Number(tokens) || 0, liveCost: Number(cost) || 0.0 }),

  /** Full reset when clearing workflow state and halting any running executions */
  resetWorkflow: async () => {
    const activeId = get().activeWorkflowId || (() => {
      try { return localStorage.getItem('codemigration_active_workflow_id'); } catch (_) { return null; }
    })();
    try {
      localStorage.removeItem('codemigration_active_workflow_id');
    } catch (_) {}

    try {
      if (activeId) {
        api.post(`/workflows/${activeId}/stop`, {}, { _silent: true }).catch(() => {});
      }
      api.post('/workflows/stop-all-active', {}, { _silent: true }).catch(() => {});
    } catch (_) {}

    set({
      activeWorkflowId: null,
      activeWorkflow: null,
      thoughts: [],
      plan: [],
      fileChanges: [],
      selectedFileChange: null,
      validationResults: null,
      isExecuting: false,
      awaitingApproval: false,
      activeStepIndex: 0,
      activeStep: 'init',
      liveTokens: 0,
      liveCost: 0.0,
    });
  },

  /** Initialize a fresh modernization session: stop all running workflows and refresh UI */
  initiateNewModernization: async (repoId = null) => {
    const activeId = get().activeWorkflowId || (() => {
      try { return localStorage.getItem('codemigration_active_workflow_id'); } catch (_) { return null; }
    })();
    try {
      localStorage.removeItem('codemigration_active_workflow_id');
    } catch (_) {}

    try {
      if (activeId) {
        api.post(`/workflows/${activeId}/stop`, {}, { _silent: true }).catch(() => {});
      }
      api.post('/workflows/stop-all-active', {}, { _silent: true }).catch(() => {});
    } catch (_) {}

    set((state) => ({
      activeWorkflowId: null,
      activeWorkflow: null,
      thoughts: [],
      plan: [],
      fileChanges: [],
      selectedFileChange: null,
      validationResults: null,
      isExecuting: false,
      awaitingApproval: false,
      activeStepIndex: 0,
      activeStep: 'init',
      selectedRepo: repoId !== null ? repoId : state.selectedRepo,
      customGoal: '',
      liveTokens: 0,
      liveCost: 0.0,
    }));
  },

  addThought: (thought) => {
    set((state) => {
      // Prevent duplicate thoughts
      const isDuplicate = state.thoughts.some(
        t => t.agent === thought.agent && t.thought === thought.thought
      );
      if (isDuplicate) return state;
      return {
        thoughts: [...state.thoughts, { ...thought, id: crypto.randomUUID(), timestamp: thought.timestamp || new Date().toISOString() }],
      };
    });
  },

  setPlan: (plan) => set({ plan }),

  addFileChange: (change) => {
    if (!change || !change.file_path) return;
    set((state) => {
      const filtered = state.fileChanges.filter(f => f.file_path !== change.file_path);
      const updated = [...filtered, change];
      return {
        fileChanges: updated,
        selectedFileChange: state.selectedFileChange ? state.selectedFileChange : change,
      };
    });
  },

  setSelectedFileChange: (change) => set({ selectedFileChange: change }),

  setValidationResults: (validation) => set({ validationResults: validation }),

  setIsExecuting: (status) => set({ isExecuting: status }),
  
  setThoughts: (thoughts) => set({ thoughts: Array.isArray(thoughts) ? thoughts : [] }),
  
  setFileChanges: (changes) => {
    const list = Array.isArray(changes) ? changes : [];
    set((state) => {
      const currentSelected = state.selectedFileChange;
      const stillExists = currentSelected && list.some(f => f.file_path === currentSelected.file_path);
      return {
        fileChanges: list,
        selectedFileChange: stillExists ? currentSelected : (list[0] || null),
      };
    });
  },
}));
