"""Catalogue access, and the tools the agent calls to ground its answers.

Everything the assistant says about a product — price, colors, sizes, stock —
comes from a function in this file. Nothing is inferred by the model.

The plain helpers at the top (`canonical_category`, `load_products`, …) are also
imported by `main.py` for the REST endpoints, so the website and the agent read
the catalogue through exactly one code path.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic_ai import RunContext

from models import (
    CategoryCount,
    CategoryPrices,
    ChatDeps,
    PriceGuide,
    ProductDetail,
    ProductFacts,
    ProductMatch,
    ProductSummary,
    SizeAvailability,
    SizeStock,
    ToolError,
)

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# Canonical categories, in the order a shopper would browse them.
CATEGORY_ORDER = [
    "T-Shirts",
    "Long Sleeves",
    "Crewnecks",
    "Hoodies",
    "Quarter-Zips",
    "Jackets",
    "Other",
]


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------


def connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise RuntimeError(f"Database not found at {db_path}")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------
# Catalogue snapshot cache
# --------------------------------------------------------------------------
#
# The catalogue and inventory are read on nearly every request and change only
# when the database file does. Without a cache, one agent search opened seven
# connections: one for the product list, then one more per result to look up
# that product's sizes -- the classic N+1. A six-result search re-read the whole
# 102-row catalogue and ran six extra queries.
#
# This holds both tables in memory and invalidates on the database file's
# modification time, so an edit to the .db is picked up on the next call without
# a restart.

_CACHE: dict[str, object] = {"mtime": None, "rows": None, "stock": None}


def _snapshot(db_path: Path) -> tuple[list[sqlite3.Row], dict[str, dict[str, int]]]:
    """Catalogue rows and stock-by-product, read at most once per file change."""
    mtime = db_path.stat().st_mtime_ns if db_path.exists() else None

    if _CACHE["mtime"] != mtime or _CACHE["rows"] is None:
        with closing(connect(db_path)) as conn:
            rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
            # One query for all 612 inventory rows, instead of one per product.
            inventory = conn.execute("SELECT product_id, size, quantity FROM inventory").fetchall()

        stock: dict[str, dict[str, int]] = {}
        for row in inventory:
            stock.setdefault(row["product_id"], {})[row["size"]] = row["quantity"]

        _CACHE.update({"mtime": mtime, "rows": rows, "stock": stock})

    return _CACHE["rows"], _CACHE["stock"]  # type: ignore[return-value]


def invalidate_cache() -> None:
    """Drop the snapshot. Called after any write that touches the catalogue."""
    _CACHE.update({"mtime": None, "rows": None, "stock": None})


def parse_json_list(raw: str | None) -> list[str]:
    """`colors` and `search_tags` are stored as JSON *strings*, not arrays."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def canonical_category(garment_type: str) -> str:
    """Collapse the 23 messy `garment_type` values into six real categories.

    The column mixes casing and specificity -- "t-shirt" / "short-sleeve T-shirt"
    / "heavyweight short-sleeve t-shirt", "hoodie" / "pullover hoodie",
    "jacket" / "full-zip fleece jacket" -- so it is never safe to filter on
    directly.
    """
    g = (garment_type or "").lower()
    if "quarter-zip" in g or "1/4" in g:
        return "Quarter-Zips"
    if "jacket" in g:
        return "Jackets"
    if "hood" in g:
        return "Hoodies"
    # T-shirts must be tested before "crew": the catalogue has a
    # "short-sleeve crew-neck t-shirt", which is a $32 tee, not a $58 crewneck.
    if "t-shirt" in g or "tee" in g:
        return "T-Shirts"
    if "crew" in g or "mockneck" in g:
        return "Crewnecks"
    if "performance" in g or "long-sleeve" in g:
        return "Long Sleeves"
    return "Other"


def image_url_for(product_id: str, image_file_path: str) -> str:
    """One of the 102 products has no .jpg on disk; the UI falls back to a
    placeholder, so this just guarantees a well-formed URL either way."""
    name = Path(image_file_path or "").name or f"{product_id}.jpg"
    return f"/images/{name}"


def row_to_summary(row: sqlite3.Row, stock: dict[str, int] | None = None) -> ProductSummary:
    return ProductSummary(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        category=canonical_category(row["garment_type"]),
        colors=parse_json_list(row["colors"]),
        price=row["price"],
        image_url=image_url_for(row["product_id"], row["image_file_path"]),
        # Ordered XS-XXL rather than however SQLite returned the rows.
        stock_by_size={
            size: (stock or {}).get(size, 0)
            for size in SIZE_ORDER
            if size in (stock or {})
        },
    )


