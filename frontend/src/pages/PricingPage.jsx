import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Check, Shield, Zap, Star, Loader2, CheckCircle2 } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import { useAuthStore } from '../stores/authStore';

export default function PricingPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  const [loadingPlan, setLoadingPlan] = useState(null);
  const [verifyingSession, setVerifyingSession] = useState(false);

  // Fetch real-time user profile to know exact current plan
  const { data: userProfile, refetch: refetchProfile } = useQuery({
    queryKey: ['pricingProfile'],
    queryFn: async () => {
      const res = await api.get('/auth/me', { _silent: true });
      return res.data;
    },
    staleTime: 10000,
  });

  const currentPlan = (userProfile?.plan_tier || user?.plan_tier || 'free').toLowerCase();

  // Check for successful Stripe redirect
  useEffect(() => {
    const isSuccess = searchParams.get('success') === 'true';
    const sessionId = searchParams.get('session_id');

    if (isSuccess && sessionId) {
      const confirmPayment = async () => {
        setVerifyingSession(true);
        const toastId = toast.loading('Verifying your payment with Stripe…');
        try {
          const res = await api.post('/subscriptions/confirm-session', { session_id: sessionId });
          toast.success(res.data.message || 'Payment confirmed! Subscription activated.', {
            id: toastId,
            duration: 5000,
          });
          // Invalidate user queries so Navbar and Pricing page reflect the upgrade immediately
          await queryClient.invalidateQueries({ queryKey: ['navUserProfile'] });
          await queryClient.invalidateQueries({ queryKey: ['pricingProfile'] });
          await queryClient.invalidateQueries({ queryKey: ['currentUserProfile'] });
          await refetchProfile();
        } catch (err) {
          toast.error(err.response?.data?.detail || 'Failed to verify payment session with Stripe.', {
            id: toastId,
          });
        } finally {
          setVerifyingSession(false);
          // Remove query params from address bar
          navigate('/pricing', { replace: true });
        }
      };

      confirmPayment();
    } else if (searchParams.get('canceled') === 'true') {
      toast('Payment was canceled.', { icon: 'ℹ️' });
      navigate('/pricing', { replace: true });
    }
  }, [searchParams, navigate, queryClient, refetchProfile]);

  const handleSubscribe = async (plan) => {
    try {
      setLoadingPlan(plan);
      const res = await api.post(`/subscriptions/create-checkout-session?plan=${plan}`);
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to initialize checkout');
    } finally {
      setLoadingPlan(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-16">
        <h1 className="text-4xl font-extrabold text-white tracking-tight sm:text-5xl">
          Simple, Transparent Pricing
        </h1>
        <p className="mt-4 text-xl text-slate-400">
          Scale your AI migration workflows with flexible plans tailored to your team.
        </p>
      </div>

      {verifyingSession && (
        <div className="mb-8 p-4 rounded-2xl bg-indigo-950/60 border border-indigo-500/50 flex items-center justify-center gap-3 text-indigo-300">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm font-medium">Verifying your payment with Stripe & activating subscription…</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {/* Free Plan */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`bg-slate-800/50 backdrop-blur-sm rounded-2xl border p-8 flex flex-col ${
            currentPlan === 'free' ? 'border-emerald-500/50 ring-1 ring-emerald-500/30' : 'border-slate-700'
          }`}
        >
          <div className="mb-8">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-bold text-slate-300">Free Tier</h3>
              {currentPlan === 'free' && (
                <span className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-950/80 px-2.5 py-0.5 rounded-full border border-emerald-700/60">
                  <CheckCircle2 className="w-3 h-3" /> Active Plan
                </span>
              )}
            </div>
            <div className="mt-4 flex items-baseline text-5xl font-extrabold text-white">
              $0
              <span className="ml-1 text-xl font-medium text-slate-400">/mo</span>
            </div>
          </div>
          <ul className="flex-1 space-y-4 mb-8">
            <li className="flex items-center text-slate-300">
              <Check className="h-5 w-5 text-indigo-400 mr-3 shrink-0" />
              <span>3 AI Workflows per 30 minutes</span>
            </li>
            <li className="flex items-center text-slate-300">
              <Check className="h-5 w-5 text-indigo-400 mr-3 shrink-0" />
              <span>Community Support</span>
            </li>
            <li className="flex items-center text-slate-500">
              <Shield className="h-5 w-5 mr-3 shrink-0" />
              <span>Basic Code Context</span>
            </li>
          </ul>
          <button
            disabled
            className="mt-auto w-full py-3 px-4 rounded-lg bg-slate-700/60 text-slate-400 font-medium cursor-not-allowed text-center"
          >
            {currentPlan === 'free' ? 'Current Plan' : 'Free Included'}
          </button>
        </motion.div>

        {/* Pro Plan */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className={`bg-gradient-to-b from-indigo-900/50 to-slate-800/50 backdrop-blur-sm rounded-2xl border p-8 flex flex-col ${
            currentPlan === 'pro' ? 'border-indigo-400 ring-2 ring-indigo-500/50' : 'border-indigo-500/60'
          }`}
        >
          <div className="mb-8">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-bold text-indigo-300">Pro Plan</h3>
              {currentPlan === 'pro' && (
                <span className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-indigo-300 bg-indigo-950 px-2.5 py-0.5 rounded-full border border-indigo-600">
                  <CheckCircle2 className="w-3 h-3" /> Active Plan
                </span>
              )}
            </div>
            <div className="mt-4 flex items-baseline text-5xl font-extrabold text-white">
              $5
              <span className="ml-1 text-xl font-medium text-slate-400">/mo</span>
            </div>
          </div>
          <ul className="flex-1 space-y-4 mb-8">
            <li className="flex items-center text-slate-300">
              <Zap className="h-5 w-5 text-indigo-400 mr-3 shrink-0" />
              <span className="font-semibold text-white">10 AI Workflows per 30 minutes</span>
            </li>
            <li className="flex items-center text-slate-300">
              <Check className="h-5 w-5 text-indigo-400 mr-3 shrink-0" />
              <span>Priority Email Support</span>
            </li>
            <li className="flex items-center text-slate-300">
              <Check className="h-5 w-5 text-indigo-400 mr-3 shrink-0" />
              <span>Deep AST Context & Graph Analysis</span>
            </li>
          </ul>
          {currentPlan === 'pro' ? (
            <button
              disabled
              className="mt-auto w-full py-3 px-4 rounded-lg bg-indigo-950/80 text-indigo-300 font-medium border border-indigo-700/60 cursor-not-allowed text-center"
            >
              Current Plan
            </button>
          ) : (
            <button
              onClick={() => handleSubscribe('pro')}
              disabled={loadingPlan === 'pro' || verifyingSession}
              className="mt-auto w-full py-3 px-4 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white font-medium transition-colors flex items-center justify-center shadow-lg shadow-indigo-500/20"
            >
              {loadingPlan === 'pro' ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Subscribe to Pro'}
            </button>
          )}
        </motion.div>

        {/* Unlimited Plan */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className={`bg-slate-800/50 backdrop-blur-sm rounded-2xl border p-8 flex flex-col ${
            currentPlan === 'unlimited' || currentPlan === 'premium'
              ? 'border-amber-400 ring-2 ring-amber-500/50'
              : 'border-purple-500/50'
          }`}
        >
          <div className="mb-8">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-bold text-purple-300">Full Time / Unlimited</h3>
              {(currentPlan === 'unlimited' || currentPlan === 'premium') && (
                <span className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-amber-300 bg-amber-950/80 px-2.5 py-0.5 rounded-full border border-amber-500/60">
                  <CheckCircle2 className="w-3 h-3" /> Active Plan
                </span>
              )}
            </div>
            <div className="mt-4 flex items-baseline text-5xl font-extrabold text-white">
              $200
              <span className="ml-1 text-xl font-medium text-slate-400">/mo</span>
            </div>
          </div>
          <ul className="flex-1 space-y-4 mb-8">
            <li className="flex items-center text-slate-300">
              <Star className="h-5 w-5 text-purple-400 mr-3 shrink-0" />
              <span className="font-semibold text-white">Unlimited AI Workflows</span>
            </li>
            <li className="flex items-center text-slate-300">
              <Check className="h-5 w-5 text-purple-400 mr-3 shrink-0" />
              <span>Zero Rate Limiting</span>
            </li>
            <li className="flex items-center text-slate-300">
              <Check className="h-5 w-5 text-purple-400 mr-3 shrink-0" />
              <span>Dedicated Slack Channel</span>
            </li>
            <li className="flex items-center text-slate-300">
              <Check className="h-5 w-5 text-purple-400 mr-3 shrink-0" />
              <span>Enterprise SLAs</span>
            </li>
          </ul>
          {currentPlan === 'unlimited' || currentPlan === 'premium' ? (
            <button
              disabled
              className="mt-auto w-full py-3 px-4 rounded-lg bg-purple-950/80 text-purple-300 font-medium border border-purple-700/60 cursor-not-allowed text-center"
            >
              Current Plan
            </button>
          ) : (
            <button
              onClick={() => handleSubscribe('unlimited')}
              disabled={loadingPlan === 'unlimited' || verifyingSession}
              className="mt-auto w-full py-3 px-4 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-medium transition-colors flex items-center justify-center shadow-lg shadow-purple-500/20"
            >
              {loadingPlan === 'unlimited' ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Get Unlimited'}
            </button>
          )}
        </motion.div>
      </div>
    </div>
  );
}
