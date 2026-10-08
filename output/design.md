# Design — "The Broadway Archive"

A creative direction for Campus Customs, and the commercial case for it.

Everything stays inside the black / white / Yale-blue palette. The imagination
is in **structure, typography and what the data is allowed to say** — not in
extra colors or decoration for its own sake.

---

## The idea

Campus Customs is a fifty-year-old print shop on one corner of Broadway. The
previous design was clean but anonymous — it could have been any Shopify store.
This direction treats the shop like what it is: **an archive with a date on it**.

Three principles:

1. **The shop's age is the hero.** 1975 is the most valuable thing Campus
   Customs owns and the hardest thing for a competitor to copy. So the founding
   year is set as architecture, not a footnote.
2. **Editorial, not e-commerce.** A serif display face against plain sans copy,
   hairline rules, oversized outlined numerals. It reads like a well-set program
   or a varsity banner rather than a product feed.
3. **The data should talk.** The catalogue knows exactly how many of each size
   are on a shelf. Most of the creative energy went into *surfacing* that,
   because it is the difference between a catalogue and a shop.

---

## What was built

### 1. "Your size" — the personalization spine

**The single most important change.** Files: `src/size.tsx`,
`src/components/SizeBar.tsx`, plus badges across the card, grid and detail page.

Stock in this catalogue exists **only per size**, and roughly a quarter of all
size rows sit at zero. A shopper browsing without a size is reading a catalogue
where a large share of what they see is not actually buyable *by them*. They
find that out one product page at a time — which is exactly where people give up.

A blue strip under the nav asks once: **"What size do you wear? We'll show you
what's actually in stock for you."** One click, and the whole store changes:

- **Every product card gets a live availability badge** read from real
  inventory — *In stock in XL* (blue), *Only 2 left in XL* (amber), *Sold out in
  XL* (grey).
- **Sold-out-for-you products dim** rather than disappear — someone may still be
  shopping for a gift.
- **An "✦ In my size (XL)" filter** on the Products page. In testing, Hoodies
  went from **27 products to 21 actually buyable in XL**.
- **Product pages open pre-selected on your size**, not the first available one,
  with a dot marking it among the six buttons.
- **The chat assistant receives it too.** Asked "I need a warm layer for the
  tailgate", it answered *"these warm layers are available in **XL**"* and
  listed three with exact counts — **without ever asking what size you wear.**

The preference is stored locally, so it works for guests and survives a return
visit with no account.

### 2. The Game countdown

File: `src/components/GameCountdown.tsx`

A live clock on the homepage counting down to Harvard–Yale, with a "Shop The
Game" link. The date is **computed, not hardcoded** — the Saturday before the
fourth Thursday in November — so it never goes stale and rolls to next year the
moment the game passes.

### 3. The editorial system

File: `src/index.css`

- **Playfair Display** for headlines against Inter for copy — the look of a
  printed program, and a deliberate contrast with the flat-sans default of every
  competitor.
- **"1975" set at up to 380px** behind the hero as a hollow outline; the footer
  closes the loop with "NEW HAVEN" in the same treatment.
- **A scrolling ribbon** of the catalogue's own vocabulary — *Residential
  Colleges · Varsity Sports · Yale Mom · The Game · Screen Printed In-House* —
  which doubles as a plain-language index of what the store covers. Respects
  `prefers-reduced-motion`.
- **A paper grain** over the whole page: one inline SVG of fractal noise at 3.5%
  opacity, no network request, so white areas read as stock rather than screen.
- **Hairline-prefixed eyebrows**, filing-card tiles with a blue top rule, and
  tabular-lining numerals so prices align in a column.

---

## Why this increases retention and purchases

### It removes the most common reason a sale dies

The failure mode in this catalogue is specific and measurable: a shopper falls
for something, clicks through, and finds their size gone. One in four size rows
is at zero, so this is routine, not rare. Every time it happens the shopper
absorbs a small disappointment and spends attention on something they could
never have bought.

The size badges move that information **from the end of the journey to the
beginning**. Nobody clicks into a dead end. The "In my size" filter goes further
and shows a catalogue where *everything* is purchasable — in the hoodie test,
21 real options instead of 27 maybes. A shopper browsing only things they can
buy converts at a strictly higher rate than one browsing a mix, because every
click can end in a purchase.

### It converts scarcity into a reason to act now

*"Only 2 left in XL"* is honest — it comes straight from `inventory.quantity` —
and it is the oldest motivator in retail. Crucially this store **cannot fake
it**, because the badge is generated from the same number the stock endpoint
returns. The urgency is real, which is also why it keeps working: a shopper who
acts on it and finds it was true learns to trust the next one.

### It gives people a reason to come back on a particular day

A storefront with no calendar gives nobody a reason to return on any specific
date. The countdown attaches the shop to the one date every Yale shopper already
has an opinion about, and it is **different every time you load it**. That is a
retention mechanic that costs nothing to run and renews itself annually.

### It makes the assistant feel like staff rather than search

Because the chat knows the saved size, it skips the question every other chatbot
asks and answers with what fits. "These are available in XL — one has only 2
left" is what a person behind a counter says. Combined with the saved history
from Problem 8, a returning shopper gets an assistant that knows their name,
their size, and what they looked at last time. That accumulated context is
switching cost: starting over somewhere else means re-explaining yourself.

### The age does commercial work

Most campus merch is interchangeable, so the buying decision collapses to price.
"Fifty years on the same corner," the 1975 numeral, and "printed in our own shop
next door" reframe it as provenance — the same move that lets a heritage brand
hold price instead of discounting. It also gives parents and alumni, who are the
higher-spending half of this catalogue, something to feel about the purchase
beyond the garment.

### Honest taste signals quality

The grain, the serif, the tabular numerals and the restraint to stay in three
colors all say the same thing: someone cares here. Shoppers read production
quality as product quality — for a store whose pitch is *we print this
ourselves*, looking carefully made is part of the argument.

---

## What it looks like in practice

| Before | After |
|---|---|
| "Yale pride, printed on Broadway" over flat black | "Fifty years on the same **corner**" with 1975 set 380px tall behind it |
| Product card: photo, name, price | …plus *Only 2 left in XL*, read from live inventory |
| Products page: 27 hoodies, some unbuyable | "✦ In my size (XL)" → 21, every one purchasable |
| Detail page opens on the first in-stock size | Opens on **your** size, marked with a dot |
| Chat: "What size do you wear?" | "These warm layers are available in **XL**…" |
| Homepage identical every visit | A countdown that is different every second |

---

## Verification

| Element | Checked |
|---|---|
| Size strip | Choosing XL switched the bar to "Showing availability in your size XL" |
| Fit badges | Home grid rendered *Only 2 left in XL*, *In stock in XL*, *Sold out in XL*; 2 cards dimmed |
| "In my size" filter | Hoodies 27 → 21, zero sold-out badges remaining, URL `?category=Hoodies&fits=1` |
| Detail page | Opened pre-selected on `XL(mine)(selected)`, "Only 2 left in XL.", CTA "Add XL to bag" |
| Size-aware chat | Led with XL availability and exact counts, never asked the size |
| Countdown | Live clock reading 44 days / 15 hrs / 34 min / 19 sec to The Game |
| Accessibility | Marquee honours `prefers-reduced-motion`; badges are text, not color alone |

`tsc --noEmit` and `npm run build` clean; backend still starts with
`uvicorn main:app --reload --port 8000` from `backend/`.
