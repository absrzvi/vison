// Carousel — horizontal pager with welcome slides

function PortalWelcome({ copy, onConnect }) {
  const [idx, setIdx] = React.useState(0);
  const slides = copy.welcome;
  const next = () => setIdx(i => Math.min(slides.length - 1, i + 1));
  const prev = () => setIdx(i => Math.max(0, i - 1));

  // swipe
  const touch = React.useRef(null);
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <div
        onTouchStart={e => (touch.current = e.touches[0].clientX)}
        onTouchEnd={e => {
          if (touch.current == null) return;
          const dx = e.changedTouches[0].clientX - touch.current;
          if (dx < -40) next();
          if (dx > 40) prev();
          touch.current = null;
        }}
        style={{ flex: 1, overflow: "hidden", position: "relative", minHeight: 0 }}>
        <div style={{
          display: "flex",
          width: `${slides.length * 100}%`,
          height: "100%",
          transform: `translateX(-${idx * (100 / slides.length)}%)`,
          transition: "transform .28s var(--ease-out)",
        }}>
          {slides.map((s, i) => (
            <WelcomeSlide key={i} slide={s} index={i} />
          ))}
        </div>
      </div>

      <Dots count={slides.length} active={idx} />

      <div style={{ padding: "10px 20px 12px" }}>
        <Button kind="primary" onClick={onConnect}>{slides[idx].cta}</Button>
      </div>
    </div>
  );
}

function WelcomeSlide({ slide, index }) {
  // Slide 1 = generic info card; Slide 2 = phone illustration; Slide 3 = content tiles
  return (
    <div style={{
      flexShrink: 0, width: `${100 / 3}%`, height: "100%", // assumes 3 slides
      padding: "20px 22px 8px",
      boxSizing: "border-box",
      display: "flex", flexDirection: "column", gap: 16, alignItems: "center", textAlign: "center", justifyContent: "center",
    }}>
      <SlideArt index={index} />
      <h1 style={{ font: "700 22px/1.2 var(--font-display)", color: "var(--fg-1)", margin: 0, letterSpacing: "-.01em" }}>{slide.title}</h1>
      <p style={{ font: "400 14.5px/1.5 var(--font-body)", color: "var(--fg-2)", margin: 0, maxWidth: 320 }}>{slide.body}</p>
      <a href={`https://${slide.url}`} onClick={e => e.preventDefault()}
         style={{ font: "600 13px var(--font-mono)", color: "var(--obb-red)", textDecoration: "none", marginTop: -4 }}>
        {slide.url}
      </a>
    </div>
  );
}

function SlideArt({ index }) {
  if (index === 0) {
    // Generic on-board portal hero - large red wifi waves over a stylised tablet
    return (
      <div style={{
        width: 200, height: 130, position: "relative",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <svg viewBox="0 0 200 130" width="200" height="130" fill="none">
          {/* tablet */}
          <rect x="40" y="35" width="120" height="78" rx="8" fill="#fff" stroke="#383838" strokeWidth="2.5" />
          <rect x="46" y="41" width="108" height="60" rx="3" fill="#F5F5F5" />
          {/* small ÖBB tab on screen */}
          <rect x="56" y="50" width="42" height="10" rx="2" fill="#E2002A" />
          <rect x="56" y="66" width="86" height="6" rx="2" fill="#9C9E9F" />
          <rect x="56" y="76" width="64" height="6" rx="2" fill="#9C9E9F" />
          <rect x="56" y="86" width="74" height="6" rx="2" fill="#E1E1E2" />
          {/* wifi arcs */}
          <path d="M120 18 a32 32 0 0 1 28 0" stroke="#E2002A" strokeWidth="4" strokeLinecap="round" />
          <path d="M115 28 a22 22 0 0 1 38 0" stroke="#E2002A" strokeWidth="4" strokeLinecap="round" />
          <circle cx="134" cy="36" r="3.5" fill="#E2002A" />
        </svg>
      </div>
    );
  }
  if (index === 1) {
    // phone with browser bar showing the URL
    return (
      <div style={{
        width: 200, height: 130, position: "relative",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <svg viewBox="0 0 200 130" width="200" height="130" fill="none">
          <rect x="62" y="10" width="76" height="115" rx="12" fill="#fff" stroke="#383838" strokeWidth="2.5" />
          <rect x="68" y="22" width="64" height="10" rx="3" fill="#F5F5F5" />
          <circle cx="74" cy="27" r="1.8" fill="#E2002A" />
          <text x="80" y="30" fontFamily="ui-monospace, Menlo, monospace" fontSize="6" fill="#383838">railnet.oebb.at</text>
          <rect x="68" y="38" width="64" height="76" rx="4" fill="#F5F5F5" />
          <rect x="74" y="44" width="32" height="6" rx="1.5" fill="#E2002A" />
          <rect x="74" y="56" width="52" height="4" rx="1" fill="#9C9E9F" />
          <rect x="74" y="64" width="46" height="4" rx="1" fill="#9C9E9F" />
          <rect x="74" y="78" width="52" height="20" rx="3" fill="#E2002A" />
          <text x="100" y="91" textAnchor="middle" fontFamily="Open Sans, sans-serif" fontWeight="700" fontSize="6.5" fill="#fff" letterSpacing="0.6">VERBINDEN</text>
          <rect x="92" y="117" width="16" height="2" rx="1" fill="#383838" />
        </svg>
      </div>
    );
  }
  // Slide 3 — content tiles
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, width: 220,
    }}>
      <ContentTile src="../../assets/icons/Filme-und-Serien_red.svg" label="Filme &amp; Serien" />
      <ContentTile src="../../assets/icons/icons_Services_im_Zug.svg" label="Services im Zug" />
    </div>
  );
}

function ContentTile({ src, label }) {
  return (
    <div style={{
      background: "#fff",
      border: "1px solid var(--border-line)",
      borderRadius: 12,
      padding: "14px 10px",
      display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
      boxShadow: "var(--shadow-card)",
    }}>
      <img src={src} style={{ height: 36, width: "auto" }} alt="" />
      <span style={{ font: "700 12px var(--font-display)", color: "var(--fg-1)" }} dangerouslySetInnerHTML={{ __html: label }} />
    </div>
  );
}

Object.assign(window, { PortalWelcome });