# --------------------------------------------------------------------------
# Catalogue queries (shared by the REST API and the agent tools)
# --------------------------------------------------------------------------


# Words that carry no signal in a product search, so they should not drag a
# query's score down ("gifts for grandma" must still find the grandma hoodie).
STOPWORDS = {
    "a", "an", "and", "any", "anything", "are", "do", "does", "for", "got", "has",
    "have", "i", "in", "is", "it", "looking", "me", "my", "of", "on", "or", "please",
    "show", "some", "something", "that", "the", "them", "there", "they", "this",
    "to", "want", "what", "which", "with", "you", "your", "gift", "gifts",
}

# Shopper phrasings that do not appear verbatim in the catalogue.
SYNONYMS = {
    "grandmother": "grandma",
    "grandfather": "grandpa",
    "nana": "grandma",
    "sweatshirt": "crewneck",
    "jumper": "crewneck",
    "tee": "t-shirt",
    "tshirt": "t-shirt",
    "pullover": "hoodie",
    "coat": "jacket",
    "grey": "gray",
}


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9\-]+", (text or "").lower())
    tokens = [SYNONYMS.get(w, w) for w in words]
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def load_products(
    db_path: Path,
    search: str | None = None,
    category: str | None = None,
    limit: int = 200,
) -> list[ProductSummary]:
    """Products, optionally filtered by category and ranked against a query.

    Search is token-based rather than one substring match, because shoppers type
    phrases ("gifts for grandma", "navy hockey sweatshirt") that never appear
    verbatim in any single column. Each query word is scored across the name,
    description, tags and colors, and results come back best-match first.
    """
    rows, stock = _snapshot(db_path)

    by_id = {row["product_id"]: row for row in rows}
    products = [row_to_summary(row, stock.get(row["product_id"])) for row in rows]

    if category and category.lower() != "all":
        products = [p for p in products if p.category.lower() == category.lower()]

    if not search or not search.strip():
        return products[:limit]

    tokens = _tokenize(search)
    if not tokens:
        return products[:limit]

    scored: list[tuple[int, str, ProductSummary]] = []
    for product in products:
        row = by_id[product.product_id]
        name = product.name.lower()
        tags = " ".join(_tokenize(row["search_tags"] or ""))
        colors = " ".join(product.colors).lower()
        description = (row["description"] or "").lower()
        category_text = product.category.lower()

        score = 0
        matched = 0
        for token in tokens:
            hit = 0
            if token in name:
                hit = 4
            elif token in tags:
                hit = 3
            elif token in colors or token in category_text:
                hit = 2
            elif token in description:
                hit = 1
            if hit:
                matched += 1
                score += hit

        if matched:
            # Products matching more of the query outrank a single strong hit.
            score += matched * 3
            scored.append((score, product.name, product))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [product for _, _, product in scored[:limit]]


def load_product(db_path: Path, product_id: str) -> ProductDetail | None:
    rows, stock = _snapshot(db_path)
    row = next((r for r in rows if r["product_id"] == product_id), None)
    if row is None:
        return None

    by_size = stock.get(product_id, {})
    sizes = [
        SizeStock(size=size, quantity=by_size.get(size, 0), in_stock=by_size.get(size, 0) > 0)
        for size in SIZE_ORDER
        if size in by_size
    ]

    summary = row_to_summary(row, by_size)
    return ProductDetail(
        **summary.model_dump(),
        description=row["description"],
        search_tags=parse_json_list(row["search_tags"]),
        sizes=sizes,
        total_quantity=sum(s.quantity for s in sizes),
        available_sizes=[s.size for s in sizes if s.in_stock],
    )


def load_categories(db_path: Path) -> list[CategoryCount]:
    rows, _ = _snapshot(db_path)

    counts: dict[str, int] = {}
    for row in rows:
        key = canonical_category(row["garment_type"])
        counts[key] = counts.get(key, 0) + 1

    return [
        CategoryCount(category=name, count=counts[name])
        for name in CATEGORY_ORDER
        if name in counts
    ]


