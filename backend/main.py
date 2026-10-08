"""Campus Customs — FastAPI backend.

Serves the catalogue, accounts, and the merch chat agent.

Run from this folder:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import agent as agent_module
import audit
from limits import CHAT_LIMIT, LOGIN_EMAIL_LIMIT, LOGIN_IP_LIMIT, SIGNUP_LIMIT, client_key
from auth import (
    create_token,
    email_problem,
    hash_password,
    normalize_email,
    password_problem,
    read_token,
    verify_password,
)
import json

from models import (
    AuthResponse,
    CategoryCount,
    ChatDeps,
    ChatHistory,
    ChatRequest,
    ChatResponse,
    LoginRequest,
    ProductCard,
    ProductDetail,
    ProductSummary,
    SignupRequest,
    StoredMessage,
    User,
)
from tools import connect, load_categories, load_product, load_products, load_related

# --------------------------------------------------------------------------
# Paths — resolved from this file, so the working directory does not matter.
# --------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
IMAGE_DIR = DATA_DIR / "products"


def db() -> sqlite3.Connection:
    return connect(DB_PATH)


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------

app = FastAPI(
    title="Campus Customs API",
    description="Catalogue, accounts and the merch chat agent.",
    version="0.2.0",
)

# The Vite dev server runs on a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if IMAGE_DIR.exists():
    app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")


@app.get("/api/health")
def health() -> dict:
    with closing(db()) as conn:
        count = conn.execute("SELECT COUNT(*) FROM catalogue").fetchone()[0]
    return {
        "status": "ok",
        "products": count,
        "model": agent_module.MODEL_NAME,
        # Whether a key is configured, never the key itself.
        "agent_ready": agent_module.api_key_is_set(),
    }


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


def user_from_row(row: sqlite3.Row) -> User:
    """Build the public user shape. Note `password_hash` is never included."""
    return User(
        id=row["id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        name=row["name"],
        email=row["email"],
        created_at=row["created_at"],
    )


def current_user(authorization: str | None = Header(default=None)) -> User:
    """Resolve `Authorization: Bearer <token>` to a user, or 401."""
    token = authorization[7:] if (authorization or "").lower().startswith("bearer ") else None
    user_id = read_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not signed in.")

    with closing(db()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    return user_from_row(row)


def optional_user(authorization: str | None = Header(default=None)) -> User | None:
    """Same as `current_user`, but guests are allowed through as None.

    Used by the chat route so the assistant can greet a signed-in shopper by
    name without requiring an account to use it.
    """
    try:
        return current_user(authorization)
    except HTTPException:
        return None


@app.post("/api/auth/signup", response_model=AuthResponse, status_code=201)
def signup(request: Request, body: SignupRequest) -> AuthResponse:
    # Caps how many accounts one source can create in an hour.
    SIGNUP_LIMIT.enforce(client_key(request))

    first = body.first_name.strip()
    last = body.last_name.strip()
    email = normalize_email(body.email)

    if not first or not last:
        raise HTTPException(status_code=400, detail="First and last name are required.")
    for problem in (email_problem(email), password_problem(body.password)):
        if problem:
            raise HTTPException(status_code=400, detail=problem)

    with closing(db()) as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            # users.email is UNIQUE -- surface this as a clean 409, not a 500.
            raise HTTPException(status_code=409, detail="An account with that email already exists.")

        cursor = conn.execute(
            """INSERT INTO users (name, email, password_hash, first_name, last_name)
               VALUES (?, ?, ?, ?, ?)""",
            (f"{first} {last}", email, hash_password(body.password), first, last),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()

    user = user_from_row(row)
    audit.log_event("account_created", user_id=user.id)
    return AuthResponse(token=create_token(user.id), user=user)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: Request, body: LoginRequest) -> AuthResponse:
    email = normalize_email(body.email)

    # Only *failed* attempts count, so getting your password right never moves
    # you toward a lockout. Limited per email (stops one account being guessed
    # at) and, far more loosely, per IP (stops a sweep across many accounts
    # without punishing everyone behind a shared campus address).
    ip_key = client_key(request)
    LOGIN_EMAIL_LIMIT.check(f"email:{email}")
    LOGIN_IP_LIMIT.check(ip_key)

    with closing(db()) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    # Same message either way, so the endpoint does not reveal which emails exist.
    if row is None or not verify_password(body.password, row["password_hash"]):
        LOGIN_EMAIL_LIMIT.record(f"email:{email}")
        LOGIN_IP_LIMIT.record(ip_key)
        # Note: the email itself is never written to the trail.
        audit.log_safety_event("login_failed", user_id=None, known_account=row is not None)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    # A correct password clears the counters outright.
    LOGIN_EMAIL_LIMIT.reset(f"email:{email}")
    LOGIN_IP_LIMIT.reset(ip_key)

    user = user_from_row(row)
    audit.log_event("login", user_id=user.id)
    return AuthResponse(token=create_token(user.id), user=user)


@app.get("/api/auth/me", response_model=User)
def me(user: User = Depends(current_user)) -> User:
    return user


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------


@app.get("/api/audit/verify")
def audit_verify() -> dict:
    """Integrity check on the audit trail.

    Read-only, and there is deliberately no endpoint anywhere in this API that
    clears, rotates or rewrites the trail.
    """
    return audit.verify_chain()


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------


@app.get("/api/categories", response_model=list[CategoryCount])
def categories() -> list[CategoryCount]:
    """Canonical categories with product counts, for the Products page filters."""
    return load_categories(DB_PATH)


@app.get("/api/products", response_model=list[ProductSummary])
def list_products(
    search: str | None = Query(None, description="Match name, description, colors or tags"),
    category: str | None = Query(None, description="Canonical category, e.g. Hoodies"),
    limit: int = Query(200, ge=1, le=500),
) -> list[ProductSummary]:
    return load_products(DB_PATH, search=search, category=category, limit=limit)


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str) -> ProductDetail:
    product = load_product(DB_PATH, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"No product '{product_id}'")
    return product


@app.get("/api/products/{product_id}/related", response_model=list[ProductSummary])
def related_products(product_id: str, limit: int = Query(4, ge=1, le=12)) -> list[ProductSummary]:
    if load_product(DB_PATH, product_id) is None:
        raise HTTPException(status_code=404, detail=f"No product '{product_id}'")
    return load_related(DB_PATH, product_id, limit=limit)


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------
#
# Conversations are persisted to chat_messages for signed-in shoppers only.
# Guests get a working assistant with no stored history -- nothing is written
# for an account that does not exist.

#: How many stored turns to replay into a returning conversation.
HISTORY_TURNS = 20


def save_message(
    user_id: int,
    role: str,
    content: str,
    products: list[ProductCard] | None = None,
) -> None:
    """Append one turn to chat_messages.

    `products_json` stores the assistant's matched products so a reloaded
    conversation still shows its cards. NULL on user turns, matching how the
    seeded rows were written.
    """
    payload = (
        json.dumps([p.model_dump() for p in products], ensure_ascii=False) if products else None
    )
    with closing(db()) as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, ?, ?, ?)",
            (user_id, role, content, payload),
        )
        conn.commit()


def load_history(user_id: int, limit: int = HISTORY_TURNS) -> list[StoredMessage]:
    """The most recent turns for one user, oldest first.

    Always filtered by user_id -- a shopper only ever sees their own thread.
    """
    with closing(db()) as conn:
        rows = conn.execute(
            """SELECT id, role, content, products_json, created_at
               FROM chat_messages WHERE user_id = ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()

    messages: list[StoredMessage] = []
    for row in reversed(rows):
        cards: list[ProductCard] = []
        if row["products_json"]:
            try:
                for item in json.loads(row["products_json"]):
                    if isinstance(item, dict) and item.get("product_id"):
                        cards.append(ProductCard(**{
                            key: value
                            for key, value in item.items()
                            if key in ProductCard.model_fields
                        }))
            except (ValueError, TypeError):
                cards = []  # a malformed row should not break the whole thread
        messages.append(
            StoredMessage(
                id=row["id"],
                role=row["role"],
                content=row["content"],
                products=cards,
                created_at=row["created_at"],
            )
        )
    return messages


