"""``GET /2/lists/{id}/members``, operation ``getListsMembers``: one page of a List's members.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/lists/{id}/members.get``:
``id`` (``ListId``, ``^[0-9]{1,19}$``), ``max_results`` (1 to 100, 100 when omitted),
``pagination_token`` ("A 64-bit signed integer.", a string the document does not bound,
sent as given), ``user.fields``, ``expansions`` (the ``UserExpansionsParameter``) and
``post.fields``; the answer ``GetListsMembersResponse``: ``data`` (``User``), ``includes``,
``errors``, ``meta`` (``result_count``, ``next_token``, ``previous_token``). Paging is the
caller's: a task returns one page and its token.

Recorded on 2026-10-29 from a List @XDevelopers owns (``xdevelopers_list_ten``): its eight
members for ``max_results=10``, ``meta.result_count`` 8 and no ``next_token``; without
``post.fields`` X answers a member's metrics in the guides' spelling (``tweet_count``),
which ``UserPublicMetrics`` reads as ``post_count``. Price: 0.010 USD a User returned,
0.005 USD a Post in ``includes`` (``pages/pricing.md``); X reported
``x-rate-limit-limit: 900``, as ``pages/rate-limits.md`` lists.
"""

import re
from collections.abc import Sequence

from xippios.core import parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import bounded, chosen, matching
from xippios.x.models import GetListsMembersResponse, PostField, UserExpansion, UserField

__all__ = ["get_lists_members"]

_LIST_ID = re.compile(r"[0-9]{1,19}")


async def get_lists_members(
    id: str,
    *,
    max_results: int | None = None,
    pagination_token: str | None = None,
    user_fields: Sequence[UserField] | None = None,
    expansions: Sequence[UserExpansion] | None = None,
    post_fields: Sequence[PostField] | None = None,
) -> GetListsMembersResponse:
    """``getListsMembers``: one page of the X users who are members of a List.

    Args:
        id: ``id``, the List's id of up to 19 digits, e.g. ``"715919216927322112"`` (a
            List of @XDevelopers').
        max_results: ``max_results``, Users per page from 1 to 100, e.g. ``10``; X's
            default, 100, when omitted.
        pagination_token: ``pagination_token``, the ``meta.next_token`` of the page
            before, sent as given.
        user_fields: ``user.fields``, the User fields to return beyond ``id``, ``name``
            and ``username``, e.g. ``[UserField.CREATED_AT, UserField.PUBLIC_METRICS]``.
        expansions: ``expansions``, e.g. ``[UserExpansion.MOST_RECENT_POST_ID]``, which
            puts each member's most recent Post into ``includes``.
        post_fields: ``post.fields``, the fields of the Posts in ``includes``, e.g.
            ``[PostField.CREATED_AT, PostField.LANG]``.

    Returns:
        One page: the members in ``data``, ``meta.next_token`` for the next page.

    Raises:
        InvalidRequestError: A value outside the document's bounds, refused before the
            call, or X's HTTP 400.
        AuthError: X refused the key in ``X_API_KEY`` (HTTP 401).
        RateLimitError: The operation's 15-minute window is spent, ``retry_after`` set.
    """
    params: dict[str, str] = {}
    if max_results is not None:
        params["max_results"] = bounded("max_results", max_results, low=1, high=100)
    if pagination_token is not None:
        params["pagination_token"] = pagination_token
    if user_fields is not None:
        params["user.fields"] = chosen("user.fields", user_fields, UserField)
    if expansions is not None:
        params["expansions"] = chosen("expansions", expansions, UserExpansion)
    if post_fields is not None:
        params["post.fields"] = chosen("post.fields", post_fields, PostField)
    path = f"/lists/{matching('id', id, _LIST_ID)}/members"
    raw = await client.get_json(path, params=params)
    return parse(GetListsMembersResponse, raw, source=SOURCE, endpoint="getListsMembers")
