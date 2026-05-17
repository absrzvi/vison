// PortalShell — phone-width white column, header with logo + language picker

function PortalShell({ lang, setLang, copy, children, showHeader = true }) {
  return (
    <div style={{
      width: "100%", height: "100%",
      background: "var(--obb-bg)",
      display: "flex", flexDirection: "column",
    }}>
      {showHeader && (
        <header style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "62px 20px 12px",
          background: "#fff",
          borderBottom: "1px solid var(--border-line)",
        }}>
          <img src="../../assets/logos/OeBB_railnet.png" alt="ÖBB railnet" style={{ height: 22, width: "auto" }} />
          <LanguagePicker lang={lang} setLang={setLang} copy={copy} />
        </header>
      )}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", background: "#fff", minHeight: 0, minWidth: 0, overflow: "hidden" }}>
        {children}
      </main>
      <footer style={{
        padding: "8px 20px 26px",
        background: "#fff",
        borderTop: "1px solid var(--border-line)",
        font: "500 10px var(--font-body)",
        color: "var(--fg-4)",
        textAlign: "center",
        letterSpacing: ".04em",
      }}>
        ÖBB‑Personenverkehr AG · railnet.oebb.at
      </footer>
    </div>
  );
}

Object.assign(window, { PortalShell });
