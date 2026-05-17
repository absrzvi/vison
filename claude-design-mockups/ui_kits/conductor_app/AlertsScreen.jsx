// AlertsScreen — full alert list

function AlertsScreen({ s, dismissed, dismiss }) {
  const visible = s.alerts.filter(a => !dismissed.has(a.title));
  return (
    <>
      <SLabel>Active Alerts · {visible.length}</SLabel>
      <AlertList alerts={visible} dismiss={dismiss} />
      {visible.length > 0 && (
        <button onClick={() => visible.forEach(a => dismiss(a.title))} style={{
          width: "100%", marginTop: 4,
          background: "transparent", border: "1px solid var(--obb-border-bright)",
          borderRadius: 10, padding: "10px",
          color: "var(--obb-text-on-dark-2)", fontSize: 11, fontWeight: 600,
          cursor: "pointer", fontFamily: "inherit",
        }}>Dismiss all dismissable</button>
      )}
    </>
  );
}

Object.assign(window, { AlertsScreen });
