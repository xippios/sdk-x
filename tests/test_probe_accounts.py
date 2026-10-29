"""The account probe: its replay over the recorded fixtures, its estimate, cap and waits.

The run replays PR 3's fixtures over a list of the three recorded accounts written to a
temporary directory, into a temporary ``--out`` and ``--cache``; nothing is recorded and
nothing reaches X. How the recorded answers stand in:

- ``get_users_by_usernames/three_accounts`` answers the lookup. It was recorded without
  ``post.fields``, so its expanded posts carry no ``created_at`` and the probe dates them
  through ``get_posts_by_ids/most_recent_three``, the same three posts: the fallback runs.
- The USDA counts fixtures answer every counts query, those of @XDevelopers and @FAO too:
  the first page of ``from:<handle>`` is ``usda_by_day``, the first of the original posts
  ``usda_originals_by_day``, every next page ``usda_by_day_page_2``. The third page so
  repeats the second, and the probe ends the query on a page that adds no day, after the
  three pages of its estimate. Every account thus has USDA's counts.
- ``get_users_posts/*_ten`` answer the samples; recorded without the expansion, every
  sample post reads as an original.
- ``GET /2/usage/tweets`` has no wrapper and no fixture: the test builds its answer in the
  OpenAPI document's ``Usage`` shape with made-up numbers, as ``test_record_fixture.py``
  builds the answers it records, and ``test_client.py`` its 429.

The metric, decision and cap tests use synthetic daily buckets and rows.
"""

import csv
import importlib.util
import json
import math
import re
import time
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
import respx
from xippios.core import RateLimitError
from xippios.core.testing import ReplayFixture, fixture_path, load_fixture, sent_query, sent_urls

from xippios.x import api
from xippios.x._client import BILLING_CYCLE
from xippios.x.models import GetPostsByIdsResponse, GetPostsCountsAllResponse, Granularity

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_accounts.py"
FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 29, 16, 0, tzinfo=UTC)
START = datetime(2026, 7, 31, tzinfo=UTC)
COUNTS_URL = "https://api.x.com/2/tweets/counts/all"
USAGE_URL = "https://api.x.com/2/usage/tweets"
USAGE = {"data": {"project_usage": "1234", "project_cap": "3000000", "cap_reset_day": 7}}
"""A made-up answer in the document's ``Usage`` shape; X's own is not recorded."""
TEXT = "[text rewritten]"
HANDLES = ("XDevelopers", "USDA", "FAO")
ACCOUNTS = """\
- handle: XDevelopers
  name: Developers
  category: platform
  region: US
  lang: en
  why: the first recorded account
  check: seen
- handle: "@USDA"
  name: Dept. of Agriculture
  category: ministry
  region: US
  lang: en
  why: the second recorded account
  check: seen
- handle: FAO
  name: Food and Agriculture Organization
  category: un-agency
  region: EU
  lang: en
  why: the third recorded account
  check: candidate
"""


