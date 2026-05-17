// Primitive UI elements — Button, Spinner, Checkbox, Carousel dots, link

function Spinner({ size = 18, color = "#fff", stroke = 2 }) {
  return (
    <div style={{
      width: size, height: size,
      border: `${stroke}px solid ${color === "#fff" ? "rgba(255,255,255,.35)" : "var(--obb-fog)"}`,
      borderTopColor: color,
      borderRadius: "50%",
      animation: "rn-spin 1.2s linear infinite",
      flexShrink: 0,
    }} />
  );
}

function Button({ kind = "primary", busy = false, busyLabel, children, onClick, fullWidth = true, ...rest }) {
  const [pressed, setPressed] = React.useState(false);
  const base = {
    height: 50,
    padding: "0 22px",
    border: 0,
    borderRadius: 8,
    font: "700 14px var(--font-body)",
    letterSpacing: ".08em",
    textTransform: "uppercase",
    cursor: busy ? "default" : "pointer",
    transition: "transform .1s var(--ease-out), background .12s var(--ease-out)",
    transform: pressed ? "scale(.98)" : "scale(1)",
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 10,
    width: fullWidth ? "100%" : "auto",
    userSelect: "none",
  };
  const styles = {
    primary: { ...base, background: pressed ? "var(--obb-red-press)" : "var(--obb-red)", color: "#fff", boxShadow: "var(--shadow-cta)" },
    secondary: { ...base, background: pressed ? "var(--obb-red-tint)" : "#fff", color: "var(--obb-red)", border: "1.5px solid var(--obb-red)", boxShadow: "none" },
    ghost: { ...base, background: "transparent", color: "var(--obb-graphite)", boxShadow: "none", letterSpacing: ".04em" },
  };
  return (
    <button
      style={styles[kind]}
      disabled={busy}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      onMouseLeave={() => setPressed(false)}
      onTouchStart={() => setPressed(true)}
      onTouchEnd={() => setPressed(false)}
      onClick={busy ? undefined : onClick}
      {...rest}
    >
      {busy ? <><Spinner color={kind === "primary" ? "#fff" : "var(--obb-red)"} /> {busyLabel}</> : children}
    </button>
  );
}

function Checkbox({ checked, onChange, children }) {
  return (
    <label style={{
      display: "flex", gap: 12, alignItems: "flex-start",
      font: "400 13px/1.55 var(--font-body)", color: "var(--fg-2)",
      cursor: "pointer", userSelect: "none",
    }}>
      <span style={{
        width: 20, height: 20, borderRadius: 4, flexShrink: 0,
        marginTop: 1,
        border: checked ? "0" : "1.5px solid var(--obb-graphite)",
        background: checked ? "var(--obb-red)" : "#fff",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        transition: "background .12s var(--ease-out), border-color .12s var(--ease-out)",
      }}>
        {checked && (
          <svg viewBox="0 0 16 16" width="13" height="13" fill="none">
            <path d="M3 8.5l3 3 7-7" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} style={{ position: "absolute", opacity: 0, pointerEvents: "none" }} />
      </span>
      <span>{children}</span>
    </label>
  );
}

function Dots({ count, active }) {
  return (
    <div style={{ display: "flex", gap: 8, justifyContent: "center", padding: "16px 0 4px" }}>
      {Array.from({ length: count }).map((_, i) => (
        <span key={i} style={{
          height: 7,
          width: i === active ? 22 : 7,
          borderRadius: i === active ? 4 : "50%",
          background: i === active ? "var(--obb-red)" : "var(--obb-line)",
          transition: "all .24s var(--ease-out)",
        }} />
      ))}
    </div>
  );
}

function Link({ children, ...rest }) {
  return <a {...rest} style={{ color: "var(--obb-red)", textDecoration: "underline", textUnderlineOffset: 2 }}>{children}</a>;
}

Object.assign(window, { Spinner, Button, Checkbox, Dots, Link });
