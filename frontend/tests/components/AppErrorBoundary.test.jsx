import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import AppErrorBoundary from '../../src/components/AppErrorBoundary';
import React from 'react';

const ProblemChild = ({ shouldThrow }) => {
  if (shouldThrow) {
    throw new Error('Test rendering error');
  }
  return <div>Everything is fine</div>;
};

describe('AppErrorBoundary component', () => {
  let consoleErrorSpy;

  beforeEach(() => {
    // Suppress console.error in tests to avoid noisy output when components throw intentionally
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('renders children if no error occurs', () => {
    render(
      <AppErrorBoundary>
        <ProblemChild shouldThrow={false} />
      </AppErrorBoundary>
    );
    expect(screen.getByText('Everything is fine')).toBeInTheDocument();
    expect(screen.queryByText('Something Went Wrong')).not.toBeInTheDocument();
  });

  it('renders fallback UI when child throws', () => {
    render(
      <AppErrorBoundary>
        <ProblemChild shouldThrow={true} />
      </AppErrorBoundary>
    );
    
    expect(screen.getByText('Something Went Wrong')).toBeInTheDocument();
    expect(screen.queryByText('Everything is fine')).not.toBeInTheDocument();
  });

  it('resets error state when Try Again is clicked', () => {
    const { rerender } = render(
      <AppErrorBoundary>
        <ProblemChild shouldThrow={true} />
      </AppErrorBoundary>
    );

    // Now error is visible
    expect(screen.getByText('Something Went Wrong')).toBeInTheDocument();

    // Rerender with a non-throwing child (simulating the fix)
    rerender(
      <AppErrorBoundary>
        <ProblemChild shouldThrow={false} />
      </AppErrorBoundary>
    );

    // The boundary still shows error until reset
    expect(screen.getByText('Something Went Wrong')).toBeInTheDocument();

    // Click retry
    const retryBtn = screen.getByText('Try Again');
    fireEvent.click(retryBtn);

    // Should now show child
    expect(screen.getByText('Everything is fine')).toBeInTheDocument();
  });
});
