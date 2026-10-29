"""Replay tests on recorded fixtures, at least one per task (conventions §10).

Each task is called through its sync facade and sends exactly the recorded query of the
fixture it replays, which ``sent_query`` compares; the fixtures are the wrappers', recorded
on 2026-10-29 from @XDevelopers, @USDA and @FAO and from a List @XDevelopers owns, their
free text rewritten (D1): ``lookup_users`` replays ``get_users_by_usernames``'
``partial_errors`` and, with ``most_recent_post``, ``xdevelopers_post_fields``;
``get_user_posts`` ``get_users_posts/usda_ten`` and ``unknown_id``;
``search_recent_posts`` ``search_posts_recent/usda_ten``, ``usda_ten_page_2`` and
``unbalanced_parenthesis``; ``count_posts`` ``get_posts_counts_all/usda_by_day`` and
``usda_by_day_page_2``; ``get_list_posts`` ``get_lists_posts/xdevelopers_list_ten`` and
``unknown_id``; ``get_conversation_posts`` ``search_posts_recent/usda_conversation``;
``get_usage`` ``get_usage/seven_days``. Two answers no recording gave are built in memory
from recorded ones and named as such: a lookup that finds no username, and a page of 99
posts, eleven copies of @USDA's nine, for the MCP result cap.

Then the adapters: the MCP server through core's in-process client (its seven tools, a
cut result's note, the error answers) and the HTTP router (its routes, an answer, a
refusal as a problem); then the live tests' nightly rule (D3).
"""

import importlib.util
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from xippios.core import InvalidRequestError, NotFoundError, Result, ResultMeta
from xippios.core.testing import (
    ReplayFixture,
    assert_time_between,
    fixture_path,
    load_fixture,
    mcp_call,
    mcp_call_text,
    recorded_query,
    sent_query,
)

