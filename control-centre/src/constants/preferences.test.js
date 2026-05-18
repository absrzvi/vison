import { describe, it, expect } from 'vitest';
import {
  DEFAULT_ALERT_THRESHOLD_SECONDS,
  DEFAULT_STALENESS_THRESHOLD_SECONDS,
  ALERT_THRESHOLD_OPTIONS,
  STALENESS_THRESHOLD_OPTIONS,
  LS_KEY_ALERT_THRESHOLD,
  LS_KEY_STALENESS_THRESHOLD,
} from './preferences';

// T7.3: correct options + named constants (AC8 — no magic numbers)
describe('preferences constants', () => {
  it('DEFAULT_ALERT_THRESHOLD_SECONDS is 60', () => {
    expect(DEFAULT_ALERT_THRESHOLD_SECONDS).toBe(60);
  });

  it('DEFAULT_STALENESS_THRESHOLD_SECONDS is 120', () => {
    expect(DEFAULT_STALENESS_THRESHOLD_SECONDS).toBe(120);
  });

  it('ALERT_THRESHOLD_OPTIONS contains exactly [30, 60, 90, 120]', () => {
    expect(ALERT_THRESHOLD_OPTIONS).toEqual([30, 60, 90, 120]);
  });

  it('STALENESS_THRESHOLD_OPTIONS contains exactly [60, 120, 180, 300]', () => {
    expect(STALENESS_THRESHOLD_OPTIONS).toEqual([60, 120, 180, 300]);
  });

  it('DEFAULT_ALERT_THRESHOLD_SECONDS is in ALERT_THRESHOLD_OPTIONS', () => {
    expect(ALERT_THRESHOLD_OPTIONS).toContain(DEFAULT_ALERT_THRESHOLD_SECONDS);
  });

  it('DEFAULT_STALENESS_THRESHOLD_SECONDS is in STALENESS_THRESHOLD_OPTIONS', () => {
    expect(STALENESS_THRESHOLD_OPTIONS).toContain(DEFAULT_STALENESS_THRESHOLD_SECONDS);
  });

  it('LS_KEY_ALERT_THRESHOLD is the expected localStorage key', () => {
    expect(LS_KEY_ALERT_THRESHOLD).toBe('oebb.cc.alertThresholdSeconds');
  });

  it('LS_KEY_STALENESS_THRESHOLD is the expected localStorage key', () => {
    expect(LS_KEY_STALENESS_THRESHOLD).toBe('oebb.cc.stalenessThresholdSeconds');
  });
});
