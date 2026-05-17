import { useState } from 'react';
import { OccupancyHeatmap } from './OccupancyHeatmap';
import { DwellTime } from './DwellTime';
import { AIDetection } from './AIDetection';
import { ExceptionWorkflow } from './ExceptionWorkflow';
import { DETECTION_TREND, getExceptionsForRange, getOccupancyHeatmap, getDwellData } from '../../mock/analytics';
import './Analytics.css';

const TABS = [
  { key: 'exceptions', label: 'Capacity Exceptions' },
  { key: 'occupancy',  label: 'Occupancy Heatmap' },
  { key: 'dwell',      label: 'Dwell Time' },
  { key: 'ai',         label: 'AI Detection Quality' },
];

const DATE_RANGES = [
  { key: '7d',  label: 'Last 7 days' },
  { key: '14d', label: 'Last 14 days' },
  { key: '30d', label: 'Last 30 days' },
];

// P2 fix: export uses the same data/range as what's displayed on screen
function mockExportCsv(tab, range) {
  const days = { '7d': 7, '14d': 14, '30d': 30 }[range] ?? 7;
  const multiplier = days / 7;
  let rows;
  if (tab === 'exceptions') {
    rows = ['Date,TrainId,Route,Departure,Coaches,PeakOccupancy(%),TrendDirection,Severity,ConradFlag,Status'];
    getExceptionsForRange(range).forEach(e => rows.push(
      `${e.date ?? '2026-05-15'},${e.trainId},"${e.route}",${e.departure},"${e.coaches.join('+')}",${e.peakOccupancy},${e.trendDirection},${e.severity},${e.conradFlag ? 'Yes' : 'No'},${e.status}`
    ));
  } else if (tab === 'occupancy') {
    // P2 fix: pass range to getOccupancyHeatmap so export matches what's on screen
    const heatmap = getOccupancyHeatmap(range);
    rows = ['Route,Hour,AvgOccupancy(%)'];
    heatmap.forEach(r => r.hours.forEach(h => rows.push(`${r.route},${h.hour},${h.occupancy}`)));
  } else if (tab === 'dwell') {
    const dwellData = getDwellData(range);
    rows = ['Station,ScheduledSec,ActualSec,ExcessSec,Breaches,TopCause'];
    dwellData.forEach(d => rows.push(
      `${d.station},${d.scheduled},${d.actual},${d.actual - d.scheduled},${d.breaches},"${d.topCause ?? ''}"`
    ));
  } else {
    // P2 fix: apply same multiplier as AIDetection component
    rows = ['Day,Unattended,Overcrowded,Oversized,FalsePositives'];
    DETECTION_TREND.forEach(d => rows.push(
      `${d.day},${Math.round(d.unattended * multiplier)},${Math.round(d.overcrowded * multiplier)},${Math.round(d.oversized * multiplier)},${Math.round(d.falsePositive * multiplier)}`
    ));
  }
  const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `oebb-${tab}-${range}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function Analytics() {
  const [activeTab, setActiveTab] = useState('exceptions');
  const [dateRange, setDateRange] = useState('7d');

  return (
    <div className="analytics">
      <div className="analytics__tab-bar">
        {TABS.map(t => (
          <button
            key={t.key}
            className={`analytics__tab ${activeTab === t.key ? 'analytics__tab--active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
        <div className="analytics__tab-bar-end">
          <div className="analytics__date-range">
            <span className="analytics__range-label">Range:</span>
            {DATE_RANGES.map(r => (
              <button
                key={r.key}
                className={`analytics__range-btn ${dateRange === r.key ? 'analytics__range-btn--active' : ''}`}
                onClick={() => setDateRange(r.key)}
              >{r.label}</button>
            ))}
          </div>
          <button
            className="btn btn--secondary analytics__export-btn"
            onClick={() => mockExportCsv(activeTab, dateRange)}
          >Export CSV</button>
        </div>
      </div>

      <div className="analytics__content">
        {activeTab === 'exceptions' && <ExceptionWorkflow dateRange={dateRange} />}
        {activeTab === 'occupancy'  && <OccupancyHeatmap dateRange={dateRange} />}
        {activeTab === 'dwell'      && <DwellTime dateRange={dateRange} />}
        {activeTab === 'ai'         && <AIDetection dateRange={dateRange} />}
      </div>
    </div>
  );
}
