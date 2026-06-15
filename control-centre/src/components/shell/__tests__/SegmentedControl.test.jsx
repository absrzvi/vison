// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SegmentedControl } from '../SegmentedControl';
import { formatSec } from '../../../constants/preferences';

describe('SegmentedControl (extracted, shared by modal + Profile)', () => {
  it('marks the active option checked and commits on click', () => {
    const onCommit = vi.fn();
    render(
      <SegmentedControl
        label="Threshold"
        options={[30, 60, 90]}
        value={60}
        onCommit={onCommit}
        formatLabel={formatSec}
      />
    );
    expect(screen.getByRole('radio', { name: '60s' })).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(screen.getByRole('radio', { name: '90s' }));
    expect(onCommit).toHaveBeenCalledWith(90);
  });

  it('ArrowRight + Enter commits the next option (roving tabindex)', () => {
    const onCommit = vi.fn();
    render(
      <SegmentedControl label="T" options={[30, 60, 90]} value={30} onCommit={onCommit} />
    );
    const group = screen.getByRole('radiogroup');
    fireEvent.keyDown(group, { key: 'ArrowRight' });
    fireEvent.keyDown(group, { key: 'Enter' });
    expect(onCommit).toHaveBeenCalledWith(60);
  });
});
