// CoachGuidancePanel — wraps the whole "Zugauslastung" card

function CoachGuidancePanel({ s, midJourneyCoach }) {
  return (
    <section style={{
      background: "#fff",
      borderTop: "3px solid var(--obb-red)",
      padding: "16px 18px 18px",
      display: "flex", flexDirection: "column", gap: 12,
    }}>
      {/* header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{
          fontSize: 11, fontWeight: 800, letterSpacing: ".10em",
          color: "var(--obb-graphite)", textTransform: "uppercase",
          margin: 0,
          display: "flex", alignItems: "center", gap: 8,
        }}>
          Zugauslastung
          <span style={{ fontWeight: 500, color: "var(--obb-silver)", letterSpacing: ".04em" }}>· Wagen 1–8</span>
        </h2>
        <FreshnessPill text={s.freshness} stale={s.stale} noData={s.noData} />
      </div>

      {/* body */}
      {s.noData ? <NoDataMessage /> : (
        <>
          <CoachDiagram coaches={s.coaches} dimmed={s.stale} />
          <TrainOrientation />

          {/* Threshold legend — quiet, but useful */}
          <Legend />

          {!s.stale && <GuidanceBox guidance={s.guidance} />}
          {!s.stale && <AccessibilityPanel access={s.access} />}

          {s.stale && <StaleNote />}
        </>
      )}
    </section>
  );
}

// ─── No-data fallback ────────────────────────────────────────────
function NoDataMessage() {
  return (
    <div style={{
      background: "var(--obb-bg)",
      borderRadius: 10,
      padding: "18px 14px",
      display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
      textAlign: "center",
    }}>
      <Icon name="wifi-off" size={26} color="var(--obb-silver)" stroke={2} />
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--obb-body)" }}>
        Auslastungsdaten nicht verfügbar
      </div>
      <div style={{ fontSize: 11, color: "var(--obb-silver)", lineHeight: 1.45 }}>
        Bitte folgen Sie der Beschilderung am Bahnsteig oder fragen Sie das Zugpersonal.
      </div>
    </div>
  );
}

// ─── Stale note ──────────────────────────────────────────────────
function StaleNote() {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "8px 12px",
      background: "rgba(245,166,35,0.07)",
      border: "1px solid rgba(245,166,35,0.30)",
      borderRadius: 8,
      fontSize: 11, color: "#C9871F", fontWeight: 600,
    }}>
      <span style={{
        width: 12, height: 12,
        border: "1.5px solid #F5A623",
        borderTopColor: "transparent",
        borderRadius: "50%",
        animation: "rn-spin 1s linear infinite",
      }} />
      Wird aktualisiert …
    </div>
  );
}

// ─── Legend ──────────────────────────────────────────────────────
function Legend() {
  const items = [
    { color: "#22C55E", label: "Viel Platz" },
    { color: "#F5A623", label: "Mäßig" },
    { color: "#FF6B00", label: "Stark besetzt" },
  ];
  return (
    <div style={{
      display: "flex", gap: 12, alignItems: "center",
      fontSize: 10, color: "var(--obb-silver)",
      padding: "2px 0 0",
    }}>
      {items.map(it => (
        <span key={it.label} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 9, height: 9, borderRadius: 2, background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

Object.assign(window, { CoachGuidancePanel, NoDataMessage });
