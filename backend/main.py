"""
KellyCopilot - Lockton Track HackKU 2026
Dynamic Business Travel Companion
- Real AI responses (Claude or Gemini)
- Web search for live flight/hotel/visa/weather info
- Trip memory across conversation
- Reminders system
- Multi-city/country support
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json, os, re
from datetime import datetime, timedelta
import urllib.request
import urllib.parse

# ── AI Provider Detection ─────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
AI_PROVIDER       = "demo"

if ANTHROPIC_API_KEY:
    try:
        import anthropic as _anthropic
        AI_PROVIDER = "anthropic"
        print(f"✅ Anthropic Claude ready (key: ...{ANTHROPIC_API_KEY[-6:]})")
    except ImportError:
        print("❌ Run: pip install anthropic")

if AI_PROVIDER == "demo" and GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        AI_PROVIDER = "gemini"
        print(f"✅ Google Gemini ready (key: ...{GEMINI_API_KEY[-6:]})")
    except ImportError:
        print("❌ Run: pip install google-generativeai")

if AI_PROVIDER == "demo":
    print("⚠️  DEMO MODE — set ANTHROPIC_API_KEY or GEMINI_API_KEY for real AI")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="KellyCopilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory trip + reminder store (per session) ────────────────────────────
trips: Dict[str, Dict] = {}        # session_id -> trip data
reminders: Dict[str, List] = {}    # session_id -> list of reminders

# ── Company policies ──────────────────────────────────────────────────────────
COMPANY_POLICIES = {
    "max_flight_cost_usd": 1200,
    "max_hotel_per_night_usd": 300,
    "approval_required_above_usd": 500,
    "preferred_airlines": ["Delta", "United", "American", "British Airways", "Lufthansa", "Singapore Airlines"],
    "booking_window_days": 14,
    "expense_submission_days": 30,
    "travel_insurance": "Required for all international trips",
    "approved_booking_platforms": ["Concur", "SAP Travel", "Egencia"],
    "meal_allowance_per_day_usd": 75,
    "car_rental_allowed": True,
    "business_class_allowed_hours": 8,
}

# ── Web search helper (DuckDuckGo Instant Answer API — free, no key) ─────────
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return a summary string."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "KellyCopilot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        results = []
        # Abstract (main answer)
        if data.get("Abstract"):
            results.append(data["Abstract"])
        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(topic["Text"])
        # Infobox
        if data.get("Infobox"):
            for item in data["Infobox"].get("content", [])[:3]:
                if item.get("value"):
                    results.append(f"{item.get('label','')}: {item['value']}")

        return "\n".join(results) if results else "No specific results found."
    except Exception as e:
        return f"Search unavailable ({e}). Using general knowledge."


def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for flight information between cities."""
    query = f"flights from {origin} to {destination} {date} airlines schedule prices"
    base  = web_search(query)
    # Also get airport codes
    airports = web_search(f"{destination} international airport IATA code terminals")
    return f"Flight search: {origin} → {destination} ({date})\n{base}\nAirport info: {airports}"


def search_hotels(city: str, dates: str) -> str:
    """Search for hotel information in a city."""
    query = f"best business hotels {city} {dates} 4-star wifi business center"
    return web_search(query)


def search_visa_requirements(nationality: str, destination_country: str) -> str:
    """Search for visa requirements."""
    query = f"{nationality} citizen visa requirements for {destination_country} 2025 2026"
    return web_search(query)


def search_travel_advisory(country: str) -> str:
    """Search for travel advisories and safety info."""
    query = f"US State Department travel advisory {country} safety 2025 2026"
    return web_search(query)


def search_weather(city: str, dates: str) -> str:
    """Search for weather forecast."""
    query = f"weather forecast {city} {dates} temperature what to pack"
    return web_search(query)


def search_local_info(city: str) -> str:
    """Search for local business travel tips."""
    query = f"business travel tips {city} transportation taxi subway office etiquette currency"
    return web_search(query)


def search_flight_status(flight_number: str) -> str:
    """Search for live flight status."""
    query = f"flight {flight_number} status today live tracker delay"
    return web_search(query)