@app.get("/api/chat/history", response_model=ChatHistory)
def chat_history(user: User = Depends(current_user)) -> ChatHistory:
    """This shopper's stored conversation. Requires an account."""
    return ChatHistory(messages=load_history(user.id))


@app.delete("/api/chat/history", status_code=204)
def clear_chat_history(user: User = Depends(current_user)) -> None:
    """Let a shopper delete their own conversation."""
    with closing(db()) as conn:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user.id,))
        conn.commit()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: Request, body: ChatRequest, user: User | None = Depends(optional_user)
) -> ChatResponse:
    """Run one turn of the merch agent and return its reply.

    Open to guests. When a shopper is signed in, their stored conversation is
    read from the database rather than taken from the request, and the new turns
    are written back. Only the shopper's display name reaches the model -- never
    an email or an id.
    """
    started = time.perf_counter()
    page_summary = (
        {
            "path": body.page.path,
            "product_id": body.page.product_id,
            "category": body.page.category,
            "preferred_size": body.page.preferred_size,
        }
        if body.page
        else {}
    )

    # Every turn is a paid model call -- this is the spend guard.
    try:
        CHAT_LIMIT.enforce(f"user:{user.id}" if user else client_key(request))
    except HTTPException as limited:
        audit.log_safety_event(
            "rate_limited",
            user_id=user.id if user else None,
            endpoint="/api/chat",
            detail=limited.detail,
        )
        raise

    if not agent_module.api_key_is_set():
        audit.log_safety_event(
            "agent_unavailable",
            user_id=user.id if user else None,
            reason="PORTKEY_API_KEY is missing",
        )
        raise HTTPException(
            status_code=503,
            detail="The merch assistant is not configured. PORTKEY_API_KEY is missing.",
        )

    # Page context: what the shopper is looking at while they type.
    page = body.page
    page_product = load_product(DB_PATH, page.product_id) if page and page.product_id else None
    page_label = None
    if page:
        if page_product:
            page_label = f"the {page_product.name} product page"
        elif page.category:
            page_label = f"the {page.category} category"
        elif page.path.startswith("/products"):
            page_label = "the Products page"

    stored = load_history(user.id) if user else []

    deps = ChatDeps(
        db_path=DB_PATH,
        user_id=user.id if user else None,
        user_name=user.name if user else None,
        returning=bool(stored),
        page_product_id=page_product.product_id if page_product else None,
        page_product_name=page_product.name if page_product else None,
        page_label=page_label,
        preferred_size=(page.preferred_size if page else None),
    )

    # Signed-in shoppers get their real stored thread; guests get whatever the
    # browser is holding in memory. Either way prior turns are replayed as text,
    # so the backend keeps no in-process conversation state.
    if user:
        turns = [(m.role, m.content) for m in stored][-10:]
    else:
        turns = [(t.role, t.content) for t in body.history[-10:]]

    transcript = "\n".join(
        f"{'Shopper' if role == 'user' else 'Assistant'}: {content}" for role, content in turns
    )
    prompt = (
        f"Earlier in this conversation:\n{transcript}\n\nShopper: {body.message}"
        if transcript
        else body.message
    )

    try:
        result = await agent_module.get_agent().run(prompt, deps=deps)
    except Exception as exc:  # noqa: BLE001
        # A single awkward message stays in the stored thread and is replayed on
        # every later turn, so one upstream content-filter rejection would brick
        # a shopper's assistant permanently. Retry once with the history
        # dropped: the current question almost always succeeds on its own.
        recovered = False
        if transcript:
            audit.log_safety_event(
                "history_replay_rejected",
                user_id=user.id if user else None,
                reason=str(exc)[:200],
                retrying_without_history=True,
            )
            try:
                result = await agent_module.get_agent().run(body.message, deps=deps)
                recovered = True
            except Exception as retry_exc:  # noqa: BLE001
                exc = retry_exc

        if not recovered:
            audit.log_event(
                "agent_error",
                user_id=user.id if user else None,
                model=agent_module.MODEL_NAME,
                page=page_summary,
                request={
                    "message": body.message[:200],
                    "message_chars": len(body.message),
                },
                error=str(exc)[:300],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise HTTPException(
                status_code=502, detail=f"The assistant could not answer: {exc}"
            ) from exc

    reply = result.output

    # Re-hydrate each card from the catalogue so every field is the database's
    # value, not whatever the model typed back. The model supplies the
    # product_id and the match note; the catalogue supplies the rest. This is
    # also what lets the front end render these with the same card component as
    # the Products page.
    cards: list[ProductCard] = []
    seen: set[str] = set()
    dropped: list[str] = []
    for card in reply.products:
        product = load_product(DB_PATH, card.product_id)
        if product is None:
            # The model named something that is not in the catalogue. Drop it
            # and record it -- this is the grounding layer catching a
            # hallucination, and it is exactly what the audit trail is for.
            dropped.append(card.product_id)
            continue
        if product.product_id in seen:
            continue  # duplicate
        seen.add(product.product_id)
        cards.append(
            ProductCard(
                product_id=product.product_id,
                note=card.note,
                name=product.name,
                price=product.price,
                image_url=product.image_url,
                category=product.category,
                garment_type=product.garment_type,
                colors=product.colors,
            )
        )

    # Reconstruct the agent loop from the message history: which tools ran, in
    # what order, with what arguments, and what each returned.
    tool_calls: list[dict] = []
    for message in result.all_messages():
        for part in message.parts:
            if part.part_kind == "tool-call" and part.tool_name != "final_result":
                tool_calls.append(
                    {
                        "tool": part.tool_name,
                        "args": audit._truncate(str(part.args), 300),
                    }
                )
            elif part.part_kind == "tool-return" and part.tool_name != "final_result":
                for call in reversed(tool_calls):
                    if call["tool"] == part.tool_name and "result_chars" not in call:
                        call["result_chars"] = len(str(part.content))
                        break

    tools_used = [call["tool"] for call in tool_calls]

    usage = {}
    try:
        counts = result.usage()
        usage = {
            "input_tokens": getattr(counts, "input_tokens", None),
            "output_tokens": getattr(counts, "output_tokens", None),
            "requests": getattr(counts, "requests", None),
        }
    except Exception:  # noqa: BLE001 - usage is nice to have, never required
        usage = {}

    audit.log_agent_turn(
        user_id=user.id if user else None,
        message=body.message,
        page=page_summary,
        model=agent_module.MODEL_NAME,
        tool_calls=tool_calls,
        reply_text=reply.message,
        product_ids=[c.product_id for c in cards],
        dropped_product_ids=dropped,
        latency_ms=int((time.perf_counter() - started) * 1000),
        usage=usage,
    )

    # Persist only for signed-in shoppers. Written after a successful reply, so
    # a failed turn does not leave a dangling question in the thread.
    if user:
        save_message(user.id, "user", body.message)
        save_message(user.id, "assistant", reply.message, cards)

    return ChatResponse(
        message=reply.message,
        products=cards,
        tools_used=tools_used,
        saved=bool(user),
    )
