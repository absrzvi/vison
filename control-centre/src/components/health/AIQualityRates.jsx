import { useEffect, useState } from 'react';
import { getResolutionRates } from '../../api/aiQuality';
import './AIQualityRates.css';

// 10-5 AC2/AC3: two orthogonal resolution-quality rates per alert class.
// no_action_rate + explicit_fp_rate shown side-by-side — never an aggregated
// single quality score (AC3). Each rate rendered as "<pct>% (<n> of <denom>)" so
// small-sample noise is visible (AC1). `—` when a rate is null/unavailable.
const PCT = rate =>
  rate === null || rate === undefined ? '—' : `${(rate * 100).toFixed(1)}%`;

function rateCell(rate, count, denom) {
  if (rate === null || rate === undefined) {
    return <span className="ai-quality__rate">—</span>;
  }
  return (
    <span className="ai-quality__rate">
      {PCT(rate)} <span className="ai-quality__denom">({count} of {denom})</span>
    </span>
  );
}

export function AIQualityRates() {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getResolutionRates(ctrl.signal)
      .then(d => { setRows(d); setLoading(false); })
      .catch(err => {
        if (err.name === 'AbortError') return;
        setError(err);
        setLoading(false);
      });
    return () => ctrl.abort();
  }, []);

  if (loading) {
    return (
      <div className="ai-quality" data-testid="ai-quality-loading">
        <span className="ai-quality__label">Alert quality</span>
        <span className="ai-quality__value">Loading…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ai-quality">
        <span className="ai-quality__label">Alert quality</span>
        <span className="ai-quality__value">Alert quality rates unavailable</span>
      </div>
    );
  }

  if (!rows || rows.length === 0) {
    return (
      <div className="ai-quality">
        <span className="ai-quality__label">Alert quality</span>
        <span className="ai-quality__value">No resolved alerts in the last 7 days.</span>
      </div>
    );
  }

  return (
    <div className="ai-quality">
      <div className="ai-quality__header">
        <span className="ai-quality__label">Alert quality — resolution rates (7d)</span>
      </div>
      <table className="ai-quality__table">
        <thead>
          <tr>
            <th>Alert class</th>
            <th>No-action rate</th>
            <th>Explicit false-positive rate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const breaching = r.explicit_fp_rate !== null && r.explicit_fp_rate >= 0.05;
            return (
              <tr key={r.alert_code}>
                <td className="ai-quality__code">{r.alert_code}</td>
                <td>{rateCell(r.no_action_rate, r.no_action_count, r.resolved_total)}</td>
                <td className={breaching ? 'ai-quality__breach' : undefined}>
                  {rateCell(r.explicit_fp_rate, r.false_alarm_count, r.resolved_total)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