# ── Extract trip details from conversation ────────────────────────────────────
def extract_trip_info(message: str, existing: dict) -> dict:
    """Parse destination, dates, purpose from natural language."""
    trip = dict(existing)

    # Destination detection — common cities/countries
    city_patterns = [
        r'\bto\s+([A-Z][a-zA-Z\s]+?)(?:\s+(?:on|next|this|for|from|in)|\.|,|$)',
        r'\b(?:visiting|traveling to|going to|flying to|trip to)\s+([A-Z][a-zA-Z\s]+?)(?:\s|\.|,|$)',
        r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b',
    ]
    for pattern in city_patterns:
        match = re.search(pattern, message)
        if match:
            candidate = match.group(1).strip()
            # Filter out non-place words
            skip = {"Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday",
                    "January","February","March","April","May","June","July","August",
                    "September","October","November","December","Next","This","The"}
            if candidate not in skip and len(candidate) > 2:
                trip["destination"] = candidate
                break

    # Date detection
    date_patterns = [
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:\s*[-–to]+\s*\d{1,2})?(?:,?\s*20\d{2})?)',
        r'(\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?)',
        r'(next\s+(?:monday|tuesday|wednesday|thursday|friday|week|month))',
        r'(this\s+(?:monday|tuesday|wednesday|thursday|friday|week|month))',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            trip["dates"] = match.group(1).strip()
            break

    # Budget/cost detection
    cost_match = re.search(r'\$\s*(\d[\d,]*)', message)
    if cost_match:
        trip["estimated_cost"] = float(cost_match.group(1).replace(",", ""))

    # Purpose detection
    purpose_keywords = {
        "client meeting": ["client", "customer", "account"],
        "conference": ["conference", "summit", "expo", "congress"],
        "training": ["training", "workshop", "course", "bootcamp"],
        "internal meeting": ["team", "quarterly", "qbr", "offsite", "all-hands"],
        "sales": ["sales", "pitch", "proposal", "deal"],
    }
    for purpose, keywords in purpose_keywords.items():
        if any(kw in message.lower() for kw in keywords):
            trip["purpose"] = purpose
            break

    return trip


# ── System prompt (fully dynamic) ────────────────────────────────────────────
def build_system_prompt(stage: str, trip: dict, search_context: str = "") -> str:
    today = datetime.now().strftime("%B %d, %Y")
    stage_focus = {
        "planning":  (
            "Help the traveler plan their trip. "
            "Ask about destination, dates, and purpose if not provided. "
            "Use the web search results to give REAL, SPECIFIC information about their destination — "
            "actual visa requirements, real airlines that fly that route, actual weather, real hotel names. "
            "Generate a personalized checklist for their specific destination country."
        ),
        "approval":  (
            "Guide the traveler through the approval process. "
            "Calculate if approval is needed based on estimated cost vs $500 threshold. "
            "Prepare a ready-to-send approval summary. "
            "Explain clearly who approves, why, and what to do if rejected."
        ),
        "traveling": (
            "Traveler is ON THE ROAD right now. Be concise and action-focused. "
            "Help with real-time issues: delays, rebooking, local navigation, currency, contacts. "
            "Use search results to give specific local info for their city. "
            "Always provide an escalation path."
        ),
        "issue":     (
            "SOMETHING WENT WRONG. Be calm and decisive. "
            "Acknowledge the problem, give 2-3 concrete options with clear tradeoffs. "
            "Use search results to find real alternatives (next flights, nearby hotels). "
            "Know exactly when to say 'call this number now' and stop."
        ),
        "post_trip": (
            "Trip is complete. Help close the loop. "
            "List ALL pending actions with deadlines. "
            "Remind about expense submission (30-day deadline). "
            "Make it a numbered to-do list — easy and quick to act on."
        ),
    }

    return f"""You are KellyCopilot — a smart, proactive AI travel companion for business travelers at Acme Corp.
Today's date: {today}

CURRENT TRIP DETAILS:
{json.dumps(trip, indent=2) if trip else "No trip added yet — ask the traveler for details."}

COMPANY TRAVEL POLICIES:
{json.dumps(COMPANY_POLICIES, indent=2)}

LIVE WEB SEARCH RESULTS (use these for specific, accurate answers):
{search_context if search_context else "No search performed yet."}

YOUR STAGE: {stage.upper()}
YOUR FOCUS: {stage_focus.get(stage, stage_focus["planning"])}

CRITICAL RULES:
1. Use the web search results above to give SPECIFIC, REAL answers — not generic advice.
   - Real airlines that fly the route
   - Real visa requirements for that country
   - Real weather for those dates
   - Real hotel names in that city
2. If the traveler asks about a NEW city/country, respond with info specific to THAT place.
3. Adapt to whatever destination/dates/purpose the traveler mentions — never give the same answer twice.
4. Keep responses under 250 words. Use bullet points for lists.
5. End every response with ONE clear "Next step ➜" action.
6. Never store or repeat passport numbers, SSNs, or credit card numbers.
7. When something requires human escalation, clearly state WHO to call and their number.
8. If the traveler adds a trip, confirm it and list reminders you've set.
9. Warm, confident, human tone — like a knowledgeable colleague, not a robot."""


