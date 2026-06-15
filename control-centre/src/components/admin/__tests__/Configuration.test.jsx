// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { Configuration } from '../Configuration';

vi.mock('../../../api/config', () => ({
  listThresholds: vi.fn(),
  patchThresholds: vi.fn(),
}));

import { listThresholds, patchThresholds } from '../../../api/config';

const CFG = {
  per_class: {
    unattended_bag: 0.75,
    door_obstruction: 0.85,
    accessibility_detected: 0.70,
    slip_fall: 0.75,
    luggage_rack_saturation: 0.70,
  },
  degraded_banner_floor: 0.60,
};

beforeEach(() => vi.clearAllMocks());

describe('Configuration — three states', () => {
  it('shows loading first', () => {
    listThresholds.mockReturnValue(new Promise(() => {}));
    render(<Configuration />);
    expect(screen.getByTestId('configuration-loading')).toBeInTheDocument();
  });

  it('shows error + retry when the list fails', async () => {
    listThresholds.mockRejectedValueOnce(Object.assign(new Error('boom'), { status: 500 }));
    render(<Configuration />);
    expect(await screen.findByTestId('configuration-error')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('boom');
  });

  it('renders the populated list with per-class rows + the floor', async () => {
    listThresholds.mockResolvedValueOnce(CFG);
    render(<Configuration />);
    expect(await screen.findByTestId('configuration-screen')).toBeInTheDocument();
    expect(screen.getByText('unattended_bag')).toBeInTheDocument();
    expect(screen.getByText('degraded_banner_floor')).toBeInTheDocument();
    // each row has an input seeded with the server value
    expect(screen.getByTestId('configuration-input-unattended_bag')).toHaveValue(0.75);
    expect(screen.getByTestId('configuration-input-degraded_banner_floor')).toHaveValue(0.6);
  });
});

describe('Configuration — mutations', () => {
  it('Save is disabled until the value changes, then patches per_class + refetches', async () => {
    listThresholds.mockResolvedValue(CFG);
    patchThresholds.mockResolvedValueOnce({ ...CFG, per_class: { ...CFG.per_class, unattended_bag: 0.80 } });
    render(<Configuration />);
    await screen.findByTestId('configuration-screen');

    const save = screen.getByTestId('configuration-save-unattended_bag');
    expect(save).toBeDisabled(); // not dirty yet

    fireEvent.change(screen.getByTestId('configuration-input-unattended_bag'), { target: { value: '0.8' } });
    expect(save).not.toBeDisabled();
    fireEvent.click(save);

    await waitFor(() =>
      expect(patchThresholds).toHaveBeenCalledWith({ per_class: { unattended_bag: 0.8 } })
    );
    // refetch after save (initial load + post-save reload)
    await waitFor(() => expect(listThresholds).toHaveBeenCalledTimes(2));
  });

  it('editing the floor patches degraded_banner_floor (not per_class)', async () => {
    listThresholds.mockResolvedValue(CFG);
    patchThresholds.mockResolvedValueOnce({ ...CFG, degraded_banner_floor: 0.55 });
    render(<Configuration />);
    await screen.findByTestId('configuration-screen');

    fireEvent.change(screen.getByTestId('configuration-input-degraded_banner_floor'), { target: { value: '0.55' } });
    fireEvent.click(screen.getByTestId('configuration-save-degraded_banner_floor'));

    await waitFor(() =>
      expect(patchThresholds).toHaveBeenCalledWith({ degraded_banner_floor: 0.55 })
    );
  });

  it('surfaces a save error (e.g. 422/403) without crashing', async () => {
    listThresholds.mockResolvedValue(CFG);
    patchThresholds.mockRejectedValueOnce(Object.assign(new Error('threshold must be a finite number in [0.0, 1.0]'), { status: 422 }));
    render(<Configuration />);
    await screen.findByTestId('configuration-screen');

    fireEvent.change(screen.getByTestId('configuration-input-slip_fall'), { target: { value: '0.9' } });
    fireEvent.click(screen.getByTestId('configuration-save-slip_fall'));
    expect(await screen.findByText(/finite number/)).toBeInTheDocument();
  });
});
