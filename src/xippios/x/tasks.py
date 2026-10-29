"""Task functions, the public API: the adapters serve ``__all__`` (conventions §2).

Seven read tasks, each a thin call of one endpoint wrapper (``api``) that returns one
upstream page as X sends it, the wrapper's response model in ``Result.data``: nothing is
ranked, stored, projected or collected across pages (Johannes, 2026-10-29). Paging is the
caller's, through the token parameter the operation names (``pagination_token`` or
``next_token``) and the ``next_token`` of the previous page's ``meta``
(``result.data.meta.next_token``). The tasks' nouns are the OpenAPI document's: posts,
users, Lists (gate P, 2026-10-29).

Spend per call, at the prices of ``docs/upstream/pages/pricing.md`` (snapshot of
2026-10-29), a post or user read again the same UTC day not billed again (a soft
guarantee, the page says): ``lookup_users`` 0.010 USD a user found, up to 100 (1.00 USD),
and 0.005 USD more a user with ``most_recent_post`` (up to 1.50 USD); ``get_user_posts``,
``search_recent_posts``, ``get_list_posts`` and ``get_conversation_posts`` 0.005 USD a
post returned, up to 100 (0.50 USD), a List's posts counted as posts, the upper bound,
since the page does not say under which resource they are billed; ``count_posts`` 0.010
USD a request, every request, since counts are not deduplicated; ``get_usage`` no price,
the page states none.

The fields each task asks for are fixed, the plan's sets of the probe (the plan §8,
``USER_FIELDS`` and ``POST_FIELDS``), which the fixtures were recorded with; a task takes
no expansion but ``lookup_users``' ``most_recent_post``.

Release metadata, the same for every task: ``meta.source`` is the source slug ``"x"``,
``meta.endpoint`` the operation's id (``getUsersPosts``), ``meta.retrieved_at`` the time
the answer arrived (the client caches nothing), ``meta.request`` the parameters sent,
under the names X takes (``user.fields``, ``max_results``), a token's value ``REDACTED``
by core's credential rule, which takes ``token`` as a whole word (core gap row 326), and
``meta.total`` ``None``: X reports no count of the records matching a request, only
``result_count``, the items of this page (ADR-0012). ``meta.published_at`` is ``None``
for every task: X states no release time for a page, each post carries its own
``created_at``, and a newest time the package computes across records is no release time
(ADR-0022, reading of 2026-10-29; conventions §4; row 338 item 2). ``meta.vintage`` is
``None``, X having no release identifier.

A 200 that carries ``errors`` is returned as the page (partial errors), except that a page
without ``data`` whose every problem is ``resource-not-found`` (a user id or a List id X
does not find, no username of a lookup found) raises ``NotFoundError`` with X's words
(conventions §5).
"""

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from xippios.core import NotFoundError, Result, ResultCap, ResultMeta, sync

from xippios.x import api
from xippios.x._client import SOURCE
from xippios.x.api._query import instant, matching, text
from xippios.x.models import (
    GetListsPostsResponse,
    GetPostsCountsAllResponse,
    GetUsageResponse,
    GetUsersByUsernamesResponse,
    GetUsersPostsResponse,
    Granularity,
    PostField,
    Problem,
    SearchPostsRecentResponse,
    UsageField,
    UserExpansion,
    UserField,
)

# In the order an agent meets them, which the adapters keep for the tools and routes: users
# first, whose ids the posts tasks take, the usage last (Johannes, 2026-10-29).
__all__ = [  # noqa: RUF022
    "lookup_users",
    "get_user_posts",
    "search_recent_posts",
    "count_posts",
    "get_list_posts",
    "get_conversation_posts",
    "get_usage",
]

# A task named here is Python-only: no tool, no route; the adapters skip it (ADR-0019 decision 4).
BULK_TASKS: frozenset[str] = frozenset()

