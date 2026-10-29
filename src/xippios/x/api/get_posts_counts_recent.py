"""``GET /2/tweets/counts/recent``, operation ``getPostsCountsRecent``: post counts, seven days.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/tweets/counts/recent.get``:
``query`` (1 to 4,096 characters; ``pages/post-counts.md`` and ``pages/rate-limits.md`` say
512), ``start_time`` ("Must be within the last 7 days", which X checks) and ``end_time``
(RFC 3339), ``next_token`` and ``pagination_token`` ("At most one of ``pagination_token``,
``next_token`` may be provided"), ``granularity`` (``minute``, ``hour``, ``day``; ``hour``
when omitted); the answer ``GetPostsCountsRecentResponse``: ``data`` (``start``, ``end``,
``post_count``), ``meta`` (``next_token``, ``total_post_count``). The document's
``since_id``, ``until_id`` and ``search_count.fields`` are not wrapped, as for
``getPostsCountsAll``: no task needs them yet. Collecting the pages is the task layer's.

Recorded on 2026-10-29 (``usda_by_day``): eight buckets by day, oldest first, the last
ending shortly before the time of the request and the first starting seven days before
that end, so both are partial days; no ``next_token``; X answers ``tweet_count`` and
``total_tweet_count``, which the models read as the document's ``post_count`` and
``total_post_count``, the total the sum of the buckets. ``granularity=week`` is refused
before the call; X answers it with HTTP 400 (``granularity_week``). Price: 0.005 USD a
request, every request, since counts are not deduplicated (``pages/pricing.md``); X
reported ``x-rate-limit-limit: 300``, as ``pages/rate-limits.md`` lists.
"""

from datetime import datetime

from xippios.core import parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import at_most_one, chosen, instant, text
from xippios.x.models import GetPostsCountsRecentResponse, Granularity

__all__ = ["get_posts_counts_recent"]


async def get_posts_counts_recent(
    query: str,
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    next_token: str | None = None,
    pagination_token: str | None = None,
    granularity: Granularity | None = None,
) -> GetPostsCountsRecentResponse:
    """``getPostsCountsRecent``: counts of X posts of the last seven days matching a query.

    Args:
        query: ``query``, a search query of 1 to 4,096 characters, e.g. ``"from:USDA"``
            or ``"from:USDA -is:retweet -is:reply"``.
        start_time: ``start_time``, the oldest time counted, a datetime with a zone within
            the last seven days, e.g. ``datetime(2026, 10, 27, tzinfo=UTC)``.
        end_time: ``end_time``, the newest time counted, likewise.
        next_token: ``next_token``, the ``meta.next_token`` of the page before; give it or
            ``pagination_token``, not both.
        pagination_token: ``pagination_token``, the same token under the other name X
            takes.
        granularity: ``granularity``, ``Granularity.DAY``, ``Granularity.HOUR`` (X's
            default) or ``Granularity.MINUTE``.

    Returns:
        One page: the buckets in ``data``, oldest first, and ``meta.total_post_count``
        across them.

    Raises:
        InvalidRequestError: A value outside the document's bounds, both tokens, refused
            before the call, or X's HTTP 400.
        AuthError: X refused the key in ``X_API_KEY`` (HTTP 401).
        RateLimitError: The operation's 15-minute window is spent, ``retry_after`` set.
    """
    params = {"query": text("query", query, max_length=4096)}
    if start_time is not None:
        params["start_time"] = instant("start_time", start_time)
    if end_time is not None:
        params["end_time"] = instant("end_time", end_time)
    at_most_one(next_token=next_token, pagination_token=pagination_token)
    if next_token is not None:
        params["next_token"] = text("next_token", next_token)
    if pagination_token is not None:
        params["pagination_token"] = text("pagination_token", pagination_token)
    if granularity is not None:
        params["granularity"] = chosen("granularity", [granularity], Granularity)
    raw = await client.get_json("/tweets/counts/recent", params=params)
    return parse(GetPostsCountsRecentResponse, raw, source=SOURCE, endpoint="getPostsCountsRecent")
