// PortalConnect — T&C screen with checkbox + primary CTA

function PortalConnect({ copy, onConnect, busy }) {
  const [agreed, setAgreed] = React.useState(false);
  const c = copy.connect;

  const introParts = c.intro.split("{tos}");
  const consentParts = c.consent.split("{privacy}");

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
      <div style={{
        flex: 1, padding: "14px 22px 12px", overflowY: "auto", overflowX: "hidden",
        display: "flex", flexDirection: "column", gap: 12,
      }}>
        <div style={{ display: "flex", justifyContent: "center", paddingTop: 4 }}>
          <WifiBadge />
        </div>

        <h1 style={{ font: "700 22px/1.2 var(--font-display)", color: "var(--fg-1)", margin: 0, letterSpacing: "-.01em", textAlign: "center" }}>{c.title}</h1>

        <p style={{ font: "400 13.5px/1.5 var(--font-body)", color: "var(--fg-2)", margin: 0 }}>
          {introParts[0]}<Link href="#" onClick={e => e.preventDefault()}>{c.tos}</Link>{introParts[1]}
        </p>

        <div style={{ background: "var(--obb-bg)", border: "1px solid var(--border-line)", borderRadius: 10, padding: "12px 14px" }}>
          <Checkbox checked={agreed} onChange={setAgreed}>
            {consentParts[0]}<Link href="#" onClick={e => e.preventDefault()}>{c.privacy}</Link>{consentParts[1]}
          </Checkbox>
        </div>

        <div style={{
          display: "flex", gap: 10, alignItems: "flex-start",
          padding: "10px 12px",
          background: "#FFF7E6",
          border: "1px solid #FAE2B0",
          borderRadius: 8,
          font: "500 12px/1.45 var(--font-body)", color: "#7A5710",
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#C9871F" strokeWidth="2" style={{ flexShrink: 0, marginTop: 1 }}>
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{c.android}</span>
        </div>
      </div>

      <div style={{
        padding: "10px 20px 12px",
        background: "#fff",
        borderTop: "1px solid var(--border-line)",
        flexShrink: 0,
      }}>
        <Button kind="primary"
          onClick={() => agreed && onConnect()}
          busy={busy} busyLabel={c.ctaBusy}>
          {c.cta}
        </Button>
        {!agreed && !busy && (
          <p style={{ font: "500 11px var(--font-body)", color: "var(--fg-4)", textAlign: "center", margin: "6px 0 0", letterSpacing: ".02em" }}>
            {copy.short === "DE" ? "Bitte stimmen Sie zu, um fortzufahren." : "Please agree to continue."}
          </p>
        )}
      </div>
    </div>
  );
}

function WifiBadge() {
  return (
    <div style={{
      width: 64, height: 64, borderRadius: "50%",
      background: "var(--obb-red-tint)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#E2002A" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 12.55a11 11 0 0 1 14.08 0" />
        <path d="M1.42 9a16 16 0 0 1 21.16 0" />
        <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
        <line x1="12" y1="20" x2="12.01" y2="20" />
      </svg>
    </div>
  );
}

Object.assign(window, { PortalConnect });
