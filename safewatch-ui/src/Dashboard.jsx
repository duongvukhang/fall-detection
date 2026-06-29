import { useState, useEffect, useCallback, useRef } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";

// ── Point this at your deployed backend ─────────────────────────────────────
const API    = import.meta.env.VITE_API_URL    || "https://YOUR_BACKEND_DOMAIN";
const WS_URL = import.meta.env.VITE_WS_URL     || "wss://YOUR_BACKEND_DOMAIN";

const PALETTE = {
  bg:      "#0d1117",
  surface: "#161b22",
  border:  "#30363d",
  text:    "#e6edf3",
  muted:   "#8b949e",
  accent:  "#e94560",
  warn:    "#f5a623",
  safe:    "#3fb950",
  info:    "#58a6ff",
};
const DONUT_COLORS = ["#e94560", "#f5a623", "#8b949e"];

// ─── Login ──────────────────────────────────────────────────────────────────
function LoginScreen({ onLogin }) {
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);

  async function handleLogin() {
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) { setError("Invalid email or password."); setLoading(false); return; }
      const data = await res.json();
      localStorage.setItem("jwt", data.access_token);
      // Decode user_id from JWT payload (base64 middle segment)
      const payload = JSON.parse(atob(data.access_token.split(".")[1]));
      localStorage.setItem("uid", payload.sub);
      onLogin();
    } catch {
      setError("Cannot reach server.");
    }
    setLoading(false);
  }

  const inp = {
    width: "100%", padding: "10px 14px", borderRadius: 8, fontSize: 14,
    background: "#0d1117", border: `1px solid ${PALETTE.border}`,
    color: PALETTE.text, outline: "none", boxSizing: "border-box",
  };

  return (
    <div style={{ minHeight:"100vh", background:PALETTE.bg, display:"flex", alignItems:"center", justifyContent:"center", fontFamily:"'Inter','Helvetica Neue',sans-serif" }}>
      <div style={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:16, padding:"40px 36px", width:360 }}>
        <div style={{ textAlign:"center", marginBottom:32 }}>
          <div style={{ fontSize:36, marginBottom:8 }}>🛡️</div>
          <div style={{ fontSize:22, fontWeight:700, color:PALETTE.text }}>SafeWatch</div>
          <div style={{ fontSize:13, color:PALETTE.muted, marginTop:4 }}>Sign in to your dashboard</div>
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
          <input style={inp} type="email" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} />
          <input style={inp} type="password" placeholder="Password" value={password} onChange={e=>setPassword(e.target.value)} onKeyDown={e=>e.key==="Enter"&&handleLogin()} />
          {error && <div style={{ color:PALETTE.accent, fontSize:13 }}>{error}</div>}
          <button onClick={handleLogin} disabled={loading} style={{ background:PALETTE.info, border:"none", borderRadius:8, color:"#fff", padding:"11px", fontSize:14, fontWeight:600, cursor:loading?"default":"pointer", opacity:loading?0.7:1 }}>
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────
function KPICard({ label, value, color, icon, flash }) {
  return (
    <div style={{ background:PALETTE.surface, border:`1px solid ${flash ? color : PALETTE.border}`, borderRadius:12, padding:"20px 24px", display:"flex", flexDirection:"column", gap:6, flex:1, minWidth:180, transition:"border-color 0.4s" }}>
      <span style={{ fontSize:26, lineHeight:1 }}>{icon}</span>
      <span style={{ fontSize:38, fontWeight:700, color, fontVariantNumeric:"tabular-nums" }}>{value}</span>
      <span style={{ fontSize:13, color:PALETTE.muted, letterSpacing:"0.03em", textTransform:"uppercase" }}>{label}</span>
    </div>
  );
}

