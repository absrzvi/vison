/** @vitest-environment jsdom */
// Story 10-1 AC22 — AI pipeline row on System Health + per-train drawer.
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AIPipelineRow } from '../components/health/AIPipelineRow';

function mockPipeline(body) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => body }),
  );
}

const GREEN_TRAIN = {
  train_id: 'V001',
  state: 'green',
  last_seen: new Date(Date.now() - 14_000).toISOString(),
  model_versions: { detector_arch: 'yolox_s_leaky', detector_code: 'git:9d4a60df' },
  hailo_device_ok: true,
};

describe('AIPipelineRow', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders green running state', async () => {
    mockPipeline({ fleet_state: 'green', trains: [GREEN_TRAIN] });
    render(<AIPipelineRow />);
    await waitFor(() => expect(screen.getByText(/Green — running/)).toBeInTheDocument());
  });

  it('renders amber degraded state', async () => {
    mockPipeline({
      fleet_state: 'amber',
      trains: [{ ...GREEN_TRAIN, state: 'amber', hailo_device_ok: false }],
    });
    render(<AIPipelineRow />);
    await waitFor(() => expect(screen.getByText(/Amber — degraded/)).toBeInTheDocument());
  });

  it('renders red not-inferencing state', async () => {
    mockPipeline({ fleet_state: 'red', trains: [{ ...GREEN_TRAIN, state: 'red' }] });
    render(<AIPipelineRow />);
    await waitFor(() => expect(screen.getByText(/Red — not inferencing/)).toBeInTheDocument());
  });

  it('renders cold-state copy when trains is empty', async () => {
    mockPipeline({ fleet_state: 'green', trains: [] });
    render(<AIPipelineRow />);
    await waitFor(() =>
      expect(screen.getByText('AI pipeline: starting. No inferences yet.')).toBeInTheDocument(),
    );
  });

  it('click opens drawer with per-train rows', async () => {
    mockPipeline({ fleet_state: 'green', trains: [GREEN_TRAIN] });
    render(<AIPipelineRow />);
    await waitFor(() => expect(screen.getByText(/Green — running/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Green — running/));
    expect(screen.getByText('V001')).toBeInTheDocument();
    expect(screen.getByText(/14s ago/)).toBeInTheDocument();
    expect(screen.getByText(/yolox_s_leaky/)).toBeInTheDocument();
  });

  it('renders nothing crash-free on fetch error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    render(<AIPipelineRow />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
  });
});
