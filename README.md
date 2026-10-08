# Campus Customs

A storefront and merch assistant for **Campus Customs**, the family-run shop that
has sold officially licensed Yale apparel from 57 Broadway in New Haven since
1975.

React + Vite + TypeScript on the front, FastAPI + Pydantic AI on the back, over a
SQLite catalogue of 102 products.

> MGT 409 — AI Foundations for Managers, Homework 4.

---

## What it does

- **Browse products** — all 102 items, filterable by category, searchable as you type
- **Create an account** — PBKDF2-hashed passwords, signed session tokens
- **Chat about merch** — a Pydantic AI agent that answers only from the database
- **See matching items** — the agent returns structured matches the site renders as product cards
- **Get answers about prices and stock** — per-size availability, read live from inventory

Plus: saved chat history per account, a "your size" preference that re-colours the
whole catalogue, and an append-only audit trail of every agent turn.

---

## Prerequisites

| | Version used |
|---|---|
| Python | 3.14 (3.11+ should be fine) |
| Node.js | 24 (18+ should be fine) |
| npm | 11 |

---

## 1. Get the data pack

**The database and product images are not in this repository.** They are course
data, they are large, and they are not ours to redistribute — so `.gitignore`
excludes them.

Unzip the course `data.zip` into this folder so the layout is:

```
hw4/
└── data/
    ├── campus_customs.db     # catalogue, inventory, users, chat_messages
    └── products/             # product photography (.jpg)
```

The backend resolves this path from its own location, so it must sit directly
inside `hw4/`. Without it the API returns a clear error on startup rather than
failing mysteriously.

---

## 2. Add your API key

```bash
cp .env.example .env
```

Then set `PORTKEY_API_KEY` in `.env`. The backend walks up from this folder
through every parent directory and loads the first `.env` it finds, so a shared
key a few levels up also works.

`.env` is git-ignored. **Never commit a real key.**

> Without a key the site still runs — browsing, accounts, search and product
> pages all work. Only the chat assistant is unavailable, and `/api/health`
> reports `"agent_ready": false`.

---

## 3. Run the backend

From the **`backend`** folder:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Using a virtual environment (recommended), from `hw4/`:

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
cd backend
../.venv/Scripts/uvicorn main:app --reload --port 8000
```

On macOS or Linux, swap `Scripts` for `bin`.

Check it:

```bash
curl http://127.0.0.1:8000/api/health
```

```json
{"status":"ok","products":102,"model":"gpt-6-luna","agent_ready":true}
```

Interactive API docs: **http://127.0.0.1:8000/docs**

---

## 4. Run the front end

In a **second terminal**, from `hw4/`:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

Vite proxies `/api` and `/images` to `127.0.0.1:8000`, so both servers need to be
running. There is no base URL to configure.

To build for production:

```bash
npm run build && npm run preview
```

---

## 5. Try it

Sign in with the seeded account:

```
test@campuscustoms.yale.edu  /  password
```

Then:

1. Click the blue chat button and ask **"What hoodies do you have?"** — the reply
   arrives with product cards, and the Products page grows a *From your chat*
   band showing the same items.
2. Open any product and ask **"Is this in large?"** — the agent resolves "this"
   from the page you are on and answers with the real count.
3. Pick a size in the strip under the nav — every product card gains a live
   availability badge for that size, and the assistant stops asking what you wear.
4. On Products, type **"hockey"** without pressing Enter — results narrow as you type.

---

## Project layout

```
hw4/
├── AI_prompts.md              Log of every prompt used to build this
├── requirements.txt           Backend dependencies
├── .env.example               Environment template
├── .gitignore
├── README.md
├── frontend/                  Vite React TypeScript app
│   └── src/
│       ├── api.ts             Typed API client
│       ├── auth.tsx           Auth context, token handling
│       ├── matches.tsx        Chat matches shared with the Products page
│       ├── size.tsx           "Your size" preference + fit badges
│       ├── markdown.tsx       Inline bold renderer
│       ├── components/        NavBar SizeBar Footer ProductCard ChatWidget GameCountdown
│       └── pages/             Home Products ProductDetail About LogIn CreateAccount
├── backend/
│   ├── main.py                FastAPI app — run with: uvicorn main:app --reload --port 8000
│   ├── agent.py               Model wiring + the configured Pydantic AI agent
│   ├── models.py              Every Pydantic type
│   ├── tools.py               Catalogue queries + the six agent tools
│   ├── auth.py                Password hashing, validation, session tokens
│   ├── limits.py              Rate limiting
│   ├── audit.py               Append-only, hash-chained audit trail
│   └── prompts/
│       └── prompt.md          Voice + safety rules S1–S10
├── output/
│   ├── harness.md             How the whole system works (start here)
│   ├── design.md              Design direction and the commercial case for it
│   ├── usability.md           Four improvements, with before/after measurements
│   ├── app_check.html         Live site check with screenshots
│   ├── app_check_images/      Screenshots linked from app_check.html
│   └── audit_trail.json       Append-only agent-loop log (JSON Lines)
└── data/                      ← local-only, git-ignored (see step 1)
    ├── campus_customs.db
    └── products/
