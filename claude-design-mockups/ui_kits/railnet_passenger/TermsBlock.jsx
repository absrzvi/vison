// TermsBlock — T&C agreement + VERBINDEN connect button

function TermsBlock({ onConnect }) {
  const [agreed, setAgreed] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [done, setDone] = React.useState(false);

  function handleConnect() {
    if (!agreed || busy) return;
    setBusy(true);
    setTimeout(() => { setBusy(false); setDone(true); onConnect && onConnect(); }, 1400);
  }

  return (
    <section style={{
      background: "var(--obb-bg)",
      padding: "16px 18px 22px",
      borderTop: "1px solid var(--obb-line)",
      display: "flex", flexDirection: "column", gap: 12,
    }}>
      <h3 style={{
        margin: 0,
        font: "700 16px/1.25 var(--font-display)",
        color: "var(--obb-ink)",
        letterSpacing: "-.01em",
      }}>Gratis WLAN am Zug</h3>
      <p style={{
        margin: 0, font: "400 12.5px/1.55 var(--font-body)",
        color: "var(--obb-graphite)",
      }}>
        Durch das Verbinden stimmen Sie den{" "}
        <a href="#" onClick={e => e.preventDefault()} style={{ color: "var(--obb-red)", textDecoration: "underline", textUnderlineOffset: 2 }}>Nutzungsbedingungen</a>
        {" "}und der{" "}
        <a href="#" onClick={e => e.preventDefault()} style={{ color: "var(--obb-red)", textDecoration: "underline", textUnderlineOffset: 2 }}>Datenschutzinformation</a>
        {" "}zu. Mit Android-Geräten bitte railnet.oebb.at im Browser öffnen.
      </p>

      <label style={{
        display: "flex", gap: 10, alignItems: "flex-start",
        font: "400 12px/1.5 var(--font-body)",
        color: "var(--obb-body)",
        cursor: "pointer", userSelect: "none",
      }}>
        <span style={{
          width: 18, height: 18, borderRadius: 4, flexShrink: 0, marginTop: 1,
          border: agreed ? "0" : "1.5px solid var(--obb-graphite)",
          background: agreed ? "var(--obb-red)" : "#fff",
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          transition: "background .12s var(--ease-out)",
        }}>
          {agreed && <Icon name="check" size={11} color="#fff" stroke={3} />}
        </span>
        <span>Ich stimme der Verarbeitung meiner MAC-Adresse und Sitzungsdaten gemäß DSGVO zu.</span>
        <input type="checkbox" checked={agreed} onChange={e => setAgreed(e.target.checked)} style={{ position: "absolute", opacity: 0, pointerEvents: "none" }} />
      </label>

      <button
        onClick={handleConnect}
        disabled={!agreed || busy || done}
        style={{
          width: "100%", height: 50, border: 0, borderRadius: 8,
          background: done ? "#1F8A4C" : "var(--obb-red)",
          color: "#fff",
          font: "700 14px var(--font-body)",
          letterSpacing: ".08em",
          textTransform: "uppercase",
          cursor: (agreed && !busy && !done) ? "pointer" : "not-allowed",
          opacity: !agreed ? 0.4 : 1,
          boxShadow: agreed && !done ? "var(--shadow-cta)" : "none",
          transition: "all .12s var(--ease-out)",
          fontFamily: "inherit",
          display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 10,
        }}>
        {done ? (
          <><Icon name="check" size={16} stroke={3} /> Verbunden</>
        ) : busy ? (
          <><span style={{ width: 16, height: 16, border: "2px solid rgba(255,255,255,.35)", borderTopColor: "#fff", borderRadius: "50%", animation: "rn-spin 1s linear infinite" }} /> Verbinde …</>
        ) : (
          "Verbinden"
        )}
      </button>
    </section>
  );
}

window.TermsBlock = TermsBlock;
