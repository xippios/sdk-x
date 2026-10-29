"""Record one X API v2 exchange into a fixture, X Content rewritten (``/record-fixture``, D1).

Run from the repository root, the key in the environment through direnv::

    direnv exec ~/github/sdk uv run scripts/record_fixture.py <wrapper> <case> key=value ...
    uv run scripts/record_fixture.py get_users_by_usernames wrong_key usernames=FAO --wrong-key

``<wrapper>`` is one of the four endpoint wrappers (``WRAPPERS``); the fixture lands at
``tests/fixtures/<wrapper>/<case>.json`` and is never overwritten. ``key=value`` pairs are
the query parameters under the names the wire takes (``user.fields``, ``expansions``),
sent in the order given; ``id`` of ``get_users_posts`` fills the path. ``--wrong-key``
sends ``Bearer not-a-valid-key`` through a throwaway client instead of the key, to record
the 401, which bills nothing.

Spend. Before the request the recorder prints its estimate, an upper bound at the prices
of ``docs/upstream/pages/pricing.md`` (snapshot of 2026-10-29): 0.005 USD a post and
0.010 USD a user returned, 0.010 USD a ``GET /2/tweets/counts/all`` request; a 4xx bills
nothing, and a resource read earlier in the same UTC day is not billed again. It records
through a client that never retries (``RetryPolicy(max_attempts=1)``), so a 5xx spends no
second request.

The accounts. D1, decided by Johannes on 2026-10-29, records fixtures from @XDevelopers,
@USDA and @FAO only (``ACCOUNTS``). The recorder's guard covers what a request names, its
usernames, ids and query, and refuses before any request one that names another account:

- ``get_users_by_usernames``: every username in ``usernames`` is one of the three, in any
  letter case. ``--unknown`` admits exactly one other, for the partial-``errors`` case; the
  answer is then refused, nothing written, if it returns a user who is not one of the three.
- ``get_users_posts``: ``id`` is one of the three accounts' ids, as the recorded
  ``get_users_by_usernames`` fixtures give them. ``--unknown`` admits one other id, for
  the not-found case; the answer is refused if it returns posts.
- ``get_posts_by_ids``: every id in ``ids`` is a post of the three, as the recorded
  fixtures give them: a user's ``most_recent_post_id`` (or ``most_recent_tweet_id``,
  ``pinned_post_id``, ``pinned_tweet_id``) in ``get_users_by_usernames``, a post's ``id``
  in ``get_users_posts``.
- ``get_posts_counts_all``: ``query`` names one of the three with ``from:`` and no other
  account (``from:``, ``to:``, ``retweets_of:`` or ``@``).

An expansion can still bring other accounts' objects into an answer: ``referenced_posts``
brings the posts a post reposts, quotes or replies to, whoever wrote them
(``get_posts_by_ids/most_recent_three`` holds post 2114868620933333409, which @XDevelopers
quoted and which is none of the three's recorded posts). The rewrite below covers their
``text``, ``description``, ``name``, ``username`` and ``location``, and nothing else. So the
recorder also refuses, before any request, every ``expansions``, ``user.fields`` and
``post.fields`` value outside ``ADMITTED``: the expansions ``most_recent_post_id`` and
``referenced_posts``, which bring posts and no users, so that the user objects of an answer
are the requested users' only; the user fields of the probe's plan with ``id``, ``name``,
``username`` and ``verified``; the post fields of the plan with ``id`` and ``text``. The
values refused carry what the rewrite does not cover for other accounts, ``url``,
``profile_image_url``, ``entities`` (whose URL entities' ``title``, ``expanded_url`` and
``display_url`` can carry a handle), ``withheld`` and the pinned post ids among them, and
stay refused until the rewrite covers them.

The rewrite. X's Developer Agreement, III.A (d), forbids distributing X Content to third
parties beyond what it permits, and the Developer Policy permits Post, Direct Message and
User IDs (``docs/upstream/terms/``). D1 (Johannes, 2026-10-29) rewrites ``text``,
``description`` and the ``name`` of persons by key; the session extended it on 2026-10-29
to the ``username`` and ``location`` of persons. The recorder rewrites a JSON response body
by key, on the ``Fixture`` core's ``fixture_from_response`` returns, before the one write
(ADR-0024, decision 4), at any depth, ``includes``, ``entities``, ``referenced_posts`` and
``errors`` alike:

- every ``text`` (a post's, a ``note_tweet``'s or ``note_post``'s) becomes ``[text
  rewritten]``;
- every ``description`` (a user's bio) becomes ``[description rewritten]``;
- in every object with a ``username`` (a user, a mention) that is not one of the three,
  in any letter case: ``username`` becomes ``[username rewritten]``, ``name`` ``[name
  rewritten]`` and ``location`` ``[location rewritten]``.

Only text values are rewritten, so every placeholder is a string where a string was. Ids,
times, metrics, ``lang``, booleans, enum values, the three accounts' names, handles,
locations and URLs stay as sent; so does a body with nothing to rewrite, a counts answer
or an error, byte for byte. The rewritten body is written compact, as X sends it. Before
the write the recorder verifies, against the unrewritten body it holds in memory, that no
rewritten value survives anywhere in the fixture (a substring of a decoded string of the
body, of the URL or of a header value; the placeholders and ``REDACTED`` masked first);
a survivor refuses the write, the message naming the key's path, never the value. The
unrewritten body is never written.

The key is read from ``X_API_KEY`` inside the script only, handed to the client and to
core's ``Scrub(secrets=[key])``, whose verify refuses an exchange that still holds it,
and never printed. Only the status, the method and path, the counts of what the answer
holds and the ``x-rate-limit-*`` headers are printed.
"""