MCP_CAPS: Mapping[str, ResultCap] = {
    "lookup_users": ResultCap(
        max_bytes=160_000,
        note=("look up fewer usernames in a call, about 70 with most_recent_post, to see the rest"),
    ),
    "get_user_posts": ResultCap(
        max_bytes=128_000,
        note=(
            "ask for fewer posts with max_results, or narrow start_time and end_time, and page "
            "on with pagination_token to see the rest"
        ),
    ),
    "search_recent_posts": ResultCap(
        max_bytes=128_000,
        note=(
            "ask for fewer posts with max_results, or narrow start_time and end_time, and page "
            "on with next_token to see the rest"
        ),
    ),
    "count_posts": ResultCap(
        note=(
            "minute buckets over more than about 13 hours pass the cap: count by day or hour, "
            "the usual choices, whose 31 days fit, or bring start_time and end_time within "
            "about 13 hours, to see the rest"
        ),
    ),
    "get_list_posts": ResultCap(
        max_bytes=128_000,
        note=(
            "ask for fewer posts with max_results and page on with pagination_token to see the rest"
        ),
    ),
    "get_conversation_posts": ResultCap(
        max_bytes=128_000,
        note=("ask for fewer posts with max_results and page on with next_token to see the rest"),
    ),
}
"""Per-tool caps that hold a whole page (conventions §8; ADR-0016 decisions 2 and 4; row 338
item 3).

A task's result is one page, a model rather than a list, so it is one row to the cap and
``max_rows`` stays the family's 200; the byte bound is the one that cuts, and a cut turns
the whole page into a note and a preview, its ``next_token`` lost. Measured on the recorded
fixtures as core serialises them (compact JSON, ``None`` fields included): a post is about
960 bytes besides its ``text``, at most 280 characters, a user about 800 besides its free
texts (a ``description`` of at most 160 characters, a ``name`` of 50, a ``location`` of
30), a count's bucket 77 bytes, the envelope about 600. So 100 posts with 280-character
ASCII texts take 100 x (960 + 280) + 600 = 124,600 bytes, under 128,000 for the post
tools; 100 users with the longest free texts 100 x (800 + 240) + 600 = 104,600, under
160,000 for ``lookup_users``, which leaves room for non-ASCII text, and with
``most_recent_post`` each user brings a post besides, 100 x (1,040 + 1,240) + 600 =
228,600, so about 70 users with their posts fit. ``count_posts`` keeps the family's
64 KB: a page of 31 days of hours, 744 buckets, takes 744 x 78 + 400 = 58,432 bytes, and
only minutes over more than about 13 hours (835 buckets) pass it. ``get_usage``, at most
90 days, stays under the default and has no entry. Each note names the tool's own
parameters.
"""

USER_FIELDS = (
    UserField.CREATED_AT,
    UserField.DESCRIPTION,
    UserField.LOCATION,
    UserField.PROTECTED,
    UserField.PUBLIC_METRICS,
    UserField.VERIFIED_TYPE,
    UserField.URL,
)
"""The ``user.fields`` ``lookup_users`` asks for beyond ``id``, ``name`` and ``username``:
the plan's set (the plan §8)."""

POST_FIELDS = (
    PostField.CREATED_AT,
    PostField.LANG,
    PostField.PUBLIC_METRICS,
    PostField.CONVERSATION_ID,
)
"""The ``post.fields`` every task that returns posts asks for beyond ``id`` and ``text``:
the plan's set (the plan §8); with them X answers in the document's names."""

USAGE_FIELDS = tuple(UsageField)
"""Every ``usage.fields`` value: ``get_usage`` returns the whole ``Usage``."""

SEARCH_QUERY_LIMIT = 512
"""Characters of a recent search's query: "512 query length" for ``GET
/2/tweets/search/recent`` (``pages/rate-limits.md``), where the OpenAPI document allows
4,096, Enterprise's."""

COUNTS_QUERY_LIMIT = 1024
"""Characters of a full-archive count's query: "1,024-character query length (4,096 for
Enterprise)" (``pages/post-counts.md``)."""

_POST_ID = re.compile(r"[0-9]{1,19}")
_NOT_FOUND = "resource-not-found"


def _values(fields: Sequence[Any]) -> list[str]:
    return [str(field) for field in fields]


def _meta(endpoint: str, request: dict[str, Any]) -> ResultMeta:
    """The meta every task gives: no ``published_at``, no ``vintage``, no ``total``."""
    return ResultMeta(source=SOURCE, endpoint=endpoint, request=request)


def _when(name: str, value: datetime | None) -> str | None:
    return None if value is None else instant(name, value)


def _absent(endpoint: str, data: object, errors: Sequence[Problem] | None) -> None:
    """Raise ``NotFoundError`` for a page without ``data`` whose problems are all not-found."""
    if data or not errors:
        return
    if all(problem.type.rstrip("/").rsplit("/", 1)[-1] == _NOT_FOUND for problem in errors):
        said = "; ".join(problem.detail for problem in errors)
        raise NotFoundError(f"X found nothing ({endpoint}): {said}", source=SOURCE)


