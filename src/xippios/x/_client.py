"""The package's one configured ``AsyncClient`` and its error mapping (conventions §6)."""

import httpx
from xippios.core import AsyncClient, BearerAuth, ClientConfig, RateLimit, XippiosError

from xippios.x._version import __version__

SOURCE = "x"
BASE_URL = "https://api.x.com/2"
API_KEY_ENV = "X_API_KEY"  # pragma: allowlist secret (a variable name, not a key)
# A self-imposed pace: upstream documents no per-second or per-minute limit (ADR-0010 decision 1).
RATE_LIMIT = RateLimit(per_minute=60, burst=1)


def classify(response: httpx.Response) -> XippiosError | None:
    """Upstream's documented error shapes as taxonomy errors, else ``None`` (conventions §6).

    The ``ClientConfig.classify`` hook: it sees every response before core's status mapping.
    """
    return None


config = ClientConfig(
    source=SOURCE,
    version=__version__,
    base_url=BASE_URL,
    rate_limit=RATE_LIMIT,
    classify=classify,
)

# A source with a documented hourly or daily quota installs a QuotaPolicy of its own on
# config (conventions §6, ADR-0015); core's README shows how.

# The key is read from the environment on the first request, never at import.
auth = BearerAuth(API_KEY_ENV, source=SOURCE)
client = AsyncClient(config, auth=auth)

__all__ = [
    "API_KEY_ENV",
    "BASE_URL",
    "RATE_LIMIT",
    "SOURCE",
    "auth",
    "classify",
    "client",
    "config",
]
