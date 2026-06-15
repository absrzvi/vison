import { useState, useEffect, useRef } from 'react';
import { useFleetData } from '../../hooks/useFleetData';
import {
  ALERT_THRESHOLD_OPTIONS,
  STALENESS_THRESHOLD_OPTIONS,
  UNATTENDED_THRESHOLD_OPTIONS,
  formatSec,
} from '../../constants/preferences';
import { SegmentedControl } from './SegmentedControl';
import './OperatorPreferences.css';

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