# ── AI Call ───────────────────────────────────────────────────────────────────
def call_ai(system: str, messages: list, stage: str) -> str:
    if AI_PROVIDER == "anthropic":
        client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp   = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=700,
            system=system,
            messages=messages,
        )
        return resp.content[0].text

    elif AI_PROVIDER == "gemini":
        model   = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system)
        history = [{"role": "user" if m["role"] == "user" else "model",
                    "parts": [m["content"]]} for m in messages[:-1]]
        chat    = model.start_chat(history=history)
        return  chat.send_message(messages[-1]["content"]).text

    else:
        # Demo: still use the system prompt to craft a contextual response
        dest    = "your destination"
        for m in reversed(messages):
            words = m["content"].split()
            for w in words:
                if w[0].isupper() and len(w) > 3:
                    dest = w
                    break
        return (
            f"[DEMO MODE — add ANTHROPIC_API_KEY for real AI]\n\n"
            f"I can see you're asking about **{dest}**. "
            f"In live mode, I would search for real flights, visa requirements, weather, "
            f"and hotel options specific to {dest} right now.\n\n"
            f"**To enable real responses:** Add your API key to backend/.env\n\n"
            f"Next step ➜ Set ANTHROPIC_API_KEY=sk-ant-... in backend/.env and restart the server."
        )


# ── Smart search decision ─────────────────────────────────────────────────────
def decide_searches(message: str, stage: str, trip: dict) -> str:
    """Figure out what to search based on the user's message."""
    msg   = message.lower()
    dest  = trip.get("destination", "")
    dates = trip.get("dates", "upcoming")
    results = []

    # Flight queries
    if any(w in msg for w in ["flight", "fly", "airline", "ticket", "route", "nonstop", "layover"]):
        origin = trip.get("origin", "New York")
        results.append(search_flights(origin, dest or "London", dates))

    # Hotel queries
    if any(w in msg for w in ["hotel", "stay", "accommodation", "lodging", "where to stay", "airbnb"]):
        results.append(search_hotels(dest or "London", dates))

    # Visa/passport queries
    if any(w in msg for w in ["visa", "passport", "entry", "permit", "document", "require"]):
        results.append(search_visa_requirements("US", dest or "the destination country"))

    # Weather queries
    if any(w in msg for w in ["weather", "temperature", "rain", "cold", "hot", "pack", "clothes", "what to wear"]):
        results.append(search_weather(dest or "London", dates))

    # Travel advisory / safety
    if any(w in msg for w in ["safe", "safety", "advisory", "warning", "risk", "danger"]):
        results.append(search_travel_advisory(dest or "the destination"))

    # Local info
    if any(w in msg for w in ["transport", "taxi", "subway", "metro", "uber", "currency", "tip", "local", "office"]):
        results.append(search_local_info(dest or "London"))

    # Flight status
    flight_match = re.search(r'\b([A-Z]{2}\d{3,4}|[A-Z]{3}\d{3,4})\b', message)
    if flight_match or any(w in msg for w in ["delay", "canceled", "status", "tracking", "my flight"]):
        fn = flight_match.group(1) if flight_match else "flight status"
        results.append(search_flight_status(fn))

    # New destination mentioned — do a comprehensive search
    if dest and dest.lower() not in ["london", "new york"] and not results:
        results.append(web_search(f"business travel {dest} tips flights hotels visa requirements 2025"))
        results.append(search_weather(dest, dates))

    # General planning with destination
    if not results and dest:
        results.append(web_search(f"business travel {dest} from USA flights hotels requirements {dates}"))

    return "\n\n---\n\n".join(results) if results else ""


# ── Pydantic models ───────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    stage: str
    session_id: str = "default"
    conversation_history: List[ChatMessage] = []

