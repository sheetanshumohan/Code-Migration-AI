import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from './stores/authStore';

import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import AppErrorBoundary from './components/AppErrorBoundary';

const Dashboard            = lazy(() => import('./pages/Dashboard'));
const RepositoryExplorer   = lazy(() => import('./pages/RepositoryExplorer'));
const MigrationStudio      = lazy(() => import('./pages/MigrationStudio'));
const WorkflowHistory      = lazy(() => import('./pages/WorkflowHistory'));
const ReportsPage          = lazy(() => import('./pages/ReportsPage'));
const AIChat               = lazy(() => import('./pages/AIChat'));
const Login                = lazy(() => import('./pages/Login'));
const AuthCallback         = lazy(() => import('./pages/AuthCallback'));
const ResetPassword        = lazy(() => import('./pages/ResetPassword'));
const PricingPage          = lazy(() => import('./pages/PricingPage'));

/** Spinner shown while lazy chunks are loading */
function PageLoader({ label = 'Loading page...' }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-indigo-400 gap-3 mt-20">
      <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      <span className="text-xs font-mono tracking-widest uppercase text-gray-500">{label}</span>
    </div>
  );
}

function ProtectedLayout() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-[#0B0F19] text-gray-100 flex flex-col font-sans">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 overflow-y-auto max-h-[calc(100vh-4rem)]">
          {/* Per-route error boundary keeps layout intact on page-level crashes */}
          <AppErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/"              element={<Dashboard />} />
                <Route path="/repositories"  element={<RepositoryExplorer />} />
                <Route path="/migration-studio" element={<MigrationStudio />} />
                <Route path="/history"       element={<WorkflowHistory />} />
                <Route path="/chat"          element={<AIChat />} />
                <Route path="/reports"       element={<ReportsPage />} />
                <Route path="/pricing"       element={<PricingPage />} />
                <Route path="*"             element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </AppErrorBoundary>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#111827',
            color: '#fff',
            border: '1px solid #374151',
            fontSize: '13px',
            maxWidth: '420px',
          },
          error: {
            duration: 6000,
          },
          success: {
            duration: 4000,
          },
        }}
      />
      {/* Top-level boundary for auth pages */}
      <AppErrorBoundary>
        <Suspense fallback={
          <div className="flex items-center justify-center min-h-screen bg-[#0B0F19] text-gray-500">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        }>
          <Routes>
            <Route path="/login"          element={<Login />} />
            <Route path="/auth/callback"  element={<AuthCallback />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/*"             element={<ProtectedLayout />} />
          </Routes>
        </Suspense>
      </AppErrorBoundary>
    </Router>
  );
}
