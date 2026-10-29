"""``GET /2/tweets/counts/all``, operation ``getPostsCountsAll``: post counts over the archive.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/tweets/counts/all.get``:
``query`` (1 to 4,096 characters; ``pages/post-counts.md`` says 1,024 outside Enterprise),
``start_time``, ``end_time`` (RFC 3339), ``next_token`` and ``pagination_token`` ("At most
one of ``pagination_token``, ``next_token`` may be provided"), ``granularity`` (``minute``,
``hour``, ``day``; ``hour`` when omitted); the answer ``GetPostsCountsAllResponse``:
``data`` (``start``, ``end``, ``post_count``), ``meta`` (``next_token``,
``total_post_count``). A page spans 31 days, at any granularity (``pages/post-counts.md``).
The document's ``since_id``, ``until_id`` and ``search_count.fields`` are not wrapped: no
task needs them yet. Collecting the pages is the task layer's.

Recorded on 2026-10-29 (``usda_by_day``, ``usda_by_day_page_2``, ``usda_originals_by_day``):
the first page holds the 31 days up to the request, its buckets oldest first, the newest
ending at the time of the request, and its ``next_token`` leads to the 31 days before; X
answers ``tweet_count`` and ``total_tweet_count``, the guides' spelling
(``pages/post-counts.md``), which the models read as the document's ``post_count`` and
``total_post_count``; ``total_tweet_count`` is the sum of the page's buckets.
``granularity=week`` is refused before the call; X answers it with HTTP 400
(``granularity_week``). Price: 0.010 USD a request, every request, since counts are not
deduplicated (``pages/pricing.md``); X reported ``x-rate-limit-limit: 300``, as
``pages/rate-limits.md`` lists.
"""

from datetime import datetime

from xippios.core import InvalidRequestError, parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import chosen, instant, text
from xippios.x.models import GetPostsCountsAllResponse, Granularity

__all__ = ["get_posts_counts_all"]


async def get_posts_counts_all(
    query: str,
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    next_token: str | None = None,
    pagination_token: str | None = None,
    granularity: Granularity | None = None,
) -> GetPostsCountsAllResponse:
    """``getPostsCountsAll``: one page of counts of X posts matching a query, by bucket.

    Args:
        query: ``query``, a search query of 1 to 4,096 characters, e.g. ``"from:USDA"``
            or ``"from:USDA -is:retweet -is:reply"``.
        start_time: ``start_time``, the oldest time counted, a datetime with a zone, e.g.
            ``datetime(2026, 7, 31, tzinfo=UTC)``.
        end_time: ``end_time``, the newest time counted, likewise.
        next_token: ``next_token``, the ``meta.next_token`` of the page before, e.g.
            ``"1jzu9lk96azp0b3x7888hrpw9huhi71ue3rvqfrhj98d"``; give it or
            ``pagination_token``, not both.
        pagination_token: ``pagination_token``, the same token under the other name X
            takes.
        granularity: ``granularity``, ``Granularity.DAY``, ``Granularity.HOUR`` (X's
            default) or ``Granularity.MINUTE``.

    Returns:
        One page: the buckets in ``data``, ``meta.total_post_count`` across them and
        ``meta.next_token`` for the 31 days before.

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
    if next_token is not None and pagination_token is not None:
        raise InvalidRequestError(
            "give next_token or pagination_token, not both: at most one may be provided",
            source=SOURCE,
        )
    if next_token is not None:
        params["next_token"] = text("next_token", next_token)
    if pagination_token is not None:
        params["pagination_token"] = text("pagination_token", pagination_token)
    if granularity is not None:
        params["granularity"] = chosen("granularity", [granularity], Granularity)
    raw = await client.get_json("/tweets/counts/all", params=params)
    return parse(GetPostsCountsAllResponse, raw, source=SOURCE, endpoint="getPostsCountsAll")
