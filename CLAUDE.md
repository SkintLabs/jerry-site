# CLAUDE.md — SunsetBot Project Instructions

## What This Project Is

SunsetBot is an AI-powered customer service chatbot for Shopify stores. Store owners install it via Shopify OAuth, their product catalog syncs automatically, and customers get an intelligent shopping assistant via an embeddable chat widget.

**Target market:** Shopify store owners. Planned pricing: $199/mo.
**Current status:** Deployed to Railway. Live at `https://sunsetbot-production.up.railway.app`. 12 test products synced, chat working with real Shopify data.

## Tech Stack

- **Backend:** Python 3.11 + FastAPI + WebSocket
- **AI/LLM:** Groq API with `llama-3.3-70b-versatile` (Llama 3.3 70B)
- **Embeddings:** SentenceTransformers (`all-MiniLM-L6-v2`, 384-dim)
- **Vector DB:** Pinecone (with in-memory mock fallback for dev)
- **Database:** SQLAlchemy async — SQLite (dev) / PostgreSQL (production)
- **Auth:** JWT (PyJWT) for widget WebSocket authentication
- **Frontend:** React 18 + TypeScript + Vite — builds to single embeddable JS file
- **Shopify CLI:** v3.91.0 (installed globally via npm)
- **ngrok:** v3.36.1 (for HTTPS tunneling during dev)
- **Python venv:** `backend/venv/` (Python 3.11)

## Project Structure

```
sunsetbot/
├── CLAUDE.md                            # THIS FILE
├── SESSION_4_HANDOFF.md                 # Project history through Session 4
├── SESSION_5_HANDOFF.md                 # Session 5 handoff (Shopify integration)
├── SESSION_6_HANDOFF.md                 # Session 6 handoff (deployment)
├── shopify.app.toml                     # Shopify app config (used by Shopify CLI)
├── railway.toml                         # Railway deployment config
├── package.json                         # Root package.json (for Shopify CLI)
├── .gitignore                           # Git ignore rules
├── backend/
│   ├── main.py                          # FastAPI app, WebSocket, REST endpoints (v3.0.0)
│   ├── Dockerfile                       # Docker build (PyTorch CPU-only for Railway)
│   ├── .dockerignore                    # Docker ignore rules
│   ├── requirements.txt                 # Python dependencies
│   ├── test_chat.html                   # Browser-based chat test UI (legacy)
│   ├── .env                             # API keys (NEVER commit)
│   ├── sunsetbot.db                     # SQLite database (auto-created on startup)
│   ├── venv/                            # Python virtual environment
│   ├── static/
│   │   ├── sunsetbot-widget.iife.js     # Built React widget (49KB gzipped)
│   │   └── demo.html                    # Demo page showing the widget
│   └── app/
│       ├── __init__.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── conversation_engine.py   # AI pipeline orchestrator (v1.2.0)
│       │   ├── product_intelligence.py  # Semantic search + product catalog (v1.2.0)
│       │   └── shopify_sync.py          # Shopify product sync service (v1.0.0)
│       ├── api/
│       │   ├── __init__.py
│       │   └── shopify.py               # Shopify OAuth + webhooks (v1.0.0)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py                # Pydantic Settings (all env vars) (v1.0.0)
│       │   └── security.py              # JWT + Shopify HMAC verification (v1.0.0)
│       └── db/
│           ├── __init__.py
│           ├── models.py                # SQLAlchemy Store model (v1.0.0)
│           └── engine.py                # Async DB engine + session factory (v1.0.0)
└── frontend/
    ├── package.json
    ├── node_modules/                    # npm dependencies (installed)
    ├── tsconfig.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx                     # Widget entry point (shadow DOM mount)
        └── Widget.tsx                   # React chat widget component
```

## How to Run

```bash
# Start backend
cd ~/sunsetbot/backend
source venv/bin/activate
python main.py
# Server: http://localhost:8000
# Swagger: http://localhost:8000/docs
# Widget demo: http://localhost:8000/static/demo.html
# Legacy test: open test_chat.html in browser

# For Shopify OAuth testing (needs HTTPS):
# Terminal 1: python main.py
# Terminal 2: ngrok http 8000
# Then update APP_URL in .env to the ngrok URL
# Visit: https://<ngrok-url>/shopify/install?shop=sunsetbot.myshopify.com

# Build widget (after making frontend changes)
cd ~/sunsetbot/frontend
npm install
npm run build
# Output: ../backend/static/sunsetbot-widget.iife.js
```

## Architecture — Full System

