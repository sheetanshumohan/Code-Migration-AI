import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  GitFork,
  Cpu,
  History,
  Network,
  FileCheck2,
  ShieldCheck,
  Settings,
  Flame,
  Sparkles,
  ShieldAlert,
  Building2
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { useAuthStore } from '../stores/authStore';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Repository Explorer', href: '/repositories', icon: GitFork },
  { name: 'Migration Studio', href: '/migration-studio', icon: Cpu, badge: 'Live' },
  { name: 'Migration History', href: '/history', icon: History },
  { name: 'AI Architecture Copilot', href: '/chat', icon: Sparkles },
  { name: 'Reports & Audits', href: '/reports', icon: FileCheck2 },
  { name: 'Pricing & Plans', href: '/pricing', icon: Sparkles },
];

export default function Sidebar() {
  return (
    <aside className="w-64 border-r border-gray-800/80 bg-[#0B0F19] flex flex-col justify-between py-6 px-3 min-h-[calc(100vh-4rem)]">
      <div className="space-y-1">
        <div className="px-3 pb-3 text-[11px] font-semibold tracking-wider text-gray-500 uppercase">
          Autonomous Engineering
        </div>
        {navigation.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30 shadow-sm shadow-indigo-500/10'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                }`
              }
            >
              <div className="flex items-center gap-3">
                <Icon className="w-4 h-4" />
                <span>{item.name}</span>
              </div>
              {item.badge && (
                <span className="px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase bg-emerald-500/20 text-emerald-400 rounded-full border border-emerald-500/30 animate-pulse">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </div>

      {/* Live Engine Stats — driven by real KPI data */}
      <SidebarEngineWidget />
    </aside>
  );
}

function SidebarEngineWidget() {
  const { data: kpi } = useQuery({
    queryKey: ['kpis'],           // shares cache with Dashboard
    queryFn: async () => {
      const res = await api.get('/metrics/kpi', { _silent: true });
      return res.data;
    },
    refetchInterval: 30000,
    staleTime: 20000,
  });

  const active = kpi?.active_workflows ?? null;

  return (
    <div className="mx-2 p-3.5 rounded-2xl glass-panel border border-indigo-500/20 bg-gradient-to-b from-indigo-950/20 to-transparent">
      <div className="flex items-center gap-2 mb-2">
        <Flame className="w-4 h-4 text-amber-400" />
        <span className="text-xs font-semibold text-gray-200">Autonomous Core</span>
      </div>
      <p className="text-[11px] text-gray-400 leading-relaxed mb-3">
        LangGraph Multi-Agent State Machine · Python 3.13
      </p>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-gray-500">Active workflows</span>
        <span className={`font-bold font-mono ${
          active === null ? 'text-gray-600' : active > 0 ? 'text-emerald-400' : 'text-gray-500'
        }`}>
          {active === null ? '—' : active}
        </span>
      </div>
    </div>
  );
}
