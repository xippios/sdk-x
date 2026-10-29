"""``GET /2/tweets``, operation ``getPostsByIds``: Posts by their ids.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/tweets.get``: ``ids`` (1 to
100, each ``^[0-9]{1,19}$``), ``post.fields``, ``expansions`` (the
``PostExpansionsParameter``) and ``user.fields``, every list comma-separated; the answer
``GetPostsByIdsResponse``: ``data``, ``includes``, ``errors``, ``meta.result_count``. An id
X does not find is a ``Problem`` in ``errors``, in an HTTP 200. The document's
``media.fields``, ``poll.fields`` and ``place.fields`` are not wrapped: no task needs them
yet, and their objects stay as sent in ``includes``.

Wire names, recorded on 2026-10-29 (``most_recent_three``): X takes the document's
``post.fields`` and ``expansions=referenced_posts`` (HTTP 200) and answers in the
document's names (``referenced_posts``, ``edit_history_post_ids``, ``repost_count``,
``includes.posts``), where the guides write ``tweet.fields``, ``referenced_tweets.id`` and
``referenced_tweets``. Price: 0.005 USD a Post returned, in ``data`` or ``includes``
(``pages/pricing.md``).
"""

import re
from collections.abc import Sequence

from xippios.core import parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import chosen, listed
from xippios.x.models import GetPostsByIdsResponse, PostExpansion, PostField, UserField

__all__ = ["get_posts_by_ids"]

_ID = re.compile(r"[0-9]{1,19}")


async def get_posts_by_ids(
    ids: Sequence[str],
    *,
    post_fields: Sequence[PostField] | None = None,
    expansions: Sequence[PostExpansion] | None = None,
    user_fields: Sequence[UserField] | None = None,
) -> GetPostsByIdsResponse:
    """``getPostsByIds``: look up to 100 X posts by id, one answer.

    Args:
        ids: ``ids``, 1 to 100 Post ids of up to 19 digits, e.g.
            ``["2115806101480337475"]``.
        post_fields: ``post.fields``, the Post fields to return beyond ``id`` and
            ``text``, e.g. ``[PostField.CREATED_AT, PostField.PUBLIC_METRICS]``.
        expansions: ``expansions``, e.g. ``[PostExpansion.REFERENCED_POSTS]``, which puts
            the reposted, quoted or replied-to Posts into ``includes``.
        user_fields: ``user.fields``, the fields of the Users in ``includes`` (with
            ``PostExpansion.AUTHOR_ID``), e.g. ``[UserField.CREATED_AT]``.

    Returns:
        The answer: the Posts found in ``data``, the expanded objects in ``includes``, a
        ``Problem`` for each id not found in ``errors``, ``meta.result_count``.

    Raises:
        InvalidRequestError: A value outside the document's bounds, refused before the
            call, or X's HTTP 400.
        AuthError: X refused the key in ``X_API_KEY`` (HTTP 401).
        RateLimitError: The operation's 15-minute window is spent, ``retry_after`` set.
    """
    params = {"ids": listed("ids", ids, max_items=100, pattern=_ID)}
    if post_fields is not None:
        params["post.fields"] = chosen("post.fields", post_fields, PostField)
    if expansions is not None:
        params["expansions"] = chosen("expansions", expansions, PostExpansion)
    if user_fields is not None:
        params["user.fields"] = chosen("user.fields", user_fields, UserField)
    raw = await client.get_json("/tweets", params=params)
    return parse(GetPostsByIdsResponse, raw, source=SOURCE, endpoint="getPostsByIds")