```

---

## Documentation

| File | What is in it |
|---|---|
| [`output/harness.md`](output/harness.md) | The reference. Every table and field, how auth works, how the agent is loaded, every model field and why, the tools, the safety rules, the audit trail, and full specs |
| [`output/design.md`](output/design.md) | The design direction and why it should increase retention and purchases |
| [`output/usability.md`](output/usability.md) | Two front-end and two back-end improvements, with measurements |
| [`output/app_check.html`](output/app_check.html) | Live test of three features, with screenshots and captions |
| [`AI_prompts.md`](AI_prompts.md) | Every prompt used to build this, by problem number |

---

## API reference

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | — | Status, product count, model, whether the agent is configured |
| GET | `/api/categories` | — | Normalized categories with counts |
| GET | `/api/products` | — | List, with `search` / `category` / `limit` |
| GET | `/api/products/{id}` | — | Detail with per-size stock |
| GET | `/api/products/{id}/related` | — | Tag-overlap matches |
| GET | `/images/{file}` | — | Product photos |
| POST | `/api/auth/signup` | — | Create an account |
| POST | `/api/auth/login` | — | Sign in |
| GET | `/api/auth/me` | Bearer | Current user |
| POST | `/api/chat` | Optional | One agent turn — guests allowed |
| GET | `/api/chat/history` | Bearer | Stored conversation |
| DELETE | `/api/chat/history` | Bearer | Delete your own conversation |
| GET | `/api/audit/verify` | — | Audit-trail integrity check (read-only) |

---

## Notes on the agent

Every price, color, size and quantity the assistant states comes from a tool call
against the database. Three layers keep it honest:

1. **The prompt** tells it that it has no reliable memory of the inventory and
   must look everything up, with ten numbered safety rules (S1–S10).
2. **The tools** are the only source of product data, and are read-only.
3. **The server re-looks-up every product** the model returns. Name, price, image
   and colors come from the catalogue, and any id that is not real is dropped
   before the response is sent — then counted in the audit trail.

The audit trail (`output/audit_trail.json`) is JSON Lines so that appending never
rewrites the file, and each record carries the SHA-256 of the one before it, so
deleting or editing a line is detectable:

```bash
curl http://127.0.0.1:8000/api/audit/verify
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Database not found at .../data/campus_customs.db` | The data pack is missing — see step 1 |
| Chat returns **503** | `PORTKEY_API_KEY` is not set — see step 2 |
| Products page shows "Catalogue unavailable" | The backend is not running on port 8000 |
| Images are broken | The backend is not running, or `data/products/` is missing |
| Chat returns **429** | Rate limit: 20 chat turns per 5 minutes |
| Code changes do not take effect | `--reload` can miss changes on synced folders (OneDrive, Dropbox). Restart the server |
