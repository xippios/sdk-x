"""The package's one configured ``AsyncClient`` and its error mapping (conventions §6)."""

import json
import time

import httpx
from xippios.core import (
    AsyncClient,
    BearerAuth,
    ClientConfig,
    InvalidRequestError,
    NotFoundError,
    RateLimit,
    RateLimitError,
    XippiosError,
)

from xippios.x._version import __version__

SOURCE = "x"
BASE_URL = "https://api.x.com/2"
API_KEY_ENV = "X_API_KEY"  # pragma: allowlist secret (a variable name, not a key)
# A self-imposed pace (ADR-0010 decision 1): X documents no per-minute limit, only
# per-endpoint windows of 15 minutes per app (docs/upstream/pages/rate-limits.md), and a
# 1/sec limit on two endpoints this package does not wrap (GET /2/tweets/search/all and
# GET /2/spaces/by/creator_ids). The windows are spent, not rationed (ADR-0010 decision 2):
# classify turns their 429 into RateLimitError with retry_after (coordination row 304).
RATE_LIMIT = RateLimit(per_minute=60, burst=1)

RATE_LIMIT_WINDOW = 900.0
"""Seconds of X's per-endpoint rate-limit window, 15 minutes (``pages/rate-limits.md``).

The wait ``classify`` gives a 429 whose ``x-rate-limit-reset`` is missing or unreadable.
"""
BILLING_CYCLE = 31 * 86_400.0
"""Seconds of the longest monthly billing cycle, 31 days: the wait of a ``usage-capped``.

X blocks requests "until the next billing cycle" once a spending limit is reached, and
caps pay-per-usage plans per "monthly billing cycle" (``pages/pricing.md``); its answer
does not say when the cycle starts, so the wait is the longest a cycle can last.
"""

_INVALID_REQUEST = frozenset({"invalid-request"})
_NOT_FOUND = frozenset({"resource-not-found"})
_RATE_LIMITED = frozenset({"rate-limit-exceeded"})
_USAGE_CAPPED = frozenset({"usage-capped"})
_SNIPPET = 300


def _payload(response: httpx.Response) -> dict[str, object]:
    """The body as a JSON object, else an empty mapping."""
    try:
        payload = json.loads(response.content)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _problem_type(payload: dict[str, object]) -> str | None:
    """The last segment of the problem's ``type`` URI, e.g. ``"invalid-request"``.

    X writes the URI on either host (``https://api.x.com/2/problems/...``, and
    ``https://api.twitter.com/2/problems/...`` in the OpenAPI document's rule problems),
    so only the segment is compared. A body without ``type`` gives the type of its first
    ``errors`` entry that has one, else ``None``.
    """
    candidates: list[object] = [payload.get("type")]
    errors = payload.get("errors")
    if isinstance(errors, list):
        candidates += [item.get("type") for item in errors if isinstance(item, dict)]
    for value in candidates:
        if isinstance(value, str) and value:
            return value.rstrip("/").rsplit("/", 1)[-1]
    return None


def _details(payload: dict[str, object]) -> str:
    """Upstream's words: ``title``, ``detail`` and each ``errors`` entry's message or detail."""
    parts = [
        str(payload[name])
        for name in ("title", "detail")
        if isinstance(payload.get(name), str) and payload[name]
    ]
    errors = payload.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if not isinstance(item, dict):
                continue
            text = item.get("message") or item.get("detail")
            if isinstance(text, str) and text and text not in parts:
                parts.append(text)
    joined = " ".join("; ".join(parts).split())
    return joined[:_SNIPPET]


def _where(response: httpx.Response) -> str:
    # Method and path only: the query is never quoted (conventions §5, ADR-0005).
    return f"{response.request.method} {response.request.url.path}"


def _until_reset(response: httpx.Response) -> float:
    """Seconds until ``x-rate-limit-reset``, a Unix timestamp, never negative.

    ``RATE_LIMIT_WINDOW``, the 15-minute window, when the header is missing or is not
    ASCII digits.
    """
    reset = response.headers.get("x-rate-limit-reset", "").strip()
    if not (reset.isascii() and reset.isdigit()):
        return RATE_LIMIT_WINDOW
    return max(0.0, float(reset) - time.time())


