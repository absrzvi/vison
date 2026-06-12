import { useEffect, useState } from 'react';
import { getAiPipelineHealth } from '../../api/aiPipeline';
import { AIPipelineDrawer } from './AIPipelineDrawer';
import './AIPipelineRow.css';

const STATE_LABEL = {
  green: 'Green — running',
  amber: 'Amber — degraded',
  red: 'Red — not inferencing',
};

// AC22: single row sourced from GET /api/v1/health/ai-pipeline.fleet_state.
export function AIPipelineRow() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    getAiPipelineHealth(ctrl.signal)
      .then(d => { setData(d); setLoading(false); })
      .catch(err => {
        if (err.name === 'AbortError') return;
        setError(err);
        setLoading(false);
      });
    return () => ctrl.abort();
  }, []);

  if (loading) {
    return (
      <div className="ai-pipeline-row" data-testid="ai-pipeline-loading">
        <span className="ai-pipeline-row__label">AI pipeline</span>
        <span className="ai-pipeline-row__value">Loading…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ai-pipeline-row">
        <span className="ai-pipeline-row__label">AI pipeline</span>
        <span className="ai-pipeline-row__value">AI pipeline status unavailable</span>
      </div>
    );
  }

  const trains = data?.trains ?? [];
  if (trains.length === 0) {
    return (
      <div className="ai-pipeline-row">
        <span className="ai-pipeline-row__label">AI pipeline</span>
        <span className="ai-pipeline-row__value">AI pipeline: starting. No inferences yet.</span>
      </div>
    );
  }

  const fleetState = data.fleet_state;
  const troubled = trains.filter(t => t.state !== 'green').map(t => `${t.train_id} (${t.state})`);
  const tooltip = fleetState === 'green' ? undefined : troubled.join(', ');

  return (
    <>
      <button
        className="ai-pipeline-row ai-pipeline-row--clickable"
        onClick={() => setDrawerOpen(v => !v)}
        title={tooltip}
      >
        <span className="ai-pipeline-row__label">AI pipeline</span>
        <span className="ai-pipeline-row__value">
          <span className={`sh-sev-dot sh-sev-dot--${fleetState}`} aria-hidden="true" />
          {STATE_LABEL[fleetState]}
        </span>
      </button>
      {drawerOpen && <AIPipelineDrawer trains={trains} onClose={() => setDrawerOpen(false)} />}
    </>
  );
}
