import { useState, useEffect, useRef, useCallback } from 'react';
import { useFleetData } from '../../hooks/useFleetData';
import {
  ALERT_THRESHOLD_OPTIONS,
  STALENESS_THRESHOLD_OPTIONS,
  UNATTENDED_THRESHOLD_OPTIONS,
} from '../../constants/preferences';
import './OperatorPreferences.css';

function SegmentedControl({ label, options, value, onCommit, formatLabel }) {
  // focusIdx is a mutable ref — keyboard navigation moves it without re-rendering.
  // tabIndex on buttons is derived from the ref via DOM manipulation in the keydown handler.
  const focusIdxRef = useRef(options.indexOf(value));
  const groupRef = useRef(null);

  // When value changes (e.g. server reconcile), keep focusIdx aligned.
  // Done in useEffect (not render body) to avoid mutating a ref during render in concurrent mode.
  useEffect(() => {
    const idx = options.indexOf(value);
    if (idx !== -1) focusIdxRef.current = idx;
  }, [value, options]);

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
  const { alertThresholdSeconds, stalenessThresholdSeconds, unattendedThresholdMinutes, updateAlertThreshold, updateStalenessThreshold, updateUnattendedThreshold } = useFleetData();
  const [toast, setToast] = useState(null);
  const panelRef = useRef(null);
  const toastTimerRef = useRef(null);

  // Close on Escape; trap Tab focus within panel
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key === 'Tab' && panelRef.current) {
        const focusable = Array.from(
          panelRef.current.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          )
        ).filter(el => !el.disabled);
        if (!focusable.length) { e.preventDefault(); return; }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) { e.preventDefault(); last.focus(); }
        } else {
          if (document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Initial focus
  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  // Clear toast timer on unmount
  useEffect(() => {
    return () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); };
  }, []);

  function showToast(msg) {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 4000);
  }

  async function handleThresholdCommit(val) {
    const err = await updateAlertThreshold(val);
    if (err) showToast('Preference not saved — please retry');
  }

  async function handleStalenessCommit(val) {
    const err = await updateStalenessThreshold(val);
    if (err) showToast('Preference not saved — please retry');
  }

  async function handleUnattendedCommit(val) {
    const err = await updateUnattendedThreshold(val);
    if (err) showToast('Preference not saved — please retry');
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
          <SegmentedControl
            label="Unattended bag alert after"
            options={UNATTENDED_THRESHOLD_OPTIONS}
            value={unattendedThresholdMinutes}
            onCommit={handleUnattendedCommit}
            formatLabel={(n) => `${n} min`}
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
