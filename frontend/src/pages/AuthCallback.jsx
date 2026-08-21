import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import toast from 'react-hot-toast';
import { Loader2, AlertTriangle } from 'lucide-react';
import api from '../services/api';

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [error, setError] = useState(null);

  useEffect(() => {
    const accessToken  = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');

    if (!accessToken) {
      setError('Authentication failed: No access token provided.');
      toast.error('Authentication failed. Redirecting to login…');
      setTimeout(() => navigate('/login', { replace: true }), 3000);
      return;
    }

    // Store token immediately so the API interceptor can attach it
    // then fetch full profile from /auth/me
    const completeOAuth = async () => {
      try {
        // Temporarily set the token in localStorage so api.js sends it
        localStorage.setItem('codemigration_token', accessToken);
        if (refreshToken) {
          localStorage.setItem('codemigration_refresh_token', refreshToken);
        }

        // Fetch full user profile (includes full_name, email, org name)
        const { data: userProfile } = await api.get('/auth/me');

        // Persist complete profile
        setAuth(userProfile, accessToken, refreshToken ?? undefined);
        toast.success(`Welcome, ${userProfile.full_name || 'Enterprise User'}!`);
        navigate('/', { replace: true });
      } catch (err) {
        // Clean up partial state
        localStorage.removeItem('codemigration_token');
        localStorage.removeItem('codemigration_refresh_token');
        const msg = err?.response?.data?.detail || 'Failed to retrieve user profile after OAuth.';
        setError(msg);
        toast.error(msg);
        setTimeout(() => navigate('/login', { replace: true }), 3000);
      }
    };

    completeOAuth();
  }, [searchParams, navigate, setAuth]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#0B0F19] text-gray-100 gap-4">
      {error ? (
        <>
          <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center">
            <AlertTriangle className="w-7 h-7 text-red-400" />
          </div>
          <h2 className="text-lg font-semibold text-red-300">{error}</h2>
          <p className="text-sm text-gray-400">Redirecting to login…</p>
        </>
      ) : (
        <>
          <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
          <h2 className="text-xl font-semibold">Completing Authentication…</h2>
          <p className="text-gray-400 text-sm">Fetching your profile from the server.</p>
        </>
      )}
    </div>
  );
}