def classify(response: httpx.Response) -> XippiosError | None:
    """X's documented error answers as taxonomy errors, else ``None`` (conventions §5, §6).

    The ``ClientConfig.classify`` hook: it sees every response before core's status
    mapping. X answers an error as ``application/problem+json`` (the OpenAPI document's
    ``Problem``: ``type``, ``title``, ``detail``) or as ``{"errors": [{"code",
    "message"}]}`` (its ``Error``; the 429 of ``pages/rate-limits.md``, ``code: 88``);
    the problem types are those of ``pages/response-codes-and-errors.md``, compared by
    the URI's last segment. A 2xx is never an error here: a 200 that carries ``errors``
    beside or instead of ``data`` is a partial answer the wrappers return as the page
    (the page's "Partial errors").

    - A ``usage-capped`` problem, at any 4xx status: ``RateLimitError`` with
      ``retry_after`` ``BILLING_CYCLE``, since the cap holds until the next billing
      cycle, whose start the answer does not give.
    - A 429, or a ``rate-limit-exceeded`` problem at any 4xx: ``RateLimitError`` with
      ``retry_after`` the seconds until ``x-rate-limit-reset`` (a Unix timestamp; never
      negative), else ``RATE_LIMIT_WINDOW`` (900 s). Retries wait it out up to the
      policy's ``backoff_max``; beyond that the error reaches the caller (ADR-0010).
    - A 400, or an ``invalid-request`` problem at any 4xx: ``InvalidRequestError`` with
      upstream's words, since the caller has to change the request (ADR-0007).
    - A 404, or a ``resource-not-found`` problem at any 4xx: ``NotFoundError``.
    - Everything else falls through to core's mapping: a 401 or 403 becomes
      ``AuthError`` (the keyless and the wrong-key 401 answer ``Unauthorized``), a 5xx
      ``UpstreamError``, retried.
    """
    status = response.status_code
    if status < 400:
        return None
    payload = _payload(response)
    kind = _problem_type(payload)
    details = _details(payload)
    said = f": {details}" if details else ""
    where = _where(response)
    if kind in _USAGE_CAPPED and status < 500:
        return RateLimitError(
            f"X usage cap reached (HTTP {status} from {where}){said}. Requests are blocked "
            "until the next billing cycle; the Developer Console shows the cycle and the "
            "spending limit.",
            retry_after=BILLING_CYCLE,
            source=SOURCE,
        )
    if status == 429 or (kind in _RATE_LIMITED and status < 500):
        wait = _until_reset(response)
        return RateLimitError(
            f"X rate limit reached (HTTP {status} from {where}){said}. The endpoint's "
            f"15-minute window resets in {wait:.0f} s.",
            retry_after=wait,
            source=SOURCE,
        )
    if status == 400 or (kind in _INVALID_REQUEST and status < 500):
        return InvalidRequestError(
            f"X refused the request (HTTP {status} from {where}){said}", source=SOURCE
        )
    if status == 404 or (kind in _NOT_FOUND and status < 500):
        return NotFoundError(f"X found nothing (HTTP {status} from {where}){said}", source=SOURCE)
    return None


config = ClientConfig(
    source=SOURCE,
    version=__version__,
    base_url=BASE_URL,
    rate_limit=RATE_LIMIT,
    classify=classify,
)

# No QuotaPolicy (Johannes, 2026-10-29): one policy per client cannot track X's
# per-endpoint windows, so a 429 is answered by classify alone.

# The key is read from the environment on the first request, never at import.
auth = BearerAuth(API_KEY_ENV, source=SOURCE)
client = AsyncClient(config, auth=auth)

__all__ = [
    "API_KEY_ENV",
    "BASE_URL",
    "BILLING_CYCLE",
    "RATE_LIMIT",
    "RATE_LIMIT_WINDOW",
    "SOURCE",
    "auth",
    "classify",
    "client",
    "config",
]
