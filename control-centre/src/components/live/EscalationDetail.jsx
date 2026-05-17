import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { SOURCE_LABEL, SEV_CLASS } from '../../constants/escalation';
import './EscalationDetail.css';

const ACTION_TAGS = [
  'Passenger assisted',
  'Police alerted',
  'Station notified',
  'Conrad instructed',
  'No action required',
  'Other',
];

const SEV_ACCENT = {
  critical: 'var(--obb-sev-critical)',
  high:     'var(--obb-sev-high)',
  medium:   'var(--obb-sev-medium)',
  low:      'var(--obb-sev-low)',
  normal:   'var(--obb-sev-normal)',
};

const STATUS_LABEL = {
  unacknowledged: 'Unacknowledged',
  acknowledged:   'Acknowledged',
  resolved:       'Resolved',
};

function computeElapsed(timestamp) {
  if (!timestamp) return null;
  try {
    const [h, m] = timestamp.split(':').map(Number);
    const now = new Date();
    const then = new Date(now);
    then.setHours(h, m, 0, 0);
    const diffMs = now - then;
    if (diffMs < 0) return null;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    return `${diffH}h ${diffMin % 60}m ago`;
  } catch {
    return null;
  }
}

export function EscalationDetail({ escalation, onClose, onAcknowledge, onResolve }) {
  const navigate = useNavigate();
  const [frameExpanded, setFrameExpanded] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [outcome, setOutcome] = useState('');
  const [selectedTags, setSelectedTags] = useState([]);

  const canSubmit = outcome.trim().length > 0 && selectedTags.length > 0;

  const handleResolve = () => {
    onResolve(escalation.id, outcome.trim(), selectedTags);
    setResolving(false);
    setOutcome('');
    setSelectedTags([]);
  };

  useEffect(() => {
    setResolving(false);
    setOutcome('');
    setSelectedTags([]);
    setFrameExpanded(false);
  }, [escalation?.id]);

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const toggleTag = (tag) => {
    setSelectedTags(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  if (!escalation) return null;

  const accentColor = SEV_ACCENT[escalation.severity] ?? 'var(--obb-border-bright)';
  const elapsed = computeElapsed(escalation.timestamp);
  const isCritical = escalation.severity === 'critical' || escalation.severity === 'high';

  return createPortal(
    <div className="esc-modal-backdrop" onClick={onClose}>
      <div
        className="esc-detail"
        onClick={e => e.stopPropagation()}
        style={{ '--sev-accent': accentColor }}
      >
        {/* Severity accent bar — 3px coloured top strip */}
        <div className="esc-detail__accent-bar" />

        {/* Scrollable body */}
        <div className="esc-detail__body">

          {/* Header: source badge + status pill + close */}
          <div className="esc-detail__header">
            <div className="esc-detail__header-left">
              <span className={`badge ${SEV_CLASS[escalation.severity]}`}>
                {SOURCE_LABEL[escalation.type]}
              </span>
              <span className={`esc-detail__status-pill esc-detail__status-pill--${escalation.status}`}>
                {STATUS_LABEL[escalation.status] ?? escalation.status}
              </span>
              {escalation.status === 'resolved' && (
                <span className="esc-detail__readonly-pill">Read only</span>
              )}
            </div>
            <button className="esc-detail__close" onClick={onClose} aria-label="Close escalation detail">&times;</button>
          </div>

          {/* Title */}
          <h2 className="esc-detail__title">{escalation.title}</h2>

          {/* Meta info bar */}
          <div className="esc-detail__meta-bar">
            <div className="esc-detail__meta-item">
              <span className="esc-detail__meta-label">Train</span>
              <span className="esc-detail__meta-value">{escalation.trainId}</span>
            </div>
            {escalation.coachId && (
              <div className="esc-detail__meta-item">
                <span className="esc-detail__meta-label">Coach</span>
                <span className="esc-detail__meta-value">{escalation.coachId}</span>
              </div>
            )}
            <div className="esc-detail__meta-item">
              <span className="esc-detail__meta-label">Time</span>
              <span className="esc-detail__meta-value">{escalation.timestamp}</span>
            </div>
            {elapsed && (
              <div className="esc-detail__meta-item">
                <span className="esc-detail__meta-label">Elapsed</span>
                <span className="esc-detail__meta-value">{elapsed}</span>
              </div>
            )}
          </div>

          {/* Description — left-border accent, larger text, critical tint */}
          <div className={`esc-detail__description-wrap${isCritical ? ' esc-detail__description-wrap--critical' : ''}`}>
            <p className={`esc-detail__description${isCritical ? ' esc-detail__description--critical' : ''}`}>
              {escalation.detail}
            </p>
          </div>

          {/* Still frame */}
          {escalation.stillFrame && (
            <div className="esc-still-frame">
              <div
                className={`esc-still-frame__container${frameExpanded ? ' esc-still-frame__container--expanded' : ''}`}
                onClick={() => setFrameExpanded(v => !v)}
                role="button"
                tabIndex={0}
                aria-label={frameExpanded ? 'Collapse still frame' : 'Expand still frame'}
                onKeyDown={e => e.key === 'Enter' && setFrameExpanded(v => !v)}
              >
                <img
                  src={escalation.stillFrame.url}
                  alt={`Still frame from ${escalation.stillFrame.camera} at ${escalation.stillFrame.capturedAt}`}
                  className="esc-still-frame__img"
                />
                {/* Overlaid chips */}
                <span className="esc-still-frame__chip esc-still-frame__chip--camera">
                  📷 {escalation.stillFrame.camera}
                </span>
                <span className="esc-still-frame__chip esc-still-frame__chip--ts">
                  🕐 {escalation.stillFrame.capturedAt}
                </span>
                <span className="esc-still-frame__chip esc-still-frame__chip--confidence">
                  {escalation.stillFrame.confidence}% conf
                </span>
                <div className="esc-still-frame__overlay">
                  <span>{frameExpanded ? '⤡ collapse' : '⤢ expand'}</span>
                </div>
              </div>
              <p className="esc-still-frame__privacy">
                Single frame from detection moment only. No live feed. Access logged.
              </p>
            </div>
          )}

          {/* Resolve form */}
          {resolving && (
            <div className="resolve-form">
              <label className="resolve-form__label">Outcome <span className="resolve-form__required">required</span></label>
              <textarea
                className="resolve-form__input"
                placeholder="Describe what happened and what action was taken…"
                value={outcome}
                onChange={e => setOutcome(e.target.value)}
                maxLength={200}
                rows={3}
              />
              <div className="resolve-form__char-count">{outcome.length} / 200</div>

              <label className="resolve-form__label">Action taken <span className="resolve-form__required">select at least one</span></label>
              <div className="resolve-form__tags">
                {ACTION_TAGS.map(tag => (
                  <button
                    key={tag}
                    className={`resolve-tag${selectedTags.includes(tag) ? ' resolve-tag--active' : ''}`}
                    onClick={() => toggleTag(tag)}
                  >
                    {tag}
                  </button>
                ))}
              </div>

              <div className="resolve-form__actions">
                <button className="btn btn--primary" onClick={handleResolve} disabled={!canSubmit}>
                  Submit Resolution
                </button>
                <button className="btn btn--ghost" onClick={() => { setResolving(false); setOutcome(''); setSelectedTags([]); }}>
                  Cancel
                </button>
              </div>
            </div>
          )}

        </div>{/* end .esc-detail__body */}

        {/* Sticky action footer */}
        <div className="esc-detail__footer">
          <div className="esc-detail__footer-left">
            {escalation.status === 'unacknowledged' && !resolving && (
              <button className="btn btn--primary" onClick={() => onAcknowledge(escalation.id)}>
                Acknowledge
              </button>
            )}
            {escalation.status === 'acknowledged' && !resolving && escalation.type !== 'roland' && (
              <button className="btn btn--primary" onClick={() => setResolving(true)}>
                Resolve
              </button>
            )}
            {escalation.status === 'resolved' && (
              <span className="esc-detail__footer-resolved">Resolved</span>
            )}
          </div>
          <div className="esc-detail__footer-right">
            <button
              className="btn btn--secondary esc-detail__live-btn"
              onClick={() => { onClose(); navigate('/dashboard/live'); }}
            >
              📹 View on Live tab
            </button>
          </div>
        </div>

      </div>
    </div>,
    document.body
  );
}