def _query(query: str, limit: int) -> str:
    """``query`` when it is 1 to ``limit`` characters, else ``InvalidRequestError``."""
    return text("query", query, max_length=limit)


async def lookup_users_async(
    usernames: list[str], most_recent_post: bool = False
) -> Result[GetUsersByUsernamesResponse]:
    """Look up X users by username: profile, creation date, public metrics and verified type.

    One request (``GET /2/users/by``) for up to 100 usernames. The users found are in
    ``data``, each with ``id`` (the id the other tasks take), ``name``, ``username``,
    ``created_at``, ``description``, ``location``, ``protected``, ``public_metrics``
    (followers, following, posts, lists, likes, media), ``verified_type`` and ``url``; a
    username X does not find is a problem in ``errors`` beside them, and when none is
    found the task raises ``NotFoundError``. Price: 0.010 USD a user found, and 0.005 USD
    more a user with ``most_recent_post``: at most 1.00 USD a call for 100 users, up to
    1.50 USD for 100 users with their posts.

    Args:
        usernames: 1 to 100 handles without ``@``, each up to 15 letters, digits or
            underscores, e.g. ``["USDA", "FAO", "XDevelopers"]``.
        most_recent_post: ``True`` puts each user's most recent post, with its
            ``created_at``, ``lang``, ``public_metrics`` and ``conversation_id``, into
            ``includes.posts`` (the expansion ``most_recent_post_id``); ``False``, the
            default, leaves it out.
    """
    expansions = [UserExpansion.MOST_RECENT_POST_ID] if most_recent_post else None
    post_fields = POST_FIELDS if most_recent_post else None
    page = await api.get_users_by_usernames(
        usernames, user_fields=USER_FIELDS, expansions=expansions, post_fields=post_fields
    )
    _absent("getUsersByUsernames", page.data, page.errors)
    request = {
        "usernames": list(usernames),
        "user.fields": _values(USER_FIELDS),
        "expansions": None if expansions is None else _values(expansions),
        "post.fields": None if post_fields is None else _values(post_fields),
    }
    return Result(data=page, meta=_meta("getUsersByUsernames", request))


lookup_users = sync(lookup_users_async)