```
Store Owner installs via Shopify OAuth
    │
    ▼ GET /shopify/install?shop=xxx.myshopify.com
    │   → Redirect to Shopify consent screen
    │   → Callback with access_token
    │   → Save store to SQLite/PostgreSQL
    │   → Trigger product sync (Shopify REST API → CatalogProduct → Pinecone)
    │   → Register webhooks for product updates
    │
Customer visits store with widget installed
    │
    ▼ <script src="sunsetbot-widget.iife.js" data-shop="xxx">
    │   → React widget mounts in shadow DOM
    │   → Fetches JWT from GET /shopify/widget-token?shop=xxx
    │   → Opens WebSocket: ws://server/ws/chat/{store_id}/{session_id}?token=xxx
    │
    ▼ WebSocket: {"message": "red dresses under $60"}
    │
main.py:websocket_chat()
    ├─ JWT verification (production) or pass-through (development)
    ├─ Rate limit check (30 msgs/min)
    ├─ Message size check (8 KB max)
    │
    ▼
ConversationEngine.process_message()
    ├─ 1. IntentClassifier.classify()     → "product_search"
    ├─ 2. EntityExtractor.extract()       → {colors: ["red"], max_price: 60, category: "dress"}
    ├─ 3. ProductIntelligence.search()    → [Product, ...] (semantic + filters)
    ├─ 4. ResponseGenerator.generate()    → Groq API → natural language response
    ├─ 5. EscalationHandler.check()       → escalate if frustrated/VIP/keywords
    ├─ 6. Update sentiment + history
    │
    ▼ WebSocket: {"type": "message", "text": "...", "products": [...]}
```

## API Endpoints

```
GET  /                              Root info
GET  /health                        Service health check
GET  /docs                          Swagger UI

# Shopify
GET  /shopify/install               Start OAuth install flow
GET  /shopify/callback              OAuth callback (exchange code for token)
GET  /shopify/widget-token          Get JWT for chat widget
POST /shopify/webhooks              Receive product/app webhooks
GET  /shopify/stores                List installed stores (admin)

# WebSocket
WS   /ws/chat/{store_id}/{session_id}?token=xxx

# Products
POST /api/products/index            Index products into vector DB
DEL  /api/products/{product_id}     Remove product from index

# Sessions
DEL  /api/sessions/{session_id}     End a session
GET  /api/sessions/active           List active sessions

# Static
GET  /static/sunsetbot-widget.iife.js   Widget JS bundle
GET  /static/demo.html                  Widget demo page
```

## Critical Patterns — DO NOT BREAK

### Branding
- Code uses **"SunsetBot"** everywhere. The folder was briefly called "VoixA" in Session 3 — ignore that.

### API Keys & Secrets
- `.env` has real Groq, Pinecone, and Shopify API keys. NEVER commit, log, or expose them.
- Store access tokens in the DB are sensitive — NEVER include in API responses or logs.
- If Groq key is missing, server starts in **degraded mode**.

### Service Initialization
- Services are initialized in the `lifespan` context manager (NOT at module level).
- The `lifespan` function MUST be defined BEFORE the `FastAPI()` constructor.
- Database tables are created on startup via `init_db()`.
- If a service fails to init, server starts in degraded mode.

### Settings (Pydantic BaseSettings)
- All env vars are centralized in `app/core/config.py` — use `get_settings()`.
- `settings.is_production` / `settings.is_development` for environment checks.
- `settings.shopify_configured` checks if Shopify API key+secret are set.
- `APP_URL` env var overrides the base URL for OAuth callbacks (set to ngrok URL in dev).

### JWT Authentication
- Widget gets a JWT from `/shopify/widget-token` containing `store_id` + `session_id`.
- WebSocket validates JWT in production mode (`ENVIRONMENT=production`).
- In development, JWT is optional — connections work without token.
- Tokens expire after 24 hours (configurable via `jwt_expiry_hours`).

### Shopify OAuth Flow
- Install URL: `/shopify/install?shop=xxx.myshopify.com`
- Callback reads ALL query params from `request.query_params` (not manually listed)
- HMAC verification uses Shopify format: sorted key=value pairs joined with &, NO url-encoding
- Nonce verification (CSRF protection)
- Store saved to DB with access token and shop info
- Product sync triggered automatically after install
- Webhooks registered for product updates and app uninstall
- **Custom distribution** used (not App Store) — install links generated in Partner dashboard

### Shopify Product Sync
- `ShopifySyncService` fetches all products via paginated REST API (250/page)
- Converts Shopify product format → `CatalogProduct` → indexes into Pinecone
- Webhook handler processes individual product create/update/delete events
- Products prefixed with `shopify-{id}` to avoid ID collisions

### Category Groups
- `EntityExtractor` has **category synonym groups** so "shoes" also matches boots, sneakers, sandals.
- Groups: footwear, tops, bottoms, outerwear, bags, jewelry, headwear.
- The extracted `category_group` list is passed to `ProductIntelligence.search()`.

### Follow-up Detection
- `IntentClassifier` detects follow-up requests ("show me more options", "different styles") and re-classifies as `product_search` if previous intent was `product_search`.