import argparse
import contextlib
import dataclasses
import json
import os
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from xippios.core import AsyncClient, BearerAuth, RetryPolicy, sync
from xippios.core.testing import REDACTED, Fixture, Scrub, fixture_from_response, fixture_path

from xippios.x._client import API_KEY_ENV, SOURCE, config

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
WRONG_KEY = "not-a-valid-key"  # pragma: allowlist secret (a deliberately invalid key)
MAX_FIXTURE_BYTES = 256 * 1024

ACCOUNTS = ("XDevelopers", "USDA", "FAO")
"""The only accounts fixtures are recorded from (D1, Johannes, 2026-10-29)."""
_ACCOUNTS = frozenset(name.lower() for name in ACCOUNTS)

PRICE_POST = 0.005
PRICE_USER = 0.010
PRICE_COUNTS_ALL = 0.010
"""USD at ``docs/upstream/pages/pricing.md`` (snapshot of 2026-10-29): Posts: Read and
User: Read per resource returned, Counts: All per request."""

PLACEHOLDERS = {
    "text": "[text rewritten]",
    "description": "[description rewritten]",
    "username": "[username rewritten]",
    "name": "[name rewritten]",
    "location": "[location rewritten]",
}
"""What D1's rewrite writes, by key; each keeps the value a string."""
_OF_OTHER_USERS = ("username", "name", "location")

ADMITTED = {
    "expansions": frozenset({"most_recent_post_id", "referenced_posts"}),
    "user.fields": frozenset(
        {
            "created_at",
            "description",
            "id",
            "location",
            "name",
            "protected",
            "public_metrics",
            "url",
            "username",
            "verified",
            "verified_type",
        }
    ),
    "post.fields": frozenset(
        {"conversation_id", "created_at", "id", "lang", "public_metrics", "text"}
    ),
}
"""The values the recorder sends for these parameters; any other is refused (docstring).

The expansions bring posts and no users, so an answer's user objects are the requested
users' only; the field values carry nothing of other accounts the rewrite leaves.
"""
_POST_ID_FIELDS = (
    "most_recent_post_id",
    "most_recent_tweet_id",
    "pinned_post_id",
    "pinned_tweet_id",
)
_CASE = re.compile(r"[a-z0-9][a-z0-9_]*")
_ID = re.compile(r"[0-9]{1,19}")