def load_related(db_path: Path, product_id: str, limit: int = 4) -> list[ProductSummary]:
    """Same-category products, ranked by how many search tags they share."""
    rows, stock = _snapshot(db_path)

    target = next((r for r in rows if r["product_id"] == product_id), None)
    if target is None:
        return []

    target_tags = {t.lower() for t in parse_json_list(target["search_tags"])}
    target_category = canonical_category(target["garment_type"])

    scored = []
    for row in rows:
        if row["product_id"] == product_id:
            continue
        tags = {t.lower() for t in parse_json_list(row["search_tags"])}
        score = len(target_tags & tags)
        if canonical_category(row["garment_type"]) == target_category:
            score += 2
        scored.append((score, row))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
    return [row_to_summary(row, stock.get(row["product_id"])) for _, row in scored[:limit]]


# --------------------------------------------------------------------------
# Agent tools
# --------------------------------------------------------------------------
#
# Registered on the agent in agent.py. Each one reads campus_customs.db and
# returns a typed model from models.py, so the assistant is always quoting real
# columns rather than recalling anything. The docstrings are written for the
# model: Pydantic AI turns them into the tool schema it sees.


def _in_stock_sizes(db_path: Path, product_id: str) -> list[str]:
    """Sizes with stock, read from the cached snapshot — no per-product query."""
    _, stock = _snapshot(db_path)
    by_size = stock.get(product_id, {})
    return [size for size in SIZE_ORDER if by_size.get(size, 0) > 0]


def search_products(
    ctx: RunContext[ChatDeps],
    query: str = "",
    category: str = "",
    max_price: float | None = None,
    available_in_size: str = "",
    limit: int = 6,
) -> list[ProductMatch]:
    """Search the Campus Customs catalogue for products.

    Matches against product names, descriptions, colors and curated search tags.
    This is the starting point for any "what do you have...", "show me..." or
    "anything for..." question.

    Reads: catalogue.name, .description, .colors, .search_tags, .garment_type,
    .price, .image_file_path, plus inventory.quantity for the in-stock sizes.

    Args:
        query: Free text - a color, sport, residential college, school,
            relative or style ("navy", "hockey", "grandma", "quarter-zip").
            Phrases are fine. Leave empty to browse a whole category.
        category: One of T-Shirts, Long Sleeves, Crewnecks, Hoodies,
            Quarter-Zips, Jackets. Leave empty for all.
        max_price: Only return products at or below this price, in dollars.
        available_in_size: Only return products currently in stock in this size
            (XS, S, M, L, XL, XXL). Use it when a shopper says what they wear.
        limit: How many to return (1-12).
    """
    products = load_products(
        ctx.deps.db_path,
        search=query.strip() or None,
        category=category.strip() or None,
        limit=200,
    )
    if max_price is not None:
        products = [p for p in products if p.price <= max_price]

    wanted_size = available_in_size.strip().upper()
    matches: list[ProductMatch] = []
    for product in products:
        sizes = _in_stock_sizes(ctx.deps.db_path, product.product_id)
        if wanted_size and wanted_size not in sizes:
            continue
        matches.append(
            ProductMatch(
                product_id=product.product_id,
                name=product.name,
                category=product.category,
                garment_type=product.garment_type,
                price=product.price,
                colors=product.colors,
                image_url=product.image_url,
                in_stock_sizes=sizes,
            )
        )
        if len(matches) >= max(1, min(limit, 12)):
            break

    return matches


def get_product_details(ctx: RunContext[ChatDeps], product_id: str) -> ProductFacts | ToolError:
    """Look up everything known about one product.

    Call this before answering any question about a specific item - especially
    what it looks like, what colors it comes in ("do you have it in pink?"), or
    what is in stock. The colors list is complete: if a color is not in it, we
    do not make this item in that color.

    Reads: catalogue.description, .colors, .search_tags, .price, .garment_type,
    .image_file_path, plus every inventory row for this product.

    Args:
        product_id: The catalogue slug, e.g. "basic-hoodie-big-yale". Get it
            from search_products - never guess one.
    """
    product = load_product(ctx.deps.db_path, product_id)
    if product is None:
        return ToolError(
            error=f"No product with id '{product_id}'.",
            hint="Use search_products to find the right product_id first.",
        )

    return ProductFacts(
        product_id=product.product_id,
        name=product.name,
        category=product.category,
        garment_type=product.garment_type,
        description=product.description,
        colors=product.colors,
        search_tags=product.search_tags,
        price=product.price,
        image_url=product.image_url,
        stock_by_size={s.size: s.quantity for s in product.sizes},
        available_sizes=product.available_sizes,
        sold_out_sizes=[s.size for s in product.sizes if not s.in_stock],
        total_quantity=product.total_quantity,
    )


