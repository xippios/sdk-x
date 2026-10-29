"""``GET /2/tweets/search/recent``, operation ``searchPostsRecent``: one page of a recent search.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/tweets/search/recent.get``:
``query`` (1 to 4,096 characters; ``pages/rate-limits.md`` gives 512 as the query length),
``max_results`` (10 to 100, 10 when omitted), ``next_token`` and ``pagination_token``,
``start_time`` ("Must be within the last 7 days", which X checks) and ``end_time``
(RFC 3339), ``since_id`` and ``until_id`` (``^[0-9]{1,19}$``), ``sort_order``
(``recency``, ``relevancy``), ``post.fields``, ``expansions`` and ``user.fields``. "At most
one of ``start_time``, ``since_id`` may be provided. At most one of ``end_time``,
``until_id`` may be provided. At most one of ``pagination_token``, ``next_token`` may be
provided." The answer ``SearchPostsRecentResponse``: ``data``, ``includes``, ``errors``,
``meta`` (``newest_id``, ``oldest_id``, ``result_count``, ``next_token``,
``previous_token``). The document's ``media.fields``, ``poll.fields`` and ``place.fields``
are not wrapped: no task needs them yet, and their objects stay as sent in ``includes``.
Collecting the pages is the task layer's.

Recorded on 2026-10-29 (``usda_ten``, ``usda_ten_page_2``, ``unbalanced_parenthesis``): ten
@USDA Posts a page, newest first without ``sort_order``, ``meta.newest_id`` and
``meta.oldest_id`` the first and last of ``data``, and a ``next_token`` that leads to the
ten before; answered in the document's names with ``post.fields``
(``edit_history_post_ids``, ``repost_count``). Unlike ``getUsersPosts``, the search returns
an edited Post's earlier versions as Posts of their own, each with the whole
``edit_history_post_ids`` (``2115805884466995409`` beside ``2115806101480337475``). A query
X cannot parse is answered with HTTP 400 and its parser's words
(``unbalanced_parenthesis``), ``InvalidRequestError``. Price: 0.005 USD a Post returned
(``pages/pricing.md``); X reported ``x-rate-limit-limit: 450``, as ``pages/rate-limits.md``
lists.
"""

import re
from collections.abc import Sequence
from datetime import datetime

from xippios.core import parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import at_most_one, bounded, chosen, instant, matching, text
from xippios.x.models import (
    PostExpansion,
    PostField,
    SearchPostsRecentResponse,
    SortOrder,
    UserField,
)

__all__ = ["search_posts_recent"]

_POST_ID = re.compile(r"[0-9]{1,19}")


async def search_posts_recent(
    query: str,
    *,
    max_results: int | None = None,
    next_token: str | None = None,
    pagination_token: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    since_id: str | None = None,
    until_id: str | None = None,
    sort_order: SortOrder | None = None,
    post_fields: Sequence[PostField] | None = None,
    expansions: Sequence[PostExpansion] | None = None,
    user_fields: Sequence[UserField] | None = None,
) -> SearchPostsRecentResponse:
    """``searchPostsRecent``: one page of X posts of the last seven days matching a query.

    Args:
        query: ``query``, a search query of 1 to 4,096 characters, e.g. ``"from:USDA"``
            or ``"from:USDA -is:retweet -is:reply"``.
        max_results: ``max_results``, Posts per page from 10 to 100, e.g. ``100``; X's
            default, 10, when omitted.
        next_token: ``next_token``, the ``meta.next_token`` of the page before, as X sent
            it; give it or ``pagination_token``, not both.
        pagination_token: ``pagination_token``, the same token under the other name X
            takes.
        start_time: ``start_time``, the oldest creation time, a datetime with a zone
            within the last seven days, e.g. ``datetime(2026, 10, 27, tzinfo=UTC)``; give
            it or ``since_id``, not both.
        end_time: ``end_time``, the newest creation time, likewise; give it or
            ``until_id``, not both.
        since_id: ``since_id``, return Posts newer than this Post id, e.g.
            ``"2115806101480337475"``.
        until_id: ``until_id``, return Posts older than this Post id, likewise.
        sort_order: ``sort_order``, ``SortOrder.RECENCY`` or ``SortOrder.RELEVANCY``.
        post_fields: ``post.fields``, e.g. ``[PostField.CREATED_AT, PostField.LANG,
            PostField.PUBLIC_METRICS, PostField.CONVERSATION_ID]``.
        expansions: ``expansions``, e.g. ``[PostExpansion.AUTHOR_ID]``, which puts each
            Post's author into ``includes``.
        user_fields: ``user.fields``, the fields of the Users in ``includes``, e.g.
            ``[UserField.CREATED_AT]``.

    Returns:
        One page: the Posts in ``data``, ``meta.next_token`` for the next page,
        ``meta.newest_id`` and ``meta.oldest_id``.

    Raises:
        InvalidRequestError: A value outside the document's bounds, two parameters of
            which it allows one, refused before the call, or X's HTTP 400 (a query it
            cannot parse, a ``start_time`` older than seven days).
        AuthError: X refused the key in ``X_API_KEY`` (HTTP 401).
        RateLimitError: The operation's 15-minute window is spent, ``retry_after`` set.
    """
    params = {"query": text("query", query, max_length=4096)}
    if max_results is not None:
        params["max_results"] = bounded("max_results", max_results, low=10, high=100)
    at_most_one(next_token=next_token, pagination_token=pagination_token)
    if next_token is not None:
        params["next_token"] = text("next_token", next_token)
    if pagination_token is not None:
        params["pagination_token"] = text("pagination_token", pagination_token)
    at_most_one(start_time=start_time, since_id=since_id)
    at_most_one(end_time=end_time, until_id=until_id)
    if start_time is not None:
        params["start_time"] = instant("start_time", start_time)
    if end_time is not None:
        params["end_time"] = instant("end_time", end_time)
    if since_id is not None:
        params["since_id"] = matching("since_id", since_id, _POST_ID)
    if until_id is not None:
        params["until_id"] = matching("until_id", until_id, _POST_ID)
    if sort_order is not None:
        params["sort_order"] = chosen("sort_order", [sort_order], SortOrder)
    if post_fields is not None:
        params["post.fields"] = chosen("post.fields", post_fields, PostField)
    if expansions is not None:
        params["expansions"] = chosen("expansions", expansions, PostExpansion)
    if user_fields is not None:
        params["user.fields"] = chosen("user.fields", user_fields, UserField)
    raw = await client.get_json("/tweets/search/recent", params=params)
    return parse(SearchPostsRecentResponse, raw, source=SOURCE, endpoint="searchPostsRecent")
