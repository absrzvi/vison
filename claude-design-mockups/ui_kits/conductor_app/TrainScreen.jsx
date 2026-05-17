// Train tab — vestibule heatmap, occupancy imbalance, camera (depending on scenario)

function TrainScreen({ s, paSent, sendPa, go }) {
  // pick the right view based on scenario shape
  if (s.heatmap) return <HeatmapView s={s} paSent={paSent} sendPa={sendPa} />;
  if (s.imbalance) return <ImbalanceView s={s} paSent={paSent} sendPa={sendPa} />;
  if (s.camera) return <CameraView s={s} paSent={paSent} sendPa={sendPa} go={go} />;
  return <CoachOverview s={s} />;
}

function CoachOverview({ s }) {
  return (
    <>
      <SLabel>Train Overview</SLabel>
      <CoachSection s={s} />
    </>
  );
}

// ─── Heatmap view (Vestibule scenario) ────────────────────────────
function HeatmapView({ s, paSent, sendPa }) {
  const hm = s.heatmap;
  const isResolved = !s.paDraft;
  return (
    <>
      <SLabel>Vestibule Heatmap — Coach {hm.coach}</SLabel>
      <HeatmapCard hm={hm} />
      {s.summary && (
        <>
          <SLabel>Coach {hm.coach} Summary</SLabel>
          <div style={{ background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)", borderRadius: 16, padding: 12 }}>
            <div style={{ background: "var(--obb-surface-3)", borderRadius: 12, padding: "10px 12px", border: "1px solid var(--obb-border-dark)" }}>
              {s.summary.map((r, i) => <DetailRow key={i} {...r} />)}
            </div>
          </div>
        </>
      )}
      {s.paDraft && (
        <>
          <SLabel>Quick Action</SLabel>
          <PAPanel draft={s.paDraft} sent={paSent} onSend={sendPa} />
        </>
      )}
    </>
  );
}

const HEATMAP_DENSITY = {
  hot:     { bg: "rgba(226,0,42,0.40)" },
  "warm-hi": { bg: "rgba(245,166,35,0.30)" },
  "warm-lo": { bg: "rgba(245,166,35,0.12)" },
  cool:    { bg: "rgba(34,197,94,0.10)" },
  empty:   { bg: "rgba(34,197,94,0.04)" },
};
const HEATMAP_TONE = { red: "#FF3B3B", amber: "#F5A623", green: "#22C55E" };

function HeatmapCard({ hm }) {
  const badgeStyle = {
    amber: { bg: "var(--obb-amber-dim)", color: "#F5A623", border: "rgba(245,166,35,0.3)" },
    red:   { bg: "var(--obb-red-dim)",   color: "#FF3B3B", border: "rgba(226,0,42,0.3)" },
    green: { bg: "var(--obb-green-dim)", color: "#22C55E", border: "rgba(34,197,94,0.3)" },
  }[hm.badgeTone];
  return (
    <div style={{
      background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
      borderRadius: 16, padding: 12, marginBottom: 10,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, gap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: "var(--obb-text-on-dark-1)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Coach {hm.coach} · Door zone density</span>
        <span style={{
          fontSize: 9, fontWeight: 700,
          padding: "3px 9px", borderRadius: 20,
          background: badgeStyle.bg, color: badgeStyle.color,
          border: `1px solid ${badgeStyle.border}`,
          whiteSpace: "nowrap", flexShrink: 0,
        }}>{hm.badge}</span>
      </div>
      <div style={{ borderRadius: 10, overflow: "hidden", marginBottom: 8, border: "1px solid var(--obb-border-dark)" }}>
        {hm.rows.map((row, i) => (
          <div key={i} style={{
            display: "flex", height: 28, alignItems: "center",
            background: "var(--obb-surface-1)",
            borderBottom: i < hm.rows.length - 1 ? "1px solid rgba(0,0,0,0.25)" : 0,
          }}>
            <div style={{
              width: 42, fontSize: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em",
              padding: "0 8px",
              color: row.labelTone === "alert" ? "#FF3B3B" : row.labelTone === "ok" ? "#22C55E" : "var(--obb-text-on-dark-4)",
              flexShrink: 0,
            }}>{row.label}</div>
            <div style={{
              flex: 1, height: "100%", display: "flex", alignItems: "center",
              padding: "0 10px", fontSize: 9, fontWeight: 800,
              color: "rgba(255,255,255,0.7)",
              background: HEATMAP_DENSITY[row.density].bg,
            }}>{row.text}</div>
            <div style={{ width: 28, fontSize: 9, fontWeight: 800, textAlign: "center", color: HEATMAP_TONE[row.countTone] }}>{row.count}</div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 10, color: hm.badgeTone === "green" ? "#22C55E" : "var(--obb-text-on-dark-3)", lineHeight: 1.55 }}>
        {hm.note}
      </div>
    </div>
  );
}

// ─── Imbalance view ──────────────────────────────────────────────
function ImbalanceView({ s, paSent, sendPa }) {
  const ib = s.imbalance;
  const total = ib.groups.reduce((a, g) => a + g.pct, 0);
  const colors = { red: "linear-gradient(90deg, #c00020, #E2002A)", amber: "linear-gradient(90deg, #cc8800, #F5A623)", green: "linear-gradient(90deg, #009966, #22C55E)" };
  return (
    <>
      <SLabel>Train Load Distribution</SLabel>
      <div style={{
        background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
        borderRadius: 16, padding: 12, marginBottom: 10,
      }}>
        <div style={{ fontSize: 10, color: "var(--obb-text-on-dark-3)" }}>End-to-end occupancy split</div>
        <div style={{ display: "flex", height: 22, borderRadius: 8, overflow: "hidden", margin: "10px 0 6px", gap: 2 }}>
          {ib.groups.map((g, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 9, fontWeight: 800, color: "rgba(255,255,255,0.9)",
              borderRadius: 6, background: colors[g.tone], flex: g.pct,
            }}>{g.pct}%</div>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "var(--obb-text-on-dark-4)", marginBottom: 8 }}>
          {ib.groups.map((g, i) => <span key={i}>{g.label}</span>)}
        </div>
        <div style={{ background: "var(--obb-surface-3)", borderRadius: 12, padding: "10px 12px", border: "1px solid var(--obb-border-dark)" }}>
          {ib.details.map((d, i) => <DetailRow key={i} {...d} />)}
        </div>
      </div>

      <SLabel>Rebalance Action</SLabel>
      <PAPanel draft={s.paDraft} sent={paSent} onSend={sendPa} />

      {s.pisPreview && (
        <div style={{
          background: "var(--obb-surface-3)", border: "1px solid var(--obb-border-dark)",
          borderRadius: 12, padding: "10px 12px", marginBottom: 10,
        }}>
          <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: ".12em", textTransform: "uppercase", color: "var(--obb-text-on-dark-4)", marginBottom: 8 }}>
            PIS Interior Screen — Coaches 1–4
          </div>
          <div style={{ background: "#000", borderRadius: 8, padding: "10px 12px", display: "flex", alignItems: "center", gap: 12, border: "1px solid #222" }}>
            <div style={{ display: "flex", gap: 2 }}>
              {s.pisPreview.coachStates.map((c, i) => {
                const bg = c === "r" ? "rgba(226,0,42,0.7)" : c === "a" ? "rgba(245,166,35,0.6)" : c === "g" ? "rgba(34,197,94,0.7)" : "#1a1a22";
                return <div key={i} style={{ width: 12, height: 9, borderRadius: 2, background: bg }} />;
              })}
            </div>
            <div>
              <div style={{ fontSize: 10, color: "#fff", fontWeight: 700 }}>{s.pisPreview.headline}</div>
              <div style={{ fontSize: 9, color: "#22C55E", marginTop: 2 }}>{s.pisPreview.subline}</div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Camera view (Unattended bag) ────────────────────────────────
function CameraView({ s, paSent, sendPa, go }) {
  const c = s.camera;
  return (
    <>
      <SLabel>{c.label}</SLabel>
      <div style={{
        background: "var(--obb-surface-2)", border: "1px solid var(--obb-border-dark)",
        borderRadius: 16, padding: 12, marginBottom: 10,
      }}>
        <CameraFrame c={c} />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--obb-text-on-dark-3)", marginBottom: 8 }}>
          <span>{c.meta}</span>
          <span style={{ color: "#F5A623", fontWeight: 700 }}>{c.timer}</span>
        </div>
        <div style={{ fontSize: 10, color: "var(--obb-text-on-dark-3)", lineHeight: 1.55 }}>{c.note}</div>
      </div>

      <SLabel>Actions</SLabel>
      <PAPanel draft={s.paDraft} sent={paSent} onSend={sendPa} onSecondary={() => go("escalate")} />

      {s.escalateNote && (
        <div style={{
          background: "var(--obb-surface-3)", border: "1px solid var(--obb-border-dark)",
          borderRadius: 10, padding: "9px 12px",
          fontSize: 10, color: "var(--obb-text-on-dark-3)", lineHeight: 1.6,
          marginBottom: 10,
        }}>
          <strong style={{ color: "var(--obb-blue-accent)" }}>Escalate</strong> sends this still‑frame, coach location, and 7‑min timer automatically to Claudia at Control Centre — no verbal description needed.
        </div>
      )}
    </>
  );
}

function CameraFrame({ c }) {
  return (
    <div style={{
      background: "#000", borderRadius: 10, height: 130, position: "relative",
      overflow: "hidden", marginBottom: 9, border: "1px solid #1a1a1a",
    }}>
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(170deg, #0e0e14 0%, #111218 50%, #0a0b0f 100%)" }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 40, background: "linear-gradient(180deg, #181818, #121212)", borderTop: "1px solid #252525" }} />
      <div style={{ position: "absolute", top: 0, left: 0, width: 22, height: "100%", background: "linear-gradient(90deg, #141414, #1a1a1a)", borderRight: "1px solid #222" }} />
      <div style={{ position: "absolute", top: 0, right: 0, width: 22, height: "100%", background: "linear-gradient(270deg, #141414, #1a1a1a)", borderLeft: "1px solid #222" }} />
      <div style={{ position: "absolute", bottom: 0, left: "50%", transform: "translateX(-50%)", width: 56, height: 90, border: "1px solid #2a2a2a", borderBottom: "none", borderRadius: "4px 4px 0 0" }} />
      {/* bag */}
      <div style={{
        position: "absolute", bottom: 38, left: "50%", transform: "translateX(-50%)",
        width: 38, height: 26, background: "linear-gradient(160deg, #2e2e3e, #222230)",
        borderRadius: "5px 5px 3px 3px", border: "1px solid #3a3a4a",
        boxShadow: "0 2px 4px rgba(0,0,0,0.5)",
      }}>
        <div style={{ position: "absolute", top: -8, left: "50%", transform: "translateX(-50%)", width: 16, height: 8, background: "#1c1c28", borderRadius: "3px 3px 0 0", border: "1px solid #333", borderBottom: "none" }} />
      </div>
      {/* highlight box */}
      <div style={{
        position: "absolute", bottom: 26, left: "50%", transform: "translateX(-50%)",
        width: 58, height: 46, border: "1.5px solid var(--obb-red)", borderRadius: 6,
        animation: "rn-pulse-strong 1.8s ease-in-out infinite",
        boxShadow: "0 0 8px rgba(226,0,42,0.25)",
      }}>
        {[["tl","-1px","0","-1px","0"],["tr","-1px","-1px","0","0"],["bl","0","0","-1px","-1px"],["br","0","-1px","-1px","0"]].map(([k,t,r,b,l]) => (
          <div key={k} style={{
            position: "absolute", width: 8, height: 8,
            top: k.startsWith("t") ? t : "auto", bottom: k.startsWith("b") ? b : "auto",
            left: k.endsWith("l") ? l : "auto", right: k.endsWith("r") ? r : "auto",
            borderColor: "var(--obb-red)", borderStyle: "solid",
            borderWidth: k === "tl" ? "2px 0 0 2px" : k === "tr" ? "2px 2px 0 0" : k === "bl" ? "0 0 2px 2px" : "0 2px 2px 0",
          }} />
        ))}
      </div>
      <div style={{ position: "absolute", top: 7, left: 9, fontSize: 7, color: "rgba(255,255,255,0.4)", fontFamily: "var(--font-mono)" }}>{c.timestamp}</div>
      <div style={{ position: "absolute", top: 7, right: 9, fontSize: 7, color: "rgba(255,255,255,0.4)", fontFamily: "var(--font-mono)", background: "rgba(0,0,0,0.5)", padding: "2px 5px", borderRadius: 3 }}>{c.coachTag}</div>
      <div style={{ position: "absolute", bottom: 8, right: 9, display: "flex", alignItems: "center", gap: 4, fontSize: 7, color: "rgba(255,255,255,0.45)", fontFamily: "var(--font-mono)" }}>
        <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--obb-red)", animation: "rn-pulse-strong 1.4s ease-in-out infinite" }} /> STILL
      </div>
    </div>
  );
}

// ─── PA panel ────────────────────────────────────────────────────
function PAPanel({ draft, sent, onSend, onSecondary }) {
  if (!draft) return null;
  return (
    <div style={{
      background: "var(--obb-surface-3)", border: "1px solid var(--obb-border-dark)",
      borderRadius: 14, padding: "11px 13px", marginBottom: 10,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 9 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: "var(--obb-red-dim)", boxShadow: "0 0 8px var(--obb-red-glow)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Icon name="volume-2" size={14} color="var(--obb-red)" stroke={2.4} />
        </div>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--obb-text-on-dark-1)", minWidth: 0, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{draft.title}</div>
        <div style={{ fontSize: 10, color: "var(--obb-text-on-dark-4)", whiteSpace: "nowrap", flexShrink: 0 }}>{draft.scope}</div>
      </div>
      <div style={{
        fontSize: 10, color: "var(--obb-text-on-dark-3)", lineHeight: 1.65,
        background: "var(--obb-surface-4)", borderRadius: 8,
        padding: "9px 11px", marginBottom: 9,
        borderLeft: "2px solid var(--obb-red)", fontStyle: "italic",
      }}>"{draft.text}"</div>
      <div style={{ display: "flex", gap: 7 }}>
        {sent ? (
          <Btn kind="secondary" style={{ background: "rgba(34,197,94,0.10)", color: "#22C55E", border: "1px solid rgba(34,197,94,0.3)" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Icon name="check" size={12} stroke={3} /> Sent
            </span>
          </Btn>
        ) : (
          <>
            <Btn kind="primary" onClick={onSend}>{draft.submitLabel || draft.primaryLabel || "Send PA"}</Btn>
            <Btn kind={draft.secondaryKind || "secondary"} onClick={onSecondary}>{draft.secondaryLabel || "Edit first"}</Btn>
          </>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { TrainScreen, CoachOverview, HeatmapView, ImbalanceView, CameraView, PAPanel });
