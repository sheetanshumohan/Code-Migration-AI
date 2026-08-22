import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useWorkflowStore } from '../stores/workflowStore';
import { LogOut, Sparkles, PlusCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

function SystemStatusBadge() {
  const { data: health, isError } = useQuery({
    queryKey: ['navSystemHealth'],
    queryFn: async () => {
      const res = await api.get('/health', { _silent: true });
      return res.data;
    },
    refetchInterval: 15000,
    retry: 1,
    staleTime: 10000,
  });

  if (isError) {
    return (
      <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-950/40 border border-red-800/50 text-xs text-red-400">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        <span>Service Degraded</span>
      </div>
    );
  }

  const isReady = health?.status === 'healthy' || health?.status === 'degraded';
  const isFullyHealthy = health?.status === 'healthy';

  return (
    <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900/60 border border-gray-800 text-xs text-gray-300">
      <span className={`w-2 h-2 rounded-full ${isFullyHealthy ? 'bg-emerald-400 animate-pulse' : isReady ? 'bg-amber-400' : 'bg-gray-500'}`} />
      {isFullyHealthy
        ? <span>All Systems Operational</span>
        : isReady
        ? <span>Systems Operational (Partial)</span>
        : <span>Checking cluster…</span>
      }
    </div>
  );
}

function UserTierBadge({ planTier }) {
  const tier = (planTier || 'free').toLowerCase();

  if (tier === 'pro') {
    return (
      <span className="ml-2 text-[10px] uppercase tracking-wider font-bold px-2.5 py-0.5 rounded-full bg-indigo-950/90 text-indigo-300 border border-indigo-600/70 shadow-sm shadow-indigo-900/40">
        Pro User
      </span>
    );
  }

  if (tier === 'unlimited' || tier === 'premium' || tier === 'full_time' || tier === 'full-time') {
    return (
      <span className="ml-2 text-[10px] uppercase tracking-wider font-bold px-2.5 py-0.5 rounded-full bg-gradient-to-r from-amber-500/20 via-purple-500/20 to-amber-500/20 text-amber-300 border border-amber-500/50 shadow-sm shadow-amber-950/50 animate-pulse">
        Premium User
      </span>
    );
  }

  // Default: Normal / Free Tier User
  return (
    <span className="ml-2 text-[10px] uppercase tracking-wider font-semibold px-2.5 py-0.5 rounded-full bg-slate-900/90 text-emerald-400 border border-emerald-700/60 shadow-sm">
      Free Tier
    </span>
  );
}

export default function Navbar() {
  const navigate = useNavigate();
  const { logout } = useAuthStore();
  const { user } = useAuthStore();
  const { initiateNewModernization } = useWorkflowStore();

  // Keep user profile data in sync with real-time backend updates
  const { data: userProfile } = useQuery({
    queryKey: ['navUserProfile'],
    queryFn: async () => {
      const res = await api.get('/auth/me', { _silent: true });
      return res.data;
    },
    staleTime: 30000,
    retry: 1,
  });

  const activePlanTier = userProfile?.plan_tier || user?.plan_tier || 'free';
  const displayName = userProfile?.full_name || user?.full_name || user?.email || 'Developer';
  const orgName = userProfile?.organization_name || user?.organization_name || null;

  return (
    <header className="h-16 border-b border-gray-800/80 bg-[#0B0F19]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Brand Identity */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-[1px] shadow-lg shadow-indigo-500/20">
          <div className="w-full h-full bg-[#0B0F19] rounded-[11px] flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-indigo-400" />
          </div>
        </div>
        <div className="flex items-center">
          <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-100 to-indigo-300 font-sans tracking-tight">
            Code Migration AI
          </span>
          <UserTierBadge planTier={activePlanTier} />
        </div>
      </div>

      {/* Actions, System Status & Profile */}
      <div className="flex items-center gap-3">
        {/* Quick New Modernization Action */}
        <button
          id="nav-new-modernization-btn"
          onClick={() => {
            initiateNewModernization();
            navigate('/migration-studio');
          }}
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600/30 to-cyan-500/30 hover:from-indigo-600/50 hover:to-cyan-500/50 border border-indigo-500/40 text-indigo-200 text-xs font-semibold shadow-sm transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          title="Start a new modernization workflow"
        >
          <PlusCircle className="w-3.5 h-3.5 text-cyan-400" />
          <span>New Modernization</span>
        </button>

        {/* Live cluster status from /admin/system-health */}
        <SystemStatusBadge />

        {/* User Info */}
        <div className="flex items-center gap-3 pl-3 border-l border-gray-800">
          <div className="text-right">
            <p className="text-xs font-medium text-gray-200">
              {displayName}
            </p>
            <p className="text-[11px] text-gray-400 capitalize">
              {activePlanTier === 'unlimited' ? 'Premium Tier' : `${activePlanTier} Plan`}
              {orgName ? ` · ${orgName}` : ''}
            </p>
          </div>
          <button
            onClick={logout}
            title="Logout"
            aria-label="Logout"
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800/80 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
