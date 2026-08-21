import React, { useState, useEffect } from 'react';
import {
  GitFork, FileCode, Search, ChevronRight, Layers,
  Loader2, AlertTriangle, RefreshCw, Plus, Trash2
} from 'lucide-react';
import toast from 'react-hot-toast';
import DependencyGraphView from '../components/DependencyGraphView';
import api from '../services/api';
import { getErrorMessage } from '../services/api';
import { useWorkflowStore } from '../stores/workflowStore';
import ErrorState from '../components/ErrorState';
import ConnectRepoModal from '../components/ConnectRepoModal';
import { useNavigate } from 'react-router-dom';

export default function RepositoryExplorer() {
  const navigate = useNavigate();

  // ── Repository list ────────────────────────────────────────────────────────
  const [repositories, setRepositories]   = useState([]);
  const [reposLoading, setReposLoading]   = useState(true);
  const [reposError,   setReposError]     = useState(null);

  // ── Selected repo — local state with store sync ────────────────────────────
  const { selectedRepo: storedRepo, setSelectedRepo } = useWorkflowStore();
  const [activeRepoId, setActiveRepoId] = useState(storedRepo || null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // ── File tree & graph ──────────────────────────────────────────────────────
  const [fileTree,    setFileTree]    = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [graphData,   setGraphData]   = useState({ nodes: [], edges: [] });
  const [isLoading,   setIsLoading]   = useState(false);
  const [hasError,    setHasError]    = useState(false);
  const [loadError,   setLoadError]   = useState(null);

  // ── Blast radius ───────────────────────────────────────────────────────────
  const [calculatingBlast, setCalculatingBlast] = useState(false);
  const [blastResults,     setBlastResults]     = useState(null);

  // ── Fetch available repositories ───────────────────────────────────────────
  const fetchRepositories = async (overrideSelectedId) => {
    setReposLoading(true);
    setReposError(null);
    try {
      const res = await api.get('/repositories', { _silent: true });
      const repoList = res.data || [];
      setRepositories(repoList);

      if (overrideSelectedId !== undefined) {
        setActiveRepoId(overrideSelectedId);
        setSelectedRepo(overrideSelectedId);
      } else if (repoList.length > 0) {
        // If current active is valid, keep it; otherwise pick first
        setActiveRepoId((prev) => {
          const match = repoList.find((r) => r.id === prev);
          const next = match ? match.id : repoList[0].id;
          setSelectedRepo(next);
          return next;
        });
      } else {
        setActiveRepoId(null);
        setSelectedRepo(null);
        setFileTree([]);
        setGraphData({ nodes: [], edges: [] });
        setSelectedFile(null);
      }
    } catch (err) {
      setReposError(err);
    } finally {
      setReposLoading(false);
    }
  };

  useEffect(() => { fetchRepositories(); }, []);

  // ── Fetch files + graph when active repo changes ───────────────────────────
  const fetchFilesAndGraph = async () => {
    if (!activeRepoId) {
      setFileTree([]);
      setGraphData({ nodes: [], edges: [] });
      setSelectedFile(null);
      setBlastResults(null);
      return;
    }
    setIsLoading(true);
    setHasError(false);
    setLoadError(null);
    setFileTree([]);
    setGraphData({ nodes: [], edges: [] });
    setBlastResults(null);
    try {
      const [filesRes, graphRes] = await Promise.all([
        api.get(`/repositories/${activeRepoId}/files`, { _silent: true }),
        api.get(`/graph/${activeRepoId}`, { _silent: true }),
      ]);
      const mapped = filesRes.data.map(f => ({
        name:    f.path,
        type:    f.type,
        loc:     f.loc     || 0,
        symbols: f.symbols || 0,
      }));
      setFileTree(mapped);
      if (mapped.length > 0) setSelectedFile(mapped[0]);
      setGraphData(graphRes.data);
    } catch (err) {
      setHasError(true);
      setLoadError(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchFilesAndGraph(); }, [activeRepoId]);

  // ── Repo change handler ────────────────────────────────────────────────────
  const handleRepoChange = (repoId) => {
    setActiveRepoId(repoId);
    setSelectedRepo(repoId);
    setSelectedFile(null);
    setBlastResults(null);
  };

  // ── Delete repository ──────────────────────────────────────────────────────
  const handleDeleteRepo = async () => {
    if (!activeRepoId) return;

    if (!window.confirm('Are you sure you want to delete this repository? This action cannot be undone and will delete all associated data (AST, embeddings, files).')) {
      return;
    }

    const deletingId = activeRepoId;
    setIsDeleting(true);
    try {
      await api.delete(`/repositories/${deletingId}`);
      toast.success('Repository deleted successfully.');

      // Clear current views immediately
      setFileTree([]);
      setGraphData({ nodes: [], edges: [] });
      setSelectedFile(null);
      setBlastResults(null);

      // Determine next repo to select
      const remaining = repositories.filter(r => r.id !== deletingId);
      const nextId = remaining.length > 0 ? remaining[0].id : null;

      setRepositories(remaining);
      setActiveRepoId(nextId);
      setSelectedRepo(nextId);

      await fetchRepositories(nextId);
    } catch (err) {
      const msg = getErrorMessage(err);
      toast.error(`Failed to delete repository: ${msg}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // ── Blast radius query ─────────────────────────────────────────────────────
  const handleCalculateBlastRadius = async () => {
    if (!activeRepoId) {
      toast.error('Please select a repository first.');
      return;
    }
    const symbolQuery = searchQuery.trim() || 'main';
    setCalculatingBlast(true);
    try {
      const res = await api.get(
        `/graph/${activeRepoId}/blast-radius?symbol_name=${encodeURIComponent(symbolQuery)}`
      );
      setBlastResults({
        symbol:         symbolQuery,
        count:          res.data.blast_radius_count,
        impacted_nodes: res.data.impacted_callers.length
          ? res.data.impacted_callers.map(c => `${c.caller_file}::${c.caller_name}`)
          : [`No downstream callers found for "${symbolQuery}"`],
      });
      toast.success(`Blast radius for "${symbolQuery}": ${res.data.blast_radius_count} callers affected.`);
    } catch (err) {
      const msg = getErrorMessage(err);
      toast.error(`Neo4j query failed: ${msg}`);
    } finally {
      setCalculatingBlast(false);
    }
  };

  // ── Filtered file list ─────────────────────────────────────────────────────
  const filteredFiles = fileTree.filter(f =>
    !searchQuery || f.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeRepo = repositories.find(r => r.id === activeRepoId);

  // ── Repo list error state ──────────────────────────────────────────────────
  if (!reposLoading && reposError) {
    return (
      <div className="max-w-7xl mx-auto pt-10">
        <ErrorState
          title="Repository List Unavailable"
          message={reposError?.response?.data?.detail || 'Failed to load your repositories.'}
          error={reposError}
          onRetry={fetchRepositories}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="p-6 rounded-3xl glass-panel border border-gray-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <GitFork className="w-5 h-5 text-cyan-400" />
            <h2 className="text-xl font-bold text-white">Repository &amp; AST Intelligence Explorer</h2>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Tree-sitter symbol hierarchy, Neo4j call graphs, and blast radius impact analysis.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Repository selector & Refresh */}
          <div className="flex items-center gap-2">
            {reposLoading ? (
              <div className="h-9 w-48 rounded-xl bg-gray-800 animate-pulse" />
            ) : (
              <select
                id="repo-selector"
                value={activeRepoId || ''}
                onChange={(e) => handleRepoChange(e.target.value)}
                disabled={repositories.length === 0}
                className="px-3.5 py-2 rounded-xl bg-gray-900 border border-gray-700 text-xs text-gray-200 focus:outline-none focus:border-cyan-500 min-w-[180px]"
              >
                {repositories.length === 0
                  ? <option value="">No repositories connected</option>
                  : repositories.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))
                }
              </select>
            )}
            <button
              onClick={() => {
                fetchRepositories(activeRepoId);
                if (activeRepoId) fetchFilesAndGraph();
              }}
              disabled={reposLoading || isLoading}
              title="Refresh Repository Data"
              className="p-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-cyan-300 transition-colors disabled:opacity-50 border border-gray-700"
            >
              <RefreshCw className={`w-4 h-4 ${reposLoading || isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            className="px-3 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/40 border border-indigo-500/30 text-indigo-300 text-xs font-semibold shadow-lg transition-all flex items-center gap-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Connect Repo</span>
          </button>

          {activeRepoId && (
            <button
              onClick={handleDeleteRepo}
              disabled={isDeleting}
              title="Delete Repository"
              className="px-3 py-2 rounded-xl bg-red-600/20 hover:bg-red-600/40 border border-red-500/30 text-red-300 text-xs font-semibold shadow-lg transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              <span className="hidden sm:inline">Delete Repo</span>
            </button>
          )}

          <button
            id="blast-radius-btn"
            onClick={handleCalculateBlastRadius}
            disabled={calculatingBlast || !activeRepoId}
            className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-cyan-500/20 transition-all flex items-center gap-2"
          >
            {calculatingBlast
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Layers className="w-4 h-4" />}
            <span>{calculatingBlast ? 'Querying Neo4j…' : 'Calculate Blast Radius'}</span>
          </button>
        </div>
      </div>

      {/* Empty state — no repositories */}
      {!reposLoading && repositories.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center border border-dashed border-gray-700 rounded-3xl">
          <GitFork className="w-12 h-12 text-gray-700" />
          <h3 className="text-lg font-bold text-gray-300">No Repositories Connected</h3>
          <p className="text-sm text-gray-500 max-w-sm">
            Connect your first Git repository to explore its AST, call graphs, and run blast radius analysis.
          </p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors"
          >
            <Plus className="w-4 h-4" />
            Connect Repository
          </button>
        </div>
      )}

      {/* Data loading state */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
          <span className="text-sm font-mono text-gray-400 tracking-widest uppercase">
            Loading AST index &amp; dependency graph…
          </span>
        </div>
      )}

      {/* Data error state */}
      {hasError && !isLoading && (
        <ErrorState
          title="Repository Data Unavailable"
          message={
            loadError?.response?.data?.detail ||
            'Failed to load the AST file index or Neo4j dependency graph. The repository may not be fully cloned yet.'
          }
          error={loadError}
          onRetry={fetchFilesAndGraph}
        />
      )}

      {/* Blast Radius Result */}
      {blastResults && (
        <div className="p-5 rounded-2xl bg-indigo-950/40 border border-indigo-500/40 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-indigo-300">
              Blast radius for <code className="bg-indigo-900/50 px-1 rounded">{blastResults.symbol}</code>
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-900 text-indigo-200">
              {blastResults.count} Dependent Callers
            </span>
          </div>
          <ul className="text-xs font-mono text-gray-300 space-y-1 pl-2 max-h-40 overflow-y-auto">
            {blastResults.impacted_nodes.map((node, i) => (
              <li key={i} className="flex items-center gap-2">
                <ChevronRight className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                <span>{node}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Main split grid — only shown when data is ready */}
      {!isLoading && !hasError && activeRepoId && repositories.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: File Tree */}
          <div className="lg:col-span-4 space-y-4">
            {/* Repo info badge */}
            {activeRepo && (
              <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-900/60 border border-gray-800 text-xs text-gray-400">
                <span className="text-emerald-400 font-mono font-bold">{activeRepo.sync_status}</span>
                <span>·</span>
                <span>{activeRepo.detected_languages?.join(', ') || 'Unknown language'}</span>
                <span>·</span>
                <span>{fileTree.length} files</span>
              </div>
            )}

            <div className="p-4 rounded-2xl glass-panel border border-gray-800 bg-[#0E1322]/90">
              <div className="relative mb-3">
                <Search className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter files or enter symbol for blast radius…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-gray-900 border border-gray-800 text-xs text-gray-200 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div className="space-y-1.5 overflow-y-auto max-h-[400px]">
                {filteredFiles.map((f) => (
                  <button
                    key={f.name}
                    onClick={() => setSelectedFile(f)}
                    className={`w-full text-left p-2.5 rounded-xl border text-xs font-mono transition-all flex items-center justify-between ${
                      selectedFile?.name === f.name
                        ? 'bg-indigo-600/20 border-indigo-500 text-indigo-200'
                        : 'bg-gray-900/40 border-gray-800 text-gray-400 hover:border-gray-700'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <FileCode className="w-4 h-4 text-indigo-400" />
                      <span className="truncate max-w-[180px]" title={f.name}>{f.name}</span>
                    </div>
                    <span className="text-[10px] text-gray-500">{f.loc > 0 ? `${f.loc} LOC` : ''}</span>
                  </button>
                ))}

                {filteredFiles.length === 0 && fileTree.length > 0 && (
                  <p className="text-xs text-gray-500 py-4 text-center">
                    No files match "<span className="text-gray-300">{searchQuery}</span>"
                  </p>
                )}

                {fileTree.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-8 gap-2 text-center">
                    <AlertTriangle className="w-6 h-6 text-gray-600" />
                    <p className="text-xs text-gray-500">
                      Repository not yet cloned or AST indexing is in progress.
                    </p>
                    <button
                      onClick={fetchFilesAndGraph}
                      className="mt-1 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-medium transition-colors"
                    >
                      <RefreshCw className="w-3 h-3" />
                      Refresh
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right: Dependency Graph */}
          <div className="lg:col-span-8 h-[550px]">
            <DependencyGraphView graphData={graphData} />
          </div>
        </div>
      )}

      <ConnectRepoModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onSuccess={fetchRepositories} 
      />
    </div>
  );
}
