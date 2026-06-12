import './ConfidenceChip.css';

const TOOLTIP = 'Model is less certain. Verify against CCTV before dispatching.';

// AC20: rendered only for model-basis alerts with loaded thresholds. The
// numeric score is never displayed here — it lives in the detail drawer.
export function ConfidenceChip({ escalation, thresholds }) {
  const basis = escalation?.confidence_basis;
  const score = escalation?.confidence_score;
  const code = escalation?.alert_code;
  if (basis !== 'model' || typeof score !== 'number' || !thresholds) return null;
  const threshold = thresholds[code];
  if (typeof threshold !== 'number') return null;

  if (score >= threshold) {
    return <span className="confidence-chip confidence-chip--high">High confidence</span>;
  }
  const verify = score < threshold * 0.85;
  return (
    <span
      className={`confidence-chip ${verify ? 'confidence-chip--verify' : 'confidence-chip--medium'}`}
      title={TOOLTIP}
    >
      <span className="confidence-chip__dot" aria-hidden="true" />
      {verify ? 'Verify' : 'Medium confidence'}
    </span>
  );
}
