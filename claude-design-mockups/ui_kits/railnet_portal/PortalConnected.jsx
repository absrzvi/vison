// PortalConnected — success state

function PortalConnected({ copy, onOpen, onRestart }) {
  const c = copy.connected;
  return (
    <div style={{
      flex: 1, padding: "28px 22px",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 18,
      textAlign: "center",
      animation: "rn-rise .35s var(--ease-out) both",
    }}>
      <SuccessBadge />
      <h1 style={{ font: "700 26px/1.2 var(--font-display)", color: "var(--fg-1)", margin: 0, letterSpacing: "-.015em" }}>{c.title}</h1>
      <p style={{ font: "400 15px/1.55 var(--font-body)", color: "var(--fg-2)", margin: 0, maxWidth: 320 }}>{c.body}</p>

      <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
        <Button kind="primary" onClick={onOpen}>{c.cta}</Button>
        <Button kind="ghost" onClick={onRestart}>
          {copy.short === "DE" ? "Neu starten" : "Restart demo"}
        </Button>
      </div>
    </div>
  );
}

function SuccessBadge() {
  return (
    <div style={{
      width: 88, height: 88, borderRadius: "50%",
      background: "#E4F4EB",
      display: "flex", alignItems: "center", justifyContent: "center",
      boxShadow: "0 4px 16px rgba(31,138,76,.18)",
      animation: "rn-pop .4s var(--ease-out) both",
    }}>
      <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="#1F8A4C" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 6 9 17l-5-5" />
      </svg>
    </div>
  );
}

Object.assign(window, { PortalConnected });
