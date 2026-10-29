"""Probe a curated list of X accounts for activity: the gate P report (the plan §8, D4, D5).

Run from the repository root: the estimate first, which calls nothing, then the run under
a cap, the key in the environment through direnv::

    uv run scripts/probe_accounts.py --accounts .local/x-accounts.yaml
    direnv exec ~/github/sdk uv run scripts/probe_accounts.py --spend --spend-cap 12

The list (D4, Johannes, 2026-10-29) is a YAML list of records ``handle, name, category,
region, lang, why, check``, ``check`` either ``seen`` or ``candidate``; it names
individuals, so it lives in ``.local/x-accounts.yaml``, which git ignores, and never in
the repository. ``handle``, ``category``, ``region`` and ``check`` are required; ``region``
``US`` and ``EU`` are the regions D5 names.

The calls, through the package's wrappers and its one client (N accounts, ``--days`` D, 90
by default):

1. ``get_users_by_usernames`` in batches of up to 100, with ``expansions=
   most_recent_post_id`` and ``post.fields=created_at``: the expanded post dates the last
   activity. An account X does not resolve (a problem in ``errors``, reported in X's own
   words: the snapshot documents no shape of its own for a suspended account) or that is
   protected is reported and dropped; the rest are measured.
2. ``get_posts_by_ids`` only for measured accounts whose expansion returned no dated post.
3. ``get_posts_counts_all`` by day from the UTC midnight D days before today's, twice per
   account, ``from:<handle>`` and ``from:<handle> -is:retweet -is:reply``, paged by
   ``next_token`` at 31 days a page: three pages for 90 days.
4. ``get_users_posts``, the ten newest posts with ``post.fields`` and no expansion: the
   sample, for judging relevance by eye.
5. One ``GET /2/usage/tweets`` after the run, printed; skipped when nothing was fetched.

Spend. ``--estimate``, the default, prints N, the call plan and the plan's formula at the
prices of ``docs/upstream/pages/pricing.md`` (snapshot of 2026-10-29), and calls nothing:
``0.010·N + 0.005·N + 0.010·N·3·2 + 0.005·N·10`` USD, 9.375 at N=75. ``--spend`` needs
``--spend-cap USD``: it refuses before any call when the estimate exceeds the cap, and
stops before a request whose upper bound would take the running spend past it. The running
spend counts what each answer returns, 0.010 a user and 0.005 a post (``includes``
too), and 0.010 a counts request, before X's same-day deduplication. No call asks for an
expansion the formula leaves out, so the formula is the whole estimate. Estimate and
actual spend are printed at the end, also when the run stops.

Rate limits. ``GET /2/tweets/counts/all`` allows 300 requests per 15 minutes
(``pages/rate-limits.md``) and a run makes 6N. The client paces at 60 a minute; X's 429
reaches the probe as ``RateLimitError`` with ``retry_after`` (``classify``), and the probe
prints the wait, sleeps it, at most ``MAX_WAIT``, and calls again (ADR-0010 decision 5).
A usage cap, ``retry_after`` a billing cycle, stops the run.

Cache. Every page is kept as JSON (``dump_upstream`` of its model) under
``.local/cache/<date>/<wrapper>/<key>.json`` (``--cache DIR`` replaces ``.local/cache``)
and read instead of fetched, so a run stopped by the cap or an error, or repeated the same
UTC day, pays only for what it has not fetched yet. The cache is X Content and never
leaves ``.local/``.

Output (``--out DIR``, ``.local/`` by default): ``probe-<date>.csv``, one row per account
(``COLUMNS``), and ``probe-<date>.md``, the summary by category and by region, the
decision line against D5 and the samples, the only place post text appears. Only
aggregates ever leave ``.local/``: the counts and the decision line, never a handle or a
text. The console prints counts, waits, the spend, the decision line and the error that
stops a run, in X's words where it gives them; it lists no handle and no text of its own.

Definitions and thresholds (D5, Johannes, 2026-10-29, the plan §8): an account is active
with at least one original post (neither a repost nor a reply) in the last 14 days, core
with an average of at least two original posts a week over the window. Go: at least 50%
of the measured accounts active, and at least 25 core over 4 or more categories. US-only:
go holds for region US alone, but region EU has fewer than 5 core; it is checked first,
since it narrows a go. No-go otherwise. "The last k days" are the daily buckets from the
UTC midnight k days before today's up to now, today's part included.
"""

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import yaml
from xippios.core import RateLimitError, UpstreamModel, XippiosError, sync

from xippios.x import api
from xippios.x._client import API_KEY_ENV, BILLING_CYCLE, RATE_LIMIT, RATE_LIMIT_WINDOW, client
from xippios.x.models import (
    Expansions,
    GetPostsByIdsResponse,
    GetPostsCountsAllResponse,
    GetUsersByUsernamesResponse,
    GetUsersPostsResponse,
    Granularity,
    Post,
    PostField,
    User,
    UserExpansion,
    UserField,
)

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
"""Operator-only files (``CLAUDE.md``, Operator-only files), ignored by git."""

PRICE_USER = 10
PRICE_POST = 5
PRICE_COUNTS_ALL = 10
"""Thousandths of a USD at ``docs/upstream/pages/pricing.md`` (snapshot of 2026-10-29):
User: Read and Posts: Read per resource returned, Counts: All per request. Spend is counted
in thousandths, so 0.005 adds up without rounding."""

