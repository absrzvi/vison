/** @vitest-environment jsdom */
// Story 10-1 AC21 — fleet-degraded banner.
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DegradedBanner } from '../components/alerts/DegradedBanner';

const COPY =
  'AI alert quality is degraded. Nomad has been notified. Continue to verify alerts against CCTV as normal.';

function mockHealth(degraded) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', ai_quality_degraded: degraded }),
    }),
  );
}

describe('DegradedBanner', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it('shows the verbatim copy when ai_quality_degraded is true', async () => {
    mockHealth(true);
    render(<DegradedBanner />);
    await waitFor(() => expect(screen.getByText(COPY)).toBeInTheDocument());
  });

  it('renders nothing when flag is false', async () => {
    mockHealth(false);
    const { container } = render(<DegradedBanner />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('is dismissible and stays dismissed for the session', async () => {
    mockHealth(true);
    const { unmount } = render(<DegradedBanner />);
    await waitFor(() => expect(screen.getByText(COPY)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByText(COPY)).toBeNull();
    unmount();

    // Remount in the same session: stays dismissed.
    render(<DegradedBanner />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByText(COPY)).toBeNull();
  });

  it('reappears next session when the flag is still true', async () => {
    mockHealth(true);
    sessionStorage.clear(); // new session
    render(<DegradedBanner />);
    await waitFor(() => expect(screen.getByText(COPY)).toBeInTheDocument());
  });

  it('renders nothing on fetch error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    const { container } = render(<DegradedBanner />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
