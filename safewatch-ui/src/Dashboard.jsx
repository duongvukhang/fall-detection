import { useState, useEffect, useCallback, useRef } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";

// ── Point this at your deployed backend ─────────────────────────────────────
const API    = import.meta.env.VITE_API_URL    || "https://YOUR_BACKEND_DOMAIN";
const WS_URL = import.meta.env.VITE_WS_URL     || "wss://YOUR_BACKEND_DOMAIN";

const PALETTE = {
  bg:      "#f8fafc", // Ultra-light slate background
  surface: "#ffffff", // Crisp white cards
  border:  "#e2e8f0", // Soft, subtle dividers
  text:    "#0f172a", // Deep slate for high-contrast text
  muted:   "#64748b", // Elegant muted slate gray
  accent:  "#e11d48", // Rose-red for critical events
  warn:    "#d97706", // Amber for alerts
  safe:    "#10b981", // Emerald green for active monitoring
  info:    "#2563eb", // Royal blue for interactive links
};
const DONUT_COLORS = ["#e11d48", "#d97706", "#94a3b8"];

const SHADOW = "0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)";
const SHADOW_MD = "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05)";
const SHADOW_LG = "0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -4px rgba(0, 0, 0, 0.05)";

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
      const payload = JSON.parse(atob(data.access_token.split(".")[1]));
      localStorage.setItem("uid", payload.sub);
      onLogin();
    } catch {
      setError("Cannot reach server.");
    }
    setLoading(false);
  }

  const inp = {
    width: "100%", padding: "12px 14px", borderRadius: 8, fontSize: 14,
    background: PALETTE.surface, border: `1px solid ${PALETTE.border}`,
    color: PALETTE.text, outline: "none", boxSizing: "border-box",
    transition: "border-color 0.2s",
  };

  return (
    <div style={{ minHeight:"100vh", background:PALETTE.bg, display:"flex", alignItems:"center", justifyContent:"center", fontFamily:"'Inter',sans-serif" }}>
      <div style={{ background:PALETTE.surface, borderRadius:16, padding:"48px 40px", width:380, boxShadow: SHADOW_LG, border: `1px solid ${PALETTE.border}` }}>
        <div style={{ textAlign:"center", marginBottom:36 }}>
          <div style={{ fontSize:32, marginBottom:12 }}></div>
          <div style={{ fontSize:24, fontWeight:700, color:PALETTE.text, letterSpacing:"-0.03em" }}>The AI Guard</div>
          <div style={{ fontSize:14, color:PALETTE.muted, marginTop:6 }}>Sign in to your dashboard</div>
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
          <input style={inp} type="email" placeholder="Email address" value={email} onChange={e=>setEmail(e.target.value)} />
          <input style={inp} type="password" placeholder="Password" value={password} onChange={e=>setPassword(e.target.value)} onKeyDown={e=>e.key==="Enter"&&handleLogin()} />
          {error && <div style={{ color:PALETTE.accent, fontSize:13, fontWeight: 500 }}>{error}</div>}
          <button onClick={handleLogin} disabled={loading} style={{ background:PALETTE.text, border:"none", borderRadius:8, color:"#fff", padding:"12px", fontSize:14, fontWeight:600, cursor:loading?"default":"pointer", opacity:loading?0.7:1, transition:"opacity 0.2s" }}>
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
    <div style={{ 
      background:PALETTE.surface, 
      border:`1px solid ${flash ? color : PALETTE.border}`, 
      borderRadius:12, padding:"24px", display:"flex", flexDirection:"column", gap:8, 
      flex:1, minWidth:220, boxShadow: SHADOW, transition:"all 0.3s ease" 
    }}>
      <div style={{ display:"flex", justifyContent:"between", alignItems:"center", width:"100%" }}>
        <span style={{ fontSize:13, fontWeight:600, color:PALETTE.muted, letterSpacing:"0.03em", textTransform:"uppercase" }}>{label}</span>
        <span style={{ fontSize:20, marginLeft:"auto" }}>{icon}</span>
      </div>
      <span style={{ fontSize:36, fontWeight:700, color:PALETTE.text, fontVariantNumeric:"tabular-nums", letterSpacing:"-0.02em" }}>{value}</span>
    </div>
  );
}

function Badge({ type }) {
  const isFall = type === "FLOOR_FALL";
  return (
    <span style={{ 
      padding:"4px 10px", borderRadius:6, fontSize:11, fontWeight:700, letterSpacing:"0.04em",
      background: isFall?"rgba(225,29,72,0.08)":"rgba(217,119,6,0.08)", 
      color: isFall?PALETTE.accent:PALETTE.warn 
    }}>
      {isFall ? "FALL" : "BED EXIT"}
    </span>
  );
}

