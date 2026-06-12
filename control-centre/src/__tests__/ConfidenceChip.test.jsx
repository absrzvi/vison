/** @vitest-environment jsdom */
// Story 10-1 AC20 — per-alert confidence chip.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ConfidenceChip } from '../components/alerts/ConfidenceChip';

const THRESHOLDS = { unattended_bag: 0.75, door_obstruction: 0.85 };

function chip({ basis = 'model', score = 0.9, alertCode = 'unattended_bag' } = {}) {
  return render(
    <ConfidenceChip
      escalation={{ confidence_basis: basis, confidence_score: score, alert_code: alertCode }}
      thresholds={THRESHOLDS}
    />,
  );
}

describe('ConfidenceChip', () => {
  it('renders High confidence above threshold, no tooltip', () => {
    chip({ score: 0.8 });
    const el = screen.getByText('High confidence');
    expect(el).toBeInTheDocument();
    expect(el.closest('[title]')).toBeNull();
  });

  it('renders Medium confidence in the 0.85×threshold band with tooltip', () => {
    // threshold 0.75 → band [0.6375, 0.75)
    chip({ score: 0.7 });
    const el = screen.getByText('Medium confidence');
    expect(el).toBeInTheDocument();
    expect(el.closest('[title]').title).toMatch(/Verify against CCTV/);
  });

  it('renders Verify below 0.85×threshold with tooltip', () => {
    chip({ score: 0.5 });
    const el = screen.getByText('Verify');
    expect(el).toBeInTheDocument();
    expect(el.closest('[title]').title).toMatch(/Verify against CCTV/);
  });

  it('renders nothing for sensor basis', () => {
    const { container } = chip({ basis: 'sensor', score: null });
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for fused basis', () => {
    const { container } = chip({ basis: 'fused', score: 0.7 });
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when thresholds are not loaded yet', () => {
    const { container } = render(
      <ConfidenceChip
        escalation={{ confidence_basis: 'model', confidence_score: 0.9, alert_code: 'unattended_bag' }}
        thresholds={null}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('never displays the numeric score', () => {
    const { container } = chip({ score: 0.93 });
    expect(container.textContent).not.toMatch(/0\.93|93/);
  });
});
