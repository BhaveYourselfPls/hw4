"""Shared Pydantic types for Campus Customs.

Three groups live here:

* **Catalogue** shapes returned by the product endpoints.
* **Auth** shapes for signup / login.
* **Agent** shapes — the dependencies the tools read, the structured product
  payload the assistant returns alongside its prose, and the chat request /
  response envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------


class SizeStock(BaseModel):
    size: str
    quantity: int
    in_stock: bool


class ProductSummary(BaseModel):
    product_id: str
    name: str
    garment_type: str
    category: str
    colors: list[str]
    price: float
    image_url: str
    #: Stock per size, carried on the list payload so the storefront can show
    #: availability on a card without a second request per product.
    stock_by_size: dict[str, int] = Field(default_factory=dict)


class ProductDetail(ProductSummary):
    description: str
    search_tags: list[str]
    sizes: list[SizeStock]
    total_quantity: int
    available_sizes: list[str]


class CategoryCount(BaseModel):
    category: str
    count: int


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


class SignupRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class User(BaseModel):
    """Public user shape. Deliberately has no `password_hash` field, so the hash
    cannot reach an API response, a log, or a model prompt."""

    id: int
    first_name: str | None
    last_name: str | None
    name: str
    email: str
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: User


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------


@dataclass
class ChatDeps:
    """Everything the agent's tools need at run time.

    Passed to `agent.run(..., deps=...)` and reachable inside every tool as
    `ctx.deps`. The user fields are how the assistant can greet someone by name
    without the model ever querying the users table itself; the page fields are
    how "do you have this in pink?" resolves to an actual product.
    """

    db_path: Path
    user_id: int | None = None
    user_name: str | None = None
    #: Whether this shopper has talked to us before — lets the agent say
    #: "welcome back" rather than re-introducing itself.
    returning: bool = False
    #: The product page the shopper is on right now, if any.
    page_product_id: str | None = None
    page_product_name: str | None = None
    page_label: str | None = None
    #: The size the shopper saved, so answers can be about what fits them.
    preferred_size: str | None = None


class ProductCard(BaseModel):
    """A matched product the UI renders as a card beside the reply.

    Carries the full `ProductSummary` field set plus a `note`, so the front end
    can render these with the *same* card component the Products page uses —
    identical look, identical click-through to the product page. Mirrors the
    `products_json` column on `chat_messages`, so a turn can be persisted and
    replayed without reshaping it.

    The model only needs to supply `product_id` and `note`; the server fills the
    rest from the catalogue.
    """

    product_id: str
    note: str = Field(default="", description="Short reason this item matched, e.g. 'navy, in L'")
    name: str = ""
    price: float = 0.0
    image_url: str = ""
    category: str = ""
    garment_type: str = ""
    colors: list[str] = Field(default_factory=list)


class ChatReply(BaseModel):
    """The agent's structured output: prose plus the items it is pointing at."""

    message: str = Field(description="The reply to show the shopper, in Markdown.")
    products: list[ProductCard] = Field(
        default_factory=list,
        description="Products referenced in the reply. Empty when none are relevant.",
    )


# --------------------------------------------------------------------------
# Tool return types
# --------------------------------------------------------------------------
#
# Every tool returns one of these rather than a loose dict. Two reasons:
# Pydantic AI shows the model a schema for what comes back, so it knows which
# fields exist; and the field names here are the ones the assistant is expected
# to quote, which keeps answers anchored to real columns.


class ProductMatch(BaseModel):
    """One search hit. Compact on purpose — details come from a follow-up call."""

    product_id: str = Field(description="Catalogue slug. Use in other tools, never show it.")
    name: str
    category: str
    garment_type: str
    price: float = Field(description="US dollars, from catalogue.price.")
    colors: list[str] = Field(description="Every color this item comes in. No others exist.")
    image_url: str
    in_stock_sizes: list[str] = Field(description="Sizes with at least one unit on hand.")


class ProductFacts(BaseModel):
    """Everything the catalogue and inventory know about one product."""

    product_id: str
    name: str
    category: str
    garment_type: str
    description: str = Field(description="Cut, color, graphic and details, from the catalogue.")
    colors: list[str] = Field(description="The complete color list. Anything else is a no.")
    search_tags: list[str]
    price: float
    image_url: str
    stock_by_size: dict[str, int] = Field(description="Units on hand, per size.")
    available_sizes: list[str]
    sold_out_sizes: list[str]
    total_quantity: int


class SizeAvailability(BaseModel):
    """Stock for one product, optionally narrowed to a single size."""

    product_id: str
    name: str
    size: str | None = Field(default=None, description="The size asked about, if one was.")
    quantity: int | None = Field(default=None, description="Units on hand in that size.")
    in_stock: bool | None = None
    low_stock: bool | None = Field(default=None, description="True when 1-5 left — worth saying.")
    stock_by_size: dict[str, int] = Field(default_factory=dict)
    available_sizes: list[str] = Field(default_factory=list)
    sold_out_sizes: list[str] = Field(default_factory=list)
    total_quantity: int = 0
    error: str | None = Field(default=None, description="Set when the lookup failed; say so plainly.")


class CategoryPrices(BaseModel):
    count: int
    min_price: float
    max_price: float


class PriceGuide(BaseModel):
    """Price range per category across the catalogue."""

    categories: dict[str, CategoryPrices]
    overall_min: float
    overall_max: float
    note: str = Field(
        default="Price is set by garment type, so items in a category usually share one price.",
    )


class ToolError(BaseModel):
    """Returned instead of data when a lookup cannot be completed."""

    error: str
    hint: str = ""


class ChatTurn(BaseModel):
    """One prior message, replayed into the model to keep context."""

    role: str  # "user" | "assistant"
    content: str


class PageContext(BaseModel):
    """Where the shopper is on the site when they send a message.

    Lets "do you have this in pink?" resolve to an actual product instead of a
    guess. Sent by the front end on every turn.
    """

    path: str = Field(default="", description="Route the shopper is on, e.g. /products")
    product_id: str | None = Field(default=None, description="Product page they are viewing.")
    category: str | None = Field(default=None, description="Category filter in effect.")
    preferred_size: str | None = Field(
        default=None, description="The size the shopper saved on the site, e.g. L."
    )


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    #: Only used for guests. Signed-in shoppers have their history read from the
    #: database, so the server never trusts the client for a stored conversation.
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    page: PageContext | None = None


class ChatResponse(BaseModel):
    message: str
    products: list[ProductCard] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    #: True when this turn was written to chat_messages.
    saved: bool = False


class StoredMessage(BaseModel):
    """One persisted turn, replayed into the panel when a shopper returns."""

    id: int
    role: str
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    created_at: str


class ChatHistory(BaseModel):
    messages: list[StoredMessage] = Field(default_factory=list)
