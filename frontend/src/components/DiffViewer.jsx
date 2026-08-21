import React from 'react';
import { DiffEditor } from '@monaco-editor/react';
import { Code2, GitCompare, Sparkles } from 'lucide-react';

const getLanguage = (path) => {
  if (!path) return 'javascript';
  const p = path.toLowerCase();
  if (p.endsWith('.py')) return 'python';
  if (p.endsWith('.ts') || p.endsWith('.tsx')) return 'typescript';
  if (p.endsWith('.js') || p.endsWith('.jsx')) return 'javascript';
  if (p.endsWith('.java')) return 'java';
  if (p.endsWith('.go')) return 'go';
  if (p.endsWith('.rs')) return 'rust';
  if (p.endsWith('.json')) return 'json';
  if (p.endsWith('.css')) return 'css';
  if (p.endsWith('.html')) return 'html';
  if (p.endsWith('.sql')) return 'sql';
  return 'javascript';
};

export default function DiffViewer({ fileChange }) {
  if (!fileChange) {
    return (
      <div className="h-full rounded-2xl glass-panel border border-gray-800 bg-[#0E1322]/90 flex flex-col items-center justify-center text-gray-500 p-8 text-center">
        <GitCompare className="w-10 h-10 text-gray-600 mb-3 opacity-60" />
        <h4 className="text-sm font-semibold text-gray-300 mb-1">AST Transformation Diff Viewer</h4>
        <p className="text-xs text-gray-500 max-w-sm">
          Select a transformed file or wait for the Refactoring Agent to generate code transformations.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full rounded-2xl glass-panel border border-gray-800 bg-[#0E1322]/90 overflow-hidden shadow-2xl">
      {/* File Header */}
      <div className="flex items-center justify-between px-5 py-3 bg-gray-900/90 border-b border-gray-800">
        <div className="flex items-center gap-2.5">
          <Code2 className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-semibold text-gray-200">
            {fileChange.file_path}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-gray-400">
            {fileChange.explanation || 'AST Refactored to Modern Standards'}
          </span>
          <span className="px-2.5 py-0.5 text-[10px] uppercase font-bold tracking-wider rounded-md bg-emerald-950 text-emerald-300 border border-emerald-800/60">
            {fileChange.status || 'Applied'}
          </span>
        </div>
      </div>

      {/* Monaco Diff Editor */}
      <div className="flex-1 min-h-[350px]">
        <DiffEditor
          original={fileChange.original_code || '// Original legacy source code'}
          modified={fileChange.transformed_code || '// Transformed modern source code'}
          language={getLanguage(fileChange.file_path)}
          theme="vs-dark"
          options={{
            renderSideBySide: true,
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            fontFamily: "'Fira Code', monospace",
            scrollBeyondLastLine: false,
            smoothScrolling: true,
          }}
        />
      </div>
    </div>
  );
}
