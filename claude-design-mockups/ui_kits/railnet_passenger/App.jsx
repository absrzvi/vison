// App — top level, glues state controls + portal

function App() {
  const [stateKey, setStateKey] = React.useState("mixed");
  const [lang, setLang] = React.useState("de");
  const state = window.STATES[stateKey];

  // UC-A05 — when the access_free scenario is shown, simulate Conrad confirming the ramp
  // after a few seconds. The portal panel updates live to "Rampe bereit".
  React.useEffect(() => {
    if (stateKey !== "access_free") return;
    const t = setTimeout(() => setStateKey("ramp_ready"), 4500);
    return () => clearTimeout(t);
  }, [stateKey]);

  return (
    <div className="stage">
      <PhoneShell>
        <PassengerPortal state={state} lang={lang} setLang={setLang} />
      </PhoneShell>
      <StateControls current={stateKey} setCurrent={setStateKey} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
