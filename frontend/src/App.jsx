import React, { Suspense, lazy, useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { useAuthStore } from './stores/authStore';
import api from './services/api';

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

function HealthCheckGate({ children }) {
  const [isHealthy, setIsHealthy] = useState(null);
  const [isBypassed, setIsBypassed] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [errorDetails, setErrorDetails] = useState(null);

  const checkHealth = async () => {
    setIsChecking(true);
    try {
      const res = await api.get('/health', { _silent: true, timeout: 60000 });
      
      // Detect if static SPA HTML was returned instead of JSON
      const isHtmlResponse = typeof res.data === 'string' && (
        res.data.toLowerCase().includes('<!doctype') || 
        res.data.toLowerCase().includes('<html')
      );
      if (isHtmlResponse) {
        setIsHealthy(false);
        setErrorDetails('Received HTML instead of API JSON response. Ensure VITE_API_URL includes the https:// protocol (e.g. https://code-migration-ai.onrender.com).');
        return false;
      }

      // Accept 'healthy', 'degraded', or any valid 200 response
      if (res.status === 200 && (
        res.data?.status === 'healthy' || 
        res.data?.status === 'degraded' || 
        res.data?.service === 'codemigration-api' ||
        (typeof res.data === 'object' && res.data !== null && 'status' in res.data)
      )) {
        setIsHealthy(true);
        setErrorDetails(null);
        return true;
      } else {
        setIsHealthy(false);
        setErrorDetails(res.data?.status ? `Service status: ${res.data.status}` : 'Backend returned unexpected response format');
        return false;
      }
    } catch (err) {
      setIsHealthy(false);
      setErrorDetails(err.response?.data?.detail || err.message || 'Unable to establish connection to backend API');
      return false;
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    let timeoutId;
    
    const runCheck = async () => {
      const ok = await checkHealth();
      if (!ok && mounted) {
        timeoutId = setTimeout(runCheck, 6000);
      }
    };

    runCheck();

    return () => {
      mounted = false;
      clearTimeout(timeoutId);
    };
  }, []);

  if (isBypassed || isHealthy === true) {
    return children;
  }

  if (isHealthy === null) {
    return (
      <div className="min-h-screen bg-[#0B0F19] text-gray-100 flex flex-col items-center justify-center font-sans">
        <PageLoader label="Connecting to backend services..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0B0F19] text-gray-100 flex flex-col items-center justify-center font-sans p-4">
      <div className="max-w-md w-full bg-gray-900/80 border border-gray-800 rounded-2xl p-8 shadow-2xl backdrop-blur-xl flex flex-col items-center text-center">
        <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-6">
          <AlertTriangle className="w-8 h-8 text-amber-400 animate-pulse" />
        </div>
        
        <h1 className="text-2xl font-bold text-white mb-2">Backend Connection Pending</h1>
        <p className="text-gray-400 text-sm mb-4 leading-relaxed">
          The backend service is currently spinning up or establishing connections.
        </p>

        <div className="w-full bg-black/40 border border-gray-800/80 rounded-lg p-3 mb-6 text-left">
          <div className="text-xs text-gray-500 font-mono mb-1">Target API Base URL:</div>
          <div className="text-xs text-indigo-400 font-mono break-all mb-2">
            {api.defaults.baseURL || '/api/v1'}
          </div>
          {errorDetails && (
            <>
              <div className="text-xs text-gray-500 font-mono mb-1">Diagnostic Detail:</div>
              <div className="text-xs text-rose-400 font-mono break-all">{errorDetails}</div>
            </>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 w-full">
          <button
            onClick={() => checkHealth()}
            disabled={isChecking}
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-all disabled:opacity-50 shadow-lg shadow-indigo-600/20"
          >
            <Loader2 className={`w-4 h-4 ${isChecking ? 'animate-spin' : ''}`} />
            {isChecking ? 'Checking...' : 'Retry Connection'}
          </button>
          <button
            onClick={() => setIsBypassed(true)}
            className="flex-1 inline-flex items-center justify-center px-4 py-2.5 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium text-sm transition-all border border-gray-700 hover:border-gray-600"
          >
            Continue to App
          </button>
        </div>
      </div>
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
          <HealthCheckGate>
            <Routes>
              <Route path="/login"          element={<Login />} />
              <Route path="/auth/callback"  element={<AuthCallback />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/*"             element={<ProtectedLayout />} />
            </Routes>
          </HealthCheckGate>
        </Suspense>
      </AppErrorBoundary>
    </Router>
  );
}
