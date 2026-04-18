# ✈️ KellyCopilot — Business Travel AI Companion
### HackKU 2026 · Lockton Track Submission

> "Everything a business traveler needs — before, during, and after the trip — in one trusted Copilot."

---

## 🎯 What It Does

KellyCopilot is a full-stack AI travel assistant that guides "Kelli" (a business traveler) through every stage of a work trip:

| Stage | What KellyCopilot Does |
|---|---|
| 📋 **Planning** | Checklist generation, policy lookup, booking option comparisons |
| ✅ **Approvals** | Auto-detects approval need, prepares request, tracks status |
| ✈️ **Traveling** | Real-time help, rebooking options, local contacts |
| ⚠️ **Issue** | Calm issue triage, clear options, escalation to humans |
| 🏁 **Post-Trip** | Expense reminders, trip summary, close-out checklist |

---

## 🏗️ Architecture

```
frontend/          ← React + Vite (port 3000)
  src/
    App.jsx        ← Full chat UI, stage switcher, side panels
    App.css        ← Dark theme styling

backend/
  main.py          ← FastAPI server (port 8000)
                     - /chat         → Claude AI stage-aware responses
                     - /flights      → Mock flight options with policy flags
                     - /hotels       → Mock hotel options with policy flags
                     - /approval/*   → Approval request & status
                     - /checklist    → Auto-generated pre-trip checklist
                     - /contacts     → Emergency contacts
                     - /policies     → Company travel policies
                     - /expense/*    → Expense submission
                     - /post-trip/*  → Post-trip summary
```

**Privacy by Design:**
- No PII stored — all data is session-scoped
- Sensitive fields (passport, SSN, card numbers) are never requested or logged
- Policy data is sanitized before being sent to the LLM
- Claude API calls use system-level guardrails per stage

---

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Python 3.10+
- Node.js 18+
- An Anthropic API key (get one at console.anthropic.com)

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...    # Windows: set ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload --port 8000
```

Backend running at: http://localhost:8000
API docs at: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend running at: http://localhost:3000

---

## 🎭 Demo Script (for judges)

**1. Planning Stage**
- Click "📋 Planning" tab
- Ask: *"What do I need for my trip to London next week?"*
- Click "✈️ Flight Options" in sidebar — see policy-compliant vs non-compliant options
- Click "📋 Pre-Trip Checklist" — auto-generated international checklist

**2. Approval Stage**
- Click "✅ Approvals" tab
- Click "📝 Request Approval" button — see auto-detection logic
- Ask: *"Do I need approval for this $650 trip?"*

**3. Traveling Stage**
- Click "✈️ Traveling" tab
- Ask: *"My flight is delayed 3 hours — what are my options?"*
- Ask: *"Who do I contact for help right now?"*

**4. Issue Stage**
- Click "⚠️ Issue" tab
- Ask: *"My flight was canceled — what should I do now?"*
- Observe escalation badge when urgent action is detected

**5. Post-Trip Stage**
- Click "🏁 Post-Trip" tab
- Click "🏁 Post-Trip Tasks" in sidebar
- Ask: *"What do I still need to do after this trip?"*

---

## 📋 Track Requirements Coverage

| Requirement | Implementation |
|---|---|
| Planning → Approval → Travel → Issues → Return | 5 stage tabs with stage-aware AI prompts |
| Anticipates needs | Quick prompts pre-loaded per stage |
| Traveler checklist | `/checklist` endpoint, auto-international detection |
| Guided approvals | `/approval/request` auto-detects need + recommends approver |
| Real-time in-trip help | Traveling stage with short, action-oriented responses |
| Issue handling | Issue stage with escalation detection |
| Post-trip follow-up | Post-trip stage + `/post-trip/summary` endpoint |
| Privacy by design | No PII storage, sanitized API calls, session-only data |
| Booking options with tradeoffs | Flights/hotels with policy compliance flags |
| Escalation path | Auto-detects escalation keywords, shows emergency contacts |

---

## 🔒 Privacy & Safety Design

1. **No persistent storage** — all conversation history is client-side only
2. **PII guardrails** — system prompt explicitly instructs Claude never to request/store passport, SSN, or payment data
3. **Policy sanitization** — company financial details are abstracted before LLM calls
4. **Session-scoped context** — trip context is passed per-request, never persisted server-side
5. **Escalation detection** — server-side keyword check triggers human handoff flag

---

## 👥 Team
HackKU 2026 — Lockton Track
