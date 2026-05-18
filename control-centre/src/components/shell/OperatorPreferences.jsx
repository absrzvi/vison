import { useState, useEffect, useRef, useCallback } from 'react';
import { useFleetData } from '../../hooks/useFleetData';
import {
  ALERT_THRESHOLD_OPTIONS,
  STALENESS_THRESHOLD_OPTIONS,
} from '../../constants/preferences';
import './OperatorPreferences.css';

function SegmentedControl({ label, options, value, onCommit, formatLabel }) {
  // focusIdx is a mutable ref — keyboard navigation moves it without re-rendering.
  // tabIndex on buttons is derived from the ref via DOM manipulation in the keydown handler.
  const focusIdxRef = useRef(options.indexOf(value));
  const groupRef = useRef(null);

  // When value changes (e.g. server reconcile), keep focusIdx aligned.
  focusIdxRef.current = options.indexOf(value) === -1 ? focusIdxRef.current : options.indexOf(value);

  function moveFocus(newIdx) {
    focusIdxRef.current = newIdx;
    const btns = groupRef.current?.querySelectorAll('.seg-btn');
    if (!btns) return;
    btns.forEach((btn, i) => {
      btn.setAttribute('tabindex', i === newIdx ? '0' : '-1');
    });
    btns[newIdx]?.focus();
  }

  const handleKeyDown = useCallback((e) => {
    const len = options.length;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      moveFocus((focusIdxRef.current + 1) % len);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      moveFocus((focusIdxRef.current - 1 + len) % len);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onCommit(options[focusIdxRef.current]);
    }
  }, [options, onCommit]);

  return (
    <div className="pref-row">
      <span className="pref-label">{label}</span>
      <div
        className="seg-group"
        role="radiogroup"
        aria-label={label}
        ref={groupRef}
        onKeyDown={handleKeyDown}
      >
        {options.map((opt, idx) => (
          <button
            key={opt}
            className={`seg-btn${opt === value ? ' seg-btn--active' : ''}`}
            role="radio"
            aria-checked={opt === value}
            tabIndex={idx === focusIdxRef.current ? 0 : -1}
            onClick={() => onCommit(opt)}
          >
            {formatLabel ? formatLabel(opt) : opt}
          </button>
        ))}
      </div>
    </div>
  );
}

function formatSec(s) {
  return `${s}s`;
}

export function OperatorPreferences({ onClose }) {
  const { alertThresholdSeconds, stalenessThresholdSeconds, updateAlertThreshold, updateStalenessThreshold } = useFleetData();
  const [toast, setToast] = useState(null);
  const panelRef = useRef(null);

  // Close on Escape
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Trap focus inside panel
  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  async function handleThresholdCommit(val) {
    const err = await updateAlertThreshold(val);
    if (err) {
      setToast('Preference not saved — please retry');
      setTimeout(() => setToast(null), 4000);
    }
  }

  async function handleStalenessCommit(val) {
    const err = await updateStalenessThreshold(val);
    if (err) {
      setToast('Preference not saved — please retry');
      setTimeout(() => setToast(null), 4000);
    }
  }

  return (
    <div className="pref-backdrop" onClick={onClose} aria-modal="true" role="dialog" aria-label="Operator Preferences">
      <div
        className="pref-panel"
        ref={panelRef}
        tabIndex={-1}
        onClick={e => e.stopPropagation()}
      >
        <div className="pref-header">
          <h2 className="pref-title">Preferences</h2>
          <button className="pref-close" onClick={onClose} aria-label="Close preferences">✕</button>
        </div>

        <div className="pref-body">
          <SegmentedControl
            label="Critical alert threshold"
            options={ALERT_THRESHOLD_OPTIONS}
            value={alertThresholdSeconds}
            onCommit={handleThresholdCommit}
            formatLabel={formatSec}
          />
          <SegmentedControl
            label="Connection staleness warning"
            options={STALENESS_THRESHOLD_OPTIONS}
            value={stalenessThresholdSeconds}
            onCommit={handleStalenessCommit}
            formatLabel={formatSec}
          />
        </div>

        {toast && (
          <div className="pref-toast" role="alert">
            {toast}
          </div>
        )}
      </div>
    </div>
  );
}
