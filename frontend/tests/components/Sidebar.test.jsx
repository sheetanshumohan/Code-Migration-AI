import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Sidebar from '../../src/components/Sidebar';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';

// Mock react-query
vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
}));
import { useQuery } from '@tanstack/react-query';

describe('Sidebar Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderSidebar = () => {
    return render(
      <BrowserRouter>
        <Sidebar />
      </BrowserRouter>
    );
  };

  it('renders navigation links', () => {
    useQuery.mockReturnValue({
      data: null,
    });

    renderSidebar();

    // Verify main navigation links exist
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Migration Studio')).toBeInTheDocument();
    expect(screen.getByText('Settings & Models')).toBeInTheDocument();
    
    // Check for badge on Migration Studio
    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('renders autonomous core widget with idle state when no active workflows', () => {
    useQuery.mockReturnValue({
      data: { active_workflows: 0 },
    });

    renderSidebar();

    expect(screen.getByText('Autonomous Core')).toBeInTheDocument();
    expect(screen.getByText('Active workflows')).toBeInTheDocument();
    // The widget displays "0"
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('renders autonomous core widget with active workflows', () => {
    useQuery.mockReturnValue({
      data: { active_workflows: 5 },
    });

    renderSidebar();

    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('5')).toHaveClass('text-emerald-400');
  });

  it('renders default widget state on missing data', () => {
    useQuery.mockReturnValue({
      data: null,
    });

    renderSidebar();

    // Em dash is rendered when active is null
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
