import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Shield, ArrowRight, Lock, Mail, Building, Check, X, AlertCircle, Eye, EyeOff } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuthStore } from '../stores/authStore';
import api, { getGoogleLoginUrl } from '../services/api';

export default function Login() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [orgName, setOrgName] = useState('');
  const [loading, setLoading] = useState(false);
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [emailTouched, setEmailTouched] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  
  const [otpStep, setOtpStep] = useState(false);
  const [otp, setOtp] = useState('');

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const error = urlParams.get('error');
    if (error === 'oauth_failed') {
      toast.error('Google Authentication failed or was cancelled.');
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const switchAuthMode = (targetIsRegister) => {
    setIsRegister(targetIsRegister);
    setIsForgotPassword(false);
    setEmail('');
    setPassword('');
    setFullName('');
    setOrgName('');
    setEmailTouched(false);
    setShowPassword(false);
    setOtpStep(false);
    setOtp('');
  };

  // Validation helpers
  const isEmailValid = useMemo(() => {
    if (!email.trim()) return false;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email.trim());
  }, [email]);

  const passwordValidation = useMemo(() => {
    return {
      minLength: password.length >= 10,
      hasUpper: /[A-Z]/.test(password),
      hasLower: /[a-z]/.test(password),
      hasNumber: /[0-9]/.test(password),
      hasSpecial: /[!@#$%^&*(),.?":{}|<>]/.test(password),
    };
  }, [password]);

  const isPasswordValid = useMemo(() => {
    if (!isRegister) return password.length > 0;
    return (
      passwordValidation.minLength &&
      passwordValidation.hasUpper &&
      passwordValidation.hasLower &&
      passwordValidation.hasNumber &&
      passwordValidation.hasSpecial
    );
  }, [isRegister, password, passwordValidation]);

  const isFormValid = useMemo(() => {
    if (otpStep) {
      return otp.trim().length === 6;
    }
    if (isForgotPassword) {
      return isEmailValid;
    }
    if (isRegister) {
      return (
        fullName.trim().length > 0 &&
        orgName.trim().length > 0 &&
        isEmailValid &&
        isPasswordValid
      );
    }
    // Standard login
    return isEmailValid && password.trim().length > 0;
  }, [otpStep, otp, isForgotPassword, isRegister, fullName, orgName, isEmailValid, isPasswordValid, password]);

  const handleGoogleLogin = () => {
    const loginUrl = getGoogleLoginUrl();
    window.location.href = loginUrl;
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    if (!isFormValid) return;
    setLoading(true);
    try {
      const res = await api.post('/auth/forgot-password', { email: email.trim() });
      toast.success(res.data.message || 'Reset link sent!');
      setIsForgotPassword(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to request password reset.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isFormValid) return;
    setLoading(true);

    try {
      if (otpStep) {
        // Submit OTP
        const endpoint = isRegister ? '/auth/verify-register-otp' : '/auth/verify-login-otp';
        const res = await api.post(endpoint, { email: email.trim(), otp: otp.trim() });
        setAuth(res.data.user, res.data.access_token, res.data.refresh_token);
        toast.success(isRegister ? 'Organization registered successfully!' : `Welcome back, ${res.data.user.full_name}.`);
        navigate('/');
      } else {
        // Step 1: Request OTP
        if (isRegister) {
          const res = await api.post('/auth/register', {
            email: email.trim(),
            password,
            full_name: fullName.trim(),
            organization_name: orgName.trim(),
          });
          if (res.data.requires_otp) {
            setOtpStep(true);
            toast.success(res.data.message);
          }
        } else {
          const res = await api.post('/auth/login', { email: email.trim(), password });
          if (res.data.requires_otp) {
            setOtpStep(true);
            toast.success(res.data.message);
          }
        }
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Authentication failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[#0B0F19] relative overflow-hidden">
      {/* Ambient background glows */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-600/20 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-md rounded-3xl p-8 glass-panel border border-indigo-500/30 bg-[#0E1322]/95 shadow-2xl relative z-10">
        {/* Brand */}
        <div className="text-center space-y-2 mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-400 p-[1px] shadow-lg shadow-indigo-500/30 mb-2">
            <div className="w-full h-full bg-[#0B0F19] rounded-[15px] flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-indigo-400" />
            </div>
          </div>
          <h2 className="text-2xl font-extrabold text-white font-sans tracking-tight">Code Migration AI</h2>
          <p className="text-xs text-gray-400">Enterprise Autonomous Code Modernization Platform</p>
        </div>

        <form onSubmit={isForgotPassword ? handleForgotPassword : handleSubmit} className="space-y-4">
          {otpStep ? (
            <div>
              <label className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
                Enter 6-Digit OTP
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-indigo-400/70" />
                </div>
                <input
                  type="text"
                  required
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 rounded-xl border border-indigo-500/20 bg-[#0B0F19]/50 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 sm:text-sm transition-all"
                  placeholder="123456"
                  maxLength={6}
                />
              </div>
            </div>
          ) : !otpStep && !isForgotPassword && isRegister && (
            <>
              <div>
                <label htmlFor="fullName" className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
                  Full Name <span className="text-rose-400">*</span>
                </label>
                <input
                  id="fullName"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full px-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label htmlFor="orgName" className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
                  Organization Name <span className="text-rose-400">*</span>
                </label>
                <input
                  id="orgName"
                  type="text"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="Acme Corp"
                  className="w-full px-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </>
          )}

          {!otpStep && (
            <div>
              <div className="flex justify-between items-center mb-1">
                <label htmlFor="email" className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider">
                  Email Address <span className="text-rose-400">*</span>
                </label>
                {email.trim().length > 0 && (
                  isEmailValid ? (
                    <span className="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
                      <Check className="w-3 h-3" /> Valid email
                    </span>
                  ) : (
                    emailTouched && (
                      <span className="text-[10px] text-rose-400 font-medium flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" /> Invalid email format
                      </span>
                    )
                  )
                )}
              </div>
              <div className="relative">
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onBlur={() => setEmailTouched(true)}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className={`w-full px-4 py-2.5 rounded-xl bg-gray-900 border text-xs text-white placeholder-gray-600 focus:outline-none transition-colors ${
                    email.trim().length > 0
                      ? isEmailValid
                        ? 'border-emerald-500/50 focus:border-emerald-400'
                        : emailTouched
                        ? 'border-rose-500/60 focus:border-rose-500'
                        : 'border-gray-800 focus:border-indigo-500'
                      : 'border-gray-800 focus:border-indigo-500'
                  }`}
                />
                {email.trim().length > 0 && isEmailValid && (
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                    <Check className="h-4 w-4 text-emerald-400" />
                  </div>
                )}
              </div>
            </div>
          )}

          {!otpStep && !isForgotPassword && (
            <div>
              <div className="flex justify-between items-center mb-1">
                <label htmlFor="password" className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider">
                  Password <span className="text-rose-400">*</span>
                </label>
                {isRegister && password.length > 0 && (
                  isPasswordValid ? (
                    <span className="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
                      <Check className="w-3 h-3" /> Password requirements met
                    </span>
                  ) : (
                    <span className="text-[10px] text-amber-400 font-medium flex items-center gap-1">
                      Incomplete requirements
                    </span>
                  )
                )}
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className={`w-full pl-4 pr-16 py-2.5 rounded-xl bg-gray-900 border text-xs text-white placeholder-gray-600 focus:outline-none transition-colors ${
                    isRegister && password.length > 0
                      ? isPasswordValid
                        ? 'border-emerald-500/50 focus:border-emerald-400'
                        : 'border-gray-800 focus:border-indigo-500'
                      : 'border-gray-800 focus:border-indigo-500'
                  }`}
                />
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center gap-1.5">
                  {isRegister && password.length > 0 && isPasswordValid && (
                    <Check className="h-4 w-4 text-emerald-400" />
                  )}
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-gray-400 hover:text-gray-200 focus:outline-none transition-colors p-1"
                    title={showPassword ? 'Hide password' : 'Show password'}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Password Requirement Rules (Shown only on Register page) */}
              {isRegister && (
                <div className={`mt-3 p-3 rounded-xl space-y-1.5 transition-colors border ${
                  isPasswordValid
                    ? 'bg-emerald-950/20 border-emerald-500/30'
                    : 'bg-gray-950/60 border-gray-800/80'
                }`}>
                  <div className="flex justify-between items-center mb-1">
                    <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">
                      Password Requirements:
                    </p>
                    {isPasswordValid && (
                      <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
                        <Check className="w-3 h-3" /> All Met
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-1 gap-1 text-[11px]">
                    <div className={`flex items-center gap-1.5 transition-colors ${passwordValidation.minLength ? 'text-emerald-400' : 'text-gray-500'}`}>
                      {passwordValidation.minLength ? <Check className="w-3.5 h-3.5 flex-shrink-0 text-emerald-400" /> : <X className="w-3.5 h-3.5 flex-shrink-0" />}
                      <span>At least 10 characters</span>
                    </div>
                    <div className={`flex items-center gap-1.5 transition-colors ${passwordValidation.hasUpper ? 'text-emerald-400' : 'text-gray-500'}`}>
                      {passwordValidation.hasUpper ? <Check className="w-3.5 h-3.5 flex-shrink-0 text-emerald-400" /> : <X className="w-3.5 h-3.5 flex-shrink-0" />}
                      <span>At least 1 uppercase letter (A-Z)</span>
                    </div>
                    <div className={`flex items-center gap-1.5 transition-colors ${passwordValidation.hasLower ? 'text-emerald-400' : 'text-gray-500'}`}>
                      {passwordValidation.hasLower ? <Check className="w-3.5 h-3.5 flex-shrink-0 text-emerald-400" /> : <X className="w-3.5 h-3.5 flex-shrink-0" />}
                      <span>At least 1 lowercase letter (a-z)</span>
                    </div>
                    <div className={`flex items-center gap-1.5 transition-colors ${passwordValidation.hasNumber ? 'text-emerald-400' : 'text-gray-500'}`}>
                      {passwordValidation.hasNumber ? <Check className="w-3.5 h-3.5 flex-shrink-0 text-emerald-400" /> : <X className="w-3.5 h-3.5 flex-shrink-0" />}
                      <span>At least 1 number (0-9)</span>
                    </div>
                    <div className={`flex items-center gap-1.5 transition-colors ${passwordValidation.hasSpecial ? 'text-emerald-400' : 'text-gray-500'}`}>
                      {passwordValidation.hasSpecial ? <Check className="w-3.5 h-3.5 flex-shrink-0 text-emerald-400" /> : <X className="w-3.5 h-3.5 flex-shrink-0" />}
                      <span>At least 1 special character (!@#$%^&*...)</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !isFormValid}
            className="w-full flex items-center justify-center py-3.5 px-4 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-indigo-500 to-cyan-500 hover:from-indigo-400 hover:to-cyan-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0B0F19] focus:ring-indigo-500 shadow-lg shadow-indigo-500/25 transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:from-indigo-500 disabled:hover:to-cyan-500 group cursor-pointer"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <>
                {otpStep ? 'Verify OTP' : isForgotPassword ? 'Send Reset Link' : isRegister ? 'Create Account' : 'Sign In'}
                <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </>
            )}
          </button>
        </form>

        {!isForgotPassword && !otpStep && (
          <>
            <div className="my-6 flex items-center gap-3">
              <div className="h-px bg-gray-800 flex-1"></div>
              <span className="text-xs text-gray-500 uppercase tracking-wider">OR</span>
              <div className="h-px bg-gray-800 flex-1"></div>
            </div>

            <button
              type="button"
              onClick={handleGoogleLogin}
              className="w-full py-2.5 rounded-xl bg-white text-gray-900 font-semibold text-xs shadow-sm hover:bg-gray-100 transition-colors flex items-center justify-center gap-2 cursor-pointer"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
              <span>Continue with Google</span>
            </button>
          </>
        )}

        <div className="mt-8 pt-4 border-t border-gray-800/60 flex flex-col items-center gap-3">
          {!otpStep && (
            <button
              type="button"
              onClick={() => switchAuthMode(!isRegister)}
              className="text-sm font-medium text-gray-300 hover:text-indigo-400 transition-colors cursor-pointer py-1"
            >
              {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Register"}
            </button>
          )}
          {!isRegister && !isForgotPassword && (
            <button
              type="button"
              onClick={() => {
                setIsForgotPassword(true);
                setPassword('');
                setShowPassword(false);
              }}
              className="text-xs text-gray-400 hover:text-indigo-300 transition-colors cursor-pointer py-1"
            >
              Forgot Password?
            </button>
          )}
          {isForgotPassword && (
            <button
              type="button"
              onClick={() => {
                setIsForgotPassword(false);
                setPassword('');
                setShowPassword(false);
              }}
              className="text-xs text-gray-400 hover:text-indigo-300 transition-colors cursor-pointer py-1"
            >
              Back to Login
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