from xippios.x import tasks
from xippios.x.http import router
from xippios.x.mcp import server
from xippios.x.models import (
    GetPostsCountsAllResponse,
    GetUsersPostsResponse,
    Granularity,
    SearchPostsRecentResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"
TEXT = "[text rewritten]"
POST_FIELDS = ["created_at", "lang", "public_metrics", "conversation_id"]
USER_FIELDS = [
    "created_at",
    "description",
    "location",
    "protected",
    "public_metrics",
    "verified_type",
    "url",
]
USDA = "61853389"
LIST_ID = "715919216927322112"
CONVERSATION = "2115806101480337475"
"""@USDA's most recent post at recording, the post that started the recorded conversation."""
TOOLS = [
    "x_lookup_users",
    "x_get_user_posts",
    "x_search_recent_posts",
    "x_count_posts",
    "x_get_list_posts",
    "x_get_conversation_posts",
    "x_get_usage",
]


def recorded(wrapper: str, case: str) -> dict[str, str]:
    return recorded_query(load_fixture(fixture_path(FIXTURES, wrapper, case)))


def body(wrapper: str, case: str) -> Any:
    return json.loads(load_fixture(fixture_path(FIXTURES, wrapper, case)).response.body)


def assert_meta(meta: ResultMeta, endpoint: str, before: datetime, after: datetime) -> None:
    """What every task's meta holds: the slug, the operation, now, no total, no vintage."""
    assert meta.source == "x"
    assert meta.endpoint == endpoint
    assert_time_between(meta.retrieved_at, before, after)
    assert meta.total is None
    assert meta.vintage is None
    assert meta.published_at_naive is False


def call[T](task: Callable[[], Result[T]]) -> tuple[Result[T], datetime, datetime]:
    """The task's result with the clock read before and after the call."""
    before = datetime.now(UTC)
    result = task()
    return result, before, datetime.now(UTC)


# lookup_users


def test_lookup_users_returns_the_found_and_the_problems(replay_fixture: ReplayFixture) -> None:
    """A username X does not find is a problem beside the users found, as X sends it."""
    route = replay_fixture("get_users_by_usernames", "partial_errors")
    result, before, after = call(lambda: tasks.lookup_users(["XDevelopers", "xippiosnouser01"]))
    assert sent_query(route) == recorded("get_users_by_usernames", "partial_errors")
    assert_meta(result.meta, "getUsersByUsernames", before, after)
    assert result.meta.published_at is None, "users are no publication"
    assert result.meta.request == {
        "usernames": ["XDevelopers", "xippiosnouser01"],
        "user.fields": USER_FIELDS,
    }
    page = result.data
    assert page.data is not None
    (user,) = page.data
    assert (user.id, user.username, user.verified_type) == ("2244994945", "XDevelopers", "business")
    assert user.public_metrics is not None
    assert user.public_metrics.post_count == 4381
    assert page.errors is not None
    (problem,) = page.errors
    assert problem.resource_id == "xippiosnouser01"
    assert problem.type.endswith("/resource-not-found")
    assert page.includes is None


def test_lookup_users_with_the_most_recent_post(replay_fixture: ReplayFixture) -> None:
    """``most_recent_post`` asks for the expansion and the plan's post fields, which X
    answers in the document's names."""
    route = replay_fixture("get_users_by_usernames", "xdevelopers_post_fields")
    result, before, after = call(lambda: tasks.lookup_users(["XDevelopers"], most_recent_post=True))
    assert sent_query(route) == recorded("get_users_by_usernames", "xdevelopers_post_fields")
    assert_meta(result.meta, "getUsersByUsernames", before, after)
    assert result.meta.request == {
        "usernames": ["XDevelopers"],
        "user.fields": USER_FIELDS,
        "expansions": ["most_recent_post_id"],
        "post.fields": POST_FIELDS,
    }
    assert result.meta.published_at is None, "the data are users; the post is an include"
    page = result.data
    assert page.data is not None
    assert page.includes is not None
    assert page.includes.posts is not None
    (post,) = page.includes.posts
    assert post.id == page.data[0].most_recent_post_id == "2114879022433800258"
    assert post.created_at is not None


def test_lookup_users_finding_nobody_is_not_found(respx_mock: respx.MockRouter) -> None:
    """No username found: no ``data``, only not-found problems, so ``NotFoundError`` with
    X's words. The answer is ``partial_errors`` without its ``data``, built in memory."""
    answer = body("get_users_by_usernames", "partial_errors")
    del answer["data"]
    respx_mock.get("https://api.x.com/2/users/by").mock(
        return_value=httpx.Response(200, json=answer)
    )
    with pytest.raises(NotFoundError, match=r"usernames: \[xippiosnouser01\]") as raised:
        tasks.lookup_users(["xippiosnouser01"])
    assert "getUsersByUsernames" in str(raised.value)


def test_lookup_users_refuses_before_the_call(respx_mock: respx.MockRouter) -> None:
    for usernames in ([], ["@USDA"], [f"user{n}" for n in range(101)]):
        with pytest.raises(InvalidRequestError):
            tasks.lookup_users(usernames)
    assert not respx_mock.calls


# get_user_posts


def test_get_user_posts(replay_fixture: ReplayFixture) -> None:
    """One page of @USDA's posts; ``published_at`` is the newest post's ``created_at``."""
    route = replay_fixture("get_users_posts", "usda_ten")
    result, before, after = call(lambda: tasks.get_user_posts(USDA))
    assert sent_query(route) == recorded("get_users_posts", "usda_ten")
    assert_meta(result.meta, "getUsersPosts", before, after)
    assert result.meta.request == {"id": USDA, "max_results": 10, "post.fields": POST_FIELDS}
    page = result.data
    assert page.data is not None
    assert page.meta is not None
    assert len(page.data) == page.meta.result_count == 9
    assert result.meta.published_at == datetime(2026, 10, 29, 14, 0, 59, tzinfo=UTC)
    assert result.meta.published_at == max(
        post.created_at for post in page.data if post.created_at is not None
    )
    assert {post.text for post in page.data} == {TEXT}
    assert page.meta.next_token


def test_get_user_posts_sends_the_token_and_the_times(replay_fixture: ReplayFixture) -> None:
    """The paging token and the times go out as the wrapper sends them; ``meta.request``
    shows the token ``REDACTED`` (core's rule, row 326). The answer is the recorded page,
    mounted on its path: no second page of the user's was recorded."""
    route = replay_fixture("get_users_posts", "usda_ten")
    token = GetUsersPostsResponse.model_validate(body("get_users_posts", "usda_ten")).meta
    assert token is not None
    assert token.next_token is not None
    result = tasks.get_user_posts(
        USDA,
        max_results=100,
        pagination_token=token.next_token,
        start_time=datetime(2026, 10, 1, tzinfo=UTC),
        end_time=datetime(2026, 10, 29, tzinfo=UTC),
    )
    assert sent_query(route) == {
        "max_results": "100",
        "pagination_token": "REDACTED",
        "start_time": "2026-10-01T00:00:00Z",
        "end_time": "2026-10-29T00:00:00Z",
        "post.fields": ",".join(POST_FIELDS),
    }
    assert result.meta.request["pagination_token"] == "REDACTED"
    assert result.meta.request["start_time"] == "2026-10-01T00:00:00Z"


def test_get_user_posts_unknown_id_is_not_found(replay_fixture: ReplayFixture) -> None:
    """X's HTTP 200 without ``data`` and with a not-found problem: ``NotFoundError``."""
    route = replay_fixture("get_users_posts", "unknown_id")
    with pytest.raises(NotFoundError, match=r"Could not find user with id") as raised:
        tasks.get_user_posts("9000000000000000000")
    assert str(raised.value).startswith("X found nothing (getUsersPosts): ")
    assert sent_query(route) == recorded("get_users_posts", "unknown_id")


# search_recent_posts


def test_search_recent_posts(replay_fixture: ReplayFixture) -> None:
    route = replay_fixture("search_posts_recent", "usda_ten")
    result, before, after = call(lambda: tasks.search_recent_posts("from:USDA"))
    assert sent_query(route) == recorded("search_posts_recent", "usda_ten")
    assert_meta(result.meta, "searchPostsRecent", before, after)
    assert result.meta.request == {
        "query": "from:USDA",
        "max_results": 10,
        "post.fields": POST_FIELDS,
    }
    page = result.data
    assert page.data is not None
    assert len(page.data) == 10
    assert result.meta.published_at == page.data[0].created_at
    assert result.meta.published_at == datetime(2026, 10, 29, 17, 14, 54, tzinfo=UTC)


def test_search_recent_posts_second_page(replay_fixture: ReplayFixture) -> None:
    """The first page's ``next_token`` leads to the ten posts before."""
    first = SearchPostsRecentResponse.model_validate(body("search_posts_recent", "usda_ten"))
    assert first.meta is not None
    assert first.meta.next_token is not None
    assert first.meta.oldest_id is not None
    route = replay_fixture("search_posts_recent", "usda_ten_page_2")
    result = tasks.search_recent_posts("from:USDA", next_token=first.meta.next_token)
    assert sent_query(route) == recorded("search_posts_recent", "usda_ten_page_2")
    assert result.meta.request["next_token"] == "REDACTED"
    assert result.data.data is not None
    assert all(int(post.id) < int(first.meta.oldest_id) for post in result.data.data)


def test_search_recent_posts_refuses_a_long_query(respx_mock: respx.MockRouter) -> None:
    """512 characters at most (``pages/rate-limits.md``), refused before the call."""
    with pytest.raises(InvalidRequestError, match="at most 512 characters"):
        tasks.search_recent_posts("from:USDA " + "x" * 503)
    assert not respx_mock.calls


def test_search_recent_posts_refused_query(replay_fixture: ReplayFixture) -> None:
    replay_fixture("search_posts_recent", "unbalanced_parenthesis")
    with pytest.raises(InvalidRequestError, match="mismatched input"):
        tasks.search_recent_posts("(from:USDA", max_results=10)


# count_posts


def test_count_posts(replay_fixture: ReplayFixture) -> None:
    """One page of 31 days by day over the full archive; counts have no publication time."""
    route = replay_fixture("get_posts_counts_all", "usda_by_day")
    result, before, after = call(
        lambda: tasks.count_posts("from:USDA", start_time=datetime(2026, 7, 31, tzinfo=UTC))
    )
    assert sent_query(route) == recorded("get_posts_counts_all", "usda_by_day")
    assert_meta(result.meta, "getPostsCountsAll", before, after)
    assert result.meta.published_at is None
    assert result.meta.request == {
        "query": "from:USDA",
        "granularity": "day",
        "start_time": "2026-07-31T00:00:00Z",
    }
    page = result.data
    assert page.data is not None
    assert page.meta is not None
    assert len(page.data) == 31
    assert page.meta.total_post_count == sum(bucket.post_count for bucket in page.data) == 218
    assert page.meta.next_token


def test_count_posts_second_page(replay_fixture: ReplayFixture) -> None:
    first = GetPostsCountsAllResponse.model_validate(body("get_posts_counts_all", "usda_by_day"))
    assert first.meta is not None
    assert first.meta.next_token is not None
    assert first.data is not None
    route = replay_fixture("get_posts_counts_all", "usda_by_day_page_2")
    result = tasks.count_posts(
        "from:USDA",
        granularity=Granularity.DAY,
        start_time=datetime(2026, 7, 31, tzinfo=UTC),
        next_token=first.meta.next_token,
    )
    assert sent_query(route) == recorded("get_posts_counts_all", "usda_by_day_page_2")
    assert result.meta.request["next_token"] == "REDACTED"
    assert result.data.data is not None
    assert result.data.data[-1].end <= first.data[0].start


def test_count_posts_refuses_a_long_query(respx_mock: respx.MockRouter) -> None:
    """1,024 characters at most (``pages/post-counts.md``), refused before the call."""
    with pytest.raises(InvalidRequestError, match="at most 1024 characters"):
        tasks.count_posts("from:USDA " + "x" * 1015)
    assert not respx_mock.calls


# get_list_posts


def test_get_list_posts(replay_fixture: ReplayFixture) -> None:
    route = replay_fixture("get_lists_posts", "xdevelopers_list_ten")
    result, before, after = call(lambda: tasks.get_list_posts(LIST_ID))
    assert sent_query(route) == recorded("get_lists_posts", "xdevelopers_list_ten")
    assert_meta(result.meta, "getListsPosts", before, after)
    assert result.meta.request == {"id": LIST_ID, "max_results": 10, "post.fields": POST_FIELDS}
    page = result.data
    assert page.data is not None
    assert len(page.data) == 9
    assert result.meta.published_at == datetime(2026, 10, 28, 23, 1, 39, tzinfo=UTC)


def test_get_list_posts_unknown_id_is_not_found(replay_fixture: ReplayFixture) -> None:
    replay_fixture("get_lists_posts", "unknown_id")
    with pytest.raises(NotFoundError, match=r"Could not find list with id"):
        tasks.get_list_posts("9000000000000000000", max_results=10)


# get_conversation_posts


def test_get_conversation_posts(replay_fixture: ReplayFixture) -> None:
    """The task builds the query; the page holds the replies and the post that started
    the conversation, every one with its ``conversation_id``."""
    route = replay_fixture("search_posts_recent", "usda_conversation")
    result, before, after = call(lambda: tasks.get_conversation_posts(CONVERSATION))
    assert sent_query(route) == recorded("search_posts_recent", "usda_conversation")
    assert_meta(result.meta, "searchPostsRecent", before, after)
    assert result.meta.request == {
        "query": f"conversation_id:{CONVERSATION}",
        "max_results": 10,
        "post.fields": POST_FIELDS,
    }
    page = result.data
    assert page.data is not None
    assert {post.conversation_id for post in page.data} == {CONVERSATION}
    assert CONVERSATION in {post.id for post in page.data}
    assert result.meta.published_at == datetime(2026, 10, 29, 21, 9, 36, tzinfo=UTC)


@pytest.mark.parametrize("conversation_id", ["", "@USDA", "1" * 20, "2115806101480337475 OR x"])
def test_get_conversation_posts_refuses_an_id_that_is_none(
    respx_mock: respx.MockRouter, conversation_id: str
) -> None:
    """The id is the document's post id pattern, ``^[0-9]{1,19}$``, checked before the call."""
    with pytest.raises(InvalidRequestError, match="conversation_id"):
        tasks.get_conversation_posts(conversation_id)
    assert not respx_mock.calls


# get_usage


def test_get_usage(replay_fixture: ReplayFixture) -> None:
    route = replay_fixture("get_usage", "seven_days")
    result, before, after = call(lambda: tasks.get_usage())
    assert sent_query(route) == recorded("get_usage", "seven_days")
    assert_meta(result.meta, "getUsage", before, after)
    assert result.meta.published_at is None
    assert result.meta.request == {
        "days": 7,
        "usage.fields": [
            "cap_reset_day",
            "daily_client_app_usage",
            "daily_project_usage",
            "project_cap",
            "project_id",
            "project_usage",
        ],
    }
    usage = result.data.data
    assert usage is not None
    assert (usage.project_usage, usage.project_cap, usage.cap_reset_day) == (458, 3_000_000, 29)


def test_get_usage_refuses_days_outside_the_bounds(respx_mock: respx.MockRouter) -> None:
    for days in (0, 91):
        with pytest.raises(InvalidRequestError, match="days"):
            tasks.get_usage(days)
    assert not respx_mock.calls


# The MCP server


@pytest.mark.anyio
async def test_the_server_lists_the_seven_tools_in_order() -> None:
    """``tasks.__all__`` in its order, read-only, each described by its task's docstring."""
    tools = await server.list_tools()
    assert [tool.name for tool in tools] == TOOLS
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.description
        assert "Price: " in tool.description, "every tool names its spend"


@pytest.mark.anyio
async def test_the_tools_keep_the_familys_bounds() -> None:
    """``MCP_CAPS`` sets notes only: every tool keeps 200 rows or 64 KB (Johannes,
    2026-10-29), and every note names the tool's own parameters."""
    assert set(tasks.MCP_CAPS) <= set(tasks.__all__)
    for name, cap in tasks.MCP_CAPS.items():
        assert (cap.max_rows, cap.max_bytes) == (200, 65_536), name
        assert cap.note is not None
        assert any(word in cap.note for word in ("max_results", "usernames", "start_time")), name


@pytest.mark.anyio
async def test_get_user_posts_tool_end_to_end(replay_fixture: ReplayFixture) -> None:
    route = replay_fixture("get_users_posts", "usda_ten")
    payload = await mcp_call(server, "x_get_user_posts", {"id": USDA})
    assert sent_query(route) == recorded("get_users_posts", "usda_ten")
    assert payload["meta"]["endpoint"] == "getUsersPosts"
    assert payload["meta"]["published_at"] == "2026-10-29T14:00:59Z"
    assert payload["meta"]["request"]["max_results"] == 10
    assert len(payload["data"]["data"]) == 9
    assert payload["data"]["meta"]["next_token"]
    assert "note" not in payload


@pytest.mark.anyio
async def test_lookup_users_tool_end_to_end(replay_fixture: ReplayFixture) -> None:
    route = replay_fixture("get_users_by_usernames", "partial_errors")
    payload = await mcp_call(
        server, "x_lookup_users", {"usernames": ["XDevelopers", "xippiosnouser01"]}
    )
    assert sent_query(route) == recorded("get_users_by_usernames", "partial_errors")
    assert [user["username"] for user in payload["data"]["data"]] == ["XDevelopers"]
    assert payload["data"]["errors"][0]["resource_id"] == "xippiosnouser01"


@pytest.mark.anyio
async def test_a_page_over_the_byte_cap_comes_with_the_tools_note(
    respx_mock: respx.MockRouter,
) -> None:
    """A full page of posts passes 64 KB of the tool's text: the result is a note and a
    preview, the note naming ``max_results`` and the paging token. The answer, 99 posts,
    is ``usda_ten``'s nine eleven times over, built in memory: no such page was recorded."""
    answer = body("get_users_posts", "usda_ten")
    answer["data"] = answer["data"] * 11
    answer["meta"]["result_count"] = len(answer["data"])
    respx_mock.get(f"https://api.x.com/2/users/{USDA}/tweets").mock(
        return_value=httpx.Response(200, json=answer)
    )
    payload = await mcp_call(server, "x_get_user_posts", {"id": USDA, "max_results": 100})
    assert set(payload) == {"note", "preview"}
    note = tasks.MCP_CAPS["get_user_posts"].note
    assert note is not None
    assert payload["note"].endswith(f"over the cap of 65536; {note}")
    assert len(payload["preview"].encode()) <= 65_536


@pytest.mark.anyio
async def test_an_upstream_refusal_is_an_error_answer(replay_fixture: ReplayFixture) -> None:
    """X's HTTP 400 comes back as the family's error text, never raised (conventions §8)."""
    replay_fixture("search_posts_recent", "unbalanced_parenthesis")
    text = await mcp_call_text(
        server, "x_search_recent_posts", {"query": "(from:USDA", "max_results": 10}
    )
    assert text.startswith(
        "error: InvalidRequestError: X refused the request "
        "(HTTP 400 from GET /2/tweets/search/recent): "
    )
    assert "mismatched input" in text


@pytest.mark.anyio
async def test_an_unknown_list_is_a_not_found_answer(replay_fixture: ReplayFixture) -> None:
    replay_fixture("get_lists_posts", "unknown_id")
    text = await mcp_call_text(
        server, "x_get_list_posts", {"id": "9000000000000000000", "max_results": 10}
    )
    assert text == (
        "error: NotFoundError: X found nothing (getListsPosts): "
        "Could not find list with id: [9000000000000000000]."
    )


@pytest.mark.anyio
async def test_an_argument_the_schema_refuses_is_an_error_answer(
    respx_mock: respx.MockRouter,
) -> None:
    text = await mcp_call_text(
        server, "x_count_posts", {"query": "from:USDA", "granularity": "week"}
    )
    assert (
        text == "error: InvalidRequestError: granularity: Input should be 'minute', 'hour' or 'day'"
    )
    assert not respx_mock.calls


# The HTTP router


def test_the_router_routes_the_seven_tasks() -> None:
    """``GET`` for the tasks of scalar parameters, ``POST`` for ``lookup_users``' list
    (ADR-0007)."""
    routes = {route.path: route.methods for route in router.routes if isinstance(route, APIRoute)}
    assert routes == {
        "/x/lookup_users": {"POST"},
        "/x/get_user_posts": {"GET"},
        "/x/search_recent_posts": {"GET"},
        "/x/count_posts": {"GET"},
        "/x/get_list_posts": {"GET"},
        "/x/get_conversation_posts": {"GET"},
        "/x/get_usage": {"GET"},
    }


@pytest.fixture
def http() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_count_posts_route_end_to_end(replay_fixture: ReplayFixture, http: TestClient) -> None:
    route = replay_fixture("get_posts_counts_all", "usda_by_day")
    answer = http.get(
        "/x/count_posts", params={"query": "from:USDA", "start_time": "2026-07-31T00:00:00Z"}
    )
    assert answer.status_code == 200
    assert sent_query(route) == recorded("get_posts_counts_all", "usda_by_day")
    assert answer.json()["meta"]["endpoint"] == "getPostsCountsAll"
    assert len(answer.json()["data"]["data"]) == 31


def test_lookup_users_route_end_to_end(replay_fixture: ReplayFixture, http: TestClient) -> None:
    replay_fixture("get_users_by_usernames", "xdevelopers_post_fields")
    answer = http.post(
        "/x/lookup_users", json={"usernames": ["XDevelopers"], "most_recent_post": True}
    )
    assert answer.status_code == 200
    assert answer.json()["meta"]["request"]["expansions"] == ["most_recent_post_id"]


def test_the_routes_answer_errors_as_problems(
    replay_fixture: ReplayFixture, http: TestClient
) -> None:
    """``NotFoundError`` is a 404 problem, a refusal before the call a 422 (conventions §9)."""
    replay_fixture("get_users_posts", "unknown_id")
    missing = http.get("/x/get_user_posts", params={"id": "9000000000000000000"})
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/problem+json")
    assert "Could not find user with id" in missing.json()["detail"]
    refused = http.get("/x/get_conversation_posts", params={"conversation_id": "not-an-id"})
    assert refused.status_code == 422


# The live tests' nightly rule (D3)


@pytest.fixture(scope="module")
def live() -> ModuleType:
    """``tests/test_live.py`` as a module, for its rule; its tests stay marked ``live``."""
    path = Path(__file__).parent / "test_live.py"
    spec = importlib.util.spec_from_file_location("x_test_live", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_nightly_run_skips_all_but_the_lookup(
    live: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scheduled run spends one billable call, ``test_lookup_users``'; the six others
    skip there, naming D3, and run on ``workflow_dispatch`` and locally."""
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    with pytest.raises(pytest.skip.Exception, match="D3"):
        live.not_in_the_nightly_run()
    for event in ("workflow_dispatch", "push"):
        monkeypatch.setenv("GITHUB_EVENT_NAME", event)
        live.not_in_the_nightly_run()
    monkeypatch.delenv("GITHUB_EVENT_NAME")
    live.not_in_the_nightly_run()


def test_every_task_has_one_live_test(live: ModuleType) -> None:
    """One smoke test per task, and only ``test_lookup_users`` runs nightly."""
    names = {name for name in dir(live) if name.startswith("test_")}
    assert {f"test_{task}" for task in tasks.__all__} <= names
    source = (Path(__file__).parent / "test_live.py").read_text(encoding="utf-8")
    calls = re.findall(r"^    not_in_the_nightly_run\(\)$", source, flags=re.MULTILINE)
    assert len(calls) == len(tasks.__all__) - 1
