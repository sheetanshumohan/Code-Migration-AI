import React, { useState } from 'react';
import { X, GitFork, Link as LinkIcon, GitBranch, Key, Loader2, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../services/api';

export default function ConnectRepoModal({ isOpen, onClose, onSuccess }) {
  const [name, setName] = useState('');
  const [gitUrl, setGitUrl] = useState('');
  const [defaultBranch, setDefaultBranch] = useState('main');
  const [authToken, setAuthToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [isValidated, setIsValidated] = useState(false);

  if (!isOpen) return null;

  const handleValidate = async (e) => {
    e.preventDefault();
    if (!gitUrl.trim()) return toast.error('Please enter a Git Clone URL.');
    setLoading(true);
    try {
      await api.post('/repositories/validate', { git_url: gitUrl.trim(), auth_token: authToken.trim() });
      setIsValidated(true);
      toast.success('Repository validated successfully! You can now connect it.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Validation failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !gitUrl.trim() || !defaultBranch.trim()) {
      return toast.error('Please fill in all required fields.');
    }

    setLoading(true);
    try {
      const payload = {
        name: name.trim(),
        git_url: gitUrl.trim(),
        default_branch: defaultBranch.trim(),
      };
      
      if (authToken.trim()) {
        payload.auth_token = authToken.trim();
      }

      await api.post('/repositories/connect', payload);
      toast.success('Repository connected successfully! It is now being analyzed.');
      
      // Reset form
      setName('');
      setGitUrl('');
      setDefaultBranch('main');
      setAuthToken('');
      setIsValidated(false);
      
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to connect repository.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-md p-6 overflow-hidden border rounded-3xl glass-panel border-indigo-500/30 bg-[#0E1322]/95 shadow-2xl">
        <div className="absolute -top-20 -left-20 w-64 h-64 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute -bottom-20 -right-20 w-64 h-64 bg-cyan-600/20 rounded-full blur-3xl pointer-events-none"></div>

        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors z-10 p-1 bg-gray-800/50 hover:bg-gray-700/50 rounded-full"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="relative z-10 flex flex-col">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-400 p-[1px] shadow-lg shadow-indigo-500/20">
              <div className="w-full h-full bg-[#0B0F19] rounded-[11px] flex items-center justify-center">
                <GitFork className="w-5 h-5 text-indigo-400" />
              </div>
            </div>
            <div>
              <h2 className="text-xl font-bold text-white font-sans tracking-tight">Connect Repository</h2>
              <p className="text-xs text-gray-400">Clone and analyze a new codebase</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
                Repository Name <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <Sparkles className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-xs text-white focus:outline-none focus:border-indigo-500"
                  placeholder="e.g. My Frontend App"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
                Git Clone URL <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <LinkIcon className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                <input
                  type="text"
                  required
                  value={gitUrl}
                  onChange={(e) => { setGitUrl(e.target.value); setIsValidated(false); }}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-xs text-white focus:outline-none focus:border-indigo-500"
                  placeholder="https://github.com/org/repo.git"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
                Default Branch <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <GitBranch className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                <input
                  type="text"
                  required
                  value={defaultBranch}
                  onChange={(e) => setDefaultBranch(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-xs text-white focus:outline-none focus:border-indigo-500"
                  placeholder="main"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-gray-300 uppercase tracking-wider mb-1">
                Personal Access Token <span className="text-gray-500 normal-case">(Optional)</span>
              </label>
              <div className="relative">
                <Key className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                <input
                  type="password"
                  value={authToken}
                  onChange={(e) => { setAuthToken(e.target.value); setIsValidated(false); }}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-xs text-white focus:outline-none focus:border-indigo-500"
                  placeholder="Required for private repositories"
                />
              </div>
              <p className="mt-1 text-[10px] text-gray-500">
                This token is encrypted securely before storing.
              </p>
            </div>

            {!isValidated ? (
              <button
                type="button"
                onClick={handleValidate}
                disabled={loading}
                className="w-full mt-2 py-3 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 disabled:opacity-50 text-white font-semibold text-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                <span>Validate Repository</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 disabled:opacity-50 text-white font-semibold text-xs shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Connecting...</span>
                  </>
                ) : (
                  <>
                    <span>Connect Repository</span>
                  </>
                )}
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
