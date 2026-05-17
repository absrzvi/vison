// App — top-level state, glues all screens together

function App() {
  const [scenario, setScenario] = React.useState("boarding");
  const [tab, setTab] = React.useState("home");
  const [paSent, setPaSent] = React.useState(false);
  const [dismissed, setDismissed] = React.useState(new Set());
  const [escalations, setEscalations] = React.useState([
    {
      category: { label: "Medical emergency", route: "Claudia" },
      coach: "Coach 4", severity: "urgent", status: "ack",
      note: "Claudia acknowledged · Medical team alerted at Salzburg Hbf · ETA 4 min",
      timestamp: "Raised 7m ago", ref: "#4821",
    },
    {
      category: { label: "Door fault — Coach 2", route: "Roland" },
      coach: "Coach 2", severity: "advisory", status: "done",
      note: "Roland: Door sensor reset remotely, safe to continue",
      timestamp: "Resolved 14m ago", ref: "#4818",
    },
  ]);

  const s = window.SCENARIOS[scenario];

  // reset state when scenario changes
  React.useEffect(() => {
    setPaSent(false);
    setDismissed(new Set());
    setTab(scenario === "vestibule" || scenario === "resolved" || scenario === "bag" ? "train" : "home");
  }, [scenario]);

  function sendPa() {
    setPaSent(true);
    // if this is the "vestibule" scenario, advance to the resolved state after a beat
    if (scenario === "vestibule") {
      setTimeout(() => setScenario("resolved"), 1600);
    }
  }

  function dismiss(title) {
    setDismissed(d => { const n = new Set(d); n.add(title); return n; });
  }

  function addEscalation(payload) {
    setEscalations(es => [
      {
        ...payload, status: "new",
        timestamp: "Just now", ref: `#${4820 + es.length + 3}`,
      },
      ...es,
    ]);
  }

  const openCount = escalations.filter(e => e.status !== "done").length;
  const visibleAlerts = s.alerts.filter(a => !dismissed.has(a.title));
  const badges = {
    alerts: visibleAlerts.length > 0 ? { count: visibleAlerts.length, urgent: visibleAlerts.some(a => a.type === "fire") } : null,
    escalate: openCount > 0 ? { count: openCount, urgent: openCount > 1 } : null,
  };

  return (
    <>
      <PhoneFrame s={s} tab={tab} setTab={setTab} badges={badges}>
        {tab === "home"     && <HomeScreen     s={s} go={setTab} paSent={paSent} sendPa={sendPa} dismissed={dismissed} dismiss={dismiss} />}
        {tab === "train"    && <TrainScreen    s={s} paSent={paSent} sendPa={sendPa} go={setTab} />}
        {tab === "alerts"   && <AlertsScreen   s={s} dismissed={dismissed} dismiss={dismiss} />}
        {tab === "escalate" && <EscalateScreen s={s} openCount={openCount} addEscalation={addEscalation} escalations={escalations} />}
        {tab === "chat"     && <ChatScreen />}
      </PhoneFrame>
      <ScenarioControls current={scenario} setCurrent={setScenario} />
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
