import { describe, it, expect } from 'vitest';
import { cn } from '../../src/lib/utils';

describe('utils cn function', () => {
  it('merges class names correctly', () => {
    const result = cn('bg-red-500', 'text-white');
    expect(result).toBe('bg-red-500 text-white');
  });

  it('handles conditional class names', () => {
    const condition = true;
    const result = cn('p-4', condition && 'm-4', !condition && 'flex');
    expect(result).toBe('p-4 m-4');
  });

  it('resolves tailwind conflicts using tailwind-merge', () => {
    const result = cn('bg-red-500', 'bg-blue-500');
    expect(result).toBe('bg-blue-500'); // the later class overrides the former
  });

  it('handles arrays and objects', () => {
    const result = cn(['p-2', 'm-2'], { 'bg-black': true, 'text-black': false });
    expect(result).toBe('p-2 m-2 bg-black');
  });
});
