import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Navbar from '../../src/components/Navbar';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
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

  const renderNavbar = () => render(
    <MemoryRouter>
      <Navbar />
    </MemoryRouter>
  );

  it('renders correctly with brand identity', () => {
    renderNavbar();
    expect(screen.getByText('Code Migration AI')).toBeInTheDocument();
  });

  it('displays user information when logged in', () => {
    useAuthStore.mockReturnValue({
      user: { full_name: 'John Doe', plan_tier: 'pro', organization_name: 'Acme Corp' },
      logout: mockLogout,
    });

    renderNavbar();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText(/pro Plan · Acme Corp/i)).toBeInTheDocument();
  });

  it('falls back to email if full_name is missing', () => {
    useAuthStore.mockReturnValue({
      user: { email: 'john@example.com' },
      logout: mockLogout,
    });

    renderNavbar();
    expect(screen.getByText('john@example.com')).toBeInTheDocument();
  });

  it('calls logout when the logout button is clicked', () => {
    useAuthStore.mockReturnValue({
      user: { full_name: 'John Doe' },
      logout: mockLogout,
    });

    renderNavbar();
    const logoutBtn = screen.getByRole('button', { name: /logout/i });
    fireEvent.click(logoutBtn);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it('displays degraded status on query error', () => {
    useQuery.mockReturnValue({
      data: null,
      isError: true,
    });

    renderNavbar();
    expect(screen.getByText('Service Degraded')).toBeInTheDocument();
  });

  it('displays all systems operational when health is healthy', () => {
    useQuery.mockReturnValue({
      data: { status: 'healthy' },
      isError: false,
    });

    renderNavbar();
    expect(screen.getByText('All Systems Operational')).toBeInTheDocument();
  });
});
