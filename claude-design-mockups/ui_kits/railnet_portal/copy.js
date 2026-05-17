// Copy table — verbatim from WIFI PAGE Railnet - CNA portal v1.1.xlsx
// Five other language slots are reserved in the spec (Language 3 / 5 / 6 / 7 / 8);
// only DE + EN are filled out here.

window.RAILNET_COPY = {
  de: {
    locale: "Deutsch",
    short: "DE",
    welcome: [
      {
        title: "Kennen Sie das Railnet?",
        body:  "Das Onboard Portal im Railjet mit Infos zur Fahrt, Services und Entertainment.",
        url:   "railnet.oebb.at",
        cta:   "WLAN verbinden",
      },
      {
        title: "Wie erreicht man das Railnet?",
        body:  'Nach dem Klick auf "Verbinden" geben Sie bei Android Nutzung railnet.oebb.at in Ihren Browser ein.',
        url:   "railnet.oebb.at",
        cta:   "WLAN verbinden",
      },
      {
        title: "Top Inhalte für Sie",
        body:  "Es stehen Ihnen Filme und Serien, wie zum Beispiel Bösterreich, Zeitungen und Magazine, die Reisevorschau und vieles mehr kostenlos zur Verfügung.",
        url:   "railnet.oebb.at",
        cta:   "WLAN verbinden",
      },
    ],
    connect: {
      title:  "Gratis WLAN am Zug",
      intro:  "Durch das Verbinden mit dem kostenlosen ÖBB WLAN erklären Sie sich mit den {tos} einverstanden.",
      tos:    "Nutzungsbedingungen",
      consent:"Ich willige ein, dass die ÖBB‑Personenverkehr AG die MAC‑Adresse sowie das Betriebssystem meines Endgerätes während der Sitzung, den Zeitstempel von Verbindungsaufnahme‑ und ‑ende, die von mir ausgewählte Sprache und das verbrauchte Datenvolumen verarbeitet. Diese Daten werden bis zu 7 Tagen gespeichert. Weitere Informationen finden Sie in der {privacy}.",
      privacy:"Datenschutzinformation",
      android:"Um zum Onboard Portal zu gelangen, geben Sie bei der Nutzung mit Android Geräten bitte railnet.oebb.at in Ihren Browser ein.",
      cta:    "VERBINDEN",
      ctaBusy:"Verbinde …",
    },
    connected: {
      title: "Verbindung erfolgreich!",
      body:  "Alles rund um Ihre Fahrt, Infos zum Zug und Infotainment finden Sie im ÖBB Railnet. Viel Spaß beim Surfen!",
      cta:   "RAILNET ÖFFNEN",
    },
  },
  en: {
    locale: "English",
    short: "EN",
    welcome: [
      {
        title: "Do you know Railnet?",
        body:  "The onboard portal on railjets with infos about the journey, services and entertainment.",
        url:   "railnet.oebb.at",
        cta:   "WiFi Connect",
      },
      {
        title: "How to get to Railnet?",
        body:  'After clicking "Connect", Android users please insert railnet.oebb.at into your browser.',
        url:   "railnet.oebb.at",
        cta:   "WiFi Connect",
      },
      {
        title: "Top content for you",
        body:  "Movies and series — for example Bösterreich — newspapers and magazines, the travel preview and much more are available free of charge.",
        url:   "railnet.oebb.at",
        cta:   "WiFi Connect",
      },
    ],
    connect: {
      title:  "Free WLAN on the train",
      intro:  "By connecting to our free WiFi, you agree to the {tos}.",
      tos:    "terms of use",
      consent:"I consent to ÖBB‑Personenverkehr AG processing the MAC address and operating system of my device during the session, the timestamps of the start and end of the connection, the language I have selected and the data volume used. Data is retained for up to 7 days. Further information can be found in the {privacy}.",
      privacy:"data protection notice",
      android:"To reach the onboard portal, Android users please insert railnet.oebb.at into your browser.",
      cta:    "CONNECT",
      ctaBusy:"Connecting …",
    },
    connected: {
      title: "Connection succeeded!",
      body:  "Everything you need to know about your journey, services onboard and infotainment can be found in our onboard portal Railnet. Have fun surfing the web!",
      cta:   "OPEN RAILNET",
    },
  },
  // Reserved slots from the spec, copy not provided
  it: { locale: "Italiano",  short: "IT", _todo: true },
  fr: { locale: "Français",  short: "FR", _todo: true },
  hu: { locale: "Magyar",    short: "HU", _todo: true },
  cs: { locale: "Čeština",   short: "CS", _todo: true },
  sk: { locale: "Slovenčina",short: "SK", _todo: true },
};
