// LanguagePicker — pill chip + dropdown flyout

function LanguagePicker({ lang, setLang, copy }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  const items = ["de", "en", "it", "fr", "hu", "cs", "sk"];
  const current = copy[lang];
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          height: 32, padding: "0 12px",
          background: "#fff",
          border: "1px solid var(--border-line)",
          borderRadius: 999,
          font: "700 12px var(--font-body)", letterSpacing: ".06em",
          color: "var(--fg-2)", cursor: "pointer",
        }}>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" /><path d="M2 12h20" /><path d="M12 2a15 15 0 0 1 4 10 15 15 0 0 1-4 10 15 15 0 0 1-4-10 15 15 0 0 1 4-10z" />
        </svg>
        {current.short}
        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ transition: "transform .2s", transform: open ? "rotate(180deg)" : "none" }}><path d="M6 9l6 6 6-6" /></svg>
      </button>
      {open && (
        <div style={{
          position: "absolute", top: 38, right: 0, minWidth: 160,
          background: "#fff", borderRadius: 12,
          border: "1px solid var(--border-line)",
          boxShadow: "var(--shadow-pop)",
          overflow: "hidden",
          zIndex: 20,
        }}>
          {items.map(k => {
            const c = copy[k];
            const disabled = c._todo;
            return (
              <button
                key={k}
                disabled={disabled}
                onClick={() => { if (!disabled) { setLang(k); setOpen(false); } }}
                style={{
                  width: "100%",
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "12px 14px",
                  background: lang === k ? "var(--obb-red-tint)" : "#fff",
                  color: disabled ? "var(--fg-mute)" : (lang === k ? "var(--obb-red-dark)" : "var(--fg-1)"),
                  font: "600 13px var(--font-body)",
                  border: 0, textAlign: "left", cursor: disabled ? "not-allowed" : "pointer",
                }}>
                <span>{c.locale}</span>
                <span style={{ font: "700 11px var(--font-body)", letterSpacing: ".06em", color: "var(--fg-4)" }}>{c.short}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
Object.assign(window, { LanguagePicker });