DAYS = 90
MIN_DAYS = 60
"""The window, and its least: the trend compares the first and the last 30 days."""
PAGE_DAYS = 31
"""Days of a ``counts/all`` page at any granularity (``pages/post-counts.md``)."""
BATCH = 100
"""Usernames or ids per lookup, the OpenAPI document's ``maxItems``."""
SAMPLE = 10
"""Posts in each account's sample."""
COUNTS_WINDOW = 300
"""``GET /2/tweets/counts/all`` requests per 15 minutes per app (``pages/rate-limits.md``)."""
MAX_WAIT = RATE_LIMIT_WINDOW
"""The longest wait for a spent rate-limit window, 15 minutes."""
MAX_WAITS = 3
"""Waits for one request before its ``RateLimitError`` stops the run."""

ACTIVE_DAYS = 14
RECENT_DAYS = 30
TREND_DAYS = 30
CORE_PER_WEEK = 2.0
GO_ACTIVE_SHARE = 0.5
GO_CORE = 25
GO_CATEGORIES = 4
US_ONLY_EU_CORE = 5
US = "US"
EU = "EU"
"""D5's definitions and thresholds (Johannes, 2026-10-29), the plan §8 as written."""

GO = "go"
US_ONLY = "US-only"
NO_GO = "no-go"
MEASURED = "measured"
PROTECTED = "protected"
UNRESOLVED = "unresolved"

FIELDS = ("handle", "name", "category", "region", "lang", "why", "check")
REQUIRED = ("handle", "category", "region", "check")
CHECKS = ("seen", "candidate")
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")

USER_FIELDS = [
    UserField.CREATED_AT,
    UserField.DESCRIPTION,
    UserField.LOCATION,
    UserField.PROTECTED,
    UserField.PUBLIC_METRICS,
    UserField.VERIFIED_TYPE,
    UserField.URL,
]
DATED = [PostField.CREATED_AT]
SAMPLE_FIELDS = [
    PostField.CREATED_AT,
    PostField.LANG,
    PostField.PUBLIC_METRICS,
    PostField.CONVERSATION_ID,
]
QUERIES = {
    "all": "from:{handle}",
    "originals": "from:{handle} -is:retweet -is:reply",
}
"""The two counts queries per account: all posts, and original posts."""
USAGE_PATH = "/usage/tweets"
USAGE_FIELDS = ("project_usage", "project_cap", "cap_reset_day")
"""What the usage reading prints: the OpenAPI document's ``Usage`` fields."""

COLUMNS = (
    "handle",
    "status",
    "resolved",
    "protected",
    "followers",
    "post_count",
    "last_post",
    "posts_14d",
    "posts_30d",
    "originals_14d",
    "originals_per_week",
    "originals_first_30d",
    "originals_last_30d",
    "trend",
    "active",
    "core",
    "category",
    "region",
    "check",
)
"""The CSV's columns, one row per listed account."""

_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


def _say(*lines: str) -> None:
    for line in lines:
        print(line)  # noqa: T201


def usd(mills: int) -> str:
    """Thousandths of a USD as USD text, e.g. ``9.375``."""
    return f"{mills / 1000:.3f}"


class AccountsError(ValueError):
    """The account list cannot be read; the message names the entry and the field."""


class CapReached(Exception):
    """The next request could take the running spend past ``--spend-cap``."""


@dataclass(frozen=True)
class Account:
    """One record of the account list (D4)."""

    handle: str
    category: str
    region: str
    check: str
    name: str = ""
    lang: str = ""
    why: str = ""


def _account(number: int, record: object) -> Account:
    if not isinstance(record, dict):
        raise AccountsError(f"entry {number} is not a record of {', '.join(FIELDS)}")
    unknown = sorted(str(key) for key in record if key not in FIELDS)
    if unknown:
        raise AccountsError(
            f"entry {number}: unknown fields {', '.join(unknown)}; a record has {', '.join(FIELDS)}"
        )
    values: dict[str, str] = {}
    for name in FIELDS:
        value = record.get(name)
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise AccountsError(
                f"entry {number}: {name} is not text; quote it (YAML reads no, yes, on and "
                "off as booleans, digits as numbers)"
            )
        values[name] = value.strip()
        if name in REQUIRED and not values[name]:
            raise AccountsError(f"entry {number}: {name} is missing")
    values["handle"] = values["handle"].removeprefix("@")
    if not _HANDLE.fullmatch(values["handle"]):
        raise AccountsError(f"entry {number}: handle is not 1 to 15 letters, digits or underscores")
    if values["check"] not in CHECKS:
        raise AccountsError(f"entry {number}: check is not one of {', '.join(CHECKS)}")
    return Account(**values)


