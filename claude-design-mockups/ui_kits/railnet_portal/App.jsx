// App — top-level state machine

function App() {
  const [lang, setLang] = React.useState("de");
  const [stage, setStage] = React.useState("welcome"); // welcome | connect | connecting | connected
  const [busy, setBusy] = React.useState(false);
  const copy = window.RAILNET_COPY[lang];

  const handleConnect = () => {
    setBusy(true);
    setTimeout(() => {
      setBusy(false);
      setStage("connected");
    }, 1600);
  };

  return (
    <IOSDevice width={390} height={780}>
      <PortalShell lang={lang} setLang={setLang} copy={window.RAILNET_COPY}>
        {stage === "welcome" && (
          <PortalWelcome copy={copy} onConnect={() => setStage("connect")} />
        )}
        {(stage === "connect" || stage === "connecting") && (
          <PortalConnect copy={copy} onConnect={handleConnect} busy={busy} />
        )}
        {stage === "connected" && (
          <PortalConnected
            copy={copy}
            onOpen={() => { setStage("welcome"); }}
            onRestart={() => { setStage("welcome"); }}
          />
        )}
      </PortalShell>
    </IOSDevice>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