async def get_user_posts_async(
    id: str,
    max_results: int = 10,
    pagination_token: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> Result[GetUsersPostsResponse]:
    """Get one page of an X user's posts, newest first, reposts and replies included.

    One request (``GET /2/users/{id}/tweets``). The posts are in ``data``, each with
    ``id``, ``text``, ``created_at``, ``lang``, ``public_metrics`` (reposts, replies,
    likes, quotes, bookmarks, views), ``conversation_id`` and ``edit_history_post_ids``;
    ``data.meta`` holds ``result_count``, ``newest_id``, ``oldest_id`` and the
    ``next_token`` of the next page, absent on the last. X may return fewer posts than
    ``max_results`` while more exist. A user id X does not find raises ``NotFoundError``.
    Price: 0.005 USD a post returned, at most 0.50 USD a call.

    Args:
        id: The user's id, up to 19 digits, from ``lookup_users``' ``data[].id``, e.g.
            ``"61853389"`` (@USDA).
        max_results: Posts on the page, from 5 to 100, e.g. ``10`` (the default) or
            ``50``.
        pagination_token: The page to return: pass the ``next_token`` from the previous
            page's ``meta`` (``data.meta.next_token``); ``None``, the default, returns the
            newest page. ``meta.request`` shows it as ``REDACTED``.
        start_time: The oldest creation time, a datetime with a zone on or after
            2010-11-06, e.g. ``"2026-10-01T00:00:00Z"``; ``None`` sets no bound.
        end_time: The newest creation time, likewise, e.g. ``"2026-10-29T00:00:00Z"``.
    """
    page = await api.get_users_posts(
        id,
        max_results=max_results,
        pagination_token=pagination_token,
        start_time=start_time,
        end_time=end_time,
        post_fields=POST_FIELDS,
    )
    _absent("getUsersPosts", page.data, page.errors)
    request = {
        "id": id,
        "max_results": max_results,
        "pagination_token": pagination_token,
        "start_time": _when("start_time", start_time),
        "end_time": _when("end_time", end_time),
        "post.fields": _values(POST_FIELDS),
    }
    return Result(data=page, meta=_meta("getUsersPosts", request))


get_user_posts = sync(get_user_posts_async)


async def search_recent_posts_async(
    query: str,
    max_results: int = 10,
    next_token: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> Result[SearchPostsRecentResponse]:
    """Search the X posts of the last seven days with a query, one page, newest first.

    One request (``GET /2/tweets/search/recent``). The posts are in ``data``, each with
    ``id``, ``text``, ``created_at``, ``lang``, ``public_metrics``, ``conversation_id``
    and ``edit_history_post_ids``; an edited post's earlier versions come as posts of
    their own. ``data.meta`` holds ``result_count``, ``newest_id``, ``oldest_id`` and the
    ``next_token`` of the next page, absent on the last; no match is an empty page. A
    query X cannot parse raises ``InvalidRequestError`` with X's words. Price: 0.005 USD
    a post returned, at most 0.50 USD a call.

    Args:
        query: X's search syntax, at most 512 characters (``pages/rate-limits.md``),
            e.g. ``"from:USDA"``, ``"from:USDA -is:retweet -is:reply"`` or
            ``"wheat from:USDA"``; longer is refused before the call.
        max_results: Posts on the page, from 10 to 100, e.g. ``10`` (the default) or
            ``50``.
        next_token: The page to return: pass the ``next_token`` from the previous page's
            ``meta`` (``data.meta.next_token``); ``None``, the default, returns the newest
            page. ``meta.request`` shows it as ``REDACTED``.
        start_time: The oldest creation time, a datetime with a zone within the last
            seven days, e.g. ``"2026-10-27T00:00:00Z"``; ``None`` sets no bound.
        end_time: The newest creation time, likewise, e.g. ``"2026-10-29T12:00:00Z"``.
    """
    sent = _query(query, SEARCH_QUERY_LIMIT)
    page = await api.search_posts_recent(
        sent,
        max_results=max_results,
        next_token=next_token,
        start_time=start_time,
        end_time=end_time,
        post_fields=POST_FIELDS,
    )
    request = {
        "query": sent,
        "max_results": max_results,
        "next_token": next_token,
        "start_time": _when("start_time", start_time),
        "end_time": _when("end_time", end_time),
        "post.fields": _values(POST_FIELDS),
    }
    return Result(data=page, meta=_meta("searchPostsRecent", request))


search_recent_posts = sync(search_recent_posts_async)


async def count_posts_async(
    query: str,
    granularity: Granularity = Granularity.DAY,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    next_token: str | None = None,
) -> Result[GetPostsCountsAllResponse]:
    """Count the X posts matching a query over the full archive, by day, hour or minute.

    One request (``GET /2/tweets/counts/all``) for one page of 31 days, the newest first
    page by page (without ``start_time`` the 31 days up to now); within the page the
    buckets in ``data`` run oldest first, each with ``start``, ``end`` and
    ``post_count``. ``data.meta`` holds ``total_post_count``, the page's sum, and the
    ``next_token`` of the 31 days before. A page of hours holds 744 buckets, of minutes
    44,640: ``day`` or ``hour`` is the usual choice, and minutes over more than about 13
    hours pass the MCP tool's result cap. Price: 0.010 USD a request, every request, since
    counts are not deduplicated.

    Args:
        query: X's search syntax, at most 1,024 characters (``pages/post-counts.md``),
            e.g. ``"from:USDA"`` or ``"from:USDA -is:retweet -is:reply"`` (original posts
            only); longer is refused before the call.
        granularity: The bucket, ``"day"`` (the default), ``"hour"`` or ``"minute"``.
        start_time: The oldest time counted, a datetime with a zone, e.g.
            ``"2026-07-31T00:00:00Z"``; ``None`` counts the 31 days up to now.
        end_time: The newest time counted, likewise, e.g. ``"2026-10-29T00:00:00Z"``.
        next_token: The page to return: pass the ``next_token`` from the previous page's
            ``meta`` (``data.meta.next_token``); ``None``, the default, returns the first
            page. ``meta.request`` shows it as ``REDACTED``.
    """
    sent = _query(query, COUNTS_QUERY_LIMIT)
    page = await api.get_posts_counts_all(
        sent,
        start_time=start_time,
        end_time=end_time,
        next_token=next_token,
        granularity=granularity,
    )
    request = {
        "query": sent,
        "granularity": Granularity(granularity).value,
        "start_time": _when("start_time", start_time),
        "end_time": _when("end_time", end_time),
        "next_token": next_token,
    }
    return Result(data=page, meta=_meta("getPostsCountsAll", request))


count_posts = sync(count_posts_async)


async def get_list_posts_async(
    id: str,
    max_results: int = 10,
    pagination_token: str | None = None,
) -> Result[GetListsPostsResponse]:
    """Get one page of the posts of an X List's members, newest first.

    One request (``GET /2/lists/{id}/tweets``). The posts are in ``data``, each with
    ``id``, ``text``, ``created_at``, ``lang``, ``public_metrics``, ``conversation_id``
    and ``edit_history_post_ids``; ``data.meta`` holds ``result_count`` and the
    ``next_token`` of the next page, absent on the last. X may return fewer posts than
    ``max_results`` while more exist. A List id X does not find raises
    ``NotFoundError``. Price: 0.005 USD a post returned, at most 0.50 USD a call
    (``pages/pricing.md`` lists List reads at 0.005 USD a resource without saying how a
    List's posts are billed; counted as posts).

    Args:
        id: The List's id, up to 19 digits, e.g. ``"715919216927322112"`` (a List of
            @XDevelopers').
        max_results: Posts on the page, from 1 to 100, e.g. ``10`` (the default) or
            ``50``.
        pagination_token: The page to return: pass the ``next_token`` from the previous
            page's ``meta`` (``data.meta.next_token``); ``None``, the default, returns the
            newest page. ``meta.request`` shows it as ``REDACTED``.
    """
    page = await api.get_lists_posts(
        id, max_results=max_results, pagination_token=pagination_token, post_fields=POST_FIELDS
    )
    _absent("getListsPosts", page.data, page.errors)
    request = {
        "id": id,
        "max_results": max_results,
        "pagination_token": pagination_token,
        "post.fields": _values(POST_FIELDS),
    }
    return Result(data=page, meta=_meta("getListsPosts", request))


get_list_posts = sync(get_list_posts_async)


async def get_conversation_posts_async(
    conversation_id: str,
    max_results: int = 10,
    next_token: str | None = None,
) -> Result[SearchPostsRecentResponse]:
    """Get one page of the posts of an X conversation of the last seven days, newest first.

    One recent search (``GET /2/tweets/search/recent``) for
    ``conversation_id:<conversation_id>``: the post that started the conversation and
    the replies to it and to each other, those of the last seven days only. The posts are
    in ``data``, each with ``id``, ``text``, ``created_at``, ``lang``, ``public_metrics``,
    ``conversation_id`` and ``edit_history_post_ids``; ``data.meta`` holds
    ``result_count``, ``newest_id``, ``oldest_id`` and the ``next_token`` of the next
    page, absent on the last. A conversation without posts in the last seven days is an
    empty page. Price: 0.005 USD a post returned, at most 0.50 USD a call.

    Args:
        conversation_id: The id of the post that started the conversation, up to 19
            digits: a post's ``conversation_id`` from the other tasks, e.g.
            ``"2115806101480337475"``.
        max_results: Posts on the page, from 10 to 100, e.g. ``10`` (the default) or
            ``50``.
        next_token: The page to return: pass the ``next_token`` from the previous page's
            ``meta`` (``data.meta.next_token``); ``None``, the default, returns the newest
            page. ``meta.request`` shows it as ``REDACTED``.
    """
    query = f"conversation_id:{matching('conversation_id', conversation_id, _POST_ID)}"
    page = await api.search_posts_recent(
        query, max_results=max_results, next_token=next_token, post_fields=POST_FIELDS
    )
    request = {
        "query": query,
        "max_results": max_results,
        "next_token": next_token,
        "post.fields": _values(POST_FIELDS),
    }
    return Result(data=page, meta=_meta("searchPostsRecent", request))


get_conversation_posts = sync(get_conversation_posts_async)


async def get_usage_async(days: int = 7) -> Result[GetUsageResponse]:
    """Get the Post usage of the X project the key's app belongs to, by day.

    One request (``GET /2/usage/tweets``) with every usage field. ``data`` holds
    ``project_usage``, the posts read in the billing cycle, ``project_cap``, the cycle's
    cap, ``cap_reset_day``, the day of the month the cycle resets, ``project_id``, and
    the usage by day of the project (``daily_project_usage``) and of each of its client
    apps (``daily_client_app_usage``). It counts posts only, not users or counts
    requests. Price: ``pages/pricing.md`` states none for this request.

    Args:
        days: The days of usage by day, from 1 to 90, e.g. ``7`` (the default) or ``30``.
    """
    answer = await api.get_usage(days=days, usage_fields=USAGE_FIELDS)
    request = {"days": days, "usage.fields": _values(USAGE_FIELDS)}
    return Result(data=answer, meta=_meta("getUsage", request))


get_usage = sync(get_usage_async)
