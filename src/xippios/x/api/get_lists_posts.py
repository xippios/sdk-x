"""``GET /2/lists/{id}/tweets``, operation ``getListsPosts``: one page of a List's Posts.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/lists/{id}/tweets.get``:
``id`` (``ListId``, ``^[0-9]{1,19}$``), ``max_results`` (1 to 100, 100 when omitted),
``pagination_token`` ("A base32hex-encoded pagination token", at least one character),
``post.fields``, ``expansions`` and ``user.fields``; the answer ``GetListsPostsResponse``:
``data``, ``includes``, ``errors``, ``meta`` (``result_count``, ``next_token``,
``previous_token``). The Posts are those of the List's members. The document's
``media.fields``, ``poll.fields`` and ``place.fields`` are not wrapped: no task needs them
yet, and their objects stay as sent in ``includes``. Collecting the pages is the task
layer's.

Recorded on 2026-10-29 from a List @XDevelopers owns (``xdevelopers_list_ten``): nine Posts
for ``max_results=10``, newest first, with a ``next_token`` (fewer than ``max_results``
while more exist, as ``pages/pagination.md`` says) and no ``newest_id`` or ``oldest_id``,
which the document's ``meta`` does not have either. A List id X does not find is answered
with HTTP 200, a ``resource-not-found`` problem in ``errors`` and no ``data``
(``unknown_id``), which the wrapper returns as the page. Price: 0.005 USD a Post returned
(``pages/pricing.md``); X reported ``x-rate-limit-limit: 900``, as ``pages/rate-limits.md``
lists.
"""

import re
from collections.abc import Sequence

from xippios.core import parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import bounded, chosen, matching, text
from xippios.x.models import GetListsPostsResponse, PostExpansion, PostField, UserField

__all__ = ["get_lists_posts"]

_LIST_ID = re.compile(r"[0-9]{1,19}")


async def get_lists_posts(
    id: str,
    *,
    max_results: int | None = None,
    pagination_token: str | None = None,
    post_fields: Sequence[PostField] | None = None,
    expansions: Sequence[PostExpansion] | None = None,
    user_fields: Sequence[UserField] | None = None,
) -> GetListsPostsResponse:
    """``getListsPosts``: one page of the posts of an X List's members, newest first.

    Args:
        id: ``id``, the List's id of up to 19 digits, e.g. ``"715919216927322112"`` (a
            List of @XDevelopers').
        max_results: ``max_results``, Posts per page from 1 to 100, e.g. ``10``; X's
            default, 100, when omitted.
        pagination_token: ``pagination_token``, the ``meta.next_token`` of the page before,
            as X sent it.
        post_fields: ``post.fields``, e.g. ``[PostField.CREATED_AT, PostField.LANG,
            PostField.PUBLIC_METRICS, PostField.CONVERSATION_ID]``.
        expansions: ``expansions``, e.g. ``[PostExpansion.AUTHOR_ID]``, which puts each
            Post's author into ``includes``.
        user_fields: ``user.fields``, the fields of the Users in ``includes``, e.g.
            ``[UserField.CREATED_AT]``.

    Returns:
        One page: the Posts in ``data``, ``meta.next_token`` for the next page.

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
        params["pagination_token"] = text("pagination_token", pagination_token)
    if post_fields is not None:
        params["post.fields"] = chosen("post.fields", post_fields, PostField)
    if expansions is not None:
        params["expansions"] = chosen("expansions", expansions, PostExpansion)
    if user_fields is not None:
        params["user.fields"] = chosen("user.fields", user_fields, UserField)
    path = f"/lists/{matching('id', id, _LIST_ID)}/tweets"
    raw = await client.get_json(path, params=params)
    return parse(GetListsPostsResponse, raw, source=SOURCE, endpoint="getListsPosts")
