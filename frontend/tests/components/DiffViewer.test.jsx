import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import DiffViewer from '../../src/components/DiffViewer';
import React from 'react';

// Mock monaco editor
vi.mock('@monaco-editor/react', () => ({
  DiffEditor: ({ original, modified, language }) => (
    <div data-testid="monaco-diff-editor">
      <div data-testid="original">{original}</div>
      <div data-testid="modified">{modified}</div>
      <div data-testid="language">{language}</div>
    </div>
  ),
}));

describe('DiffViewer Component', () => {
  it('renders empty state when no fileChange is provided', () => {
    render(<DiffViewer />);
    
    expect(screen.getByText('AST Transformation Diff Viewer')).toBeInTheDocument();
    expect(
      screen.getByText('Select a transformed file or wait for the Refactoring Agent to generate code transformations.')
    ).toBeInTheDocument();
  });

  it('renders diff editor with python language for .py files', () => {
    const fileChange = {
      file_path: 'backend/app/main.py',
      original_code: 'print("hello")',
      transformed_code: 'print("hello world")',
    };

    render(<DiffViewer fileChange={fileChange} />);

    expect(screen.getByText('backend/app/main.py')).toBeInTheDocument();
    expect(screen.getByTestId('monaco-diff-editor')).toBeInTheDocument();
    
    // Check if the mock receives the correct language
    expect(screen.getByTestId('language')).toHaveTextContent('python');
    expect(screen.getByTestId('original')).toHaveTextContent('print("hello")');
    expect(screen.getByTestId('modified')).toHaveTextContent('print("hello world")');
  });

  it('renders diff editor with javascript language for non-.py files', () => {
    const fileChange = {
      file_path: 'frontend/src/App.jsx',
      original_code: 'const a = 1;',
      transformed_code: 'const a = 2;',
      status: 'Pending',
      explanation: 'Updated constant'
    };

    render(<DiffViewer fileChange={fileChange} />);

    expect(screen.getByText('frontend/src/App.jsx')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Updated constant')).toBeInTheDocument();
    
    expect(screen.getByTestId('language')).toHaveTextContent('javascript');
  });

  it('renders default fallback text when status or explanation is missing', () => {
    const fileChange = {
      file_path: 'test.js',
    };

    render(<DiffViewer fileChange={fileChange} />);
    
    expect(screen.getByText('Applied')).toBeInTheDocument();
    expect(screen.getByText('AST Refactored to Modern Standards')).toBeInTheDocument();
  });
});
