// Hero — entertainment promo block sitting above the coach panel.
// Uses the real Filme-und-Serien red SVG from the design system.

function Hero() {
  return (
    <section style={{
      background: "var(--obb-bg)",
      borderTop: "1px solid var(--obb-line)",
      padding: "18px 18px 16px",
      display: "flex", gap: 14, alignItems: "center",
    }}>
      <div style={{
        width: 64, height: 64, borderRadius: 14,
        background: "#fff",
        border: "1px solid var(--obb-line)",
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>
        <img src="../../assets/icons/Filme-und-Serien_red.svg" alt="" style={{ height: 40, width: "auto" }} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontSize: 10, fontWeight: 700, letterSpacing: ".08em",
          color: "var(--obb-red)", textTransform: "uppercase", marginBottom: 4,
        }}>Top Inhalte für Sie</div>
        <h2 style={{
          fontSize: 17, fontWeight: 700,
          color: "var(--obb-ink)", letterSpacing: "-.01em",
          margin: 0, lineHeight: 1.2,
        }}>Filme, Serien &amp; Magazine</h2>
        <div style={{
          fontSize: 11, color: "var(--obb-graphite)",
          lineHeight: 1.45, marginTop: 4,
        }}>Kostenlos im Railnet — auch ohne Internet.</div>
      </div>
    </section>
  );
}

window.Hero = Hero;
