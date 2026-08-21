import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import DependencyGraphView from '../../src/components/DependencyGraphView';
import React from 'react';

// Mock reactflow to prevent SVG/canvas rendering issues in JSDOM
vi.mock('@xyflow/react', async () => {
  const actualReact = await import('react');
  return {
    ReactFlow: ({ children, nodes, edges }) => (
      <div data-testid="react-flow">
        <div data-testid="nodes-count">{nodes?.length || 0}</div>
        <div data-testid="edges-count">{edges?.length || 0}</div>
        {children}
      </div>
    ),
    MiniMap: () => <div data-testid="minimap" />,
    Controls: () => <div data-testid="controls" />,
    Background: () => <div data-testid="background" />,
    useNodesState: (init) => {
      const [state, setState] = actualReact.useState(init);
      return [state, setState, vi.fn()];
    },
    useEdgesState: (init) => {
      const [state, setState] = actualReact.useState(init);
      return [state, setState, vi.fn()];
    },
    Handle: () => <div data-testid="handle" />,
    Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
    MarkerType: { Arrow: 'arrow', ArrowClosed: 'arrowclosed' },
  };
});

describe('DependencyGraphView Component', () => {
  it('renders the graph container and header', () => {
    render(<DependencyGraphView />);
    
    expect(screen.getByText('Interactive AST Dependency Graph')).toBeInTheDocument();
    expect(screen.getByText(/No dependency graph nodes found/i)).toBeInTheDocument();
  });

  it('renders with empty graph data gracefully', () => {
    render(<DependencyGraphView graphData={{ nodes: [], edges: [] }} />);
    
    expect(screen.getByText(/No dependency graph nodes found/i)).toBeInTheDocument();
  });

  it('processes and renders nodes and edges correctly', () => {
    const mockData = {
      nodes: [
        { id: '1', data: { label: 'Node 1' } },
        { id: '2', data: { label: 'Node 2' } },
      ],
      edges: [
        { id: 'e1-2', source: '1', target: '2' },
      ],
    };

    render(<DependencyGraphView graphData={mockData} />);
    
    // Check if the mock ReactFlow received the correct counts
    expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    expect(screen.getByTestId('nodes-count')).toHaveTextContent('2');
    expect(screen.getByTestId('edges-count')).toHaveTextContent('1');
  });
});