function Badge({ type }) {
  const isFall = type === "FLOOR_FALL";
  return (
    <span style={{ padding:"3px 10px", borderRadius:6, fontSize:11, fontWeight:700, background: isFall?"rgba(233,69,96,0.15)":"rgba(245,166,35,0.15)", color: isFall?PALETTE.accent:PALETTE.warn }}>
      {isFall ? "FALL" : "BED EXIT"}
    </span>
  );
}

function ImageModal({ url, onClose }) {
  if (!url) return null;
  return (
    <div onClick={onClose} style={{ position:"fixed", inset:0, zIndex:100, background:"rgba(0,0,0,0.8)", backdropFilter:"blur(4px)", display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div onClick={e=>e.stopPropagation()} style={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:14, overflow:"hidden", maxWidth:720, width:"90%" }}>
        <div style={{ padding:"14px 18px", borderBottom:`1px solid ${PALETTE.border}`, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <span style={{ color:PALETTE.text, fontWeight:600 }}>Verification Photo</span>
          <button onClick={onClose} style={{ background:"none", border:"none", color:PALETTE.muted, fontSize:22, cursor:"pointer" }}>×</button>
        </div>
        <img src={url} alt="Event frame" style={{ width:"100%", display:"block" }} />
      </div>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:8, padding:"8px 14px", fontSize:13 }}>
      <div style={{ color:PALETTE.muted, marginBottom:4 }}>{label}</div>
      {payload.map(p => <div key={p.name} style={{ color:p.color }}>{p.name}: <strong>{p.value}</strong></div>)}
    </div>
  );
}

// ─── Live indicator dot ──────────────────────────────────────────────────────
function LiveDot({ connected }) {
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:6, fontSize:12, color: connected ? PALETTE.safe : PALETTE.muted }}>
      <span style={{ width:8, height:8, borderRadius:"50%", background: connected ? PALETTE.safe : PALETTE.muted, boxShadow: connected ? `0 0 6px ${PALETTE.safe}` : "none", display:"inline-block" }} />
      {connected ? "Live" : "Connecting…"}
    </span>
  );
}