class TripInput(BaseModel):
    session_id: str = "default"
    destination: str
    origin: str = "New York"
    dates: str
    purpose: str
    estimated_cost: float = 0
    traveler_name: str = "Kelli"
    nationality: str = "US"

class ReminderInput(BaseModel):
    session_id: str = "default"
    message: str
    due_date: str  # ISO string or relative like "2026-04-25"

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "KellyCopilot running ✅", "ai_provider": AI_PROVIDER,
            "version": "2.0.0 — Dynamic"}

@app.get("/health")
def health():
    return {"status": "ok", "ai_provider": AI_PROVIDER,
            "anthropic_key_set": bool(ANTHROPIC_API_KEY),
            "gemini_key_set": bool(GEMINI_API_KEY),
            "timestamp": datetime.now().isoformat()}


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint.
    - Extracts trip info from messages automatically
    - Runs relevant web searches based on what user asked
    - Feeds live search results into the AI prompt
    - Returns dynamic, specific answers
    """
    try:
        sid  = req.session_id
        trip = trips.get(sid, {})

        # Update trip context from the current message
        trip = extract_trip_info(req.message, trip)
        trips[sid] = trip

        # Auto-set reminders when a trip is added
        if trip.get("destination") and trip.get("dates") and not trip.get("reminders_set"):
            _auto_set_reminders(sid, trip)
            trip["reminders_set"] = True
            trips[sid] = trip

        # Decide what to search based on the user's message
        search_ctx = decide_searches(req.message, req.stage, trip)

        # Build messages for AI
        system   = build_system_prompt(req.stage, trip, search_ctx)
        messages = [{"role": m.role, "content": m.content}
                    for m in req.conversation_history[-12:]]
        messages.append({"role": "user", "content": req.message})

        reply    = call_ai(system, messages, req.stage)
        escalate = any(w in reply.lower() for w in
                       ["call immediately", "contact now", "emergency",
                        "call the travel desk", "call your manager"])

        return {
            "reply": reply,
            "stage": req.stage,
            "escalate": escalate,
            "ai_provider": AI_PROVIDER,
            "trip_detected": trip,
            "reminders": reminders.get(sid, []),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"❌ Chat error: {e}")
        import traceback; traceback.print_exc()
        return {
            "reply": f"⚠️ Error: {str(e)}\n\nPlease check the backend terminal for details.",
            "stage": req.stage, "escalate": False,
            "ai_provider": "error",
            "timestamp": datetime.now().isoformat(),
        }


@app.post("/trip/add")
def add_trip(t: TripInput):
    """Explicitly add/update a trip and auto-generate reminders."""
    sid = t.session_id
    trip = {
        "destination": t.destination,
        "origin": t.origin,
        "dates": t.dates,
        "purpose": t.purpose,
        "estimated_cost": t.estimated_cost,
        "traveler_name": t.traveler_name,
        "nationality": t.nationality,
        "added_at": datetime.now().isoformat(),
        "reminders_set": True,
    }
    trips[sid] = trip
    _auto_set_reminders(sid, trip)

    # Quick info search for the destination
    visa_info    = search_visa_requirements(t.nationality, t.destination)
    weather_info = search_weather(t.destination, t.dates)
    flight_info  = search_flights(t.origin, t.destination, t.dates)

    needs_approval = t.estimated_cost > COMPANY_POLICIES["approval_required_above_usd"]

    return {
        "status": "Trip added ✅",
        "trip": trip,
        "reminders_set": reminders.get(sid, []),
        "needs_approval": needs_approval,
        "approval_threshold": COMPANY_POLICIES["approval_required_above_usd"],
        "live_info": {
            "visa": visa_info[:400],
            "weather": weather_info[:400],
            "flights": flight_info[:400],
        },
        "checklist": _generate_checklist(t.destination, t.nationality),
    }


@app.get("/trip/{session_id}")
def get_trip(session_id: str):
    """Get current trip details for a session."""
    trip = trips.get(session_id, {})
    if not trip:
        return {"status": "no_trip", "message": "No trip added yet."}

    # Refresh live info
    dest = trip.get("destination", "")
    dates = trip.get("dates", "")
    live = {}
    if dest:
        live["weather"]   = search_weather(dest, dates)[:400]
        live["advisory"]  = search_travel_advisory(dest)[:400]
        live["local_tips"]= search_local_info(dest)[:400]

    return {"trip": trip, "live_info": live,
            "reminders": reminders.get(session_id, [])}


@app.get("/reminders/{session_id}")
def get_reminders(session_id: str):
    """Get all reminders for a session."""
    rems = reminders.get(session_id, [])
    now  = datetime.now()
    for r in rems:
        try:
            due = datetime.fromisoformat(r["due_date"])
            r["overdue"]    = due < now
            r["days_until"] = (due - now).days
        except Exception:
            pass
    return {"reminders": rems, "count": len(rems)}


@app.post("/reminders/add")
def add_reminder(r: ReminderInput):
    sid = r.session_id
    if sid not in reminders:
        reminders[sid] = []
    reminder = {
        "id": len(reminders[sid]) + 1,
        "message": r.message,
        "due_date": r.due_date,
        "created_at": datetime.now().isoformat(),
        "done": False,
    }
    reminders[sid].append(reminder)
    return {"status": "Reminder added ✅", "reminder": reminder}


@app.patch("/reminders/{session_id}/{reminder_id}/done")
def mark_reminder_done(session_id: str, reminder_id: int):
    for r in reminders.get(session_id, []):
        if r["id"] == reminder_id:
            r["done"] = True
            return {"status": "marked done ✅"}
    return {"status": "not found"}


@app.get("/search/flights")
def search_flights_endpoint(origin: str, destination: str, dates: str = ""):
    """Live flight search for any city pair."""
    result = search_flights(origin, destination, dates)
    # Also get visa info
    visa = search_visa_requirements("US", destination)
    weather = search_weather(destination, dates)
    return {
        "origin": origin,
        "destination": destination,
        "dates": dates,
        "flight_info": result,
        "visa_info": visa[:500],
        "weather": weather[:300],
        "policy_max_usd": COMPANY_POLICIES["max_flight_cost_usd"],
        "note": "Information sourced from live web search.",
    }


@app.get("/search/hotels")
def search_hotels_endpoint(city: str, dates: str = "", nights: int = 3):
    """Live hotel search for any city."""
    result = search_hotels(city, dates)
    local  = search_local_info(city)
    return {
        "city": city,
        "dates": dates,
        "nights": nights,
        "hotel_info": result,
        "local_tips": local[:400],
        "policy_max_per_night_usd": COMPANY_POLICIES["max_hotel_per_night_usd"],
        "policy_total_usd": COMPANY_POLICIES["max_hotel_per_night_usd"] * nights,
    }


@app.get("/search/visa")
def search_visa_endpoint(destination_country: str, nationality: str = "US"):
    """Live visa requirements for any country."""
    result   = search_visa_requirements(nationality, destination_country)
    advisory = search_travel_advisory(destination_country)
    return {
        "destination": destination_country,
        "nationality": nationality,
        "visa_info": result,
        "travel_advisory": advisory[:400],
    }


@app.get("/search/weather")
def search_weather_endpoint(city: str, dates: str = ""):
    """Live weather search for any city."""
    result = search_weather(city, dates)
    return {"city": city, "dates": dates, "weather_info": result}


@app.get("/search/flight-status")
def flight_status_endpoint(flight_number: str):
    """Live flight status for any flight number."""
    result = search_flight_status(flight_number)
    return {"flight_number": flight_number, "status_info": result,
            "searched_at": datetime.now().isoformat()}


@app.post("/approval/request")
def request_approval(data: dict):
    cost    = data.get("estimated_cost", 0)
    dest    = data.get("destination", "")
    purpose = data.get("purpose", "business travel")
    dates   = data.get("dates", "")

    international = any(kw in dest.lower() for kw in
                        ["london","paris","tokyo","sydney","berlin","dubai","singapore",
                         "toronto","mexico","india","china","germany","france","japan",
                         "australia","canada","uk","united kingdom"])

    approver = "Sarah Mitchell (Direct Manager)"
    if cost > 1000:
        approver = "David Chen (VP Finance)"
    if international:
        approver = "Jennifer Park (Head of Operations)"

    needs = cost > COMPANY_POLICIES["approval_required_above_usd"]
    return {
        "needs_approval": needs,
        "approver": approver if needs else None,
        "estimated_turnaround": "24-48 hours",
        "status": "pending" if needs else "auto_approved",
        "summary": {"destination": dest, "dates": dates,
                    "purpose": purpose, "estimated_cost": cost},
        "message": (f"Request sent to {approver}. Response in 24-48 hours."
                    if needs else "✅ Auto-approved — within policy limits!"),
    }


@app.get("/contacts")
def get_contacts():
    return {"contacts": [
        {"role": "24/7 Travel Support", "name": "Acme Travel Desk",
         "phone": "+1-800-555-TRAVEL", "available": "24/7"},
        {"role": "Direct Manager",      "name": "Sarah Mitchell",
         "phone": "+1-555-234-5678",    "available": "Business hours EST"},
        {"role": "HR Emergency",        "name": "HR Department",
         "phone": "+1-800-555-0100",    "available": "24/7"},
        {"role": "Travel Insurance",    "name": "TravelGuard",
         "phone": "+1-800-555-9999",    "available": "24/7"},
        {"role": "Corporate Card Help", "name": "AmEx Corporate",
         "phone": "+1-800-555-2639",    "available": "24/7"},
    ]}


@app.get("/policies")
def get_policies():
    return {"policies": COMPANY_POLICIES,
            "last_updated": "2026-01-15",
            "contact": "travel@acmecorp.com"}


# ── Internal helpers ──────────────────────────────────────────────────────────
def _auto_set_reminders(session_id: str, trip: dict):
    """Auto-generate smart reminders when a trip is added."""
    if session_id not in reminders:
        reminders[session_id] = []

    dest    = trip.get("destination", "your destination")
    dates   = trip.get("dates", "")
    now     = datetime.now()

    auto = [
        {"message": f"✈️ Book flights to {dest} via Concur",
         "due_date": (now + timedelta(days=1)).strftime("%Y-%m-%d")},
        {"message": f"🏨 Book hotel in {dest} via Concur",
         "due_date": (now + timedelta(days=1)).strftime("%Y-%m-%d")},
        {"message": "📝 Submit travel approval request",
         "due_date": (now + timedelta(days=2)).strftime("%Y-%m-%d")},
        {"message": f"🛂 Check visa/passport requirements for {dest}",
         "due_date": (now + timedelta(days=2)).strftime("%Y-%m-%d")},
        {"message": "💳 Notify credit card company of international travel",
         "due_date": (now + timedelta(days=3)).strftime("%Y-%m-%d")},
        {"message": "📱 Enable international phone plan",
         "due_date": (now + timedelta(days=4)).strftime("%Y-%m-%d")},
        {"message": f"🧳 Pack for {dest} trip",
         "due_date": (now + timedelta(days=5)).strftime("%Y-%m-%d")},
        {"message": "🧾 Submit expense report after trip",
         "due_date": (now + timedelta(days=35)).strftime("%Y-%m-%d")},
    ]

    existing_msgs = {r["message"] for r in reminders[session_id]}
    for i, r in enumerate(auto):
        if r["message"] not in existing_msgs:
            reminders[session_id].append({
                "id": len(reminders[session_id]) + 1,
                "message": r["message"],
                "due_date": r["due_date"],
                "created_at": now.isoformat(),
                "done": False,
                "auto": True,
            })


def _generate_checklist(destination: str, nationality: str = "US") -> list:
    """Generate destination-specific checklist."""
    base = [
        {"item": "Book flights via Concur",              "priority": "critical"},
        {"item": "Book hotel via Concur",                "priority": "critical"},
        {"item": "Submit travel approval request",       "priority": "high"},
        {"item": "Purchase travel insurance",            "priority": "high"},
        {"item": "Notify credit card of travel",         "priority": "high"},
        {"item": "Save emergency contacts offline",      "priority": "high"},
        {"item": "Enable international phone plan",      "priority": "medium"},
        {"item": "Download offline maps (Google Maps)",  "priority": "medium"},
        {"item": "Check CDC health advisories",          "priority": "medium"},
        {"item": "Pack power adapter for destination",   "priority": "medium"},
        {"item": "Get local currency / notify bank",     "priority": "medium"},
        {"item": "Confirm meeting details with contacts","priority": "low"},
    ]
    # Passport check for international
    base.insert(0, {"item": f"Confirm passport validity 6+ months beyond trip dates", "priority": "critical"})
    # Visa check
    base.insert(1, {"item": f"Check visa requirements for {destination}", "priority": "critical"})
    return base
