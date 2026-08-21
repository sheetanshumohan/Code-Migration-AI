import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ErrorState from '../../src/components/ErrorState';
import React from 'react';

describe('ErrorState component', () => {
  it('renders default title and message', () => {
    render(<ErrorState />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
    expect(screen.getByText('An unexpected error occurred while communicating with the server. Please try again.')).toBeInTheDocument();
  });

  it('renders custom title and message', () => {
    render(<ErrorState title="Custom Title" message="Custom Error Message" />);
    expect(screen.getByText('Custom Title')).toBeInTheDocument();
    expect(screen.getByText('Custom Error Message')).toBeInTheDocument();
  });

  it('renders retry button when onRetry is provided', () => {
    const handleRetry = vi.fn();
    render(<ErrorState onRetry={handleRetry} />);
    
    const retryBtn = screen.getByRole('button', { name: /retry/i });
    expect(retryBtn).toBeInTheDocument();
    
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it('does not render retry button if onRetry is not provided', () => {
    render(<ErrorState />);
    const retryBtn = screen.queryByRole('button', { name: /retry/i });
    expect(retryBtn).not.toBeInTheDocument();
  });

  it('renders compact mode correctly', () => {
    render(<ErrorState compact={true} message="Compact Error" onRetry={vi.fn()} />);
    expect(screen.getByText('Compact Error')).toBeInTheDocument();
    // In compact mode, the button text is "Retry" instead of "Retry Request"
    expect(screen.getByRole('button', { name: /retry/i })).toHaveTextContent('Retry');
  });

  it('handles specific error statuses (e.g. 404)', () => {
    // We can test if it accepts the error prop without crashing
    render(<ErrorState error={404} title="Not Found" />);
    expect(screen.getByText('Not Found')).toBeInTheDocument();
  });
});