// ─── Alert toast ─────────────────────────────────────────────────────────────
function Toast({ event, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 8000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  const isFall = event.event_type === "FLOOR_FALL";
  return (
    <div style={{
      position:"fixed", bottom:24, right:24, zIndex:200,
      background: isFall ? "rgba(233,69,96,0.95)" : "rgba(245,166,35,0.95)",
      color:"#fff", borderRadius:12, padding:"16px 20px", minWidth:300,
      boxShadow:"0 8px 32px rgba(0,0,0,0.4)", animation:"slideIn 0.3s ease",
    }}>
      <div style={{ fontWeight:700, fontSize:15, marginBottom:4 }}>
        {isFall ? "⚠️ Fall Detected" : "🚶 Bed Exit Detected"}
      </div>
      <div style={{ fontSize:13, opacity:0.9 }}>Room {event.room_number} · Track #{event.patient_track_id}</div>
      {event.kinematics && <div style={{ fontSize:12, opacity:0.8, marginTop:2 }}>{event.kinematics}</div>}
      <button onClick={onDismiss} style={{ position:"absolute", top:10, right:12, background:"none", border:"none", color:"#fff", fontSize:18, cursor:"pointer", opacity:0.7 }}>×</button>
    </div>
  );
}

// ─── Main Dashboard ──────────────────────────────────────────────────────────
function Dashboard({ onLogout }) {
  const [kpi,         setKpi]         = useState({ active_protected_beds:0, total_falls_24h:0, active_bed_exit_warnings:0 });
  const [hourly,      setHourly]      = useState([]);
  const [typology,    setTypology]    = useState([]);
  const [events,      setEvents]      = useState([]);
  const [modal,       setModal]       = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState("");
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [wsConnected, setWsConnected] = useState(false);
  const [toast,       setToast]       = useState(null);
  const [flashKpi,    setFlashKpi]    = useState(false);
  const wsRef = useRef(null);

  const mono = { fontFamily:"'JetBrains Mono','Fira Code',monospace" };

  // ── REST fetch (initial load + manual refresh) ───────────────────────────
  const refresh = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const token   = localStorage.getItem("jwt");
      const headers = { Authorization: `Bearer ${token}` };
      const [kpiRes, aggRes, evtRes] = await Promise.all([
        fetch(`${API}/api/v1/dashboard/kpi`,             { headers }),
        fetch(`${API}/api/v1/dashboard/aggregations`,    { headers }),
        fetch(`${API}/api/v1/dashboard/events?limit=50`, { headers }),
      ]);
      if (kpiRes.status === 401) { onLogout(); return; }
      setKpi(await kpiRes.json());
      const agg = await aggRes.json();
      setHourly(agg.hourly        ?? []);
      setTypology(agg.fall_typology ?? []);
      const evt = await evtRes.json();
      setEvents(evt.events        ?? []);
      setLastRefresh(new Date());
    } catch {
      setError("Could not reach the backend.");
    }
    setLoading(false);
  }, [onLogout]);

  // ── WebSocket (real-time push) ───────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem("jwt");
    const uid   = localStorage.getItem("uid");
    if (!token || !uid) return;

    let ws;
    let reconnectTimer;

    function connect() {
      ws = new WebSocket(`${WS_URL}/api/v1/ws/${uid}?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        console.log("[WS] Connected");
      };

      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          if (data.type === "PING") return;   // keepalive, ignore

          if (data.type === "NEW_EVENT") {
            const ev = data.event;

            // Prepend to audit trail
            setEvents(prev => [ev, ...prev].slice(0, 50));

            // Toast alert
            setToast(ev);

            // Flash KPI cards and bump counters
            setFlashKpi(true);
            setTimeout(() => setFlashKpi(false), 1200);
            setKpi(prev => ({
              ...prev,
              total_falls_24h: ev.event_type === "FLOOR_FALL"
                ? prev.total_falls_24h + 1 : prev.total_falls_24h,
              active_bed_exit_warnings: ev.event_type === "BED_EXIT"
                ? prev.active_bed_exit_warnings + 1 : prev.active_bed_exit_warnings,
            }));

            // Add to hourly chart
            const bucket = new Date(ev.timestamp).toISOString().slice(0, 13) + ":00";
            setHourly(prev => {
              const existing = prev.find(h => h.hour === bucket);
              if (existing) {
                return prev.map(h => h.hour === bucket
                  ? { ...h, falls: h.falls + (ev.event_type === "FLOOR_FALL" ? 1 : 0), exits: h.exits + (ev.event_type === "BED_EXIT" ? 1 : 0) }
                  : h
                );
              }
              return [...prev, { hour: bucket, falls: ev.event_type === "FLOOR_FALL" ? 1 : 0, exits: ev.event_type === "BED_EXIT" ? 1 : 0 }]
                .sort((a, b) => a.hour.localeCompare(b.hour));
            });
          }
        } catch (e) {
          console.warn("[WS] Parse error", e);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        console.log("[WS] Disconnected — reconnecting in 5 s");
        reconnectTimer = setTimeout(connect, 5000);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div style={{ fontFamily:"'Inter','Helvetica Neue',sans-serif", background:PALETTE.bg, minHeight:"100vh", color:PALETTE.text, padding:"24px 28px" }}>
      <style>{`@keyframes slideIn { from { transform: translateX(120%); opacity:0; } to { transform: translateX(0); opacity:1; } }`}</style>

      {/* Header */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:28 }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <span style={{ fontSize:28 }}>🛡️</span>
          <div>
            <div style={{ fontSize:22, fontWeight:700, letterSpacing:"-0.02em" }}>SafeWatch</div>
            <div style={{ fontSize:12, color:PALETTE.muted }}>Edge-to-Cloud Fall Detection</div>
          </div>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:14 }}>
          <LiveDot connected={wsConnected} />
          <span style={{ fontSize:12, color:PALETTE.muted }}>Updated: {lastRefresh.toLocaleTimeString()}</span>
          <button onClick={refresh} disabled={loading} style={{ background:"transparent", border:`1px solid ${PALETTE.border}`, color:loading?PALETTE.muted:PALETTE.info, borderRadius:8, padding:"6px 14px", cursor:loading?"default":"pointer", fontSize:13, fontWeight:500 }}>
            {loading ? "Refreshing…" : "↻ Refresh"}
          </button>
          <button onClick={onLogout} style={{ background:"transparent", border:`1px solid ${PALETTE.border}`, color:PALETTE.muted, borderRadius:8, padding:"6px 14px", cursor:"pointer", fontSize:13 }}>Sign out</button>
        </div>
      </div>

      {error && <div style={{ background:"rgba(233,69,96,0.1)", border:`1px solid ${PALETTE.accent}`, borderRadius:8, padding:"10px 16px", marginBottom:20, fontSize:13, color:PALETTE.accent }}>⚠️ {error}</div>}

      {/* KPI Row */}
      <div style={{ display:"flex", gap:16, marginBottom:24, flexWrap:"wrap" }}>
        <KPICard label="Active Protected Beds"    value={kpi.active_protected_beds}   color={PALETTE.safe}   icon="🛏️" flash={flashKpi} />
        <KPICard label="Total Falls — 24 Hours"   value={kpi.total_falls_24h}          color={PALETTE.accent} icon="⚠️" flash={flashKpi} />
        <KPICard label="Active Bed-Exit Warnings" value={kpi.active_bed_exit_warnings} color={PALETTE.warn}   icon="🚶" flash={flashKpi} />
      </div>

      {/* Charts Row */}
      <div style={{ display:"flex", gap:16, marginBottom:24, flexWrap:"wrap" }}>
        <div style={{ flex:2, minWidth:340, background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:12, padding:"20px 20px 12px" }}>
          <div style={{ fontSize:14, fontWeight:600, marginBottom:16 }}>Hourly Incident Distribution — 24 h</div>
          {hourly.length === 0
            ? <div style={{ color:PALETTE.muted, fontSize:13, padding:"60px 0", textAlign:"center" }}>No incidents in the last 24 hours</div>
            : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={hourly} margin={{ top:4, right:8, left:-20, bottom:0 }}>
                  <XAxis dataKey="hour" tick={{ fill:PALETTE.muted, fontSize:11 }} tickLine={false} axisLine={false} interval={3} />
                  <YAxis tick={{ fill:PALETTE.muted, fontSize:11 }} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="falls" stroke={PALETTE.accent} strokeWidth={2} dot={false} name="Falls" />
                  <Line type="monotone" dataKey="exits" stroke={PALETTE.warn}   strokeWidth={2} dot={false} name="Bed Exits" />
                </LineChart>
              </ResponsiveContainer>
            )
          }
          <div style={{ display:"flex", gap:20, marginTop:8, justifyContent:"center" }}>
            {[["Falls", PALETTE.accent], ["Bed Exits", PALETTE.warn]].map(([l, c]) => (
              <div key={l} style={{ display:"flex", alignItems:"center", gap:6, fontSize:12, color:PALETTE.muted }}>
                <span style={{ width:18, height:3, background:c, display:"inline-block", borderRadius:2 }} />{l}
              </div>
            ))}
          </div>
        </div>

        <div style={{ flex:1, minWidth:260, background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:12, padding:"20px 20px 12px" }}>
          <div style={{ fontSize:14, fontWeight:600, marginBottom:8 }}>Fall Typology — 24 h</div>
          {typology.length === 0
            ? <div style={{ color:PALETTE.muted, fontSize:13, padding:"60px 0", textAlign:"center" }}>No falls recorded</div>
            : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={typology} dataKey="count" nameKey="label" cx="50%" cy="50%" innerRadius={52} outerRadius={80} paddingAngle={3}>
                    {typology.map((_, idx) => <Cell key={idx} fill={DONUT_COLORS[idx % DONUT_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v,n) => [v,n]} contentStyle={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:8, fontSize:12 }} />
                </PieChart>
              </ResponsiveContainer>
            )
          }
          <div style={{ display:"flex", flexDirection:"column", gap:6, marginTop:4 }}>
            {typology.map((t, i) => (
              <div key={t.label} style={{ display:"flex", alignItems:"center", gap:8, fontSize:12 }}>
                <span style={{ width:10, height:10, borderRadius:3, background:DONUT_COLORS[i], flexShrink:0 }} />
                <span style={{ color:PALETTE.muted, flex:1, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{t.label}</span>
                <span style={{ color:PALETTE.text, fontWeight:600, ...mono }}>{t.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Audit Trail */}
      <div style={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:12, overflow:"hidden" }}>
        <div style={{ padding:"16px 20px", borderBottom:`1px solid ${PALETTE.border}`, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <div style={{ fontSize:14, fontWeight:600 }}>Incident Audit Trail</div>
          <span style={{ fontSize:12, color:PALETTE.muted }}>{events.length} recent events</span>
        </div>
        {events.length === 0
          ? <div style={{ color:PALETTE.muted, fontSize:13, padding:"40px", textAlign:"center" }}>No events recorded yet.</div>
          : (
            <div style={{ overflowX:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
                <thead>
                  <tr style={{ borderBottom:`1px solid ${PALETTE.border}` }}>
                    {["Time","Room","Track ID","Event","Kinematics","Impact Zone","Head Risk","Photo"].map(h => (
                      <th key={h} style={{ padding:"10px 16px", textAlign:"left", fontWeight:500, color:PALETTE.muted, whiteSpace:"nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {events.map((e, idx) => (
                    <tr key={e.id ?? idx} style={{ borderBottom:`1px solid ${PALETTE.border}`, background: idx%2===0?"transparent":"rgba(255,255,255,0.015)" }}>
                      <td style={{ padding:"11px 16px", ...mono, color:PALETTE.muted, fontSize:12, whiteSpace:"nowrap" }}>{new Date(e.timestamp).toLocaleString()}</td>
                      <td style={{ padding:"11px 16px", fontWeight:600 }}>{e.room_number}</td>
                      <td style={{ padding:"11px 16px", ...mono, color:PALETTE.info }}>#{e.patient_track_id}</td>
                      <td style={{ padding:"11px 16px" }}><Badge type={e.event_type} /></td>
                      <td style={{ padding:"11px 16px", color:PALETTE.muted, maxWidth:220, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{e.kinematics||"—"}</td>
                      <td style={{ padding:"11px 16px", color:PALETTE.muted }}>{e.primary_impact||"—"}</td>
                      <td style={{ padding:"11px 16px", whiteSpace:"nowrap" }}>{e.head_strike_risk||"—"}</td>
                      <td style={{ padding:"11px 16px" }}>
                        {e.image_url
                          ? <button onClick={()=>setModal(e.image_url)} style={{ background:"rgba(88,166,255,0.1)", border:`1px solid rgba(88,166,255,0.3)`, color:PALETTE.info, borderRadius:6, padding:"4px 12px", cursor:"pointer", fontSize:12, fontWeight:500 }}>View</button>
                          : <span style={{ color:PALETTE.border }}>—</span>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </div>

      <ImageModal url={modal} onClose={()=>setModal(null)} />
      {toast && <Toast event={toast} onDismiss={()=>setToast(null)} />}
    </div>
  );
}

// ─── App root ────────────────────────────────────────────────────────────────
export default function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("jwt"));
  function handleLogout() { localStorage.removeItem("jwt"); localStorage.removeItem("uid"); setLoggedIn(false); }
  return loggedIn
    ? <Dashboard onLogout={handleLogout} />
    : <LoginScreen onLogin={()=>setLoggedIn(true)} />;
}