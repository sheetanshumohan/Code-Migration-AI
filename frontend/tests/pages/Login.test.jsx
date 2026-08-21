import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Login from '../../src/pages/Login';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';

// Mock Dependencies
vi.mock('../../src/services/api', () => ({
  default: {
    post: vi.fn(),
  },
}));
import api from '../../src/services/api';

vi.mock('../../src/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));
import { useAuthStore } from '../../src/stores/authStore';

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));
import toast from 'react-hot-toast';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('Login Page', () => {
  let mockSetAuth;

  beforeEach(() => {
    mockSetAuth = vi.fn();
    useAuthStore.mockImplementation((selector) => {
      // Return setAuth when the component selects it
      return mockSetAuth;
    });

    vi.clearAllMocks();
  });

  const renderLogin = () => {
    return render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );
  };

  it('renders login form by default', () => {
    renderLogin();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByText(/don't have an account\? register/i)).toBeInTheDocument();
  });

  it('switches to register form when register link is clicked', () => {
    renderLogin();
    fireEvent.click(screen.getByText(/don't have an account\? register/i));
    
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
    expect(screen.getByText(/already have an account\? sign in/i)).toBeInTheDocument();
    // Check if new fields are present
    expect(screen.getByText(/full name/i)).toBeInTheDocument();
    expect(screen.getByText(/organization name/i)).toBeInTheDocument();
  });

  it('submits login and shows OTP step on success', async () => {
    api.post.mockResolvedValueOnce({ data: { requires_otp: true, message: 'OTP sent' } });
    
    renderLogin();
    
    // Fill the inputs (email, password are the only text/password inputs initially)
    const emailInput = screen.getByLabelText(/email address/i);
    const passwordInput = screen.getByLabelText(/^password/i);
    
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/login', {
        email: 'test@example.com',
        password: 'password123',
      });
    });

    // Verify OTP step appears
    await waitFor(() => {
      expect(screen.getByText(/enter 6-digit otp/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /verify otp/i })).toBeInTheDocument();
    });
  });

  it('submits OTP and navigates on success', async () => {
    // Setup to be already in OTP step for a login
    // Since state is internal, we simulate the first step
    api.post.mockResolvedValueOnce({ data: { requires_otp: true, message: 'OTP sent' } });
    renderLogin();
    
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/enter 6-digit otp/i)).toBeInTheDocument();
    });

    // Now submit OTP
    api.post.mockResolvedValueOnce({ 
      data: { user: { full_name: 'Test' }, access_token: 'token', refresh_token: 'refresh' } 
    });

    const otpInput = screen.getByPlaceholderText('123456');
    fireEvent.change(otpInput, { target: { value: '111111' } });
    fireEvent.click(screen.getByRole('button', { name: /verify otp/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/verify-login-otp', {
        email: 'test@example.com',
        otp: '111111',
      });
      expect(mockSetAuth).toHaveBeenCalledWith({ full_name: 'Test' }, 'token', 'refresh');
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  it('shows error toast on API failure', async () => {
    api.post.mockRejectedValueOnce({ response: { data: { detail: 'Invalid credentials' } } });
    
    renderLogin();
    
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'wrong' } });
    
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Invalid credentials');
    });
  });

  it('disables submit button if required fields are missing or invalid', () => {
    renderLogin();
    const submitBtn = screen.getByRole('button', { name: /sign in/i });
    expect(submitBtn).toBeDisabled();

    // Fill invalid email
    const emailInput = screen.getByLabelText(/email address/i);
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    fireEvent.blur(emailInput);
    expect(screen.getByText(/invalid email format/i)).toBeInTheDocument();
    expect(submitBtn).toBeDisabled();

    // Fill valid email and password
    fireEvent.change(emailInput, { target: { value: 'user@example.com' } });
    const passwordInput = screen.getByLabelText(/^password/i);
    fireEvent.change(passwordInput, { target: { value: 'secret123' } });
    expect(submitBtn).not.toBeDisabled();
  });

  it('displays interactive password requirement checklist on register page', () => {
    renderLogin();
    fireEvent.click(screen.getByText(/don't have an account\? register/i));

    const createAccountBtn = screen.getByRole('button', { name: /create account/i });
    expect(createAccountBtn).toBeDisabled();

    expect(screen.getByText(/password requirements:/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 1 uppercase letter/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 1 lowercase letter/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 1 number/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 1 special character/i)).toBeInTheDocument();

    // Fill inputs meeting all criteria
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jane Doe' } });
    fireEvent.change(screen.getByLabelText(/organization name/i), { target: { value: 'Tech Corp' } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'jane@techcorp.com' } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'Valid@Pass123' } });

    expect(createAccountBtn).not.toBeDisabled();
  });

  it('toggles password visibility with show/hide button', () => {
    renderLogin();
    const passwordInput = screen.getByLabelText(/^password/i);
    expect(passwordInput).toHaveAttribute('type', 'password');

    const toggleBtn = screen.getByRole('button', { name: /show password/i });
    fireEvent.click(toggleBtn);
    expect(passwordInput).toHaveAttribute('type', 'text');

    const hideBtn = screen.getByRole('button', { name: /hide password/i });
    fireEvent.click(hideBtn);
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('clears input fields when switching between Login and Register modes', () => {
    renderLogin();
    const emailInput = screen.getByLabelText(/email address/i);
    const passwordInput = screen.getByLabelText(/^password/i);

    fireEvent.change(emailInput, { target: { value: 'user@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Secret123!' } });

    expect(emailInput.value).toBe('user@example.com');
    expect(passwordInput.value).toBe('Secret123!');

    // Switch to register
    fireEvent.click(screen.getByText(/don't have an account\? register/i));

    const newEmailInput = screen.getByLabelText(/email address/i);
    const newPasswordInput = screen.getByLabelText(/^password/i);
    expect(newEmailInput.value).toBe('');
    expect(newPasswordInput.value).toBe('');
  });
});
