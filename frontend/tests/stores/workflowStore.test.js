import { describe, it, expect, beforeEach } from 'vitest';
import { useWorkflowStore } from '../../src/stores/workflowStore';

describe('workflowStore', () => {
  beforeEach(() => {
    // Reset Zustand store state before each test
    useWorkflowStore.setState({
      activeWorkflow: null,
      activeStep: 'init',
      thoughts: [],
      plan: [],
      fileChanges: [],
      validationResults: null,
      isExecuting: false,
      selectedFileChange: null,
      selectedRepo: null,
    });
  });

  it('sets active workflow', () => {
    const mockWorkflow = { id: 1, name: 'Test Workflow' };
    useWorkflowStore.getState().setActiveWorkflow(mockWorkflow);
    expect(useWorkflowStore.getState().activeWorkflow).toEqual(mockWorkflow);
  });

  it('adds a thought and assigns an id', () => {
    const mockThought = { message: 'Analyzing code' };
    useWorkflowStore.getState().addThought(mockThought);
    
    const thoughts = useWorkflowStore.getState().thoughts;
    expect(thoughts).toHaveLength(1);
    expect(thoughts[0].message).toBe('Analyzing code');
    expect(thoughts[0].id).toBeDefined(); // crypto.randomUUID() generates this
  });

  it('adds a file change and sets it as selected', () => {
    const change1 = { file_path: 'src/index.js', diff: '+ const a = 1;' };
    const change2 = { file_path: 'src/app.js', diff: '+ const b = 2;' };

    useWorkflowStore.getState().addFileChange(change1);
    
    let state = useWorkflowStore.getState();
    expect(state.fileChanges).toHaveLength(1);
    expect(state.selectedFileChange).toEqual(change1);

    useWorkflowStore.getState().addFileChange(change2);
    
    state = useWorkflowStore.getState();
    expect(state.fileChanges).toHaveLength(2);
    // selectedFileChange should remain change1 because it was already set
    expect(state.selectedFileChange).toEqual(change1);
  });

  it('resets workflow state', () => {
    // Set some state first
    useWorkflowStore.setState({
      thoughts: [{ id: '1', message: 'test' }],
      fileChanges: [{ file_path: 'test.js' }],
      activeStep: 'running',
    });

    useWorkflowStore.getState().resetWorkflow();
    const state = useWorkflowStore.getState();

    expect(state.thoughts).toHaveLength(0);
    expect(state.fileChanges).toHaveLength(0);
    expect(state.selectedFileChange).toBeNull();
    expect(state.validationResults).toBeNull();
    expect(state.activeStep).toBe('init');
  });

  it('sets isExecuting', () => {
    useWorkflowStore.getState().setIsExecuting(true);
    expect(useWorkflowStore.getState().isExecuting).toBe(true);
  });
});