@pytest.fixture(scope="module")
def probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location("probe_accounts", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def served(case: str) -> httpx.Response:
    """The recorded answer of ``get_posts_counts_all/<case>``, as ``replay_fixture`` serves it."""
    fixture = load_fixture(fixture_path(FIXTURES, "get_posts_counts_all", case))
    return httpx.Response(
        fixture.response.status, headers=fixture.response.headers, content=fixture.response.content
    )


def counts_answer(request: httpx.Request) -> httpx.Response:
    """USDA's recorded counts for every counts query (the module docstring)."""
    if "next_token" in request.url.params:
        return served("usda_by_day_page_2")
    if "-is:retweet" in request.url.params["query"]:
        return served("usda_originals_by_day")
    return served("usda_by_day")


@pytest.fixture
def routes(replay_fixture: ReplayFixture, respx_mock: respx.MockRouter) -> dict[str, respx.Route]:
    return {
        "users": replay_fixture("get_users_by_usernames", "three_accounts"),
        "posts": replay_fixture("get_posts_by_ids", "most_recent_three"),
        "xdevelopers_ten": replay_fixture("get_users_posts", "xdevelopers_ten"),
        "usda_ten": replay_fixture("get_users_posts", "usda_ten"),
        "fao_ten": replay_fixture("get_users_posts", "fao_ten"),
        "counts": respx_mock.get(COUNTS_URL).mock(side_effect=counts_answer),
        "usage": respx_mock.get(USAGE_URL).mock(return_value=httpx.Response(200, json=USAGE)),
    }


@pytest.fixture
def listed(tmp_path: Path) -> Path:
    path = tmp_path / "x-accounts.yaml"
    path.write_text(ACCOUNTS, encoding="utf-8")
    return path


def spend_argv(listed: Path, cap: str) -> list[str]:
    folder = listed.parent
    return [
        *("--accounts", str(listed), "--spend", "--spend-cap", cap),
        *("--out", str(folder / "out"), "--cache", str(folder / "cache")),
    ]


def calls(routes: dict[str, respx.Route]) -> dict[str, int]:
    return {name: route.call_count for name, route in routes.items()}


def billed_dating() -> int:
    """Thousandths of a USD the replayed ``get_posts_by_ids`` answer bills, read from the
    fixture as it stands, so the test holds whether or not it carries a referenced post in
    ``includes``."""
    fixture = load_fixture(fixture_path(FIXTURES, "get_posts_by_ids", "most_recent_three"))
    page = GetPostsByIdsResponse.model_validate_json(fixture.response.body)
    included = page.includes.posts if page.includes is not None else None
    return 5 * (len(page.data or []) + len(included or []))


USERS = 3 * 10 + 3 * 5
"""What ``three_accounts`` bills: three users and their three most recent posts."""
COUNTS = 18 * 10
SAMPLES = (10 + 9 + 10) * 5


def buckets(case: str) -> dict[str, int]:
    """The recorded buckets' counts by their start, read from the fixture's JSON."""
    fixture = load_fixture(fixture_path(FIXTURES, "get_posts_counts_all", case))
    return {
        item["start"]: item["tweet_count"] for item in json.loads(fixture.response.body)["data"]
    }


def between(counts: dict[str, int], since: str, until: str = "9999") -> int:
    return sum(count for start, count in counts.items() if since <= start < until)


def test_the_probe_replays_the_three_accounts_into_its_reports(
    probe: ModuleType,
    routes: dict[str, respx.Route],
    listed: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every call once in the plan's order, the CSV's rows and columns, the MD's sections and
    its decision line from the CSV's numbers; then a second run over the same cache."""
    out = listed.parent / "out"
    assert probe.main(spend_argv(listed, "1"), now=NOW) == 0
    first = calls(routes)
    assert first == {
        "users": 1,
        "posts": 1,
        "xdevelopers_ten": 1,
        "usda_ten": 1,
        "fao_ten": 1,
        "counts": 3 * 2 * 3,
        "usage": 1,
    }

    assert sent_query(routes["users"]) == {
        "usernames": "XDevelopers,USDA,FAO",
        "user.fields": "created_at,description,location,protected,public_metrics,verified_type,url",
        "expansions": "most_recent_post_id",
        "post.fields": "created_at",
    }
    assert sent_query(routes["posts"]) == {
        "ids": "2114879022433800258,2115806101480337475,2115789000682180921",
        "post.fields": "created_at",
    }
    assert sent_query(routes["usda_ten"]) == {
        "max_results": "10",
        "post.fields": "created_at,lang,public_metrics,conversation_id",
    }
    sent = [httpx.URL(url).params for url in sent_urls(routes["counts"])]
    assert {(params["granularity"], params["start_time"]) for params in sent} == {
        ("day", "2026-07-31T00:00:00Z")
    }
    expected_queries = [
        query.format(handle=handle)
        for handle in HANDLES
        for query in ("from:{handle}", "from:{handle} -is:retweet -is:reply")
        for _ in range(3)
    ]
    assert [params["query"] for params in sent] == expected_queries
    assert [params.get("next_token") for params in sent] == [None, "REDACTED", "REDACTED"] * 6

    with (out / "probe-2026-10-29.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    assert tuple(reader.fieldnames or ()) == probe.COLUMNS
    assert [row["handle"] for row in rows] == list(HANDLES)
    assert {row["status"] for row in rows} == {"measured"}
    assert [(row["followers"], row["post_count"]) for row in rows] == [
        ("697765", "4381"),
        ("1114940", "25727"),
        ("756206", "46908"),
    ]
    assert [row["last_post"] for row in rows] == [
        "2026-10-27T00:37:06Z",
        "2026-10-29T14:00:59Z",
        "2026-10-29T12:53:01Z",
    ]
    assert [(row["category"], row["region"], row["check"]) for row in rows] == [
        ("platform", "US", "seen"),
        ("ministry", "US", "seen"),
        ("un-agency", "EU", "candidate"),
    ]

    # USDA's buckets as the routes served them, counted here from the fixtures' JSON.
    every = buckets("usda_by_day") | buckets("usda_by_day_page_2")
    originals = buckets("usda_originals_by_day") | buckets("usda_by_day_page_2")
    first_30 = between(originals, "2026-07-31", "2026-08-30")
    last_30 = between(originals, "2026-09-29")
    per_week = sum(originals.values()) / (90 / 7)
    measured = {
        "posts_14d": str(between(every, "2026-10-15")),
        "posts_30d": str(between(every, "2026-09-29")),
        "originals_14d": str(between(originals, "2026-10-15")),
        "originals_per_week": f"{per_week:.2f}",
        "originals_first_30d": str(first_30),
        "originals_last_30d": str(last_30),
        "trend": f"{last_30 / first_30:.2f}" if first_30 else "",
        "active": "yes" if between(originals, "2026-10-15") else "no",
        "core": "yes" if per_week >= 2 else "no",
    }
    for row in rows:
        assert {name: row[name] for name in measured} == measured

    report = (out / "probe-2026-10-29.md").read_text(encoding="utf-8")
    sections = ["## Decision", "## By category", "## By region", "## Not measured"]
    sections += ["## Spend", "## Samples"]
    assert [line for line in report.splitlines() if line.startswith("## ")] == sections
    assert "None: every listed account was resolved and is public." in report
    samples = report.split("## Samples", 1)[1]
    assert [line for line in samples.splitlines() if line.startswith("### ")] == [
        "### @XDevelopers (platform, US)",
        "### @USDA (ministry, US)",
        "### @FAO (un-agency, EU)",
    ]
    assert sum(line.endswith(f": {TEXT}") for line in samples.splitlines()) == 10 + 9 + 10

    def counted(group: list[dict[str, str]]) -> Any:
        core = [row for row in group if row["core"] == "yes"]
        return probe.Tally(
            measured=len(group),
            active=sum(row["active"] == "yes" for row in group),
            core=len(core),
            categories=len({row["category"] for row in core}),
        )

    decision = probe.Decision(
        verdict="no-go",  # 3 accounts cannot reach 25 core
        everyone=counted(rows),
        us=counted([row for row in rows if row["region"] == "US"]),
        eu_core=counted([row for row in rows if row["region"] == "EU"]).core,
    )
    line = probe.decision_line(decision)
    assert line.startswith("Decision (D5): no-go. Measured accounts: ")
    assert line in report.splitlines()

    printed = capsys.readouterr().out
    assert line in printed
    actual = probe.usd(USERS + billed_dating() + COUNTS + SAMPLES)
    assert f"spend: estimate 0.375 USD, actual {actual} USD in 24 requests" in printed
    assert "usage (GET /2/usage/tweets): project_usage 1234, project_cap 3000000" in printed
    assert all(handle not in printed for handle in HANDLES), "the console prints no handle"
    assert TEXT not in printed
    assert TEXT not in (out / "probe-2026-10-29.csv").read_text(encoding="utf-8")

    table = (out / "probe-2026-10-29.csv").read_text(encoding="utf-8")
    assert probe.main(spend_argv(listed, "1"), now=NOW) == 0
    assert calls(routes) == first, "a second run the same day reads every page from the cache"
    assert (out / "probe-2026-10-29.csv").read_text(encoding="utf-8") == table
    again = capsys.readouterr().out
    assert "actual 0.000 USD in 0 requests, before X's same-day deduplication; 23 pages" in again
    assert "usage: not read, nothing was fetched" in again


def test_a_run_stopped_at_the_cap_keeps_its_pages_for_the_next(
    probe: ModuleType,
    routes: dict[str, respx.Route],
    listed: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """At 0.38 USD, above the estimate of 0.375, two samples fit and the third's upper
    bound (ten posts, 0.050) does not: the run stops before it and writes no report; a
    re-run with a higher cap fetches only the rest."""
    out = listed.parent / "out"
    assert probe.main(spend_argv(listed, "0.38"), now=NOW) == 1
    stopped = calls(routes)
    assert stopped["counts"] == 18
    assert (stopped["xdevelopers_ten"], stopped["usda_ten"]) == (1, 1)
    assert (stopped["fao_ten"], stopped["usage"]) == (0, 0)
    assert not out.exists()
    spent = probe.usd(USERS + billed_dating() + COUNTS + (10 + 9) * 5)
    printed = capsys.readouterr().out
    assert (
        "stopped: the next request (get_users_posts, up to 0.050 USD) could take the spend of "
        f"{spent} USD past the cap of 0.380 USD; nothing was sent"
    ) in printed
    assert f"spend: estimate 0.375 USD, actual {spent} USD in 22 requests" in printed

    assert probe.main(spend_argv(listed, "1"), now=NOW) == 0
    resumed = calls(routes)
    assert {name: resumed[name] - stopped[name] for name in resumed} == {
        "users": 0,
        "posts": 0,
        "xdevelopers_ten": 0,
        "usda_ten": 0,
        "fao_ten": 1,
        "counts": 0,
        "usage": 1,
    }
    assert (out / "probe-2026-10-29.md").exists()


def test_a_cap_under_the_estimate_refuses_before_any_call(
    probe: ModuleType, listed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.route()
        assert probe.main(spend_argv(listed, "0.3"), now=NOW) == 1
    assert route.call_count == 0
    assert "not run: the estimate of 0.375 USD exceeds the cap of 0.300 USD" in (
        capsys.readouterr().out
    )
    assert not (listed.parent / "out").exists()
    assert not (listed.parent / "cache").exists()


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--spend"], "--spend needs --spend-cap USD"),
        (["--spend-cap", "5"], "--spend-cap goes with --spend"),
        (["--spend", "--spend-cap", "0"], "--spend-cap takes a positive amount"),
        (["--spend", "--spend-cap", "inf"], "--spend-cap takes a positive amount"),
        (["--estimate", "--spend", "--spend-cap", "5"], "not allowed with argument"),
        (["--days", "59"], "--days takes at least 60"),
    ],
)
def test_the_command_line_refuses_a_spend_without_a_cap(
    probe: ModuleType, argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exited:
        probe.parse_args(argv)
    assert exited.value.code == 2
    assert message in capsys.readouterr().err


def test_the_estimate_for_75_accounts_calls_nothing(
    probe: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The plan's formula at N=75: 0.750 + 0.375 + 4.500 + 3.750 = 9.375 USD, which the plan
    rounds to about 9.40; 527 requests."""
    entries = [
        f"- {{handle: synthetic{n:02d}, category: c{n % 5}, region: US, check: candidate}}"
        for n in range(75)
    ]
    path = tmp_path / "x-accounts.yaml"
    path.write_text("\n".join(entries), encoding="utf-8")
    with respx.mock(assert_all_called=False) as router:
        route = router.route()
        assert probe.main(["--accounts", str(path)], now=NOW) == 0
        assert probe.main(["--accounts", str(path), "--estimate"], now=NOW) == 0
    assert route.call_count == 0
    printed = capsys.readouterr().out
    assert len(re.findall(r"^  total +9\.375 USD$", printed, re.MULTILINE)) == 2
    for term in ("0.010 x 75 ", "0.005 x 75 ", "0.010 x 75 x 3 x 2", "0.005 x 75 x 10"):
        assert term in printed
    assert re.search(
        r"^  get_posts_counts_all +450  75 accounts x 2 queries x 3 pages$", printed, re.M
    )
    assert re.search(r"^  total +527  and up to 1 fallback lookups$", printed, re.MULTILINE)
    plan = probe.Plan(75, 90)
    assert [mills for _, _, mills in plan.components] == [750, 375, 4500, 3750]
    assert plan.total == 9375, "the formula is the whole estimate: no call asks for more"
    assert "get_users_posts            75  10 posts each, no expansion" in printed


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("handle: USDA", "is not a non-empty YAML list"),
        ("[]", "is not a non-empty YAML list"),
        ("- [USDA]", "entry 1 is not a record"),
        (
            "- {handle: USDA, category: c, region: US, check: seen, notes: x}",
            "unknown fields notes",
        ),
        ("- {handle: USDA, region: US, check: seen}", "entry 1: category is missing"),
        ("- {handle: USDA, category: c, region: no, check: seen}", "entry 1: region is not text"),
        ("- {handle: U S, category: c, region: US, check: seen}", "entry 1: handle is not"),
        ("- {handle: USDA, category: c, region: US, check: maybe}", "check is not one of"),
        (
            "- {handle: USDA, category: c, region: US, check: seen}\n"
            "- {handle: '@usda', category: c, region: US, check: seen}",
            "entry 2: the handle is listed twice",
        ),
        ("- {handle: USDA\n", "is not YAML (line 2)"),
    ],
)
def test_the_account_list_is_checked_before_anything_is_called(
    probe: ModuleType, tmp_path: Path, text: str, message: str
) -> None:
    path = tmp_path / "x-accounts.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(probe.AccountsError, match=re.escape(message)):
        probe.read_accounts(path)


def test_a_missing_list_is_not_run(
    probe: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert probe.main(["--accounts", str(tmp_path / "absent.yaml")], now=NOW) == 1
    assert "not run: cannot read the account list" in capsys.readouterr().out


def day(days_before_today: int) -> datetime:
    """The start of the daily bucket ``days_before_today`` days before ``NOW``'s day."""
    return datetime(2026, 10, 29, tzinfo=UTC) - timedelta(days=days_before_today)


def test_day_counts_keep_the_first_count_of_a_repeated_bucket(probe: ModuleType) -> None:
    def page(*starts: tuple[int, int]) -> GetPostsCountsAllResponse:
        data = [
            {"start": day(n).isoformat(), "end": day(n - 1).isoformat(), "tweet_count": count}
            for n, count in starts
        ]
        return GetPostsCountsAllResponse.model_validate({"data": data})

    counts = probe.day_counts([page((2, 5), (1, 3)), page((3, 1), (2, 9)), page()])
    assert counts == {day(3): 1, day(2): 5, day(1): 3}
    assert probe.posts_from(counts, day(2)) == 8
    assert probe.posts_from(counts, day(3), day(1)) == 6


def test_active_needs_an_original_post_in_the_last_14_days(probe: ModuleType) -> None:
    def active(posts: dict[datetime, int], originals: dict[datetime, int]) -> bool:
        return bool(probe.measure(posts, originals, now=NOW, days=90).active)

    assert active({}, {day(14): 1}), "the bucket 14 days before today's is in"
    assert active({}, {day(0): 1}), "today's part counts"
    assert not active({}, {day(15): 1})
    assert not active({day(0): 7}, {}), "reposts and replies do not make an account active"


def test_core_is_two_original_posts_a_week_over_the_window(probe: ModuleType) -> None:
    needed = math.ceil(2 * 90 / 7)  # 26 original posts in 90 days
    enough = {day(n): 1 for n in range(1, needed + 1)}
    short = {day(n): 1 for n in range(1, needed)}
    assert probe.measure({}, enough, now=NOW, days=90).core
    assert not probe.measure({}, short, now=NOW, days=90).core
    assert probe.measure({}, enough, now=NOW, days=90).originals_per_week == pytest.approx(
        needed / (90 / 7)
    )
    before = {day(91): 50, day(1): 1}
    assert probe.measure({}, before, now=NOW, days=90).originals_per_week == pytest.approx(
        1 / (90 / 7)
    ), "a bucket before the window does not count"


def test_the_trend_sets_the_last_30_days_against_the_first_30(probe: ModuleType) -> None:
    originals = {day(90): 4, day(61): 6, day(60): 100, day(30): 5, day(0): 1}
    activity = probe.measure({day(14): 2, day(29): 3, day(31): 4}, originals, now=NOW, days=90)
    assert (activity.originals_first_30d, activity.originals_last_30d) == (10, 6)
    assert activity.trend == pytest.approx(0.6)
    assert (activity.posts_14d, activity.posts_30d) == (2, 5)
    assert probe.measure({}, {day(1): 3}, now=NOW, days=90).trend is None
    row = probe.Row(probe.Account("a", "c", "US", "seen"), "measured", activity=activity)
    cells = probe.csv_row(row)
    per_week = f"{(4 + 6 + 100 + 5 + 1) / (90 / 7):.2f}"
    assert (cells["trend"], cells["originals_per_week"], cells["active"]) == (
        "0.60",
        per_week,
        "yes",
    )
    assert (cells["resolved"], cells["followers"], cells["last_post"]) == ("no", "", "")


def rows_of(probe: ModuleType, groups: list[tuple[int, str, str, bool, bool]]) -> list[Any]:
    """Measured rows: ``(how many, category, region, active, core)`` per group."""
    rows: list[Any] = []
    for count, category, region, active, core in groups:
        for _ in range(count):
            account = probe.Account(
                handle=f"a{len(rows)}", category=category, region=region, check="seen"
            )
            activity = probe.Activity(
                posts_14d=0,
                posts_30d=0,
                originals_14d=0,
                originals_per_week=0.0,
                originals_first_30d=0,
                originals_last_30d=0,
                trend=None,
                active=active,
                core=core,
            )
            rows.append(probe.Row(account, "measured", activity=activity))
    return rows


def test_go_at_the_thresholds(probe: ModuleType) -> None:
    """Half of 50 active, 25 core over 4 categories, 7 of them in the EU: go."""
    rows = rows_of(
        probe,
        [
            (7, "ministry", "EU", True, True),
            (6, "agency", "US", True, True),
            (6, "university", "US", True, True),
            (6, "press", "US", True, True),
            (25, "press", "US", False, False),
        ],
    )
    rows.append(probe.Row(probe.Account("gone", "press", "US", "seen"), "unresolved"))
    rows.append(probe.Row(probe.Account("shut", "press", "US", "seen"), "protected"))
    decision = probe.decide(rows)
    assert decision.verdict == "go"
    assert decision.everyone == probe.Tally(measured=50, active=25, core=25, categories=4)
    assert probe.decision_line(decision) == (
        "Decision (D5): go. Measured accounts: 25 of 50 active (50%), go needs 50%; 25 core, "
        "go needs 25; in 4 categories, go needs 4. Region US: 18 of 43 active (42%), 18 core "
        "in 3 categories. Region EU: 7 core, US-only needs fewer than 5."
    )


@pytest.mark.parametrize(
    ("change", "verdict"),
    [
        ((1, "ministry", "EU", False, False), "no-go"),  # 25 of 51 active
        ((0, "ministry", "EU", True, True), "go"),
    ],
)
def test_half_active_is_the_least_for_go(
    probe: ModuleType, change: tuple[int, str, str, bool, bool], verdict: str
) -> None:
    base = [
        (7, "ministry", "EU", True, True),
        (6, "agency", "US", True, True),
        (6, "university", "US", True, True),
        (6, "press", "US", True, True),
        (25, "press", "US", False, False),
    ]
    assert probe.decide(rows_of(probe, [*base, change])).verdict == verdict


def test_no_go_under_25_core_or_4_categories(probe: ModuleType) -> None:
    short = rows_of(probe, [(24, "ministry", "EU", True, True), (1, "a", "US", True, False)])
    assert probe.decide(short).verdict == "no-go"
    narrow = rows_of(
        probe,
        [
            (10, "ministry", "EU", True, True),
            (10, "agency", "US", True, True),
            (10, "press", "US", True, True),
        ],
    )
    assert probe.decide(narrow).everyone.categories == 3
    assert probe.decide(narrow).verdict == "no-go"


def test_us_only_when_go_holds_for_the_us_and_the_eu_core_is_under_5(probe: ModuleType) -> None:
    us = [(7, cat, "US", True, True) for cat in ("ministry", "agency", "university", "press")]
    assert probe.decide(rows_of(probe, [*us, (4, "ministry", "EU", True, True)])).verdict == (
        "US-only"
    ), "checked first: a go overall narrows to US-only"
    assert probe.decide(rows_of(probe, [*us, (5, "ministry", "EU", True, True)])).verdict == "go"
    weak_us = [(5, cat, "US", True, True) for cat in ("ministry", "agency", "university", "press")]
    assert probe.decide(rows_of(probe, [*weak_us, (6, "ministry", "EU", True, True)])).verdict == (
        "go"
    ), "region US alone has 20 core, so not US-only; all together 26 core over 4 categories"
    assert probe.decide(rows_of(probe, [*weak_us, (4, "ministry", "EU", True, True)])).verdict == (
        "no-go"
    ), "24 core all together, 20 in region US"


def test_the_cap_is_checked_before_each_request(probe: ModuleType) -> None:
    spend = probe.Spend(cap=100, spent=90)
    spend.allow(10, "get_posts_counts_all")
    with pytest.raises(probe.CapReached, match=r"up to 0\.011 USD"):
        spend.allow(11, "get_posts_counts_all")
    spend.add("get_posts_counts_all", 10)
    assert (spend.spent, spend.requests["get_posts_counts_all"]) == (100, 1)


def test_what_an_answer_is_billed(probe: ModuleType) -> None:
    users = load_fixture(fixture_path(FIXTURES, "get_users_by_usernames", "three_accounts"))
    posts = load_fixture(fixture_path(FIXTURES, "get_users_posts", "usda_ten"))
    models = probe.GetUsersByUsernamesResponse, probe.GetUsersPostsResponse
    assert probe.billed(models[0].model_validate_json(users.response.body)) == 3 * 10 + 3 * 5
    assert probe.billed(models[1].model_validate_json(posts.response.body)) == 9 * 5
    assert probe.billed(GetPostsCountsAllResponse()) == 10


def test_the_usage_reading_names_what_it_lacks(probe: ModuleType) -> None:
    assert probe.usage_line({"data": {"project_usage": "29", "cap_reset_day": 29}}) == (
        "usage (GET /2/usage/tweets): project_usage 29, project_cap not given, cap_reset_day 29"
    )
    assert probe.usage_line([]).endswith("cap_reset_day not given")


@pytest.mark.anyio
async def test_a_spent_window_is_waited_out_and_the_request_sent_again(
    probe: ModuleType,
    respx_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """X's 429 with its reset 600 s ahead: beyond core's retries (30 s), so the probe prints
    the wait, sleeps it and calls again; the built 429 carries only the header."""
    waits: list[float] = []

    async def asleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(probe, "_sleep", asleep)
    reset = int(time.time()) + 600
    route = respx_mock.get(COUNTS_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"x-rate-limit-reset": str(reset)}),
            served("usda_by_day"),
        ]
    )
    call = partial(
        api.get_posts_counts_all, "from:USDA", granularity=Granularity.DAY, start_time=START
    )
    page = await probe.with_waits(call)
    assert route.call_count == 2
    assert len(waits) == 1
    assert 590 < waits[0] <= 600
    assert page.meta is not None
    assert page.meta.total_post_count == 218
    printed = capsys.readouterr().out
    assert "rate limit: X rate limit reached (HTTP 429 from GET /2/tweets/counts/all)" in printed
    assert "then resuming" in printed


@pytest.mark.anyio
async def test_a_usage_cap_or_a_fourth_429_stops_the_run(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []

    async def asleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(probe, "_sleep", asleep)

    async def capped() -> None:
        raise RateLimitError("X usage cap reached", retry_after=BILLING_CYCLE, source="x")

    with pytest.raises(RateLimitError, match="usage cap"):
        await probe.with_waits(capped)
    assert waits == []

    async def spent() -> None:
        raise RateLimitError("X rate limit reached", retry_after=2000.0, source="x")

    with pytest.raises(RateLimitError, match="rate limit"):
        await probe.with_waits(spent)
    assert waits == [900.0, 900.0, 900.0], "each wait at most the 15-minute window"