def check_stock(ctx: RunContext[ChatDeps], product_id: str, size: str = "") -> SizeAvailability:
    """Check whether a product is in stock, optionally in one specific size.

    Stock exists only per size - roughly a quarter of all size rows sit at zero,
    so never state that something is available without calling this. When
    low_stock comes back true there are 5 or fewer left, which is worth saying.
    Every product has at least one size available, so you can always offer an
    alternative size rather than a dead end.

    Reads: inventory.size and inventory.quantity for this product.

    Args:
        product_id: The catalogue slug.
        size: XS, S, M, L, XL or XXL. Leave empty for the full breakdown.
    """
    product = load_product(ctx.deps.db_path, product_id)
    if product is None:
        return SizeAvailability(
            product_id=product_id,
            name="",
            error=f"No product with id '{product_id}'.",
        )

    by_size = {s.size: s.quantity for s in product.sizes}
    sold_out = [s for s, q in by_size.items() if q == 0]

    if size:
        wanted = size.strip().upper()
        if wanted not in by_size:
            return SizeAvailability(
                product_id=product_id,
                name=product.name,
                error=f"We do not carry size '{size}'. Sizes run {', '.join(by_size)}.",
                stock_by_size=by_size,
                available_sizes=product.available_sizes,
                sold_out_sizes=sold_out,
                total_quantity=product.total_quantity,
            )
        quantity = by_size[wanted]
        return SizeAvailability(
            product_id=product_id,
            name=product.name,
            size=wanted,
            quantity=quantity,
            in_stock=quantity > 0,
            low_stock=0 < quantity <= 5,
            stock_by_size=by_size,
            available_sizes=product.available_sizes,
            sold_out_sizes=sold_out,
            total_quantity=product.total_quantity,
        )

    return SizeAvailability(
        product_id=product_id,
        name=product.name,
        stock_by_size=by_size,
        available_sizes=product.available_sizes,
        sold_out_sizes=sold_out,
        total_quantity=product.total_quantity,
    )


def get_price_guide(ctx: RunContext[ChatDeps]) -> PriceGuide:
    """Price range for every category across the whole catalogue.

    Price is set by garment type, so items within a category usually share one
    price. Use this to answer "how much are your hoodies?" without searching
    first. Quote these numbers rather than any price you remember.

    Reads: catalogue.price and catalogue.garment_type for all 102 products.
    """
    products = load_products(ctx.deps.db_path, limit=500)

    by_category: dict[str, list[float]] = {}
    for p in products:
        by_category.setdefault(p.category, []).append(p.price)

    return PriceGuide(
        categories={
            category: CategoryPrices(
                count=len(prices), min_price=min(prices), max_price=max(prices)
            )
            for category, prices in by_category.items()
        },
        overall_min=min(p.price for p in products),
        overall_max=max(p.price for p in products),
    )


def find_similar(ctx: RunContext[ChatDeps], product_id: str, limit: int = 4) -> list[ProductMatch]:
    """Find products similar to one the shopper is already looking at.

    Ranks other products by shared search tags, favouring the same category.
    Use it for "what else goes with this?" and - more importantly - to offer a
    real alternative when something is sold out in their size.

    Reads: catalogue.search_tags and .garment_type to rank, then the same fields
    as search_products for the results.

    Args:
        product_id: The catalogue slug to match against.
        limit: How many to return (1-8).
    """
    related = load_related(ctx.deps.db_path, product_id, limit=max(1, min(limit, 8)))
    return [
        ProductMatch(
            product_id=p.product_id,
            name=p.name,
            category=p.category,
            garment_type=p.garment_type,
            price=p.price,
            colors=p.colors,
            image_url=p.image_url,
            in_stock_sizes=_in_stock_sizes(ctx.deps.db_path, p.product_id),
        )
        for p in related
    ]


def get_catalogue_overview(ctx: RunContext[ChatDeps]) -> dict[str, int]:
    """How many products we carry in each category.

    Use this for "what do you sell?" or "how big is your selection?" before
    listing anything, so the shape of the answer matches the real catalogue.

    Reads: catalogue.garment_type across all products.
    """
    return {c.category: c.count for c in load_categories(ctx.deps.db_path)}


#: Registered on the Agent in agent.py.
AGENT_TOOLS = [
    search_products,
    get_product_details,
    check_stock,
    get_price_guide,
    find_similar,
    get_catalogue_overview,
]
