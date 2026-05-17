// ChatScreen — Diagnostics agent

const CANNED_REPLIES = {
  "hvac": "Recirculation fan fault (0x3A12) — triggered 11 min ago. Pattern seen twice in 14 days. Likely bearing wear. Not safety‑critical now; flag for maintenance at Salzburg.",
  "door": "Door 2 in coach 4 — closure sensor reset successfully. No recent fault history. Safe to continue.",
  "rack": "Coach 3 luggage rack at 94% capacity. Surge predicted at Linz (8 min). Consider PA to redirect new boarders to coach 7+.",
  "smoke":"Coach 5 smoke detector tripped 22 sec ago. Suppression armed. Driver and Control notified. Evacuation protocol available.",
  "default": "I can pull fault history, predict next failures, and translate Stadler alarm codes. Try asking about HVAC, doors, racks, or a specific coach number.",
};

function ChatScreen() {
  const [msgs, setMsgs] = React.useState([
    { role: "user", text: "What's wrong with the HVAC in coach 3?" },
    { role: "ai",   text: CANNED_REPLIES.hvac },
  ]);
  const [draft, setDraft] = React.useState("");
  const scrollerRef = React.useRef(null);

  React.useEffect(() => {
    if (scrollerRef.current) scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
  }, [msgs]);

  function send() {
    if (!draft.trim()) return;
    const q = draft.trim();
    setMsgs(m => [...m, { role: "user", text: q }]);
    setDraft("");
    setTimeout(() => {
      const k = q.toLowerCase();
      const key = /hvac|temperature|cool|heat|air/.test(k) ? "hvac"
        : /door/.test(k) ? "door"
        : /rack|luggage|bag/.test(k) ? "rack"
        : /smoke|fire/.test(k) ? "smoke"
        : "default";
      setMsgs(m => [...m, { role: "ai", text: CANNED_REPLIES[key] }]);
    }, 700);
  }

  return (
    <>
      <SLabel>Diagnostics Agent</SLabel>
      <div style={{
        background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
        borderRadius: 16, padding: 12, marginBottom: 10,
        display: "flex", flexDirection: "column", minHeight: 0,
      }}>
        <div ref={scrollerRef} style={{
          display: "flex", flexDirection: "column", gap: 8,
          marginBottom: 10, maxHeight: 280, overflowY: "auto",
          paddingRight: 2,
        }}>
          {msgs.map((m, i) => m.role === "user" ? (
            <div key={i} style={{
              background: "var(--obb-surface-4)", borderRadius: "11px 11px 2px 11px",
              padding: "9px 12px", fontSize: 11, color: "var(--obb-text-on-dark-2)",
              marginLeft: 24,
            }}>{m.text}</div>
          ) : (
            <div key={i} style={{
              background: "linear-gradient(135deg, rgba(7,61,110,0.4), rgba(10,82,152,0.25))",
              border: "1px solid rgba(10,82,152,0.3)",
              borderRadius: "2px 11px 11px 11px",
              padding: "9px 12px", fontSize: 11, color: "var(--obb-text-on-dark-1)",
              lineHeight: 1.6, marginRight: 24,
            }}>
              <div style={{ fontSize: 8, fontWeight: 800, letterSpacing: ".1em", color: "var(--obb-blue-accent)", marginBottom: 5, textTransform: "uppercase" }}>Diagnostics AI</div>
              {m.text}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 7 }}>
          <input
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => e.key === "Enter" && send()}
            placeholder="Ask about any fault…"
            style={{
              flex: 1, background: "var(--obb-surface-3)",
              border: "1px solid var(--obb-border-bright)", borderRadius: 22,
              padding: "8px 14px", color: "var(--obb-text-on-dark-1)",
              fontSize: 11, outline: "none", fontFamily: "inherit",
            }}
          />
          <button onClick={send} style={{
            background: "linear-gradient(135deg, var(--obb-blue-mid), var(--obb-blue))",
            border: 0, borderRadius: 22, padding: "8px 16px",
            color: "#fff", fontSize: 11, fontWeight: 700,
            cursor: "pointer", boxShadow: "0 2px 8px rgba(7,61,110,0.4)",
            fontFamily: "inherit",
          }}>Send</button>
        </div>
      </div>
      <div style={{ fontSize: 10, color: "var(--obb-text-on-dark-4)", textAlign: "center", lineHeight: 1.55 }}>
        Try: "HVAC coach 3", "Door fault", "Rack capacity"
      </div>
    </>
  );
}

Object.assign(window, { ChatScreen });
