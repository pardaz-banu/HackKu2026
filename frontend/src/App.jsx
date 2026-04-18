import { useState, useRef, useEffect } from "react";
import "./App.css";

const API = "http://localhost:8000";
const DEFAULT_SESSION = "kelli-" + Math.random().toString(36).slice(2, 8);

const STAGES = [
  { id: "planning",  label: "📋 Planning",   color: "#3B82F6", desc: "Before trip" },
  { id: "approval",  label: "✅ Approvals",  color: "#8B5CF6", desc: "Get approved" },
  { id: "traveling", label: "✈️ Traveling",  color: "#10B981", desc: "On the road" },
  { id: "issue",     label: "⚠️ Issue",       color: "#F59E0B", desc: "Need help" },
  { id: "post_trip", label: "🏁 Post-Trip",  color: "#6366F1", desc: "Close the loop" },
];

const STAGE_PROMPTS = {
  planning: [
    "What do I need for a trip to Tokyo next month?",
    "What flights go from New York to Dubai in May?",
    "What visa do I need for India?",
    "What's the weather like in London in April?",
    "What are the best business hotels in Singapore?",
  ],
  approval: [
    "Do I need approval for a $1,400 trip to Paris?",
    "My Paris trip costs $800 — who approves it?",
    "Prepare my approval request for London",
    "Why was my approval rejected?",
  ],
  traveling: [
    "My flight AA203 is delayed — what are my options?",
    "What's the best way to get from Heathrow to central London?",
    "What currency do I need in Japan?",
    "Who do I call for emergency travel help right now?",
    "What's covered if I need to rebook?",
  ],
  issue: [
    "My flight was canceled — what do I do?",
    "I missed my connection in Frankfurt",
    "My hotel lost my reservation in Tokyo",
    "I lost my passport in Paris — help!",
    "Bad weather has closed the airport",
  ],
  post_trip: [
    "What do I need to do after my London trip?",
    "How do I submit my expenses?",
    "What's the deadline for expense submission?",
    "Summarize my trip follow-up tasks",
  ],
};

