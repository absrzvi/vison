import { useEffect, useRef, useCallback } from 'react';

// Extracted from OperatorPreferences (E11-S3 D5) so the gear-modal AND the
// Profile screen share ONE keyboard-navigable segmented control — no duplicated
// roving-tabindex logic. Pure and self-contained: owns its own focus index and
// group ref, has no reference to any modal. Moving it here is a literal cut-paste;
// the modal's focus-trap operates on its own panelRef and is unaffected.
export function SegmentedControl({ label, options, value, onCommit, formatLabel }) {
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
