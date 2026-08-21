import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Navbar from '../../src/components/Navbar';
import React from 'react';
import { useAuthStore } from '../../src/stores/authStore';

// Mock the Auth Store
vi.mock('../../src/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

// Mock react-query
vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
}));

import { useQuery } from '@tanstack/react-query';

describe('Navbar component', () => {
  let mockLogout;

  beforeEach(() => {
    mockLogout = vi.fn();
    useAuthStore.mockReturnValue({
      user: null,
      logout: mockLogout,
    });
    
    useQuery.mockReturnValue({
      data: null,
      isError: false,
    });
  });

  it('renders correctly with brand identity', () => {
    render(<Navbar />);
    expect(screen.getByText('Code Migration AI')).toBeInTheDocument();
  });

  it('displays user information when logged in', () => {
    useAuthStore.mockReturnValue({
      user: { full_name: 'John Doe', role: 'admin', organization_name: 'Acme Corp' },
      logout: mockLogout,
    });

    render(<Navbar />);
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText(/admin · Acme Corp/i)).toBeInTheDocument();
  });

  it('falls back to email if full_name is missing', () => {
    useAuthStore.mockReturnValue({
      user: { email: 'john@example.com' },
      logout: mockLogout,
    });

    render(<Navbar />);
    expect(screen.getByText('john@example.com')).toBeInTheDocument();
  });

  it('calls logout when the logout button is clicked', () => {
    useAuthStore.mockReturnValue({
      user: { full_name: 'John Doe' },
      logout: mockLogout,
    });

    render(<Navbar />);
    const logoutBtn = screen.getByRole('button', { name: /logout/i });
    fireEvent.click(logoutBtn);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it('displays degraded status on query error', () => {
    useQuery.mockReturnValue({
      data: null,
      isError: true,
    });

    render(<Navbar />);
    expect(screen.getByText('Service Degraded')).toBeInTheDocument();
  });

  it('displays active workers when query is successful', () => {
    useQuery.mockReturnValue({
      data: { celery_workers: 4, queue_depth: 10 },
      isError: false,
    });

    render(<Navbar />);
    expect(screen.getByText(/4 Workers Active · 10 Queued/i)).toBeInTheDocument();
  });
});