def read_accounts(path: Path) -> list[Account]:
    """The account list at ``path``, checked before anything is called.

    Args:
        path: A YAML list of records, e.g. ``.local/x-accounts.yaml``.

    Raises:
        AccountsError: The file cannot be read, is not a non-empty YAML list, or an entry
            is not a record of ``FIELDS`` with its required fields as text, a valid
            handle and ``check`` ``seen`` or ``candidate``, or repeats a handle. The
            message names the entry and the field, never a value.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise AccountsError(f"cannot read the account list {path}: {error.strerror}") from None
    try:
        records = yaml.safe_load(text)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark is not None else ""
        raise AccountsError(f"the account list {path} is not YAML{where}") from None
    if not isinstance(records, list) or not records:
        raise AccountsError(f"the account list {path} is not a non-empty YAML list of records")
    accounts: list[Account] = []
    seen: set[str] = set()
    for number, record in enumerate(records, 1):
        account = _account(number, record)
        if account.handle.lower() in seen:
            raise AccountsError(f"entry {number}: the handle is listed twice")
        seen.add(account.handle.lower())
        accounts.append(account)
    return accounts


def counts_pages(days: int) -> int:
    """``counts/all`` pages a query takes over ``days`` days and today's part, e.g. 3 for 90."""
    return math.ceil((days + 1) / PAGE_DAYS)


@dataclass(frozen=True)
class Plan:
    """The calls of a run over ``accounts`` accounts and the plan's formula: the estimate."""

    accounts: int
    days: int

    @property
    def pages(self) -> int:
        """Pages per counts query."""
        return counts_pages(self.days)

    @property
    def lookups(self) -> int:
        """``get_users_by_usernames`` requests, one per batch of up to 100."""
        return math.ceil(self.accounts / BATCH)

    @property
    def counts(self) -> int:
        """``get_posts_counts_all`` requests: two queries a page each per account."""
        return self.accounts * len(QUERIES) * self.pages

    @property
    def requests(self) -> int:
        """Every request but the fallback lookups: users, counts, samples, the usage reading."""
        return self.lookups + self.counts + self.accounts + 1

    @property
    def components(self) -> tuple[tuple[str, str, int], ...]:
        """The formula's terms: label, the term written out, thousandths of a USD."""
        n = self.accounts
        return (
            ("users", f"{usd(PRICE_USER)} x {n}", PRICE_USER * n),
            ("recent posts", f"{usd(PRICE_POST)} x {n}", PRICE_POST * n),
            (
                "counts/all",
                f"{usd(PRICE_COUNTS_ALL)} x {n} x {self.pages} x {len(QUERIES)}",
                PRICE_COUNTS_ALL * n * self.pages * len(QUERIES),
            ),
            ("sample posts", f"{usd(PRICE_POST)} x {n} x {SAMPLE}", PRICE_POST * n * SAMPLE),
        )

    @property
    def total(self) -> int:
        """The estimate in thousandths of a USD."""
        return sum(mills for _, _, mills in self.components)

    def lines(self) -> list[str]:
        """The estimate as printed: N, the call plan, the formula, the time."""
        n = self.accounts
        minutes = math.ceil(self.requests / RATE_LIMIT.per_minute)
        waits = max(0, math.ceil(self.counts / COUNTS_WINDOW) - 1)
        calls = [
            (
                "get_users_by_usernames",
                f"{self.lookups}",
                f"batches of up to {BATCH}, the most recent post expanded",
            ),
            (
                "get_posts_by_ids",
                f"0 to {self.lookups}",
                "only where the expansion returned no dated post",
            ),
            (
                "get_posts_counts_all",
                f"{self.counts}",
                f"{n} accounts x {len(QUERIES)} queries x {self.pages} pages",
            ),
            ("get_users_posts", f"{n}", f"{SAMPLE} posts each, no expansion"),
            ("GET /2/usage/tweets", "1", "after the run; the snapshot states no price"),
            ("total", f"{self.requests}", f"and up to {self.lookups} fallback lookups"),
        ]
        lines = [
            f"accounts: {n}; window: {self.days} days, {self.pages} counts pages a query",
            "calls:",
            *(f"  {name:<22} {count:>6}  {note}" for name, count, note in calls),
            "estimate at the prices of docs/upstream/pages/pricing.md (2026-10-29):",
        ]
        lines += [
            f"  {label:<14} {term:<22} {usd(mills):>8} USD"
            for label, term, mills in self.components
        ]
        lines += [
            f"  {'total':<14} {'':<22} {usd(self.total):>8} USD",
            "X bills a resource read again the same UTC day once; counts requests every time",
            f"time: about {minutes} min of requests at {RATE_LIMIT.per_minute} a minute, and "
            f"{waits} wait(s) of up to {MAX_WAIT / 60:.0f} min for the counts window "
            f"({COUNTS_WINDOW} requests per 15 minutes)",
        ]
        return lines


@dataclass
class Spend:
    """The running spend against the cap, in thousandths of a USD, and the requests made."""

    cap: int
    spent: int = 0
    requests: Counter[str] = field(default_factory=Counter)
    cached: Counter[str] = field(default_factory=Counter)

    def allow(self, upper: int, what: str) -> None:
        """Pass when a request costing up to ``upper`` keeps the spend within the cap.

        Raises:
            CapReached: ``spent + upper`` would pass the cap; nothing is sent.
        """
        if self.spent + upper > self.cap:
            raise CapReached(
                f"the next request ({what}, up to {usd(upper)} USD) could take the spend of "
                f"{usd(self.spent)} USD past the cap of {usd(self.cap)} USD; nothing was sent"
            )

    def add(self, what: str, cost: int) -> None:
        """Count one request and what it cost."""
        self.spent += cost
        self.requests[what] += 1

    def line(self, plan: Plan) -> str:
        """Estimate and actual spend of this run, as printed at the end."""
        return (
            f"estimate {usd(plan.total)} USD, actual {usd(self.spent)} USD in "
            f"{sum(self.requests.values())} requests, before X's same-day deduplication; "
            f"{sum(self.cached.values())} pages read from the cache"
        )


