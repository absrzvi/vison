// PassengerPortal — the full captive page

function PassengerPortal({ state, lang, setLang, onConnect }) {
  return (
    <>
      <PortalHeader lang={lang} setLang={setLang} />
      <Hero />
      <CoachGuidancePanel s={state} />
      <TermsBlock onConnect={onConnect} />
    </>
  );
}

window.PassengerPortal = PassengerPortal;
