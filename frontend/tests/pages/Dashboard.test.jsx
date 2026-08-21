import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Dashboard from '../../src/pages/Dashboard';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';

// Mock recharts to avoid rendering actual SVG charts in tests
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  AreaChart: () => <div data-testid="area-chart" />,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

// Mock hooks
vi.mock('../../src/services/useTelemetry', () => ({
  useTelemetry: vi.fn(),
  useKpis: vi.fn(),
}));
import { useTelemetry, useKpis } from '../../src/services/useTelemetry';

describe('Dashboard Page', () => {
  const mockRefetchTelemetry = vi.fn();
  const mockRefetchKpis = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderDashboard = () => {
    return render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );
  };

  it('renders loading skeletons when fetching data', () => {
    useTelemetry.mockReturnValue({ isLoading: true, refetch: mockRefetchTelemetry });
    useKpis.mockReturnValue({ isLoading: true, refetch: mockRefetchKpis });

    const { container } = renderDashboard();
    // Verify skeletons are rendered (by checking for pulse animation classes or just not crashing)
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders error state when API fails', () => {
    useTelemetry.mockReturnValue({
      isError: true,
      error: { response: { data: { detail: 'Network Error' } } },
      refetch: mockRefetchTelemetry,
    });
    useKpis.mockReturnValue({
      isError: false,
      refetch: mockRefetchKpis,
    });

    renderDashboard();

    expect(screen.getByText('Dashboard Unavailable')).toBeInTheDocument();
    expect(screen.getByText('Network Error')).toBeInTheDocument();
  });

  it('renders KPI data correctly on success', () => {
    useTelemetry.mockReturnValue({
      data: [{ time: '10:00', tokens: 150 }],
      isLoading: false,
      isError: false,
      refetch: mockRefetchTelemetry,
    });

    useKpis.mockReturnValue({
      data: {
        active_workflows: 5,
        ast_nodes: 12500,
        generated_prs: 12,
        sandbox_score: 95,
      },
      isLoading: false,
      isError: false,
      refetch: mockRefetchKpis,
    });

    renderDashboard();

    // Verify KPI values are displayed
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('12,500')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    
    // Verify chart is rendered since there is workflow data
    expect(screen.getByTestId('area-chart')).toBeInTheDocument();
  });

  it('renders empty state when no repositories are connected', () => {
    useTelemetry.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: mockRefetchTelemetry,
    });

    useKpis.mockReturnValue({
      data: {
        active_workflows: 0,
        ast_nodes: 0,
        generated_prs: 0,
        sandbox_score: null,
      },
      isLoading: false,
      isError: false,
      refetch: mockRefetchKpis,
    });

    renderDashboard();

    expect(screen.getByText('No workflow telemetry yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /connect repo/i })).toBeInTheDocument();
  });
});
