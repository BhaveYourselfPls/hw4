"""Rate limiting for the endpoints that cost something when abused.

Two endpoints need protection for different reasons:

* **Login and signup** — without a limit, an attacker can guess passwords as
  fast as the server answers. PBKDF2 at 120k iterations makes each attempt
  slow, but not slow enough to be a limit on its own.
* **Chat** — every turn is a paid model call. One loop in a browser console
  could run up a bill against the course budget.

A fixed-window counter in memory, which is the right size of solution here: one
process, one machine, no Redis. The window is per key, so a burst at the end of
one window plus a burst at the start of the next is possible — acceptable for
slowing down abuse rather than enforcing an exact quota.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request


@dataclass
class RateLimit:
    """Allow `limit` requests per `window_seconds` for each key."""

    limit: int
    window_seconds: int
    name: str
    #: key -> (window start, count so far)
    _hits: dict[str, tuple[float, int]] = field(default_factory=dict)

    def check(self, key: str) -> None:
        """Raise 429 if `key` is already over its limit. Does not count."""
        now = time.monotonic()
        started, count = self._hits.get(key, (now, 0))

        if now - started >= self.window_seconds:
            return  # window expired

        if count >= self.limit:
            retry_after = max(1, int(self.window_seconds - (now - started)))
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Too many {self.name} attempts. "
                    f"Please wait {retry_after} seconds and try again."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    def record(self, key: str) -> None:
        """Count one attempt against `key`."""
        now = time.monotonic()
        started, count = self._hits.get(key, (now, 0))

        if now - started >= self.window_seconds:
            started, count = now, 0  # window expired, start a new one

        self._hits[key] = (started, count + 1)

        # Opportunistic cleanup so the dict cannot grow without bound.
        if len(self._hits) > 2048:
            self._hits = {
                k: v for k, v in self._hits.items() if now - v[0] < self.window_seconds
            }

    def enforce(self, key: str) -> None:
        """Check then count — for endpoints where every call is costly."""
        self.check(key)
        self.record(key)

    def reset(self, key: str) -> None:
        """Forget a key — used after a successful login, so one person getting
        their password right does not leave them near the limit."""
        self._hits.pop(key, None)


# Tuned to be invisible to a real shopper and obstructive to a script.
#
# Login counts *failures only* and resets on success, so someone who mistypes
# twice and then gets it right never accumulates anything.
#
# The two login limits are deliberately far apart. Campus and office networks
# put many people behind one address, so a tight per-IP limit would lock out
# a whole building because of one person's bad afternoon. The narrow limit is
# per *email* — that is the one that actually stops an account being guessed at
# — while the per-IP limit is loose enough for shared networks but still caps a
# script sweeping many accounts from one place.
LOGIN_EMAIL_LIMIT = RateLimit(limit=8, window_seconds=300, name="sign-in")
LOGIN_IP_LIMIT = RateLimit(limit=40, window_seconds=300, name="sign-in")
SIGNUP_LIMIT = RateLimit(limit=5, window_seconds=3600, name="account creation")
CHAT_LIMIT = RateLimit(limit=20, window_seconds=300, name="chat")


def client_key(request: Request) -> str:
    """Best-effort client identity: the proxy-forwarded IP, else the socket."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
