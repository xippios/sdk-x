"""``GET /2/usage/tweets``, operation ``getUsage``: the project's Post usage.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/usage/tweets.get``: ``days``
(an integer from 1 to 90, 7 when omitted) and ``usage.fields`` (``UsageFieldsParameter``,
at least one, none twice, comma-separated); the answer ``GetUsageResponse``: ``data``
(``Usage``: ``cap_reset_day``, ``daily_client_app_usage``, ``daily_project_usage``,
``project_cap``, ``project_id``, ``project_usage``) and ``errors``. ``pages/usage.md``
describes the endpoint ("Get Post usage data") with an example whose shape differs from
the document's; the wrapper follows the document, which the recording confirms
(``seven_days``). The usage is the project's, the one the Bearer Token's app belongs to,
not a user's.

Price: ``pages/pricing.md`` (snapshot of 2026-10-29) states none for this operation. Rate
limit: 50 requests per 15 minutes per app (``pages/rate-limits.md``).
"""

from collections.abc import Sequence

from xippios.core import parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import bounded, chosen
from xippios.x.models import GetUsageResponse, UsageField

__all__ = ["get_usage"]


async def get_usage(
    *,
    days: int | None = None,
    usage_fields: Sequence[UsageField] | None = None,
) -> GetUsageResponse:
    """``getUsage``: the Post usage of the app's X project, by day.

    Args:
        days: ``days``, the days of usage to return, from 1 to 90, e.g. ``7``; X's
            default, 7, when omitted.
        usage_fields: ``usage.fields``, the Usage fields to return, e.g.
            ``[UsageField.PROJECT_USAGE, UsageField.DAILY_PROJECT_USAGE]``.

    Returns:
        The answer: the project's usage in ``data``, problems in ``errors``.

    Raises:
        InvalidRequestError: A value outside the document's bounds, refused before the
            call, or X's HTTP 400.
        AuthError: X refused the key in ``X_API_KEY`` (HTTP 401).
        RateLimitError: The operation's 15-minute window is spent, ``retry_after`` set.
    """
    params: dict[str, str] = {}
    if days is not None:
        params["days"] = bounded("days", days, low=1, high=90)
    if usage_fields is not None:
        params["usage.fields"] = chosen("usage.fields", usage_fields, UsageField)
    raw = await client.get_json("/usage/tweets", params=params)
    return parse(GetUsageResponse, raw, source=SOURCE, endpoint="getUsage")
