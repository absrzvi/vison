// Bottom navigation — 5 tabs

const NAV_TABS = [
  { key: "home",     label: "Home",     icon: "home" },
  { key: "train",    label: "Train",    icon: "train-front" },
  { key: "alerts",   label: "Alerts",   icon: "bell" },
  { key: "escalate", label: "Escalate", icon: "zap" },
  { key: "chat",     label: "Chat",     icon: "message-circle" },
];

function BottomNav({ tab, setTab, badges }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-around",
      background: "var(--obb-surface-2)",
      border: "1px solid var(--obb-border-bright)",
      borderRadius: 20,
      padding: "9px 4px 7px",
      marginTop: 10,
      boxShadow: "0 -1px 0 rgba(255,255,255,0.04)",
    }}>
      {NAV_TABS.map(t => {
        const active = tab === t.key;
        const badge = badges && badges[t.key];
        return (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              display: "flex", flexDirection: "column", alignItems: "center", gap: 3,
              fontSize: 8, fontWeight: 600,
              color: active ? "var(--obb-red)" : "var(--obb-text-on-dark-4)",
              background: active ? "var(--obb-red-dim)" : "transparent",
              cursor: "pointer", padding: "5px 10px",
              borderRadius: 12, border: 0,
              transition: "all .15s var(--ease-out)",
              position: "relative",
              fontFamily: "inherit",
            }}>
            <span style={{ position: "relative", display: "inline-block" }}>
              <Icon name={t.icon} size={18} stroke={2.2} />
              {badge && (
                <span style={{
                  position: "absolute", top: -4, right: -8,
                  background: badge.urgent ? "#FF3B3B" : "var(--obb-red)",
                  color: "#fff",
                  fontSize: 7, fontWeight: 800,
                  borderRadius: 7, padding: "1px 4px",
                  minWidth: 14, textAlign: "center",
                  boxShadow: badge.urgent ? "none" : "0 0 6px rgba(226,0,42,0.5)",
                }}>{badge.count}</span>
              )}
            </span>
            <span>{t.label}</span>
          </button>
        );
      })}
    </div>
  );
}

Object.assign(window, { BottomNav });
