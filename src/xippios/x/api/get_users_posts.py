"""``GET /2/users/{id}/tweets``, operation ``getUsersPosts``: one page of a User's Posts.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/users/{id}/tweets.get``:
``id`` (``UserId``, ``^[0-9]{1,19}$``), ``max_results`` (5 to 100), ``pagination_token``,
``start_time`` and ``end_time`` (RFC 3339; "Must be on or after 2010-11-06", and
``start_time`` earlier than ``end_time``, which X checks), ``post.fields``, ``expansions``
and ``user.fields``; the answer ``GetUsersPostsResponse`` with ``meta`` (``result_count``,
``newest_id``, ``oldest_id``, ``next_token``, ``previous_token``), newest first
(``pages/pagination.md``). The document's ``since_id``, ``until_id``, ``exclude``,
``media.fields``, ``poll.fields`` and ``place.fields`` are not wrapped: no task needs them
yet. Paging is the caller's: a task returns one page and its token.

Recorded on 2026-10-29: ten Posts of each of the three accounts with ``post.fields``,
answered in the document's names (``*_ten``); @USDA's page held 9 Posts with a
``next_token`` (fewer than ``max_results`` while more exist, as ``pages/pagination.md``
says). An id without a User is answered with HTTP 200, a ``resource-not-found`` problem in
``errors`` and no ``data`` (``unknown_id``), which the wrapper returns as the page. Price:
0.005 USD a Post returned (``pages/pricing.md``); X reported ``x-rate-limit-limit: 10000``,
as ``pages/rate-limits.md`` lists.
"""

import re
from collections.abc import Sequence
from datetime import datetime

from xippios.core import parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import bounded, chosen, instant, matching, text
from xippios.x.models import GetUsersPostsResponse, PostExpansion, PostField, UserField

__all__ = ["get_users_posts"]

_USER_ID = re.compile(r"[0-9]{1,19}")


async def get_users_posts(
    id: str,
    *,
    max_results: int | None = None,
    pagination_token: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    post_fields: Sequence[PostField] | None = None,
    expansions: Sequence[PostExpansion] | None = None,
    user_fields: Sequence[UserField] | None = None,
) -> GetUsersPostsResponse:
    """``getUsersPosts``: one page of an X user's posts, newest first.

    Args:
        id: ``id``, the User's id of up to 19 digits, e.g. ``"61853389"`` (@USDA).
        max_results: ``max_results``, Posts per page from 5 to 100, e.g. ``100``; X's
            default when omitted.
        pagination_token: ``pagination_token``, the ``meta.next_token`` of the page before,
            e.g. ``"7140dibdnow9c7btwp0g7849820ht9hksst1xyioo1kxi"``.
        start_time: ``start_time``, the oldest creation time, a datetime with a zone on
            or after 2010-11-06, e.g. ``datetime(2026, 7, 31, tzinfo=UTC)``.
        end_time: ``end_time``, the newest creation time, likewise.
        post_fields: ``post.fields``, e.g. ``[PostField.CREATED_AT, PostField.LANG,
            PostField.PUBLIC_METRICS, PostField.CONVERSATION_ID]``.
        expansions: ``expansions``, e.g. ``[PostExpansion.REFERENCED_POSTS]``.
        user_fields: ``user.fields``, the fields of the Users in ``includes``, e.g.
            ``[UserField.CREATED_AT]``.

    Returns:
        One page: the Posts in ``data``, ``meta.next_token`` for the next page, or a
        ``Problem`` in ``errors`` and no ``data`` when X finds no User with ``id``.

    Raises:
        InvalidRequestError: A value outside the document's bounds, refused before the
            call, or X's HTTP 400.
        AuthError: X refused the key in ``X_API_KEY`` (HTTP 401).
        RateLimitError: The operation's 15-minute window is spent, ``retry_after`` set.
    """
    params: dict[str, str] = {}
    if max_results is not None:
        params["max_results"] = bounded("max_results", max_results, low=5, high=100)
    if pagination_token is not None:
        params["pagination_token"] = text("pagination_token", pagination_token)
    if start_time is not None:
        params["start_time"] = instant("start_time", start_time)
    if end_time is not None:
        params["end_time"] = instant("end_time", end_time)
    if post_fields is not None:
        params["post.fields"] = chosen("post.fields", post_fields, PostField)
    if expansions is not None:
        params["expansions"] = chosen("expansions", expansions, PostExpansion)
    if user_fields is not None:
        params["user.fields"] = chosen("user.fields", user_fields, UserField)
    path = f"/users/{matching('id', id, _USER_ID)}/tweets"
    raw = await client.get_json(path, params=params)
    return parse(GetUsersPostsResponse, raw, source=SOURCE, endpoint="getUsersPosts")
