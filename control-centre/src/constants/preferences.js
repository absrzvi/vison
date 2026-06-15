export const DEFAULT_ALERT_THRESHOLD_SECONDS = 60;
export const DEFAULT_STALENESS_THRESHOLD_SECONDS = 120;
export const DEFAULT_UNATTENDED_THRESHOLD_MINUTES = 5;
export const ALERT_THRESHOLD_OPTIONS = [30, 60, 90, 120];
export const STALENESS_THRESHOLD_OPTIONS = [60, 120, 180, 300];
export const UNATTENDED_THRESHOLD_OPTIONS = [1, 2, 5, 10, 15];
export const LS_KEY_ALERT_THRESHOLD = 'oebb.cc.alertThresholdSeconds';
export const LS_KEY_STALENESS_THRESHOLD = 'oebb.cc.stalenessThresholdSeconds';
export const LS_KEY_UNATTENDED_THRESHOLD = 'oebb.cc.unattendedThresholdMinutes';
export const WS_STALENESS_THRESHOLD_MS = 120_000;

// Segmented-control label formatter for second-valued thresholds (shared by the
// gear-modal and the Profile screen — E11-S3).
export const formatSec = (s) => `${s}s`;
