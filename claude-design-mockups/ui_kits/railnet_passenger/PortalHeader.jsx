// PortalHeader — ÖBB logo + language picker, sticky at top of captive page

function PortalHeader({ lang, setLang }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const onDoc = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <header style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "44px 18px 12px",
      background: "#fff",
      borderBottom: "1px solid var(--obb-line)",
    }}>
      <img src="../../assets/logos/OeBB_railnet.png" alt="ÖBB Railnet" style={{ height: 22, width: "auto" }} />

      <div ref={ref} style={{ position: "relative" }}>
        <button
          onClick={() => setOpen(o => !o)}
          style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            background: "var(--obb-bg)",
            border: "1px solid var(--obb-line)",
            borderRadius: 999,
            padding: "5px 10px",
            font: "700 11px var(--font-body)",
            color: "var(--obb-body)",
            letterSpacing: ".04em",
            cursor: "pointer",
            fontFamily: "inherit",
          }}>
          <Icon name="globe" size={12} stroke={2.2} />
          {lang.toUpperCase()}
          <Icon name="chevron-down" size={10} stroke={2.4}
                style={{ transition: "transform .2s", transform: open ? "rotate(180deg)" : "none" }} />
        </button>
        {open && <LangDropdown current={lang} setLang={(k) => { setLang(k); setOpen(false); }} />}
      </div>
    </header>
  );
}

function LangDropdown({ current, setLang }) {
  const langs = [
    { k: "de", label: "Deutsch",   available: true  },
    { k: "en", label: "English",   available: false },
    { k: "it", label: "Italiano",  available: false },
    { k: "fr", label: "Français",  available: false },
  ];
  return (
    <div style={{
      position: "absolute", top: 34, right: 0,
      minWidth: 160,
      background: "#fff",
      border: "1px solid var(--obb-line)",
      borderRadius: 10,
      boxShadow: "var(--shadow-pop)",
      overflow: "hidden",
      zIndex: 20,
    }}>
      {langs.map(l => (
        <button key={l.k} disabled={!l.available}
                onClick={() => l.available && setLang(l.k)}
                style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  width: "100%", padding: "10px 12px",
                  background: current === l.k ? "var(--obb-red-tint)" : "#fff",
                  color: l.available ? (current === l.k ? "var(--obb-red-dark)" : "var(--obb-ink)") : "var(--obb-mute)",
                  border: 0, fontFamily: "inherit",
                  font: "600 12px var(--font-body)",
                  textAlign: "left",
                  cursor: l.available ? "pointer" : "not-allowed",
                }}>
          <span>{l.label}</span>
          <span style={{ font: "700 10px var(--font-body)", color: "var(--obb-silver)", letterSpacing: ".06em" }}>
            {l.available ? l.k.toUpperCase() : "—"}
          </span>
        </button>
      ))}
    </div>
  );
}

window.PortalHeader = PortalHeader;
