import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { SOURCE_LABEL, SEV_CLASS } from '../../constants/escalation';
import { useFleetData } from '../../context/FleetContext';
import './EscalationDetail.css';

const ACTION_TAGS = [
  'Resolved remotely',
  'Field team dispatched',
  'False alarm',
  'No action needed',
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
  const { escalationActionState } = useFleetData();
  const [frameExpanded, setFrameExpanded] = useState(false);
  // E10-S1 AC20 — "Model details" disclosure (Freya micro-spec 2026-06-12).
  const [modelDetailsOpen, setModelDetailsOpen] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [outcome, setOutcome] = useState('');
  const [selectedTags, setSelectedTags] = useState([]);
  const [submitAttempted, setSubmitAttempted] = useState(false);

  const actionState = escalation ? escalationActionState[escalation.id] : undefined;
  const isPending = actionState === 'pending';
  const actionError = actionState instanceof Error ? actionState : null;

  const canSubmit = outcome.trim().length > 0 && selectedTags.length > 0;
  const outcomeEmpty = submitAttempted && outcome.trim().length === 0;
  const tagsEmpty = submitAttempted && selectedTags.length === 0;

  // Clear form only after the context confirms success (escalation status changed).
  // Track the status we submitted from so we know when the context has caught up.
  const submittedFromStatus = useRef(null);
  useEffect(() => {
    if (!escalation || !submittedFromStatus.current) return;
    if (escalation.status !== submittedFromStatus.current) {
      // Status advanced — safe to clear the resolve form now.
      submittedFromStatus.current = null;
      setResolving(false);
      setOutcome('');
      setSelectedTags([]);
      setSubmitAttempted(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [escalation?.status]);

  // P1 — if the action errored, the ref stays set and blocks future form-clears.
  // Clear it whenever an error lands so the next successful attempt works correctly.
  useEffect(() => {
    if (actionError) {
      submittedFromStatus.current = null;
    }
  }, [actionError]);

  const handleAcknowledge = () => {
    // Clear any stale error before re-trying (P8).
    onAcknowledge(escalation.id);
  };

  const handleResolve = () => {
    setSubmitAttempted(true);
    if (!canSubmit) return;
    // Record the status we're resolving from; form clears when context confirms (P4).
    submittedFromStatus.current = escalation.status;
    onResolve(escalation.id, outcome.trim(), selectedTags);
  };

  // Reset all form state when the selected escalation changes (P10 — also discards
  // any pending stale state for the previous escalation's id).
  const prevEscId = useRef(escalation?.id);
  if (prevEscId.current !== escalation?.id) {
    prevEscId.current = escalation?.id;
    submittedFromStatus.current = null;
    setResolving(false);
    setOutcome('');
    setSelectedTags([]);
    setFrameExpanded(false);
    setModelDetailsOpen(false);
    setSubmitAttempted(false);
  }

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
        {/* Severity accent bar */}
        <div className="esc-detail__accent-bar" />

        {/* Scrollable body */}
        <div className="esc-detail__body">

          {/* Header */}
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

          {/* Description */}
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

          {/* Model details — E10-S1 AC20, placement per Freya micro-spec:
              below the evidence (still frame / description), above the action
              surfaces. Rendered only for model/fused basis; collapsed by default. */}
          {(escalation.confidence_basis === 'model' || escalation.confidence_basis === 'fused') &&
            typeof escalation.confidence_score === 'number' && (
            <div className="esc-model-details">
              <div
                className="esc-model-details__toggle"
                role="button"
                tabIndex={0}
                aria-expanded={modelDetailsOpen}
                onClick={() => setModelDetailsOpen(v => !v)}
                onKeyDown={e => e.key === 'Enter' && setModelDetailsOpen(v => !v)}
              >
                {modelDetailsOpen ? '▾' : '▸'} Model details
              </div>
              {modelDetailsOpen && (
                <div className="esc-model-details__body">
                  <div className="esc-model-details__row">
                    <span className="esc-model-details__label">Confidence</span>
                    <span className="esc-model-details__score">
                      {(escalation.confidence_score * 100).toFixed(1)}%
                    </span>
                    <span className="esc-model-details__basis">({escalation.confidence_basis})</span>
                  </div>
                  {Object.entries(escalation.model_versions ?? {}).map(([k, v]) => (
                    <div key={k} className="esc-model-details__row">
                      <span className="esc-model-details__label">{k}</span>
                      <span className="esc-model-details__value">{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Error toast — shown until next action attempt clears it (P8) */}
          {actionError && (
            <div className="esc-detail__error-toast" role="alert">
              Action failed — please try again
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
              {/* AC5 — outcome validation (P2/P3) */}
              {outcomeEmpty && (
                <p className="resolve-form__validation-msg">Outcome required</p>
              )}
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
              {/* P3 — tags validation */}
              {tagsEmpty && (
                <p className="resolve-form__validation-msg">Select at least one action</p>
              )}

              <div className="resolve-form__actions">
                <button
                  className="btn btn--primary"
                  onClick={handleResolve}
                  disabled={isPending}
                >
                  {isPending ? 'Submitting…' : 'Submit Resolution'}
                </button>
                <button className="btn btn--ghost" onClick={() => { setResolving(false); setOutcome(''); setSelectedTags([]); setSubmitAttempted(false); submittedFromStatus.current = null; }}>
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
              <button
                className="btn btn--primary"
                onClick={handleAcknowledge}
                disabled={isPending}
              >
                {isPending ? 'Acknowledging…' : 'Acknowledge'}
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
