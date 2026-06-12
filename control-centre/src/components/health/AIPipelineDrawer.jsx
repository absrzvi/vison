import './AIPipelineRow.css';

function relativeTime(iso) {
  if (!iso) return 'never';
  const diffMs = Date.now() - Date.parse(iso);
  if (Number.isNaN(diffMs) || diffMs < 0) return 'just now';
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ${m % 60}m ago`;
}

// AC22 drawer: per-train rows — no sparkline, no per-class breakdown.
export function AIPipelineDrawer({ trains, onClose }) {
  return (
    <div className="ai-pipeline-drawer">
      <div className="ai-pipeline-drawer__header">
        <span>AI pipeline — per train</span>
        <button
          className="ai-pipeline-drawer__close"
          onClick={onClose}
          aria-label="Close AI pipeline detail"
        >
          &times;
        </button>
      </div>
      {trains.map(t => (
        <div key={t.train_id} className="ai-pipeline-drawer__train">
          <div className="ai-pipeline-drawer__train-header">
            <span className={`sh-sev-dot sh-sev-dot--${t.state}`} aria-hidden="true" />
            <span className="ai-pipeline-drawer__train-id">{t.train_id}</span>
            <span className="ai-pipeline-drawer__last-seen">{relativeTime(t.last_seen)}</span>
          </div>
          <div className="ai-pipeline-drawer__meta">
            <span className="ai-pipeline-drawer__meta-label">Hailo device</span>
            <span>{t.hailo_device_ok ? 'OK' : 'Not OK'}</span>
          </div>
          {Object.entries(t.model_versions ?? {}).map(([k, v]) => (
            <div key={k} className="ai-pipeline-drawer__meta">
              <span className="ai-pipeline-drawer__meta-label">{k}</span>
              <span className="ai-pipeline-drawer__meta-value">{v}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