@dataclass(frozen=True)
class Operation:
    """One wrapped operation: its path relative to ``BASE_URL`` and the parameters taken.

    ``params`` are the OpenAPI document's names, the ones the wrappers send: X takes them
    (``post.fields``, recorded 2026-10-29; ``CLAUDE.md``, Paths, names and errors).
    """

    operation_id: str
    path: str
    params: frozenset[str]


WRAPPERS = {
    "get_users_by_usernames": Operation(
        "getUsersByUsernames",
        "/users/by",
        frozenset({"usernames", "user.fields", "expansions", "post.fields"}),
    ),
    "get_posts_by_ids": Operation(
        "getPostsByIds",
        "/tweets",
        frozenset({"ids", "post.fields", "expansions", "user.fields"}),
    ),
    "get_users_posts": Operation(
        "getUsersPosts",
        "/users/{id}/tweets",
        frozenset(
            {
                "id",
                "max_results",
                "pagination_token",
                "start_time",
                "end_time",
                "post.fields",
                "expansions",
                "user.fields",
            }
        ),
    ),
    "get_posts_counts_all": Operation(
        "getPostsCountsAll",
        "/tweets/counts/all",
        frozenset(
            {"query", "start_time", "end_time", "next_token", "pagination_token", "granularity"}
        ),
    ),
}
"""The four wrappers the recorder serves; any other is refused."""


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """The command line: wrapper, case, query parameters and the two options."""
    parser = argparse.ArgumentParser(
        prog="record_fixture.py",
        description="Record one X API v2 request as a test fixture, X Content rewritten (D1).",
    )
    parser.add_argument("wrapper", help=f"one of {', '.join(WRAPPERS)}")
    parser.add_argument("case", help="fixture name, e.g. three_accounts")
    parser.add_argument(
        "params", nargs="*", metavar="key=value", help="query parameters, e.g. usernames=USDA"
    )
    parser.add_argument(
        "--wrong-key", action="store_true", help=f"send Bearer {WRONG_KEY} instead of the key"
    )
    parser.add_argument(
        "--unknown",
        action="store_true",
        help="admit one username or user id outside the three accounts, for an error case",
    )
    args = parser.parse_intermixed_args(argv)
    if not _CASE.fullmatch(args.case):
        parser.error(f"case {args.case!r}: use lower-case letters, digits and underscores")
    if any("=" not in item for item in args.params):
        parser.error("parameters are key=value")
    args.params = {key: value for key, _, value in (item.partition("=") for item in args.params)}
    return args


def _csv(value: str | None) -> list[str]:
    return [item for item in (value or "").split(",") if item]


