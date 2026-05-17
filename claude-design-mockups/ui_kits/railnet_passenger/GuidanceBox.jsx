// GuidanceBox — recommendation / warning / info per scenario

const GUIDANCE_STYLE = {
  recommend: {
    bg: "rgba(34,197,94,0.08)",
    border: "rgba(34,197,94,0.35)",
    accent: "#22C55E",
    icon: "arrow-right",
  },
  warn: {
    bg: "rgba(245,166,35,0.10)",
    border: "rgba(245,166,35,0.4)",
    accent: "#C9871F",
    icon: "alert-triangle",
  },
  info: {
    bg: "rgba(74,158,255,0.08)",
    border: "rgba(74,158,255,0.3)",
    accent: "#1F6BC9",
    icon: "info",
  },
};

function GuidanceBox({ guidance }) {
  if (!guidance) return null;
  const s = GUIDANCE_STYLE[guidance.tone];
  // arrow direction
  const arrowIcon = guidance.direction === "left" ? "arrow-left" : "arrow-right";
  const showArrow = guidance.tone === "recommend" || guidance.tone === "info";

  return (
    <div style={{
      background: s.bg,
      border: `1px solid ${s.border}`,
      borderRadius: 10,
      padding: "12px 14px",
      display: "flex",
      gap: 12,
      alignItems: "flex-start",
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: "#fff",
        border: `1px solid ${s.border}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>
        <Icon name={showArrow ? arrowIcon : s.icon} size={20} color={s.accent} stroke={2.5} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{
          fontSize: 15, fontWeight: 700,
          color: "var(--obb-ink)", lineHeight: 1.25,
          letterSpacing: "-.01em",
        }}>{guidance.primary}</div>
        {guidance.sub && (
          <div style={{
            fontSize: 12, color: "var(--obb-graphite)",
            lineHeight: 1.4, marginTop: 3,
          }}>{guidance.sub}</div>
        )}
        {guidance.platformHint && (
          <div style={{
            fontSize: 11, color: s.accent,
            fontWeight: 600, marginTop: 6,
            display: "inline-flex", alignItems: "center", gap: 4,
          }}>
            <Icon name="map-pin" size={11} stroke={2.5} />
            {guidance.platformHint}
          </div>
        )}
      </div>
    </div>
  );
}

window.GuidanceBox = GuidanceBox;
