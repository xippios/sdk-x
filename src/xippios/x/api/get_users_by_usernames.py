"""``GET /2/users/by``, operation ``getUsersByUsernames``: Users by their usernames.

Reference: ``docs/upstream/openapi/openapi.json``, ``paths./2/users/by.get``: ``usernames``
(1 to 100, each ``^[A-Za-z0-9_]{1,15}$``), ``user.fields``, ``expansions`` (the
``UserExpansionsParameter``) and ``post.fields``, every list comma-separated; the answer
``GetUsersByUsernamesResponse``: ``data``, ``includes``, ``errors``. A username X does not
find is a ``Problem`` in ``errors`` beside the Users found, in an HTTP 200 (``partial_errors``;
``pages/response-codes-and-errors.md``, "Partial errors"), never an exception.

Wire names, recorded on 2026-10-29: X takes the document's ``expansions=most_recent_post_id``
and ``post.fields`` (HTTP 200, ``three_accounts``, ``xdevelopers_post_fields``). With
``post.fields`` in the request it answers in the document's names (``most_recent_post_id``,
``post_count``, ``includes.posts``); without it in the guides' (``most_recent_tweet_id``,
``tweet_count``, ``includes.tweets``), which the models accept too (``models``). A username
over 15 characters is refused before the call; X answers it with HTTP 400
(``username_too_long``). A wrong key gets HTTP 401 (``wrong_key``), ``AuthError``. X reported
``x-rate-limit-limit: 2000`` on this operation, where ``pages/rate-limits.md`` lists 300 per
15 minutes per app. Price: 0.010 USD a User returned, 0.005 USD a Post in ``includes``
(``pages/pricing.md``).
"""

import re
from collections.abc import Sequence

from xippios.core import parse

from xippios.x._client import SOURCE, client
from xippios.x.api._query import chosen, listed
from xippios.x.models import GetUsersByUsernamesResponse, PostField, UserExpansion, UserField

__all__ = ["get_users_by_usernames"]

_USERNAME = re.compile(r"[A-Za-z0-9_]{1,15}")


async def get_users_by_usernames(
    usernames: Sequence[str],
    *,
    user_fields: Sequence[UserField] | None = None,
    expansions: Sequence[UserExpansion] | None = None,
    post_fields: Sequence[PostField] | None = None,
) -> GetUsersByUsernamesResponse:
    """``getUsersByUsernames``: look up to 100 X users by username, one answer.

    Args:
        usernames: ``usernames``, 1 to 100 handles without ``@``, each up to 15 letters,
            digits or underscores, e.g. ``["XDevelopers", "USDA", "FAO"]``.
        user_fields: ``user.fields``, the User fields to return beyond ``id``, ``name``
            and ``username``, e.g. ``[UserField.CREATED_AT, UserField.PUBLIC_METRICS]``.
        expansions: ``expansions``, e.g. ``[UserExpansion.MOST_RECENT_POST_ID]``, which
            puts each User's most recent Post into ``includes``.
        post_fields: ``post.fields``, the fields of the Posts in ``includes``, e.g.
            ``[PostField.CREATED_AT, PostField.LANG]``.

    Returns:
        The answer: the Users found in ``data``, the expanded Posts in ``includes``, a
        ``Problem`` for each username not found in ``errors``.

    Raises:
        InvalidRequestError: A value outside the document's bounds, refused before the
            call, or X's HTTP 400.
        AuthError: X refused the key in ``X_API_KEY`` (HTTP 401).
        RateLimitError: The operation's 15-minute window is spent, ``retry_after`` set.
    """
    params = {"usernames": listed("usernames", usernames, max_items=100, pattern=_USERNAME)}
    if user_fields is not None:
        params["user.fields"] = chosen("user.fields", user_fields, UserField)
    if expansions is not None:
        params["expansions"] = chosen("expansions", expansions, UserExpansion)
    if post_fields is not None:
        params["post.fields"] = chosen("post.fields", post_fields, PostField)
    raw = await client.get_json("/users/by", params=params)
    return parse(GetUsersByUsernamesResponse, raw, source=SOURCE, endpoint="getUsersByUsernames")
