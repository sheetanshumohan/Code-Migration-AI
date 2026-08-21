import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import AgentThoughtStream from '../../src/components/AgentThoughtStream';
import React from 'react';

describe('AgentThoughtStream Component', () => {
  it('renders default empty state', () => {
    render(<AgentThoughtStream />);
    
    expect(screen.getByText('Autonomous Agent Thought Stream')).toBeInTheDocument();
    expect(screen.getByText('Engine Ready')).toBeInTheDocument();
    expect(screen.getByText(/Agent thought feed ready/i)).toBeInTheDocument();
  });

  it('renders executing state correctly', () => {
    render(<AgentThoughtStream isExecuting={true} />);
    
    expect(screen.getByText('Reasoning & Executing...')).toBeInTheDocument();
    expect(screen.queryByText('Engine Ready')).not.toBeInTheDocument();
  });

  it('renders thoughts in the stream', () => {
    const mockThoughts = [
      { id: 1, agent: 'Architect', thought: 'Analyzing repository structure' },
      { id: 2, agent: 'Coder', thought: 'Refactoring auth module' }
    ];

    render(<AgentThoughtStream thoughts={mockThoughts} />);

    expect(screen.getByText('Architect')).toBeInTheDocument();
    expect(screen.getByText('Analyzing repository structure')).toBeInTheDocument();
    
    expect(screen.getByText('Coder')).toBeInTheDocument();
    expect(screen.getByText('Refactoring auth module')).toBeInTheDocument();

    // The empty state message should not be present
    expect(screen.queryByText(/Agent thought feed ready/i)).not.toBeInTheDocument();
  });

  it('falls back to Orchestrator if agent name is not provided', () => {
    const mockThoughts = [
      { id: 1, thought: 'General processing' }
    ];

    render(<AgentThoughtStream thoughts={mockThoughts} />);

    expect(screen.getByText('Orchestrator')).toBeInTheDocument();
    expect(screen.getByText('General processing')).toBeInTheDocument();
  });
});
