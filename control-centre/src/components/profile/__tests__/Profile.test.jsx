// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { Profile } from '../Profile';

const auth = { username: 'claudia', role: 'admin', isAuthenticated: true };
const fleet = {
  alertThresholdSeconds: 60,
  stalenessThresholdSeconds: 120,
  updateAlertThreshold: vi.fn(),
  updateStalenessThreshold: vi.fn(),
};

vi.mock('../../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../../hooks/useFleetData', () => ({ useFleetData: () => fleet }));

beforeEach(() => {
  vi.clearAllMocks();
  fleet.updateAlertThreshold.mockResolvedValue(undefined);
  fleet.updateStalenessThreshold.mockResolvedValue(undefined);
});

describe('Profile — identity + states', () => {
  it('renders the username and role of the authenticated user', () => {
    render(<Profile />);
    expect(screen.getByTestId('profile-screen')).toBeInTheDocument();
    expect(screen.getByTestId('profile-username')).toHaveTextContent('claudia');
    expect(screen.getByTestId('profile-role')).toHaveTextContent('admin');
  });

  it('surfaces ONLY the two server-backed controls (no unattended-bag control)', () => {
    render(<Profile />);
    expect(screen.getByRole('radiogroup', { name: /critical alert threshold/i })).toBeInTheDocument();
    expect(screen.getByRole('radiogroup', { name: /connection staleness/i })).toBeInTheDocument();
    // unattended_threshold_min is localStorage-only → must NOT appear on Profile (D5)
    expect(screen.queryByText(/unattended/i)).not.toBeInTheDocument();
  });
});

describe('Profile — round-trip + error state', () => {
  it('committing an alert-threshold change PATCHes via the updater', async () => {
    render(<Profile />);
    // 90s is unique to the alert-threshold control (staleness has no 90 option).
    fireEvent.click(screen.getByRole('radio', { name: '90s' }));
    await waitFor(() =>
      expect(fleet.updateAlertThreshold).toHaveBeenCalledWith(90)
    );
  });

  it('shows a save-error toast when the PATCH fails', async () => {
    fleet.updateAlertThreshold.mockResolvedValueOnce(new Error('save failed'));
    render(<Profile />);
    // scope to the alert-threshold radiogroup — '120' appears in both controls.
    const alertGroup = screen.getByRole('radiogroup', { name: /critical alert threshold/i });
    fireEvent.click(within(alertGroup).getByRole('radio', { name: '120s' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });
});