### Groq/LLM Model
- Currently using `llama-3.3-70b-versatile` via Groq.
- The old `llama-3.1-70b-versatile` was decommissioned by Groq in Feb 2026.
- Model configurable via `GROQ_MODEL` env var.

### Security
- JWT auth on WebSocket (production mode)
- Shopify HMAC verification on OAuth callback and webhooks
- Rate limiting: 30 msgs/min per session, 10 WS connections per IP
- Max 8 KB per WebSocket frame, max 2000 chars per message
- CORS wildcard auto-disables credentials
- Duplicate session detection
- Prompt injection mitigation (XML delimiters)
- Graceful shutdown

### Widget (React)
- Built with Vite as a single IIFE file (~49KB gzipped)
- Mounts inside shadow DOM for CSS isolation from host page
- Customizable via `data-*` attributes on script tag (data-shop, data-server, data-color, data-position)
- Auto-reconnects with exponential backoff (max 5 attempts)
- Mobile responsive
- Falls back to demo mode if widget-token endpoint returns 404

### Entity Extraction
- Uses regex (fast, <1ms) — NOT ML.
- Size regex requires "size" prefix for numbers.
- Plural normalization: "dresses" → "dress", "boots" → "boot".
- Supports: price, size, color, material, attribute, occasion, category.

## Shopify Account Details

- **Partner account:** Linked (created Feb 22, 2026)
- **Dev store domain:** `sunsetbot.myshopify.com`
- **App name:** SunsetBot
- **App Client ID:** `b323444b85e59301f81c74e556dd7efe` (also in .env as SHOPIFY_API_KEY)
- **Distribution:** Custom distribution (install link generated via Partner dashboard)
- **App installed on dev store:** YES (Feb 22, 2026)
- **Legacy install flow:** Disabled (incompatible with declarative webhooks)
- **Railway account:** Created, linked to GitHub
- **Railway domain:** `sunsetbot-production.up.railway.app`
- **Railway services:** sunsetbot (app) + PostgreSQL
- **GitHub repo:** `Buddafest/sunsetbot` (private)

## What Needs Building Next (Prioritized)

1. **Shopify CLI deploy** — Run `shopify app deploy` to push updated URLs (Railway) to Shopify Partners. Needed before any new store installs.
2. **Redis session persistence** — Replace `_InMemoryContextManager`. `to_json()`/`from_json()` already work.
3. **Store-specific StoreConfig** — Load store name/policies from DB into ConversationEngine (currently uses hardcoded defaults).
4. **Billing / Shopify App Store** — Usage metering, Shopify billing API integration.
5. **Store owner dashboard** — Analytics, conversation viewer, escalation alerts.
6. **Automated tests** — No pytest tests exist yet. Smoke tests in `if __name__ == "__main__"` blocks.

## Common Commands

```bash
# Start backend server (local dev)
cd ~/sunsetbot/backend && source venv/bin/activate && python main.py

# Health check (local)
curl http://localhost:8000/health

# Health check (production)
curl https://sunsetbot-production.up.railway.app/health

# Demo page (production)
open https://sunsetbot-production.up.railway.app/static/demo.html

# List installed stores
curl http://localhost:8000/shopify/stores

# Resync products for a store
curl -X POST "http://localhost:8000/shopify/resync?shop=sunsetbot.myshopify.com"

# Start ngrok for Shopify OAuth testing
ngrok http 8000

# Build widget (from frontend dir)
cd ~/sunsetbot/frontend && npm run build

# Deploy to Shopify (push app config)
cd ~/sunsetbot && npx @shopify/cli@latest app deploy

# Git push (triggers Railway auto-deploy)
cd ~/sunsetbot && git push origin main

# View widget demo
open http://localhost:8000/static/demo.html
```

## Session History

- **Session 1 (Feb 14):** PRD, architecture doc, branding
- **Session 2 (Feb ~15):** conversation_engine.py — full AI pipeline
- **Session 3 (Feb ~18):** product_intelligence.py + main.py + test_chat.html
- **Session 4 (Feb 21):** Comprehensive audit — 8 bugs fixed, security hardening, performance optimization, category groups, follow-up detection
- **Session 5 (Feb 22):** Shopify integration (OAuth, product sync, webhooks), JWT auth, database layer, React chat widget, centralized settings. **OAuth tested and working — app installed on dev store.**
- **Session 5.5 (Feb 23):** Code review fixes — WS race condition (asyncio.Lock), JWT secret validation, input sanitization (NFKC), Groq rate-limit retry (specific RateLimitError), hardcoded URL fix.
- **Session 6 (Feb 23):** 12 test products created via Shopify API, product sync pipeline verified end-to-end, Railway deployment (Dockerfile with CPU-only PyTorch, PostgreSQL), Shopify app URLs updated to Railway domain. **App is now live at `https://sunsetbot-production.up.railway.app`.**

Full details in `SESSION_6_HANDOFF.md`.
