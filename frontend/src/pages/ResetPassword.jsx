import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sparkles, ArrowRight, Lock, Check, X, Eye, EyeOff } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../services/api';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      toast.error('Invalid or missing reset token.');
      navigate('/login', { replace: true });
    }
  }, [token, navigate]);

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
    return (
      passwordValidation.minLength &&
      passwordValidation.hasUpper &&
      passwordValidation.hasLower &&
      passwordValidation.hasNumber &&
      passwordValidation.hasSpecial
    );
  }, [passwordValidation]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isPasswordValid) {
      return toast.error('Password does not meet the requirements.');
    }
    if (password !== confirmPassword) {
      return toast.error('Passwords do not match.');
    }

    setLoading(true);
    try {
      await api.post('/auth/reset-password', {
        token,
        new_password: password,
      });
      toast.success('Password reset successfully. Please log in.');
      navigate('/login', { replace: true });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to reset password.');
    } finally {
      setLoading(false);
    }
  };

  if (!token) return null;

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[#0B0F19] relative overflow-hidden">
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-600/20 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-md rounded-3xl p-8 glass-panel border border-indigo-500/30 bg-[#0E1322]/95 shadow-2xl relative z-10">
        <div className="text-center space-y-2 mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-400 p-[1px] shadow-lg shadow-indigo-500/30 mb-2">
            <div className="w-full h-full bg-[#0B0F19] rounded-[15px] flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-indigo-400" />
            </div>
          </div>
          <h2 className="text-2xl font-extrabold text-white font-sans tracking-tight">Set New Password</h2>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
              New Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
              <input
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-xs text-white focus:outline-none focus:border-indigo-500"
                placeholder="Min 10 characters"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300 transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {password.length > 0 && (
              <div className="space-y-2 mt-3 p-3 bg-gray-900/50 rounded-xl border border-gray-800/50 text-xs">
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
            )}
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
              Confirm Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
              <input
                type={showConfirmPassword ? "text" : "password"}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-xs text-white focus:outline-none focus:border-indigo-500"
                placeholder="Confirm password"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300 transition-colors"
              >
                {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !isPasswordValid || password !== confirmPassword}
            className="w-full mt-4 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-xs shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <span>{loading ? 'Processing...' : 'Reset Password'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