def _bodies(wrapper: str) -> Iterator[Any]:
    """The decoded response bodies of the recorded fixtures of ``wrapper``."""
    for path in sorted((FIXTURES / wrapper).glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        try:
            yield json.loads(fixture["response"]["body"])
        except (KeyError, TypeError, ValueError):
            continue


def _three(node: Any) -> bool:
    return isinstance(node, dict) and str(node.get("username", "")).lower() in _ACCOUNTS


def account_ids() -> frozenset[str]:
    """The three accounts' user ids, as the recorded ``get_users_by_usernames`` give them."""
    ids: set[str] = set()
    for body in _bodies("get_users_by_usernames"):
        users = body.get("data") if isinstance(body, dict) else None
        for user in users if isinstance(users, list) else []:
            if _three(user) and isinstance(user.get("id"), str):
                ids.add(user["id"])
    return frozenset(ids)


def account_post_ids() -> frozenset[str]:
    """Post ids of the three accounts, as the recorded fixtures give them."""
    ids: set[str] = set()
    for body in _bodies("get_users_by_usernames"):
        users = body.get("data") if isinstance(body, dict) else None
        for user in users if isinstance(users, list) else []:
            if _three(user):
                ids.update(str(user[name]) for name in _POST_ID_FIELDS if user.get(name))
    for body in _bodies("get_users_posts"):
        posts = body.get("data") if isinstance(body, dict) else None
        for post in posts if isinstance(posts, list) else []:
            if isinstance(post, dict) and isinstance(post.get("id"), str):
                ids.add(post["id"])
    return frozenset(ids)


_USER_OPERAND = re.compile(r"(?i)(?:\b(from|to|retweets_of):\s*|@)([A-Za-z0-9_]+)")


def refusal(wrapper: str, params: dict[str, str], *, unknown: bool) -> str | None:
    """Why the request must not be sent, else ``None`` (the accounts of D1, the names)."""
    operation = WRAPPERS.get(wrapper)
    if operation is None:
        return f"{wrapper!r} is not one of the four wrappers ({', '.join(WRAPPERS)})"
    stray = sorted(set(params) - operation.params)
    if stray:
        taken = ", ".join(sorted(operation.params))
        return f"{wrapper} takes no {', '.join(stray)}; it takes {taken}"
    for name, admitted in ADMITTED.items():
        refused = [value for value in _csv(params.get(name)) if value not in admitted]
        if refused:
            return (
                f"{name} {', '.join(refused)} is refused until the rewrite covers what it may "
                f"carry of other accounts; {name} admits {', '.join(sorted(admitted))}"
            )
    if wrapper == "get_users_by_usernames":
        others = [name for name in _csv(params.get("usernames")) if name.lower() not in _ACCOUNTS]
        if len(others) > (1 if unknown else 0):
            return (
                f"usernames are recorded for {', '.join(ACCOUNTS)} only; --unknown admits one "
                f"other, for an error case, and {len(others)} were given"
            )
    if wrapper == "get_users_posts":
        user_id = params.get("id", "")
        if not _ID.fullmatch(user_id):
            return "get_users_posts needs id=<a user id of up to 19 digits>"
        if user_id not in account_ids() and not unknown:
            return (
                f"id is not one of the user ids of {', '.join(ACCOUNTS)} in the recorded "
                "get_users_by_usernames fixtures; --unknown admits another, for an error case"
            )
    if wrapper == "get_posts_by_ids":
        known = account_post_ids()
        others = [post_id for post_id in _csv(params.get("ids")) if post_id not in known]
        if others:
            return (
                f"ids are recorded for posts of {', '.join(ACCOUNTS)} only, as the recorded "
                f"fixtures give them; {len(others)} of the ids are not among them"
            )
    if wrapper == "get_posts_counts_all":
        operands = _USER_OPERAND.findall(params.get("query", ""))
        named = {name.lower() for _, name in operands}
        froms = {name.lower() for operator, name in operands if operator.lower() == "from"}
        if not froms or not named <= _ACCOUNTS:
            return f"query names one of {', '.join(ACCOUNTS)} with from: and no other account"
    return None


def estimate(wrapper: str, params: dict[str, str], *, wrong_key: bool) -> tuple[float, list[str]]:
    """The spend's upper bound in USD, and the expansions the bound does not count."""
    if wrong_key:
        return 0.0, []
    if wrapper == "get_posts_counts_all":
        return PRICE_COUNTS_ALL, []
    expansions = set(_csv(params.get("expansions")))
    uncounted: list[str] = []
    if wrapper == "get_users_by_usernames":
        users = len(_csv(params.get("usernames")))
        cost = users * PRICE_USER
        for expansion in sorted(expansions):
            if expansion in _POST_ID_FIELDS:
                cost += users * PRICE_POST
            else:
                uncounted.append(expansion)
        return cost, uncounted
    if wrapper == "get_posts_by_ids":
        posts = len(_csv(params.get("ids")))
    else:
        posts = int(params.get("max_results", "10"))
    cost = posts * PRICE_POST
    for expansion in sorted(expansions):
        if expansion in ("referenced_posts", "referenced_tweets.id"):
            cost += 2 * posts * PRICE_POST  # a reply that quotes references two posts
        elif expansion in ("author_id", "in_reply_to_user_id"):
            cost += posts * PRICE_USER
        else:
            uncounted.append(expansion)
    return cost, uncounted


def _rewrite(node: Any, path: str, originals: list[tuple[str, str]]) -> Any:
    """``node`` with D1's rewrite applied, the rewritten values appended to ``originals``."""
    if isinstance(node, list):
        return [_rewrite(item, f"{path}[{index}]", originals) for index, item in enumerate(node)]
    if not isinstance(node, dict):
        return node
    other = isinstance(node.get("username"), str) and node["username"].lower() not in _ACCOUNTS
    result: dict[str, Any] = {}
    for key, value in node.items():
        where = f"{path}.{key}"
        rewrite = key in ("text", "description") or (other and key in _OF_OTHER_USERS)
        if rewrite and isinstance(value, str):
            originals.append((where, value))
            result[key] = PLACEHOLDERS[key]
        else:
            result[key] = _rewrite(value, where, originals)
    return result


def rewrite(fixture: Fixture) -> tuple[Fixture, list[tuple[str, str]]]:
    """D1's rewrite on ``fixture``: the rewritten fixture and each value rewritten with its path.

    A body that is not JSON, or holds nothing to rewrite, is kept as sent, byte for byte.
    """
    body = fixture.response.body
    if fixture.response.body_base64:
        return fixture, []
    try:
        decoded = json.loads(body)
    except ValueError:
        return fixture, []
    originals: list[tuple[str, str]] = []
    rewritten = _rewrite(decoded, "body", originals)
    if not originals:
        return fixture, []
    text = json.dumps(rewritten, ensure_ascii=False, separators=(",", ":"))
    response = fixture.response.model_copy(update={"body": text})
    return fixture.model_copy(update={"response": response}), originals


def _strings(node: Any) -> Iterator[str]:
    """Every key and string value of a decoded JSON document."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)


def _masked(text: str) -> str:
    for placeholder in (*PLACEHOLDERS.values(), REDACTED):
        text = text.replace(placeholder, "\0")
    return text


def survivors(fixture: Fixture, originals: Sequence[tuple[str, str]]) -> list[str]:
    """Paths of rewritten values still found in ``fixture``; never a value.

    Searched: every decoded string of the response body (so a value behind a JSON escape
    is found), the body's raw text, the request URL and every header value, each with
    the placeholders and ``REDACTED`` masked first.
    """
    places = [fixture.request.url, fixture.response.body]
    places += [value for _, value in fixture.response.headers]
    with contextlib.suppress(ValueError):
        places += list(_strings(json.loads(fixture.response.body)))
    masked = [_masked(text) for text in places]
    found = []
    for where, value in originals:
        needle = value.strip()
        if needle and needle not in PLACEHOLDERS.values() and any(needle in t for t in masked):
            found.append(where)
    return found


def unknown_answered(wrapper: str, fixture: Fixture) -> str | None:
    """Why an answer to ``--unknown`` must not be written: it found someone; else ``None``."""
    try:
        body = json.loads(fixture.response.body)
    except ValueError:
        return None
    data = body.get("data") if isinstance(body, dict) else None
    if wrapper == "get_users_by_usernames":
        users = data if isinstance(data, list) else []
        if any(not _three(user) for user in users):
            return "the unknown username belongs to an account; nothing is written"
    if wrapper == "get_users_posts" and data:
        return "the unknown id has posts; nothing is written"
    return None


_CUT_MARKS = ("truncated", "original_bytes", "original_count", "sha256")


def to_json(fixture: Fixture) -> str:
    """The fixture as text, laid out as core's writer lays it out (no cut: no cut marks)."""
    data = fixture.model_dump(mode="json")
    if not fixture.response.truncated:
        for name in _CUT_MARKS:
            data["response"].pop(name, None)
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


async def exchange_async(client: AsyncClient, path: str, params: dict[str, str]) -> httpx.Response:
    """One GET through ``client``; an error status is returned, not raised."""
    return await client.request("GET", path, params=params, raise_on_error=False)


exchange = sync(exchange_async)


def _summary(fixture: Fixture) -> str:
    """Counts of what the answer holds, and the rate-limit headers; never content."""
    parts = [f"HTTP {fixture.response.status}"]
    try:
        body = json.loads(fixture.response.body)
    except ValueError:
        body = None
    if isinstance(body, dict):
        for name in ("data", "errors"):
            if isinstance(body.get(name), list):
                parts.append(f"{name}: {len(body[name])}")
        includes = body.get("includes")
        if isinstance(includes, dict):
            parts += [f"includes.{k}: {len(v)}" for k, v in includes.items() if isinstance(v, list)]
    headers = {name.lower(): value for name, value in fixture.response.headers}
    parts += [
        f"{name}: {headers[name]}" for name in sorted(headers) if name.startswith("x-rate-limit")
    ]
    return ", ".join(parts)


def main(argv: Sequence[str] | None = None) -> int:
    """Refuse or record, scrub and rewrite in memory, verify, write; the exit status."""
    args = parse_args(argv)
    refused = refusal(args.wrapper, args.params, unknown=args.unknown)
    if refused:
        print(f"not recorded: {refused}")  # noqa: T201
        return 1
    operation = WRAPPERS[args.wrapper]
    path = fixture_path(FIXTURES, args.wrapper, args.case)
    if path.exists():
        print(f"not recorded: {path.relative_to(ROOT)} exists; fixtures are recorded once")  # noqa: T201
        return 1
    params = dict(args.params)
    request_path = operation.path.format(id=params.pop("id", ""))
    cost, uncounted = estimate(args.wrapper, args.params, wrong_key=args.wrong_key)
    note = f" plus the expansions it does not count ({', '.join(uncounted)})" if uncounted else ""
    print(  # noqa: T201
        f"estimate: at most {cost:.3f} USD{note} (pages/pricing.md, 2026-10-29; a 4xx bills "
        "nothing; a resource read earlier this UTC day is not billed again)"
    )
    once = dataclasses.replace(config, retry=RetryPolicy(max_attempts=1))
    key = os.environ.get(API_KEY_ENV, "")
    if args.wrong_key:
        auth = BearerAuth(API_KEY_ENV, key=WRONG_KEY, source=SOURCE)
    elif not key:
        print(f"not recorded: {API_KEY_ENV} is not set")  # noqa: T201
        return 1
    else:
        auth = BearerAuth(API_KEY_ENV, source=SOURCE)
    client = AsyncClient(once, auth=auth)
    response = exchange(client, request_path, params)
    print(f"GET {response.request.url.path}")  # noqa: T201
    try:
        scrubbed = fixture_from_response(response, scrub=Scrub(secrets=[key] if key else []))
    except ValueError as refused_by_scrub:  # names where, never a value
        print(f"not written {path.relative_to(ROOT)}: {refused_by_scrub}")  # noqa: T201
        return 1
    print(_summary(scrubbed))  # noqa: T201
    if args.unknown:
        found = unknown_answered(args.wrapper, scrubbed)
        if found:
            print(f"not written {path.relative_to(ROOT)}: {found}")  # noqa: T201
            return 1
    fixture, originals = rewrite(scrubbed)
    left = survivors(fixture, originals)
    if left:
        print(  # noqa: T201
            f"not written {path.relative_to(ROOT)}: rewritten values survive at " + ", ".join(left)
        )
        return 1
    text = to_json(fixture)
    if len(text.encode("utf-8")) > MAX_FIXTURE_BYTES:
        print(f"not written {path.relative_to(ROOT)}: over 256 KiB; narrow the request")  # noqa: T201
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"written {path.relative_to(ROOT)}: {len(originals)} values rewritten")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
