import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { KpiStripSkeleton } from '../KpiStrip';
import { FleetListSkeleton } from '../FleetList';
import { UnifiedFeedSkeleton } from '../UnifiedFeed';

describe('KpiStripSkeleton', () => {
  it('renders 5 skeleton tiles', () => {
    const html = renderToStaticMarkup(<KpiStripSkeleton />);
    // kpi-tile appears once per tile
    const tileMatches = html.match(/class="kpi-tile"/g) ?? [];
    expect(tileMatches.length).toBe(5);
  });

  it('has testid kpi-strip-skeleton', () => {
    const html = renderToStaticMarkup(<KpiStripSkeleton />);
    expect(html).toContain('data-testid="kpi-strip-skeleton"');
  });

  it('uses skeleton-pulse class on inner blocks', () => {
    const html = renderToStaticMarkup(<KpiStripSkeleton />);
    expect(html).toContain('skeleton-pulse');
  });
});

describe('FleetListSkeleton', () => {
  it('renders 3 skeleton train cards', () => {
    const html = renderToStaticMarkup(<FleetListSkeleton />);
    // Count exact class="train-card" (not train-card__header etc.)
    const cardMatches = html.match(/<div class="train-card"/g) ?? [];
    expect(cardMatches.length).toBe(3);
  });

  it('has testid fleet-list-skeleton', () => {
    const html = renderToStaticMarkup(<FleetListSkeleton />);
    expect(html).toContain('data-testid="fleet-list-skeleton"');
  });

  it('uses skeleton-pulse class', () => {
    const html = renderToStaticMarkup(<FleetListSkeleton />);
    expect(html).toContain('skeleton-pulse');
  });
});

describe('UnifiedFeedSkeleton', () => {
  it('renders 4 skeleton feed items', () => {
    const html = renderToStaticMarkup(<UnifiedFeedSkeleton />);
    // Count exact class="feed-item" opening tags
    const itemMatches = html.match(/<div class="feed-item"/g) ?? [];
    expect(itemMatches.length).toBe(4);
  });

  it('has testid unified-feed-skeleton', () => {
    const html = renderToStaticMarkup(<UnifiedFeedSkeleton />);
    expect(html).toContain('data-testid="unified-feed-skeleton"');
  });

  it('uses skeleton-pulse class', () => {
    const html = renderToStaticMarkup(<UnifiedFeedSkeleton />);
    expect(html).toContain('skeleton-pulse');
  });
});
