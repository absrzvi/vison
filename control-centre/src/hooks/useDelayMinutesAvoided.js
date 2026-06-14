import { useEffect, useState } from 'react';
import { getDelayMinutesAvoided } from '../api/kpi';

// E10-S4: fleet-wide delay-minutes avoided (trailing 24h). A slow-changing daily
// metric, so it is fetched once on mount and refreshed on an interval — NOT carried
// on the live SSE kpis object (that is per-tick operational state). Returns null
// until the first successful fetch (and on error) so the tile can render its
// unavailable state.
const REFRESH_MS = 5 * 60 * 1000; // 5 min — daily metric, no need to poll fast

export function useDelayMinutesAvoided() {
  const [minutes, setMinutes] = useState(null);

  useEffect(() => {
    let active = true;
    let inFlight = null; // the current request's controller; aborted before each refresh

    async function load() {
      // Abort any still-in-flight refresh so a slow earlier request can't resolve
      // after (and overwrite) a newer one with a stale value.
      inFlight?.abort();
      const controller = new AbortController();
      inFlight = controller;
      try {
        const data = await getDelayMinutesAvoided(controller.signal);
        if (active && !controller.signal.aborted) setMinutes(data.delay_minutes_avoided);
      } catch (err) {
        if (err.name !== 'AbortError' && active) setMinutes(null);
      }
    }

    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      active = false;
      inFlight?.abort();
      clearInterval(id);
    };
  }, []);

  return minutes;
}