function ImageModal({ url, onClose }) {
  if (!url) return null;
  return (
    <div onClick={onClose} style={{ position:"fixed", inset:0, zIndex:100, background:"rgba(15,23,42,0.3)", backdropFilter:"blur(8px)", display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div onClick={e=>e.stopPropagation()} style={{ background:PALETTE.surface, borderRadius:16, overflow:"hidden", maxWidth:720, width:"90%", boxShadow: SHADOW_LG }}>
        <div style={{ padding:"16px 20px", borderBottom:`1px solid ${PALETTE.border}`, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <span style={{ color:PALETTE.text, fontWeight:600, fontSize:15 }}>Verification Photo</span>
          <button onClick={onClose} style={{ background:"none", border:"none", color:PALETTE.muted, fontSize:24, cursor:"pointer", lineHeight:1 }}>×</button>
        </div>
        <img src={url} alt="Event frame" style={{ width:"100%", display:"block" }} />
      </div>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:8, padding:"10px 14px", fontSize:13, boxShadow: SHADOW_MD }}>
      <div style={{ color:PALETTE.muted, marginBottom:6, fontWeight:500 }}>{label}</div>
      {payload.map(p => <div key={p.name} style={{ color:PALETTE.text, display:"flex", gap:12, justifyContent:"space-between", margin:"2px 0" }}><span>{p.name}:</span> <strong>{p.value}</strong></div>)}
    </div>
  );
}

function LiveDot({ connected }) {
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:6, fontSize:13, fontWeight:500, color: connected ? PALETTE.safe : PALETTE.muted }}>
      <span style={{ width:8, height:8, borderRadius:"50%", background: connected ? PALETTE.safe : PALETTE.muted, display:"inline-block" }} />
      {connected ? "Live Connected" : "Connecting…"}
    </span>
  );
}

