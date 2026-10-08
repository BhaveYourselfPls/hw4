# Usability & Performance Improvements

Four improvements to Campus Customs — two on the front end, two on the back end.
Each section states the problem, the fix, where to find it, and **how to check
it yourself**.

| # | Side | Improvement | Check it in |
|---|---|---|---|
| 1 | Front end | Live search + visible, removable filters | Products page |
| 2 | Front end | Chat keyboard & screen-reader support, full-screen on mobile | Chat panel |
| 3 | Back end | Catalogue snapshot cache — fixes an N+1 query | `backend/tools.py` |
| 4 | Back end | Rate limiting on sign-in, signup and chat | `backend/limits.py` |

---

## Front end 1 — Live search, and filters you can see and remove

**File:** `frontend/src/pages/Products.tsx`

### The problem

Two things made the Products page quietly frustrating:

1. **Search did nothing until you pressed Enter.** The box was wrapped in a form
   that only submitted on Enter, so a shopper could type "hockey", see 102
   unchanged products, and reasonably conclude the search was broken. Nothing
   on screen suggested a keypress was required.
2. **Active filters were invisible.** Picking a category and typing a term left
   no indication of *why* the grid had shrunk, and the only way out was to find
   the "All" chip and manually clear the text box. Arriving from a footer link
   like `/products?category=Hoodies` was worse — the filter was applied with no
   obvious way to undo it.

### The fix

- **Live search, debounced 250ms.** Results update as you type. The debounce
  means one request after you pause, not one per keystroke.
- **An inline × in the search box** to clear the term in one click.
- **An active-filter bar** above the grid: "Filtering by [Hoodies ×] ["hockey" ×]
  — Clear all". Each pill removes just that filter; "Clear all" resets both.
- **`aria-live` on the result count**, so the change is announced rather than
  only visible.

The URL stays the source of truth throughout, so results remain shareable and
the back button still works.

### Why it helps

Search now behaves the way people expect from every other store — you see the
catalogue narrow as you type, which turns searching into browsing. And the
filter bar makes state legible: at any moment it is obvious what is being
filtered and how to undo exactly one piece of it, instead of starting over.

### How to check it

1. Go to **Products**. Note the count: *102 products*.
2. Type `hockey` in the search box — **do not press Enter**. Within a moment the
   count becomes *5 products matching "hockey"* and the grid shows 5 items.
3. A bar appears above the grid: **FILTERING BY "hockey" × Clear all**.
4. Click the **Hoodies** chip. The bar now reads **Hoodies × "hockey" × Clear
   all**, and the count reads *2 products in Hoodies matching "hockey"*.
5. Click the **"hockey" ×** pill. Only the search clears — *27 products in
   Hoodies* — and the URL drops to `?category=Hoodies`.

---

## Front end 2 — The chat panel works with a keyboard, a screen reader, and on a phone

**File:** `frontend/src/components/ChatWidget.tsx` (plus `index.css`)

### The problem

The chat panel was mouse-only and silent to assistive technology:

- **Opening it left focus behind on the page.** You had to reach for the mouse
  to type, and a keyboard user had to tab through the entire page to get in.
- **Escape did nothing.** The only way to close it was clicking the small ×.
- **Closing dumped focus onto `<body>`**, so a keyboard user lost their place
  entirely and had to tab from the top of the document again.
- **Replies were announced to nobody.** The message log had no live region, so a
  screen-reader user got no indication an answer had arrived.
- **On a phone the panel was cramped** — a 370px floating card inside a 375px
  viewport, with product cards squeezed into what was left.

### The fix

- **Autofocus the message input** when the panel opens — you can just start
  typing.
- **Escape closes the panel.**
- **Focus returns to the chat button** on close. This needed care: the panel and
  the button are different elements, so focus has to move *after* the re-render,
  or it falls to `<body>`. Handled with a `returnFocus` flag in an effect.
- **`role="log"` + `aria-live="polite"`** on the message list, so each new reply
  is announced; `aria-expanded` on the launcher button.
- **Full-screen panel under 640px**, so the conversation and its product cards
  are legible on a phone.

### Why it helps

A shopper can now run the whole conversation without touching the mouse, and
focus never gets lost — which is the difference between a keyboard user being
able to use the assistant and not. The live region means a screen-reader user
knows an answer arrived instead of sitting in silence. And on a phone, the
feature stops being a cramped box in the corner.

### How to check it

1. Click the blue chat button. **The cursor is already in the message box** —
   start typing without clicking.
2. Press **Escape**. The panel closes.
3. Press **Tab** — focus is on the chat button, right where you left it (before,
   focus was lost to the top of the page).
4. In dev tools, inspect the message list: `role="log"`, `aria-live="polite"`.
5. Narrow the browser below 640px and open the chat — it fills the screen.

---

## Back end 1 — Catalogue snapshot cache (fixes an N+1 query)

**File:** `backend/tools.py` — `_snapshot()` and `invalidate_cache()`

### The problem

Every catalogue read opened a fresh SQLite connection and re-read all 102 rows,
and the stock lookup was a textbook **N+1 query**: the agent's `search_products`
fetched the product list with one query, then ran *one more query per result* to
find that product's in-stock sizes.

Measured before the fix:

```
search_products(query='hoodie', limit=6): 11.4 ms, 7 db connections
10x load_products(search='navy'):         40.2 ms, 10 connections
```

Seven connections for one search — and that scales with the result limit, so a
12-result search meant 13. A single chat turn calls these tools several times,
so the cost multiplied with every conversation.

### The fix

A module-level snapshot holding both tables in memory:

- **One query for the catalogue, one for all 612 inventory rows** — the whole
  stock table is read at once and indexed by product, replacing the per-product
  queries entirely.
- **Invalidated by the database file's modification time**, so editing the `.db`
  is picked up on the next call with no restart. Correctness does not depend on
  anyone remembering to clear a cache.
- `load_products`, `load_product`, `load_categories`, `load_related` and
  `_in_stock_sizes` all read through it.

Measured after:

```
search_products(query='hoodie', limit=6): 2.45 ms, 0 db connections  (4.7x faster)
10x load_products(search='navy'):         22.8 ms, 0 connections     (1.8x faster)
```

Identical results — same 6 hits, same categories (25/2/29/27/11/8 = 102), same
product detail.

### Why it helps

The catalogue is read on nearly every request — every page load, every filter
change, every keystroke of the new live search, and several times per chat turn.
Removing the N+1 means the agent's tool calls no longer get slower as they
return more products, and the live search stays responsive while typing. It also
removes connection churn under concurrent users.

### Honest caveat

The cache keys on the whole database file's mtime, and `chat_messages` lives in
the same file — so saving a chat turn invalidates the catalogue snapshot too.
That costs one extra re-read on the next call. Correct, just not optimal;
splitting the cache key per table would fix it if it ever mattered.

### How to check it

Run from `backend/`:

```bash
../.venv/Scripts/python.exe -c "import time, tools; from main import DB_PATH; n=[0]; o=tools.connect; tools.connect=lambda p:(n.__setitem__(0,n[0]+1), o(p))[1]; C=type('C',(),{'deps':type('d',(),{'db_path':DB_PATH})}); tools.search_products(C(),query='hoodie',limit=6); n[0]=0; t=time.perf_counter(); r=tools.search_products(C(),query='hoodie',limit=6); print(f'{(time.perf_counter()-t)*1000:.2f} ms, {n[0]} connections, {len(r)} results')"
```

Expect roughly `2.4 ms, 0 connections, 6 results`. Comment out the `_snapshot`
call in `load_products` to see the original 7 connections.

---

## Back end 2 — Rate limiting on sign-in, signup and chat

**File:** `backend/limits.py`, wired into `backend/main.py`

### The problem

Two endpoints were unprotected, which the auth write-up had already flagged as a
gap:

1. **Login could be brute-forced.** PBKDF2 at 120,000 iterations makes each
   attempt slow, but a script could still run attempts continuously, forever,
   against any account.
2. **Chat had no spend guard.** Every turn is a paid model call. A loop in a
   browser console could run up the course budget with nobody noticing.

### The fix

A fixed-window counter in memory — the right size of solution for one process on
one machine, no Redis required.

| Limit | Allowance | Keyed on |
|---|---|---|
| Sign-in (per account) | 8 **failures** / 5 min | email |
| Sign-in (per address) | 40 **failures** / 5 min | IP |
| Signup | 5 / hour | IP |
| Chat | 20 / 5 min | user id, or IP for guests |

Three design decisions that matter more than the numbers:

- **Only failed logins count, and success clears the counter.** Mistyping your
  password twice and then getting it right leaves you with a clean slate. An
  attempt-counting limit would have punished ordinary fumbling.
- **The per-email limit is tight; the per-IP limit is deliberately loose.** This
  was a bug I caught while testing: with a single tight IP limit, one attacker
  locked out a legitimate shopper on the same address. Campus and office
  networks put hundreds of people behind one IP, so a tight IP limit would take
  out a whole building. The *email* key is what actually protects an account;
  the IP key only needs to stop a broad sweep.
- **Browsing is never limited.** All catalogue `GET` endpoints are untouched —
  only the endpoints that cost something are capped.

Responses are `429` with a human message and a `Retry-After` header.

### Why it helps

It closes a real attack path on accounts without making the site annoying for
the people it is protecting, and it puts a ceiling on what a runaway script can
spend. The failures-only rule and the split keys are what keep it invisible to
anyone using the site normally.

### How to check it

1. **Brute force is stopped.** POST to `/api/auth/login` with
   `victim@yale.edu` and a wrong password nine times. Attempts 1–8 return `401
   Incorrect email or password.`; attempt 9 returns `429 Too many sign-in
   attempts. Please wait 299 seconds and try again.` with `Retry-After: 299`.
2. **Other shoppers are unaffected.** Immediately after that, log in as
   `test@campuscustoms.yale.edu` / `password` from the same machine — **200 OK**.
   (Before the fix, this returned 429.)
3. **Success resets the counter.** Fail twice as the test user, then log in
   correctly (200). You get a full 8 failures again, confirming nothing carried
   over.
4. **Browsing is unlimited.** Request `/api/products?search=navy` fifteen times
   — all `200`.

---

## Verification summary

| Improvement | Verified |
|---|---|
| Live search | Typed "hockey" with no Enter → 102 → 5 products, URL `?search=hockey` |
| Filter bar | Two filters shown; removing the search pill left `?category=Hoodies`, 27 products |
| Chat keyboard | Focus on input at open; Escape closed it; focus returned to `BUTTON.chat-fab` |
| Chat a11y | Message log carries `role="log"`, `aria-live="polite"` |
| Mobile chat | At 375×812 the panel measured 375×812 — full screen |
| Cache | 11.4 ms / 7 connections → 2.45 ms / 0 connections, identical results |
| Rate limit | 8 failures then 429 + `Retry-After: 299`; other account still 200; success reset confirmed |

`tsc --noEmit` and `npm run build` are clean; the backend still starts with
`uvicorn main:app --reload --port 8000` from `backend/`.
