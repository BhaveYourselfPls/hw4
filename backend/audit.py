"""Append-only audit trail for agent-loop activity.

Every run of the merch agent writes one record to `output/audit_trail.json`:
what was asked, which tools the agent called with what arguments, what came
back, how long it took, and anything the safety layer had to stop.

## Why the file is JSON Lines

The file holds **one complete JSON object per line**, not a single JSON array.
That is a deliberate choice and it is what makes "append-only" true rather than
aspirational:

* A JSON array has to be closed with `]`. Appending to one means reading the
  whole file, parsing it, rewriting it — a read-modify-**write** cycle. Every
  append is an opportunity to lose the file, and a crash mid-write truncates
  everything ever recorded.
* With one object per line, an append is `open(path, "a")` and a single
  `write()`. Nothing existing is ever read, moved, or rewritten. A crash can
  at worst leave one partial trailing line; every record before it survives.

The extension stays `.json` as specified. Each line parses as JSON on its own,
and `read_entries()` below returns the whole thing as a list.

## Why entries are hash-chained

Append-only is a property of the code, not of the filesystem — anyone with an
editor can delete a line. So each record carries the SHA-256 of the record
before it. Removing, reordering or editing any line breaks the chain from that
point on, and `verify_chain()` reports exactly where. The log cannot be made
un-tamperable, but tampering cannot be made invisible.

## What is never written

No passwords, no password hashes, no session tokens, no email addresses. Users
appear as a numeric `user_id` only; guests as `null`.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
AUDIT_DIR = PROJECT_ROOT / "output"
AUDIT_PATH = AUDIT_DIR / "audit_trail.json"

#: Messages are truncated before they are written. Long enough to audit what
#: was asked, short enough that the log does not become a content archive.
MAX_TEXT = 500

GENESIS = "genesis"

# Appends are serialized so two concurrent requests cannot interleave a line.
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _digest(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _truncate(text: str | None, limit: int = MAX_TEXT) -> str:
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _tail() -> tuple[int, str]:
    """(sequence number, hash) of the last record, without reading the whole file.

    Seeks to the end and walks backwards for the final newline, so the cost does
    not grow with the size of the log.
    """
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return 0, GENESIS

    with AUDIT_PATH.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        end = handle.tell()
        block = min(8192, end)
        handle.seek(end - block)
        chunk = handle.read(block).decode("utf-8", errors="replace")

    lines = [line for line in chunk.splitlines() if line.strip()]
    if not lines:
        return 0, GENESIS

    last = lines[-1]
    try:
        record = json.loads(last)
    except ValueError:
        # A partial trailing line from an interrupted write. Chain from it
        # anyway so the break is visible rather than silently healed.
        return 0, _digest(last)

    return int(record.get("seq", 0)), _digest(last)


def log_event(event: str, **fields: Any) -> dict:
    """Append one record. Never raises into the request path.

    Auditing must not be able to take the site down: if the log cannot be
    written, the failure is reported in the return value and the caller carries
    on serving the shopper.
    """
    with _lock:
        try:
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            seq, prev_hash = _tail()

            record = {
                "seq": seq + 1,
                "ts": _now(),
                "event": event,
                **fields,
                "prev_hash": prev_hash,
            }
            line = json.dumps(record, ensure_ascii=False, sort_keys=False)

            # "a" is the only mode this module ever opens the file with. On
            # POSIX, O_APPEND makes each write atomic at the end of the file.
            with AUDIT_PATH.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

            return record
        except Exception as exc:  # noqa: BLE001 - auditing must never 500 a request
            return {"event": event, "audit_error": str(exc)}


def log_agent_turn(
    *,
    user_id: int | None,
    message: str,
    page: dict | None,
    model: str,
    tool_calls: list[dict],
    reply_text: str,
    product_ids: list[str],
    dropped_product_ids: list[str],
    latency_ms: int,
    usage: dict | None = None,
) -> dict:
    """Record one complete pass of the agent loop."""
    return log_event(
        "agent_turn",
        user_id=user_id,
        authenticated=user_id is not None,
        model=model,
        page=page or {},
        request={"message": _truncate(message), "message_chars": len(message or "")},
        loop={
            "tool_calls": tool_calls,
            "tool_count": len(tool_calls),
            "tool_names": [call["tool"] for call in tool_calls],
        },
        response={
            "message": _truncate(reply_text),
            "message_chars": len(reply_text or ""),
            "product_ids": product_ids,
            "product_count": len(product_ids),
        },
        safety={
            # Products the model named that are not in the catalogue. A non-empty
            # list here is the signal that the grounding layer did real work.
            "dropped_product_ids": dropped_product_ids,
            "hallucinated_products": len(dropped_product_ids),
        },
        usage=usage or {},
        latency_ms=latency_ms,
    )


def log_safety_event(event: str, **fields: Any) -> dict:
    """Record something the safety layer refused or limited."""
    return log_event(event, **fields)


def read_entries() -> list[dict]:
    """The whole trail as a list. Skips any partial trailing line."""
    if not AUDIT_PATH.exists():
        return []

    entries: list[dict] = []
    with AUDIT_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    return entries


def verify_chain() -> dict:
    """Walk the hash chain and report the first break, if any."""
    if not AUDIT_PATH.exists():
        return {"ok": True, "entries": 0, "note": "No audit trail yet."}

    expected_prev = GENESIS
    expected_seq = 1
    count = 0

    with AUDIT_PATH.open("r", encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except ValueError:
                return {"ok": False, "entries": count, "broken_at_line": number,
                        "reason": "Line is not valid JSON."}

            if record.get("prev_hash") != expected_prev:
                return {"ok": False, "entries": count, "broken_at_line": number,
                        "seq": record.get("seq"),
                        "reason": "prev_hash does not match the previous record — "
                                  "a line was edited, removed or reordered."}
            if record.get("seq") != expected_seq:
                return {"ok": False, "entries": count, "broken_at_line": number,
                        "reason": f"Expected seq {expected_seq}, found {record.get('seq')}."}

            expected_prev = _digest(raw)
            expected_seq += 1
            count += 1

    return {"ok": True, "entries": count, "note": "Hash chain intact."}


if __name__ == "__main__":  # `python audit.py` prints a summary
    result = verify_chain()
    print(json.dumps(result, indent=2))
    entries = read_entries()
    if entries:
        turns = [e for e in entries if e.get("event") == "agent_turn"]
        print(f"\n{len(entries)} records, {len(turns)} agent turns")
        print(f"first: {entries[0]['ts']}")
        print(f"last:  {entries[-1]['ts']}")