def billed(page: UpstreamModel) -> int:
    """What X bills for one answer in thousandths of a USD, at the snapshot's prices.

    A counts page is billed per request; a lookup or a timeline per user and post it
    returns, in ``data`` and in ``includes``.
    """
    if isinstance(page, GetPostsCountsAllResponse):
        return PRICE_COUNTS_ALL
    users = posts = 0
    if isinstance(page, GetUsersByUsernamesResponse):
        users += len(page.data or [])
    elif isinstance(page, GetPostsByIdsResponse | GetUsersPostsResponse):
        posts += len(page.data or [])
    includes = getattr(page, "includes", None)
    if isinstance(includes, Expansions):
        users += len(includes.users or [])
        posts += len(includes.posts or [])
    return users * PRICE_USER + posts * PRICE_POST


def cache_key(label: str, params: Mapping[str, object]) -> str:
    """``label`` and a digest of the request's parameters, e.g. ``usda-all-p1-0f3c…``."""
    text = json.dumps(params, sort_keys=True, default=str)
    return f"{label}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"


@dataclass(frozen=True)
class Cache:
    """The pages of one UTC day, ``<root>/<wrapper>/<key>.json``."""

    root: Path

    def path(self, wrapper: str, key: str) -> Path:
        """Where the page of ``wrapper`` under ``key`` is kept."""
        return self.root / wrapper / f"{key}.json"

    def read[T: UpstreamModel](self, model: type[T], wrapper: str, key: str) -> T | None:
        """The kept page as ``model``, or ``None`` when there is none or it does not read."""
        try:
            return model.model_validate_json(self.path(wrapper, key).read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return None

    def write(self, wrapper: str, key: str, page: UpstreamModel) -> None:
        """Keep ``page`` as its ``dump_upstream``."""
        path = self.path(wrapper, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(page.dump_upstream(), ensure_ascii=False), encoding="utf-8")


async def with_waits[T](call: Callable[[], Awaitable[T]]) -> T:
    """``call()``, waiting out a spent rate-limit window and calling again (ADR-0010).

    A ``RateLimitError`` whose ``retry_after`` is a window's (``classify``: until
    ``x-rate-limit-reset``) is waited out, at most ``MAX_WAIT``, the wait printed first;
    one with a billing cycle's (a usage cap), or a fourth for the same call, is raised.
    """
    waits = 0
    while True:
        try:
            return await call()
        except RateLimitError as error:
            wait = RATE_LIMIT_WINDOW if error.retry_after is None else error.retry_after
            if wait >= BILLING_CYCLE or waits >= MAX_WAITS:
                raise
            wait = min(wait, MAX_WAIT)
            _say(f"rate limit: {error} Waiting {wait:.0f} s, then resuming.")
            await _sleep(wait)
            waits += 1


def midnight(moment: datetime) -> datetime:
    """The UTC midnight that starts ``moment``'s day."""
    return moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def window_start(now: datetime, days: int) -> datetime:
    """``start_time`` of the counts: the UTC midnight ``days`` days before today's."""
    return midnight(now) - timedelta(days=days)


def day_counts(pages: Iterable[GetPostsCountsAllResponse]) -> dict[datetime, int]:
    """Posts per daily bucket, by the bucket's start, over the pages of one query.

    A bucket repeated on a later page keeps its first count.
    """
    counts: dict[datetime, int] = {}
    for page in pages:
        for bucket in page.data or []:
            counts.setdefault(bucket.start, bucket.post_count)
    return counts


def posts_from(
    counts: Mapping[datetime, int], since: datetime, until: datetime | None = None
) -> int:
    """Posts in the buckets that start at or after ``since`` and before ``until``."""
    return sum(
        count
        for start, count in counts.items()
        if start >= since and (until is None or start < until)
    )


@dataclass(frozen=True)
class Activity:
    """What one account's daily counts say, by D5's definitions."""

    posts_14d: int
    posts_30d: int
    originals_14d: int
    originals_per_week: float
    originals_first_30d: int
    originals_last_30d: int
    trend: float | None
    active: bool
    core: bool


def measure(
    posts: Mapping[datetime, int], originals: Mapping[datetime, int], *, now: datetime, days: int
) -> Activity:
    """D5's measures from the daily counts of all posts and of original posts.

    Args:
        posts: Posts per day of ``from:<handle>``, by bucket start (``day_counts``).
        originals: The same of ``from:<handle> -is:retweet -is:reply``.
        now: The time of the run, e.g. ``datetime(2026, 10, 29, 16, tzinfo=UTC)``.
        days: The window, e.g. ``90``.

    Returns:
        Posts and original posts in the last 14 and 30 days, original posts a week over
        the window, the first and the last 30 days of original posts and their ratio
        (``None`` when the first 30 hold none), active and core.
    """
    start = window_start(now, days)
    today = midnight(now)
    per_week = posts_from(originals, start) / (days / 7)
    first = posts_from(originals, start, start + timedelta(days=TREND_DAYS))
    last = posts_from(originals, today - timedelta(days=TREND_DAYS))
    recent = posts_from(originals, today - timedelta(days=ACTIVE_DAYS))
    return Activity(
        posts_14d=posts_from(posts, today - timedelta(days=ACTIVE_DAYS)),
        posts_30d=posts_from(posts, today - timedelta(days=RECENT_DAYS)),
        originals_14d=recent,
        originals_per_week=per_week,
        originals_first_30d=first,
        originals_last_30d=last,
        trend=last / first if first else None,
        active=recent >= 1,
        core=per_week >= CORE_PER_WEEK,
    )


@dataclass(frozen=True)
class Row:
    """One listed account and what the probe found."""

    account: Account
    status: str
    user: User | None = None
    problem: str = ""
    last_post: datetime | None = None
    activity: Activity | None = None
    sample: tuple[Post, ...] = ()

    @property
    def measured(self) -> bool:
        """Resolved and not protected."""
        return self.status == MEASURED

    @property
    def active(self) -> bool:
        """An original post in the last 14 days."""
        return self.activity is not None and self.activity.active

    @property
    def core(self) -> bool:
        """Two original posts a week on average over the window."""
        return self.activity is not None and self.activity.core


@dataclass(frozen=True)
class Tally:
    """Measured, active and core accounts of a group, and the categories of its core."""

    measured: int
    active: int
    core: int
    categories: int

    @property
    def holds(self) -> bool:
        """Go's conditions: half active, 25 core over 4 categories."""
        return (
            self.measured > 0
            and self.active / self.measured >= GO_ACTIVE_SHARE
            and self.core >= GO_CORE
            and self.categories >= GO_CATEGORIES
        )


def tally(rows: Iterable[Row]) -> Tally:
    """Count the measured, active and core accounts of ``rows``."""
    measured = [row for row in rows if row.measured]
    core = [row for row in measured if row.core]
    return Tally(
        measured=len(measured),
        active=sum(row.active for row in measured),
        core=len(core),
        categories=len({row.account.category.casefold() for row in core}),
    )


def _region(row: Row) -> str:
    return row.account.region.upper()


@dataclass(frozen=True)
class Decision:
    """D5's answer and the numbers it rests on."""

    verdict: str
    everyone: Tally
    us: Tally
    eu_core: int


def decide(rows: Sequence[Row]) -> Decision:
    """Go, US-only or no-go by D5's thresholds; US-only first, since it narrows a go."""
    everyone = tally(rows)
    us = tally(row for row in rows if _region(row) == US)
    eu_core = tally(row for row in rows if _region(row) == EU).core
    if us.holds and eu_core < US_ONLY_EU_CORE:
        verdict = US_ONLY
    elif everyone.holds:
        verdict = GO
    else:
        verdict = NO_GO
    return Decision(verdict=verdict, everyone=everyone, us=us, eu_core=eu_core)


def _share(group: Tally) -> str:
    share = f"{group.active / group.measured:.0%}" if group.measured else "none measured"
    return f"{group.active} of {group.measured} active ({share})"


def decision_line(decision: Decision) -> str:
    """The decision and every number it rests on, in one line."""
    everyone, us = decision.everyone, decision.us
    return (
        f"Decision (D5): {decision.verdict}. Measured accounts: {_share(everyone)}, go needs "
        f"{GO_ACTIVE_SHARE:.0%}; {everyone.core} core, go needs {GO_CORE}; in "
        f"{everyone.categories} categories, go needs {GO_CATEGORIES}. Region {US}: "
        f"{_share(us)}, {us.core} core in {us.categories} categories. Region {EU}: "
        f"{decision.eu_core} core, {US_ONLY} needs fewer than {US_ONLY_EU_CORE}."
    )


def _flag(value: bool | None) -> str:
    return "" if value is None else ("yes" if value else "no")


def _time(moment: datetime | None) -> str:
    return "" if moment is None else moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def csv_row(row: Row) -> dict[str, str]:
    """One row of the CSV, under ``COLUMNS``; empty where nothing was measured."""
    user, activity = row.user, row.activity
    metrics = user.public_metrics if user is not None else None
    cells: dict[str, Any] = {
        "handle": row.account.handle,
        "status": row.status,
        "resolved": _flag(user is not None),
        "protected": _flag(user.protected if user is not None else None),
        "followers": metrics.followers_count if metrics else "",
        "post_count": metrics.post_count if metrics else "",
        "last_post": _time(row.last_post),
        "category": row.account.category,
        "region": row.account.region,
        "check": row.account.check,
    }
    if activity is not None:
        cells |= {
            "posts_14d": activity.posts_14d,
            "posts_30d": activity.posts_30d,
            "originals_14d": activity.originals_14d,
            "originals_per_week": f"{activity.originals_per_week:.2f}",
            "originals_first_30d": activity.originals_first_30d,
            "originals_last_30d": activity.originals_last_30d,
            "trend": "" if activity.trend is None else f"{activity.trend:.2f}",
            "active": _flag(activity.active),
            "core": _flag(activity.core),
        }
    return {column: str(cells.get(column, "")) for column in COLUMNS}


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _table(rows: Sequence[Row], name: str, key: Callable[[Row], str]) -> list[str]:
    groups: dict[str, list[Row]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    lines = [
        f"| {name} | listed | resolved | measured | active | core |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, members in [*sorted(groups.items()), ("all", list(rows))]:
        group = tally(members)
        resolved = sum(member.user is not None for member in members)
        lines.append(
            f"| {_cell(label)} | {len(members)} | {resolved} | {group.measured} | "
            f"{group.active} | {group.core} |"
        )
    return lines


def _sample_line(post: Post) -> str:
    metrics = post.public_metrics
    counts = f"{metrics.like_count} likes, {metrics.repost_count} reposts" if metrics else ""
    when = f"{post.created_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC" if post.created_at else ""
    head = " · ".join(part for part in (when, post.lang or "", counts) if part)
    return f"- {head}: {' '.join((post.text or '').split())}"


def report(
    rows: Sequence[Row],
    *,
    decision: Decision,
    now: datetime,
    days: int,
    plan: Plan,
    spend: Spend,
    usage: str,
) -> str:
    """``probe-<date>.md``: summary, decision line, accounts not measured, spend, samples."""
    start = window_start(now, days)
    lines = [
        f"# Account probe, {now:%Y-%m-%d}",
        "",
        f"{len(rows)} accounts listed; posts counted by UTC day from {_time(start)} to "
        f"{_time(now)}, {days} days and today's part. Measured: resolved and not protected. "
        f"Active: at least one original post (neither a repost nor a reply) in the last "
        f"{ACTIVE_DAYS} days. Core: at least {CORE_PER_WEEK:g} original posts a week on "
        f"average over the {days} days. Trend: original posts of the last {TREND_DAYS} days "
        f"against the first {TREND_DAYS} of the window. Per account: probe-{now:%Y-%m-%d}.csv.",
        "",
        "## Decision",
        "",
        decision_line(decision),
        "",
        "## By category",
        "",
        *_table(rows, "category", lambda row: row.account.category),
        "",
        "## By region",
        "",
        *_table(rows, "region", lambda row: row.account.region),
        "",
        "## Not measured",
        "",
    ]
    missing = [row for row in rows if not row.measured]
    if missing:
        lines += ["| handle | status | X's answer |", "| --- | --- | --- |"]
        lines += [
            f"| @{row.account.handle} | {row.status} | {_cell(row.problem)} |" for row in missing
        ]
    else:
        lines.append("None: every listed account was resolved and is public.")
    lines += ["", "## Spend", "", f"This run: {spend.line(plan)}.", "", f"{usage}.", ""]
    lines += ["## Samples", ""]
    for row in rows:
        if not row.measured:
            continue
        account = row.account
        lines += [f"### @{account.handle} ({account.category}, {account.region})", ""]
        lines += [_sample_line(post) for post in row.sample] or ["No posts returned."]
        lines.append("")
    return "\n".join(lines)


def write_reports(
    out: Path,
    rows: Sequence[Row],
    *,
    decision: Decision,
    now: datetime,
    days: int,
    plan: Plan,
    spend: Spend,
    usage: str,
) -> tuple[Path, Path]:
    """Write ``probe-<date>.csv`` and ``probe-<date>.md`` into ``out``; their paths."""
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"probe-{now:%Y-%m-%d}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(csv_row(row) for row in rows)
    md_path = out / f"probe-{now:%Y-%m-%d}.md"
    text = report(rows, decision=decision, now=now, days=days, plan=plan, spend=spend, usage=usage)
    md_path.write_text(text, encoding="utf-8")
    return csv_path, md_path


def usage_line(payload: object) -> str:
    """The usage reading's ``project_usage``, ``project_cap`` and ``cap_reset_day``."""
    data = payload.get("data") if isinstance(payload, dict) else None
    found = data if isinstance(data, dict) else {}
    parts = [
        f"{name} {found[name]}" if name in found else f"{name} not given" for name in USAGE_FIELDS
    ]
    return "usage (GET /2/usage/tweets): " + ", ".join(parts)


class Probe:
    """One run over the list: the calls, the cache and the spend.

    Args:
        accounts: The list, e.g. from ``read_accounts``.
        days: The window, e.g. ``90``.
        now: The time of the run, timezone-aware.
        cache: The day's cache.
        spend: The spend and its cap.
    """

    def __init__(
        self, accounts: Sequence[Account], *, days: int, now: datetime, cache: Cache, spend: Spend
    ) -> None:
        self.accounts = list(accounts)
        self.days = days
        self.now = now
        self.start = window_start(now, days)
        self.cache = cache
        self.spend = spend
        self.usage = "usage: not read"

    async def _fetch[T: UpstreamModel](
        self,
        wrapper: str,
        key: str,
        model: type[T],
        call: Callable[[], Awaitable[T]],
        *,
        upper: int,
    ) -> T:
        cached = self.cache.read(model, wrapper, key)
        if cached is not None:
            self.spend.cached[wrapper] += 1
            return cached
        self.spend.allow(upper, wrapper)
        page = await with_waits(call)
        self.spend.add(wrapper, billed(page))
        self.cache.write(wrapper, key, page)
        return page

    def _step(self, wrapper: str, tail: str) -> None:
        made, kept = self.spend.requests[wrapper], self.spend.cached[wrapper]
        _say(f"{wrapper}: {made} requested, {kept} from the cache; {tail}")

    async def _look_up(self) -> tuple[dict[str, User], dict[str, str], dict[str, datetime]]:
        """Users by lower-case handle, X's problems by handle, and the dated expanded posts."""
        users: dict[str, User] = {}
        problems: dict[str, str] = {}
        dated: dict[str, datetime] = {}
        handles = [account.handle for account in self.accounts]
        for number, first in enumerate(range(0, len(handles), BATCH), 1):
            batch = handles[first : first + BATCH]
            params = {
                "usernames": batch,
                "user.fields": USER_FIELDS,
                "expansions": [UserExpansion.MOST_RECENT_POST_ID],
                "post.fields": DATED,
            }
            page = await self._fetch(
                "get_users_by_usernames",
                cache_key(f"batch{number}", params),
                GetUsersByUsernamesResponse,
                partial(
                    api.get_users_by_usernames,
                    batch,
                    user_fields=USER_FIELDS,
                    expansions=[UserExpansion.MOST_RECENT_POST_ID],
                    post_fields=DATED,
                ),
                upper=len(batch) * (PRICE_USER + PRICE_POST),
            )
            for user in page.data or []:
                if user.username:
                    users[user.username.lower()] = user
            for problem in page.errors or []:
                name = (problem.value or problem.resource_id or "").lower()
                if name:
                    problems[name] = f"{problem.title}: {problem.detail}"
            for post in (page.includes.posts if page.includes else None) or []:
                if post.created_at is not None:
                    dated[post.id] = post.created_at
        return users, problems, dated

    async def _date(self, ids: Sequence[str]) -> dict[str, datetime]:
        """``created_at`` of the posts ``ids``, looked up in batches of up to 100."""
        dated: dict[str, datetime] = {}
        for first in range(0, len(ids), BATCH):
            batch = list(ids[first : first + BATCH])
            params = {"ids": batch, "post.fields": DATED}
            page = await self._fetch(
                "get_posts_by_ids",
                cache_key(f"batch{first // BATCH + 1}", params),
                GetPostsByIdsResponse,
                partial(api.get_posts_by_ids, batch, post_fields=DATED),
                upper=len(batch) * PRICE_POST,
            )
            for post in page.data or []:
                if post.created_at is not None:
                    dated[post.id] = post.created_at
        return dated

    async def _counts(self, account: Account, name: str) -> dict[datetime, int]:
        """The daily counts of one of ``QUERIES`` for ``account``, paged by ``next_token``.

        Paging ends without a ``next_token``, when the window's first day is in, on a page
        that adds no day, or after ``counts_pages`` pages.
        """
        query = QUERIES[name].format(handle=account.handle)
        params = {"query": query, "granularity": Granularity.DAY, "start_time": self.start}
        pages: list[GetPostsCountsAllResponse] = []
        token: str | None = None
        for number in range(1, counts_pages(self.days) + 1):
            page = await self._fetch(
                "get_posts_counts_all",
                cache_key(f"{account.handle.lower()}-{name}-p{number}", params),
                GetPostsCountsAllResponse,
                partial(
                    api.get_posts_counts_all,
                    query,
                    start_time=self.start,
                    granularity=Granularity.DAY,
                    next_token=token,
                ),
                upper=PRICE_COUNTS_ALL,
            )
            before = len(day_counts(pages))
            pages.append(page)
            found = day_counts(pages)
            token = page.meta.next_token if page.meta else None
            if not token or len(found) == before or min(found) <= self.start:
                break
        return day_counts(pages)

    async def _sample(self, user: User) -> GetUsersPostsResponse:
        """The ten newest posts of ``user``, no expansion."""
        params = {"id": user.id, "max_results": SAMPLE, "post.fields": SAMPLE_FIELDS}
        return await self._fetch(
            "get_users_posts",
            cache_key(user.id, params),
            GetUsersPostsResponse,
            partial(
                api.get_users_posts,
                user.id,
                max_results=SAMPLE,
                post_fields=SAMPLE_FIELDS,
            ),
            upper=SAMPLE * PRICE_POST,
        )

    async def _read_usage(self) -> str:
        if not self.spend.requests:
            return "usage: not read, nothing was fetched"
        try:
            payload = await with_waits(partial(client.get_json, USAGE_PATH))
        except XippiosError as error:
            return f"usage: not read ({error})"
        finally:
            self.spend.add("GET /2/usage/tweets", 0)
        return usage_line(payload)

    async def run(self) -> list[Row]:
        """The calls in the plan's order; one row per listed account.

        Raises:
            CapReached: A request could take the spend past the cap; nothing more is sent.
            XippiosError: X refused, e.g. ``AuthError`` or a usage cap's ``RateLimitError``.
        """
        users, problems, dated = await self._look_up()
        measured = [
            (account, users[account.handle.lower()])
            for account in self.accounts
            if account.handle.lower() in users
            and users[account.handle.lower()].protected is not True
        ]
        protected = sum(user.protected is True for user in users.values())
        self._step(
            "get_users_by_usernames",
            f"{len(users)} of {len(self.accounts)} resolved, {protected} protected, "
            f"{len(self.accounts) - len(users)} unresolved",
        )
        undated = [
            user.most_recent_post_id
            for _, user in measured
            if user.most_recent_post_id and user.most_recent_post_id not in dated
        ]
        if undated:
            dated |= await self._date(undated)
            found = sum(post_id in dated for post_id in undated)
            self._step("get_posts_by_ids", f"{found} of {len(undated)} last posts dated")
        else:
            _say("get_posts_by_ids: not needed, every expansion returned its post dated")
        counts: dict[str, tuple[dict[datetime, int], dict[datetime, int]]] = {}
        for account, _ in measured:
            counts[account.handle] = (
                await self._counts(account, "all"),
                await self._counts(account, "originals"),
            )
        self._step("get_posts_counts_all", f"{len(measured)} accounts counted")
        samples: dict[str, tuple[Post, ...]] = {}
        for account, user in measured:
            samples[account.handle] = tuple((await self._sample(user)).data or [])
        self._step(
            "get_users_posts", f"{sum(len(posts) for posts in samples.values())} posts sampled"
        )
        self.usage = await self._read_usage()
        _say(self.usage)
        return [
            self._row(account, users, problems, dated, counts, samples) for account in self.accounts
        ]

    def _row(
        self,
        account: Account,
        users: Mapping[str, User],
        problems: Mapping[str, str],
        dated: Mapping[str, datetime],
        counts: Mapping[str, tuple[dict[datetime, int], dict[datetime, int]]],
        samples: Mapping[str, tuple[Post, ...]],
    ) -> Row:
        user = users.get(account.handle.lower())
        if user is None:
            problem = problems.get(account.handle.lower(), "not in X's answer")
            return Row(account, UNRESOLVED, problem=problem)
        if user.protected is True:
            return Row(account, PROTECTED, user=user, problem="protected")
        sample = samples.get(account.handle, ())
        last = dated.get(user.most_recent_post_id or "")
        if last is None:
            times = [post.created_at for post in sample if post.created_at is not None]
            last = max(times, default=None)
        posts, originals = counts[account.handle]
        activity = measure(posts, originals, now=self.now, days=self.days)
        return Row(account, MEASURED, user=user, last_post=last, activity=activity, sample=sample)


async def _probe_async(probe: Probe) -> list[Row]:
    return await probe.run()


_probe = sync(_probe_async)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """The command line; ``--spend`` without ``--spend-cap`` is refused."""
    parser = argparse.ArgumentParser(
        prog="probe_accounts.py",
        description="Probe a curated list of X accounts for activity (the gate P report).",
    )
    parser.add_argument(
        "--accounts",
        type=Path,
        default=LOCAL / "x-accounts.yaml",
        metavar="PATH",
        help="the YAML account list (default: .local/x-accounts.yaml)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--estimate", action="store_true", help="print the estimate, call nothing (the default)"
    )
    mode.add_argument("--spend", action="store_true", help="run the calls; needs --spend-cap")
    parser.add_argument(
        "--spend-cap", type=float, metavar="USD", help="the most this run may spend, e.g. 12"
    )
    parser.add_argument(
        "--days", type=int, default=DAYS, help=f"the window in days (default {DAYS})"
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=LOCAL / "cache",
        metavar="DIR",
        help="the page cache, a directory per UTC day (default: .local/cache)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=LOCAL,
        metavar="DIR",
        help="where probe-<date>.csv and .md go (default: .local)",
    )
    args = parser.parse_args(argv)
    if args.spend and args.spend_cap is None:
        parser.error("--spend needs --spend-cap USD, the most this run may spend")
    if args.spend_cap is not None and not args.spend:
        parser.error("--spend-cap goes with --spend")
    if args.spend_cap is not None and not (math.isfinite(args.spend_cap) and args.spend_cap > 0):
        parser.error("--spend-cap takes a positive amount in USD, e.g. 12")
    if args.days < MIN_DAYS:
        parser.error(f"--days takes at least {MIN_DAYS}: the trend compares two 30-day spans")
    return args


def main(argv: Sequence[str] | None = None, *, now: datetime | None = None) -> int:
    """Estimate, or run under the cap and write the reports; the exit status.

    Args:
        argv: The command line without the program, e.g. ``["--spend", "--spend-cap",
            "12"]``; ``sys.argv[1:]`` when ``None``.
        now: The time of the run, for a test; the current time when ``None``.
    """
    args = parse_args(argv)
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    try:
        accounts = read_accounts(args.accounts)
    except AccountsError as error:
        _say(f"not run: {error}")
        return 1
    plan = Plan(len(accounts), args.days)
    _say(*plan.lines())
    if not args.spend:
        return 0
    cap = round(args.spend_cap * 1000)
    if plan.total > cap:
        _say(f"not run: the estimate of {usd(plan.total)} USD exceeds the cap of {usd(cap)} USD")
        return 1
    if not os.environ.get(API_KEY_ENV):
        _say(f"not run: {API_KEY_ENV} is not set; run through direnv exec")
        return 1
    _say(f"cap: {usd(cap)} USD")
    spend = Spend(cap)
    cache = Cache(args.cache / f"{moment:%Y-%m-%d}")
    probe = Probe(accounts, days=args.days, now=moment, cache=cache, spend=spend)
    try:
        rows = _probe(probe)
    except (CapReached, XippiosError) as error:
        _say(
            f"stopped: {error}",
            f"spend: {spend.line(plan)}",
            "the pages fetched are in the cache; a re-run today reads them without a request",
        )
        return 1
    decision = decide(rows)
    csv_path, md_path = write_reports(
        args.out,
        rows,
        decision=decision,
        now=moment,
        days=args.days,
        plan=plan,
        spend=spend,
        usage=probe.usage,
    )
    _say(f"spend: {spend.line(plan)}", f"wrote {csv_path} and {md_path}", decision_line(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
