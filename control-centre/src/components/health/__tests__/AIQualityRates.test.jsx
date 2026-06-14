// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';

vi.mock('../../../api/aiQuality', () => ({
  getResolutionRates: vi.fn(),
}));

import { getResolutionRates } from '../../../api/aiQuality';
import { AIQualityRates } from '../AIQualityRates';

const ROWS = [
  {
    alert_code: 'door_obstruction',
    resolved_total: 71,
    no_action_count: 5,
    no_action_rate: 5 / 71,
    false_alarm_count: 3,
    explicit_fp_rate: 3 / 71, // 4.2% — below NFR3, not a breach
  },
  {
    alert_code: 'slip_fall',
    resolved_total: 10,
    no_action_count: 0,
    no_action_rate: 0,
    false_alarm_count: 2,
    explicit_fp_rate: 0.2, // 20% — breaches NFR3 (≥5%)
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe('AIQualityRates — loading state', () => {
  it('shows loading on first render', () => {
    getResolutionRates.mockReturnValue(new Promise(() => {})); // never resolves
    render(<AIQualityRates />);
    expect(screen.getByTestId('ai-quality-loading')).toBeTruthy();
  });
});

describe('AIQualityRates — populated state', () => {
  it('renders both rates per class with "% (n of d)" denominators (AC1)', async () => {
    getResolutionRates.mockResolvedValueOnce(ROWS);
    render(<AIQualityRates />);
    await waitFor(() => expect(screen.getByText('door_obstruction')).toBeTruthy());
    // no_action_rate 5/71 = 7.04%, denom shown (two decimals — boundary-safe)
    expect(screen.getByText(/7\.04%/)).toBeTruthy();
    expect(screen.getByText(/\(5 of 71\)/)).toBeTruthy();
    // explicit_fp_rate 3/71 = 4.23%, denom shown
    expect(screen.getByText(/4\.23%/)).toBeTruthy();
    expect(screen.getByText(/\(3 of 71\)/)).toBeTruthy();
  });

  it('two decimals keep the label distinct from the tint at the 5% boundary', async () => {
    // 4.96% (below gate, no tint) and 5.04% (above gate, tinted) must read
    // differently — a one-decimal label would render both as "5.0%".
    getResolutionRates.mockResolvedValueOnce([
      {
        alert_code: 'below_gate',
        resolved_total: 121, no_action_count: 0, no_action_rate: 0,
        false_alarm_count: 6, explicit_fp_rate: 6 / 121, // 4.96%
      },
      {
        alert_code: 'above_gate',
        resolved_total: 119, no_action_count: 0, no_action_rate: 0,
        false_alarm_count: 6, explicit_fp_rate: 6 / 119, // 5.04%
      },
    ]);
    const { container } = render(<AIQualityRates />);
    await waitFor(() => expect(screen.getByText('below_gate')).toBeTruthy());
    expect(screen.getByText(/4\.96%/)).toBeTruthy();
    expect(screen.getByText(/5\.04%/)).toBeTruthy();
    // exactly one class is tinted as a breach
    expect(container.querySelectorAll('.ai-quality__breach').length).toBe(1);
  });

  it('shows two distinct rate columns, no aggregated single score (AC3)', async () => {
    getResolutionRates.mockResolvedValueOnce(ROWS);
    render(<AIQualityRates />);
    await waitFor(() => expect(screen.getByText('No-action rate')).toBeTruthy());
    expect(screen.getByText('Explicit false-positive rate')).toBeTruthy();
    // No blended/overall quality-score label exists.
    expect(screen.queryByText(/overall|aggregate|combined|quality score/i)).toBeNull();
  });

  it('tints an explicit_fp_rate ≥ 5% as an NFR3 breach (AC4)', async () => {
    getResolutionRates.mockResolvedValueOnce(ROWS);
    const { container } = render(<AIQualityRates />);
    await waitFor(() => expect(screen.getByText('slip_fall')).toBeTruthy());
    expect(container.querySelector('.ai-quality__breach')).toBeTruthy();
  });
});

describe('AIQualityRates — null rate renders "—", not 0% (AC2)', () => {
  it('renders — for a null rate', async () => {
    getResolutionRates.mockResolvedValueOnce([
      {
        alert_code: 'fire',
        resolved_total: 0,
        no_action_count: 0,
        no_action_rate: null,
        false_alarm_count: 0,
        explicit_fp_rate: null,
      },
    ]);
    render(<AIQualityRates />);
    await waitFor(() => expect(screen.getByText('fire')).toBeTruthy());
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBe(2); // both rates show —
  });
});

describe('AIQualityRates — empty + error states', () => {
  it('renders an empty message when no classes resolved', async () => {
    getResolutionRates.mockResolvedValueOnce([]);
    render(<AIQualityRates />);
    await waitFor(() =>
      expect(screen.getByText(/No resolved alerts/i)).toBeTruthy()
    );
  });

  it('renders an error message when the fetch fails', async () => {
    getResolutionRates.mockRejectedValueOnce(new Error('API error 500'));
    render(<AIQualityRates />);
    await waitFor(() =>
      expect(screen.getByText(/unavailable/i)).toBeTruthy()
    );
  });
});