function Toast({ event, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 8000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  const isFall = event.event_type === "FLOOR_FALL";
  const borderLeftColor = isFall ? PALETTE.accent : PALETTE.warn;
  
  return (
    <div style={{
      position:"fixed", bottom:24, right:24, zIndex:200,
      background: PALETTE.surface, color: PALETTE.text, borderRadius:12, padding:"20px", minWidth:320,
      boxShadow:"0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)", 
      borderLeft: `4px solid ${borderLeftColor}`, borderTop: `1px solid ${PALETTE.border}`,
      borderRight: `1px solid ${PALETTE.border}`, borderBottom: `1px solid ${PALETTE.border}`,
      animation:"slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
    }}>
      <div style={{ fontWeight:700, fontSize:15, marginBottom:4, display:"flex", alignItems:"center", gap:6 }}>
        {isFall ? "⚠️ Fall Detected" : "🚶 Bed Exit Detected"}
      </div>
      <div style={{ fontSize:13, color: PALETTE.muted }}>Room {event.room_number} · Track #{event.patient_track_id}</div>
      {event.kinematics && <div style={{ fontSize:12, color: PALETTE.muted, marginTop:6, fontStyle: "italic" }}>{event.kinematics}</div>}
      <button onClick={onDismiss} style={{ position:"absolute", top:14, right:14, background:"none", border:"none", color:PALETTE.muted, fontSize:20, cursor:"pointer", opacity:0.7 }}>×</button>
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

  useEffect(() => {
    const token = localStorage.getItem("jwt");
    const uid   = localStorage.getItem("uid");
    if (!token || !uid) return;

    let ws;
    let reconnectTimer;

    function connect() {
      ws = new WebSocket(`${WS_URL}/api/v1/ws/${uid}?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => { setWsConnected(true); };
      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          if (data.type === "PING") return;

          if (data.type === "NEW_EVENT") {
            const ev = data.event;
            setEvents(prev => [ev, ...prev].slice(0, 50));
            setToast(ev);
            setFlashKpi(true);
            setTimeout(() => setFlashKpi(false), 1200);
            setKpi(prev => ({
              ...prev,
              total_falls_24h: ev.event_type === "FLOOR_FALL" ? prev.total_falls_24h + 1 : prev.total_falls_24h,
              active_bed_exit_warnings: ev.event_type === "BED_EXIT" ? prev.active_bed_exit_warnings + 1 : prev.active_bed_exit_warnings,
            }));

            const bucket = new Date(ev.timestamp).toISOString().slice(0, 13) + ":00";
            setHourly(prev => {
              const existing = prev.find(h => h.hour === bucket);
              if (existing) {
                return prev.map(h => h.hour === bucket
                  ? { ...h, falls: h.falls + (ev.event_type === "FLOOR_FALL" ? 1 : 0), exits: h.exits + (ev.event_type === "BED_EXIT" ? 1 : 0) }
                  : h
                );
              }
              return [...prev, { hour: bucket, falls: ev.event_type === "FLOOR_FALL" ? 1 : 0, exits: ev.event_type === "BED_EXIT" ? 1 : 0 }].sort((a, b) => a.hour.localeCompare(b.hour));
            });
          }
        } catch (e) { console.warn("[WS] Parse error", e); }
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimer = setTimeout(connect, 5000);
      };
      ws.onerror = () => ws.close();
    }

    connect();
    return () => { clearTimeout(reconnectTimer); ws?.close(); };
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div style={{ fontFamily:"'Inter',sans-serif", background:PALETTE.bg, minHeight:"100vh", color:PALETTE.text, padding:"40px 48px" }}>
      <style>{`@keyframes slideIn { from { transform: translateY(20px); opacity:0; } to { transform: translateY(0); opacity:1; } }`}</style>

      {/* Header */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:40 }}>
        <div style={{ display:"flex", alignItems:"center", gap:14 }}>
        
          <div>
            <div style={{ fontSize:24, fontWeight:700, letterSpacing:"-0.03em" }}>The AI Guard</div>
            <div style={{ fontSize:13, color:PALETTE.muted, marginTop:2 }}>Edge-to-Cloud Incident Intelligence</div>
          </div>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:20 }}>
          <LiveDot connected={wsConnected} />
          <span style={{ fontSize:13, color:PALETTE.muted }}>Updated: {lastRefresh.toLocaleTimeString()}</span>
          <button onClick={refresh} disabled={loading} style={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, color:PALETTE.text, borderRadius:8, padding:"8px 16px", cursor:loading?"default":"pointer", fontSize:13, fontWeight:600, boxShadow: SHADOW }}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
          <button onClick={onLogout} style={{ background:"transparent", border:"none", color:PALETTE.muted, cursor:"pointer", fontSize:13, fontWeight:500 }}>Sign out</button>
        </div>
      </div>

      {error && <div style={{ background:"#fef2f2", border:`1px solid #fecaca`, borderRadius:8, padding:"12px 16px", marginBottom:24, fontSize:13, color:PALETTE.accent, fontWeight:500 }}>⚠️ {error}</div>}

      {/* KPI Row */}
      <div style={{ display:"flex", gap:24, marginBottom:32, flexWrap:"wrap" }}>
        <KPICard label="Active Protected Beds"    value={kpi.active_protected_beds}   color={PALETTE.safe}   flash={flashKpi} />
        <KPICard label="Total Falls (24h)"        value={kpi.total_falls_24h}          color={PALETTE.accent}  flash={flashKpi} />
        <KPICard label="Active Bed Exits"         value={kpi.active_bed_exit_warnings} color={PALETTE.warn}    flash={flashKpi} />
      </div>

      {/* Charts Row */}
      <div style={{ display:"flex", gap:24, marginBottom:32, flexWrap:"wrap" }}>
        <div style={{ flex:2, minWidth:400, background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:12, padding:"24px", boxShadow: SHADOW }}>
          <div style={{ fontSize:15, fontWeight:700, marginBottom:24, letterSpacing: "-0.01em" }}>Hourly Incident Distribution</div>
          {hourly.length === 0
            ? <div style={{ color:PALETTE.muted, fontSize:13, padding:"74px 0", textAlign:"center" }}>No incidents registered in the last 24 hours</div>
            : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={hourly} margin={{ top:4, right:8, left:-20, bottom:0 }}>
                  <XAxis dataKey="hour" tick={{ fill:PALETTE.muted, fontSize:11 }} tickLine={false} axisLine={false} interval={3} />
                  <YAxis tick={{ fill:PALETTE.muted, fontSize:11 }} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="falls" stroke={PALETTE.accent} strokeWidth={2.5} dot={false} name="Falls" />
                  <Line type="monotone" dataKey="exits" stroke={PALETTE.warn}   strokeWidth={2.5} dot={false} name="Bed Exits" />
                </LineChart>
              </ResponsiveContainer>
            )
          }
          <div style={{ display:"flex", gap:24, marginTop:16, justifyContent:"center" }}>
            {[["Falls", PALETTE.accent], ["Bed Exits", PALETTE.warn]].map(([l, c]) => (
              <div key={l} style={{ display:"flex", alignItems:"center", gap:8, fontSize:12, color:PALETTE.muted, fontWeight:500 }}>
                <span style={{ width:12, height:4, background:c, display:"inline-block", borderRadius:2 }} />{l}
              </div>
            ))}
          </div>
        </div>

        <div style={{ flex:1, minWidth:280, background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:12, padding:"24px", boxShadow: SHADOW }}>
          <div style={{ fontSize:15, fontWeight:700, marginBottom:16, letterSpacing: "-0.01em" }}>Fall Typology</div>
          {typology.length === 0
            ? <div style={{ color:PALETTE.muted, fontSize:13, padding:"74px 0", textAlign:"center" }}>No logs available</div>
            : (
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={typology} dataKey="count" nameKey="label" cx="50%" cy="50%" innerRadius={55} outerRadius={75} paddingAngle={4}>
                    {typology.map((_, idx) => <Cell key={idx} fill={DONUT_COLORS[idx % DONUT_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v,n) => [v,n]} contentStyle={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:8, fontSize:12, boxShadow:SHADOW }} />
                </PieChart>
              </ResponsiveContainer>
            )
          }
          <div style={{ display:"flex", flexDirection:"column", gap:8, marginTop:12 }}>
            {typology.map((t, i) => (
              <div key={t.label} style={{ display:"flex", alignItems:"center", gap:8, fontSize:13 }}>
                <span style={{ width:8, height:8, borderRadius:"50%", background:DONUT_COLORS[i], flexShrink:0 }} />
                <span style={{ color:PALETTE.muted, flex:1, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{t.label}</span>
                <span style={{ color:PALETTE.text, fontWeight:600, ...mono }}>{t.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Audit Trail */}
      <div style={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, borderRadius:12, overflow:"hidden", boxShadow: SHADOW }}>
        <div style={{ padding:"20px 24px", borderBottom:`1px solid ${PALETTE.border}`, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <div style={{ fontSize:15, fontWeight:700, letterSpacing: "-0.01em" }}>Incident Audit Trail</div>
          <span style={{ fontSize:12, fontWeight:500, color:PALETTE.muted, background:PALETTE.bg, padding:"4px 10px", borderRadius:20 }}>{events.length} recent logs</span>
        </div>
        {events.length === 0
          ? <div style={{ color:PALETTE.muted, fontSize:13, padding:"48px", textAlign:"center" }}>No real-time logs currently populated.</div>
          : (
            <div style={{ overflowX:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
                <thead>
                  <tr style={{ borderBottom:`1px solid ${PALETTE.border}`, background: PALETTE.bg }}>
                    {["Time","Room","Track ID","Event","Kinematics","Impact Zone","Head Risk","Photo"].map(h => (
                      <th key={h} style={{ padding:"12px 24px", textAlign:"left", fontWeight:600, color:PALETTE.muted, whiteSpace:"nowrap", fontSize:12, textTransform:"uppercase", letterSpacing:"0.03em" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {events.map((e, idx) => (
                    <tr key={e.id ?? idx} style={{ borderBottom:`1px solid ${PALETTE.border}`, background: "transparent", transition:"background 0.2s" }} onMouseEnter={(e)=>e.currentTarget.style.backgroundColor="#f8fafc"} onMouseLeave={(e)=>e.currentTarget.style.backgroundColor="transparent"}>
                      <td style={{ padding:"14px 24px", ...mono, color:PALETTE.muted, fontSize:12, whiteSpace:"nowrap" }}>{new Date(e.timestamp).toLocaleString()}</td>
                      <td style={{ padding:"14px 24px", fontWeight:600, color:PALETTE.text }}>{e.room_number}</td>
                      <td style={{ padding:"14px 24px", ...mono, color:PALETTE.info, fontWeight:500 }}>#{e.patient_track_id}</td>
                      <td style={{ padding:"14px 24px" }}><Badge type={e.event_type} /></td>
                      <td style={{ padding:"14px 24px", color:PALETTE.muted, maxWidth:220, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{e.kinematics||"—"}</td>
                      <td style={{ padding:"14px 24px", color:PALETTE.muted }}>{e.primary_impact||"—"}</td>
                      <td style={{ padding:"14px 24px", color:PALETTE.muted, fontWeight:500 }}>{e.head_strike_risk||"—"}</td>
                      <td style={{ padding:"14px 24px" }}>
                        {e.image_url
                          ? <button onClick={()=>setModal(e.image_url)} style={{ background:PALETTE.surface, border:`1px solid ${PALETTE.border}`, color:PALETTE.text, borderRadius:6, padding:"4px 12px", cursor:"pointer", fontSize:12, fontWeight:600, boxShadow: SHADOW }}>View</button>
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