export default function App() {
  const [session]         = useState(DEFAULT_SESSION);
  const [stage, setStage] = useState("planning");
  const [messages, setMessages] = useState([{
    role: "assistant",
    content: "Hi! I'm **KellyCopilot** ✈️ — your AI business travel companion.\n\nI can help you with trips to **any city or country** — flights, hotels, visas, weather, approvals, and real-time travel issues.\n\nTell me where you're headed, or add a trip using the panel on the left!\n\nNext step ➜ Tell me your destination and travel dates.",
    stage: "planning",
  }]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const [trip, setTrip]           = useState(null);
  const [reminders, setReminders] = useState([]);
  const [activePanel, setActivePanel]   = useState(null); // "trip"|"reminders"|"search"|"contacts"|"policies"
  const [panelData, setPanelData]       = useState(null);
  const [panelLoading, setPanelLoading] = useState(false);
  const [tripForm, setTripForm]   = useState({
    destination: "", origin: "New York", dates: "",
    purpose: "client meeting", estimated_cost: "", traveler_name: "Kelli",
  });
  const [searchForm, setSearchForm] = useState({ type: "flights", origin: "New York", city: "", dates: "", flight_number: "" });
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  // Poll reminders every 30s if trip is set
  useEffect(() => {
    if (!trip) return;
    const load = () => fetch(`${API}/reminders/${session}`).then(r => r.json())
      .then(d => setReminders(d.reminders || [])).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [trip, session]);

  async function sendMessage(text) {
    const msg = text || input.trim();
    if (!msg) return;
    setInput("");

    const newMessages = [...messages, { role: "user", content: msg, stage }];
    setMessages(newMessages);
    setLoading(true);

    try {
      const res  = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msg,
          stage,
          session_id: session,
          conversation_history: newMessages.slice(-14).map(m => ({ role: m.role, content: m.content })),
        }),
      });
      const data = await res.json();

      setMessages(prev => [...prev, {
        role: "assistant",
        content: data.reply,
        stage,
        escalate: data.escalate,
      }]);

      // Update trip if detected
      if (data.trip_detected && Object.keys(data.trip_detected).length > 0) {
        setTrip(data.trip_detected);
      }
      if (data.reminders && data.reminders.length > 0) {
        setReminders(data.reminders);
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "⚠️ Connection error. Make sure the backend is running on port 8000.\n\n```\ncd backend\nuvicorn main:app --reload --port 8000\n```",
        stage,
      }]);
    }
    setLoading(false);
  }

  async function submitTrip() {
    if (!tripForm.destination || !tripForm.dates) {
      alert("Please fill in destination and dates.");
      return;
    }
    setPanelLoading(true);
    try {
      const res  = await fetch(`${API}/trip/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...tripForm, session_id: session, estimated_cost: parseFloat(tripForm.estimated_cost) || 0 }),
      });
      const data = await res.json();
      setTrip(data.trip);
      setReminders(data.reminders_set || []);
      setPanelData(data);
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `✅ **Trip to ${tripForm.destination} added!**\n\n` +
          `I've set up **${data.reminders_set?.length || 8} reminders** to keep you on track.\n\n` +
          (data.needs_approval ? `⚠️ **Approval required** — estimated cost $${tripForm.estimated_cost} exceeds $500 policy threshold.\n\n` : `✅ **No approval needed** — within auto-approval limits.\n\n`) +
          `**Live info fetched:**\n` +
          (data.live_info?.visa ? `- Visa: ${data.live_info.visa.slice(0, 120)}...\n` : "") +
          (data.live_info?.weather ? `- Weather: ${data.live_info.weather.slice(0, 100)}...\n` : "") +
          `\nNext step ➜ Check the Reminders panel to see all your pre-trip tasks.`,
        stage: "planning",
      }]);
    } catch (e) {
      alert("Error adding trip: " + e.message);
    }
    setPanelLoading(false);
  }

  async function loadPanel(type) {
    setActivePanel(type);
    setPanelData(null);
    if (type === "reminders") {
      setPanelData({ reminders });
      return;
    }
    if (type === "contacts") {
      setPanelLoading(true);
      const d = await fetch(`${API}/contacts`).then(r => r.json());
      setPanelData(d);
      setPanelLoading(false);
      return;
    }
    if (type === "policies") {
      setPanelLoading(true);
      const d = await fetch(`${API}/policies`).then(r => r.json());
      setPanelData(d);
      setPanelLoading(false);
      return;
    }
  }

  async function runSearch() {
    setPanelLoading(true);
    let url = "";
    const { type, origin, city, dates, flight_number } = searchForm;
    if (type === "flights")       url = `${API}/search/flights?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(city)}&dates=${encodeURIComponent(dates)}`;
    if (type === "hotels")        url = `${API}/search/hotels?city=${encodeURIComponent(city)}&dates=${encodeURIComponent(dates)}`;
    if (type === "visa")          url = `${API}/search/visa?destination_country=${encodeURIComponent(city)}`;
    if (type === "weather")       url = `${API}/search/weather?city=${encodeURIComponent(city)}&dates=${encodeURIComponent(dates)}`;
    if (type === "flight-status") url = `${API}/search/flight-status?flight_number=${encodeURIComponent(flight_number)}`;

    try {
      const d = await fetch(url).then(r => r.json());
      setPanelData(d);
    } catch (e) {
      setPanelData({ error: e.message });
    }
    setPanelLoading(false);
  }

  async function toggleReminder(id) {
    await fetch(`${API}/reminders/${session}/${id}/done`, { method: "PATCH" });
    setReminders(prev => prev.map(r => r.id === id ? { ...r, done: true } : r));
  }

  const pendingReminders = reminders.filter(r => !r.done).length;
  const currentStage     = STAGES.find(s => s.id === stage);

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <span className="logo">✈️ KellyCopilot</span>
          {trip?.destination && (
            <div className="trip-pill">
              <span>📍 {trip.destination}</span>
              {trip.dates && <span>📅 {trip.dates}</span>}
              {trip.purpose && <span>💼 {trip.purpose}</span>}
            </div>
          )}
        </div>
        <div className="header-right">
          {pendingReminders > 0 && (
            <button className="reminder-bell" onClick={() => loadPanel("reminders")}>
              🔔 {pendingReminders} reminder{pendingReminders > 1 ? "s" : ""}
            </button>
          )}
          <span className="lockton-tag">Lockton Track · HackKU 2026</span>
        </div>
      </header>

      {/* ── Stage nav ── */}
      <nav className="stage-nav">
        {STAGES.map(s => (
          <button key={s.id}
            className={`stage-btn ${stage === s.id ? "active" : ""}`}
            style={stage === s.id ? { borderColor: s.color, color: s.color } : {}}
            onClick={() => setStage(s.id)}>
            <span className="stage-label">{s.label}</span>
            <span className="stage-desc">{s.desc}</span>
          </button>
        ))}
      </nav>

      <div className="main">
        {/* ── Left Sidebar ── */}
        <aside className="sidebar">

          {/* Trip form */}
          <div className="sidebar-section">
            <div className="section-title">➕ Add Trip</div>
            <input className="s-input" placeholder="Destination (e.g. Tokyo)"
              value={tripForm.destination}
              onChange={e => setTripForm(p => ({ ...p, destination: e.target.value }))} />
            <input className="s-input" placeholder="From (e.g. New York)"
              value={tripForm.origin}
              onChange={e => setTripForm(p => ({ ...p, origin: e.target.value }))} />
            <input className="s-input" placeholder="Dates (e.g. May 10-14)"
              value={tripForm.dates}
              onChange={e => setTripForm(p => ({ ...p, dates: e.target.value }))} />
            <input className="s-input" placeholder="Estimated cost $"
              value={tripForm.estimated_cost}
              onChange={e => setTripForm(p => ({ ...p, estimated_cost: e.target.value }))} />
            <select className="s-input" value={tripForm.purpose}
              onChange={e => setTripForm(p => ({ ...p, purpose: e.target.value }))}>
              <option>client meeting</option>
              <option>conference</option>
              <option>training</option>
              <option>internal meeting</option>
              <option>sales</option>
            </select>
            <button className="s-btn primary" onClick={submitTrip} disabled={panelLoading}>
              {panelLoading ? "Adding…" : "✅ Add Trip & Set Reminders"}
            </button>
          </div>

          {/* Live search */}
          <div className="sidebar-section">
            <div className="section-title">🔍 Live Search</div>
            <select className="s-input" value={searchForm.type}
              onChange={e => setSearchForm(p => ({ ...p, type: e.target.value }))}>
              <option value="flights">✈️ Flights</option>
              <option value="hotels">🏨 Hotels</option>
              <option value="visa">🛂 Visa Requirements</option>
              <option value="weather">🌤 Weather</option>
              <option value="flight-status">📡 Flight Status</option>
            </select>
            {searchForm.type === "flights" && (
              <input className="s-input" placeholder="From city"
                value={searchForm.origin}
                onChange={e => setSearchForm(p => ({ ...p, origin: e.target.value }))} />
            )}
            {searchForm.type !== "flight-status" ? (
              <input className="s-input"
                placeholder={searchForm.type === "flights" ? "To city" : "City / Country"}
                value={searchForm.city}
                onChange={e => setSearchForm(p => ({ ...p, city: e.target.value }))} />
            ) : (
              <input className="s-input" placeholder="Flight number (e.g. AA203)"
                value={searchForm.flight_number}
                onChange={e => setSearchForm(p => ({ ...p, flight_number: e.target.value }))} />
            )}
            {(searchForm.type === "flights" || searchForm.type === "hotels" || searchForm.type === "weather") && (
              <input className="s-input" placeholder="Dates (optional)"
                value={searchForm.dates}
                onChange={e => setSearchForm(p => ({ ...p, dates: e.target.value }))} />
            )}
            <button className="s-btn" onClick={() => { setActivePanel("search"); runSearch(); }}>
              🔍 Search
            </button>
          </div>

          {/* Quick tools */}
          <div className="sidebar-section">
            <div className="section-title">🛠 Quick Tools</div>
            <button className="s-btn" onClick={() => loadPanel("reminders")}>
              🔔 Reminders {pendingReminders > 0 ? `(${pendingReminders})` : ""}
            </button>
            <button className="s-btn" onClick={() => loadPanel("contacts")}>📞 Emergency Contacts</button>
            <button className="s-btn" onClick={() => loadPanel("policies")}>📖 Travel Policies</button>
          </div>

          {/* Panel display */}
          {activePanel && (
            <div className="panel">
              <div className="panel-header">
                <span>{activePanel.toUpperCase()}</span>
                <button onClick={() => { setActivePanel(null); setPanelData(null); }}>✕</button>
              </div>
              {panelLoading && <div className="panel-loading">Searching…</div>}
              {panelData && <PanelContent type={activePanel} data={panelData}
                onToggleReminder={toggleReminder} />}
            </div>
          )}
        </aside>

        {/* ── Chat ── */}
        <section className="chat-area">
          <div className="messages">
            {messages.map((m, i) => (
              <div key={i} className={`message ${m.role}`}>
                {m.role === "assistant" && <div className="avatar">🤖</div>}
                <div className="bubble-wrap">
                  {m.escalate && <div className="escalate-badge">⚠️ Escalation needed — human contact required</div>}
                  <div className={`bubble ${m.role}`}>
                    <MsgText content={m.content} />
                  </div>
                  {m.role === "assistant" && m.stage && (
                    <span className="stage-tag">{STAGES.find(s => s.id === m.stage)?.label}</span>
                  )}
                </div>
                {m.role === "user" && <div className="avatar user-av">👩‍💼</div>}
              </div>
            ))}
            {loading && (
              <div className="message assistant">
                <div className="avatar">🤖</div>
                <div className="bubble assistant loading-bubble">
                  <span className="dot" /><span className="dot" /><span className="dot" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Quick prompts */}
          <div className="quick-prompts">
            {STAGE_PROMPTS[stage]?.map((p, i) => (
              <button key={i} className="quick-btn" onClick={() => sendMessage(p)}>{p}</button>
            ))}
          </div>

          {/* Input */}
          <div className="input-row">
            <input className="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()}
              placeholder={`Ask about any city, flight, visa, hotel, or travel issue…`}
              disabled={loading} />
            <button className="send-btn" onClick={() => sendMessage()}
              disabled={loading || !input.trim()}>
              {loading ? "⏳" : "Send ↗"}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

// ── Panel content renderer ────────────────────────────────────────────────────
function PanelContent({ type, data, onToggleReminder }) {
  if (data.error) return <div className="panel-error">❌ {data.error}</div>;

  if (type === "reminders") {
    const items = data.reminders || [];
    if (items.length === 0) return <div className="panel-empty">No reminders yet. Add a trip to auto-generate them!</div>;
    return (
      <div>
        {items.map(r => (
          <div key={r.id} className={`reminder-item ${r.done ? "done" : ""}`}>
            <button className="check-btn" onClick={() => !r.done && onToggleReminder(r.id)}>
              {r.done ? "✅" : "⬜"}
            </button>
            <div className="reminder-body">
              <div className="reminder-msg">{r.message}</div>
              <div className="reminder-due">Due: {r.due_date}</div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (type === "search") {
    const keys = ["flight_info","hotel_info","visa_info","weather_info","status_info","travel_advisory","local_tips","local_tips","weather"];
    return (
      <div>
        {data.origin && <div className="search-meta">{data.origin} → {data.destination || data.city}</div>}
        {data.city && !data.origin && <div className="search-meta">📍 {data.city}</div>}
        {data.flight_number && <div className="search-meta">Flight: {data.flight_number}</div>}
        {data.dates && <div className="search-meta">📅 {data.dates}</div>}
        {data.policy_max_usd && <div className="policy-note">Policy max: ${data.policy_max_usd}</div>}
        {data.policy_max_per_night_usd && <div className="policy-note">Policy max/night: ${data.policy_max_per_night_usd}</div>}
        {keys.map(k => data[k] && (
          <div key={k} className="search-result-block">
            <div className="result-label">{k.replace(/_/g," ").toUpperCase()}</div>
            <div className="result-text">{data[k]}</div>
          </div>
        ))}
        <div className="search-note">⚡ Results from live web search</div>
      </div>
    );
  }

  if (type === "contacts") {
    return (
      <div>
        {data.contacts?.map((c, i) => (
          <div key={i} className="contact-card">
            <div className="c-role">{c.role}</div>
            <div className="c-name">{c.name}</div>
            <div className="c-phone">{c.phone}</div>
            <div className="c-hours">{c.available}</div>
          </div>
        ))}
      </div>
    );
  }

  if (type === "policies") {
    return (
      <div>
        {Object.entries(data.policies || {}).map(([k, v]) => (
          <div key={k} className="policy-row">
            <span className="p-key">{k.replace(/_/g, " ")}</span>
            <span className="p-val">{Array.isArray(v) ? v.join(", ") : String(v)}</span>
          </div>
        ))}
        <div className="policy-contact">Questions? {data.contact}</div>
      </div>
    );
  }

  return null;
}

// ── Markdown-lite message renderer ───────────────────────────────────────────
function MsgText({ content }) {
  const lines = content.split("\n");
  return (
    <div className="msg-text">
      {lines.map((line, i) => {
        if (line.startsWith("```")) return <div key={i} className="code-block-marker" />;
        if (line.startsWith("- ") || line.startsWith("• "))
          return <div key={i} className="bullet">• {parseBold(line.slice(2))}</div>;
        if (/^\d+\.\s/.test(line))
          return <div key={i} className="bullet">{parseBold(line)}</div>;
        if (line.startsWith("**") && line.endsWith("**") && line.length > 4)
          return <div key={i} className="bold-line">{line.slice(2,-2)}</div>;
        if (line.startsWith("# ") || line.startsWith("## "))
          return <div key={i} className="heading">{line.replace(/^#+\s/, "")}</div>;
        if (line.trim() === "") return <div key={i} style={{height:8}} />;
        return <p key={i}>{parseBold(line)}</p>;
      })}
    </div>
  );
}

function parseBold(text) {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  return parts.map((p, i) => i % 2 === 1 ? <strong key={i}>{p}</strong> : p);
}
