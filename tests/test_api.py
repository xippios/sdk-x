"""Replay tests for the four endpoint wrappers (layer 1), one per recorded case.

The fixtures were recorded on 2026-10-29 from @XDevelopers, @USDA and @FAO with the free
text rewritten by the recorder (D1, ``scripts/record_fixture.py``), so every ``text`` and
``description`` reads as its placeholder. Each test calls the wrapper with the parameters
the fixture was recorded with and compares what was sent with ``sent_query``; a page is
dumped with ``dump_upstream`` and read back to the same model, as the probe's cache will.
"""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from xippios.core import AuthError, InvalidRequestError
from xippios.core.testing import (
    ReplayFixture,
    fixture_path,
    load_fixture,
    recorded_query,
    sent_query,
    sent_urls,
)

from xippios.x import api
from xippios.x.api._query import instant
from xippios.x.models import (
    GetPostsByIdsResponse,
    GetPostsCountsAllResponse,
    GetUsersByUsernamesResponse,
    GetUsersPostsResponse,
    Granularity,
    PostExpansion,
    PostField,
    ReferencedPostType,
    UserExpansion,
    UserField,
)

pytestmark = pytest.mark.anyio

FIXTURES = Path(__file__).parent / "fixtures"
TEXT = "[text rewritten]"
DESCRIPTION = "[description rewritten]"
PLAN_USER_FIELDS = [
    UserField.CREATED_AT,
    UserField.DESCRIPTION,
    UserField.LOCATION,
    UserField.PROTECTED,
    UserField.PUBLIC_METRICS,
    UserField.VERIFIED_TYPE,
    UserField.URL,
]
PLAN_POST_FIELDS = [
    PostField.CREATED_AT,
    PostField.LANG,
    PostField.PUBLIC_METRICS,
    PostField.CONVERSATION_ID,
]
ACCOUNTS = {"2244994945": "XDevelopers", "61853389": "USDA", "19649135": "FAO"}
START = datetime(2026, 7, 31, tzinfo=UTC)


def recorded(wrapper: str, case: str) -> dict[str, str]:
    return recorded_query(load_fixture(fixture_path(FIXTURES, wrapper, case)))


async def test_users_by_usernames_answered_in_the_guides_names(
    replay_fixture: ReplayFixture,
) -> None:
    """Without ``post.fields`` X answers ``most_recent_tweet_id``, ``tweet_count`` and
    ``includes.tweets``; the model reads them under the document's names."""
    route = replay_fixture("get_users_by_usernames", "three_accounts")
    page = await api.get_users_by_usernames(
        ["XDevelopers", "USDA", "FAO"],
        user_fields=PLAN_USER_FIELDS,
        expansions=[UserExpansion.MOST_RECENT_POST_ID],
    )
    assert sent_query(route) == recorded("get_users_by_usernames", "three_accounts")
    assert page.data is not None
    assert {user.id: user.username for user in page.data} == ACCOUNTS
    usda = next(user for user in page.data if user.username == "USDA")
    assert usda.name == "Dept. of Agriculture"
    assert usda.description == DESCRIPTION
    assert usda.verified_type == "government"
    assert usda.protected is False
    assert usda.created_at == datetime(2009, 7, 31, 19, 29, 19, tzinfo=UTC)
    assert usda.public_metrics is not None
    assert usda.public_metrics.post_count == 25727
    assert usda.most_recent_post_id == "2115806101480337475"
    assert page.includes is not None
    assert page.includes.posts is not None
    assert {post.id for post in page.includes.posts} == {
        user.most_recent_post_id for user in page.data
    }
    assert {post.text for post in page.includes.posts} == {TEXT}
    assert page.errors is None
    assert GetUsersByUsernamesResponse.model_validate(page.dump_upstream()) == page


async def test_users_by_usernames_answered_in_the_documents_names(
    replay_fixture: ReplayFixture,
) -> None:
    """With ``post.fields`` X answers ``most_recent_post_id``, ``post_count`` and
    ``includes.posts``: the same values as the guides' spelling gave."""
    route = replay_fixture("get_users_by_usernames", "xdevelopers_post_fields")
    page = await api.get_users_by_usernames(
        ["XDevelopers"],
        user_fields=PLAN_USER_FIELDS,
        expansions=[UserExpansion.MOST_RECENT_POST_ID],
        post_fields=PLAN_POST_FIELDS,
    )
    assert sent_query(route) == recorded("get_users_by_usernames", "xdevelopers_post_fields")
    assert page.data is not None
    (user,) = page.data
    assert user.public_metrics is not None
    assert user.public_metrics.post_count == 4381
    assert user.most_recent_post_id == "2114879022433800258"
    assert page.includes is not None
    assert page.includes.posts is not None
    (post,) = page.includes.posts
    assert post.id == user.most_recent_post_id
    assert post.public_metrics is not None
    assert post.public_metrics.repost_count == 55
    assert post.lang == "en"
    assert GetUsersByUsernamesResponse.model_validate(page.dump_upstream()) == page


async def test_users_by_usernames_partial_errors(replay_fixture: ReplayFixture) -> None:
    """A username X does not find is a problem beside the users found, in an HTTP 200."""
    route = replay_fixture("get_users_by_usernames", "partial_errors")
    page = await api.get_users_by_usernames(
        ["XDevelopers", "xippiosnouser01"], user_fields=PLAN_USER_FIELDS
    )
    assert sent_query(route) == recorded("get_users_by_usernames", "partial_errors")
    assert page.data is not None
    assert [user.username for user in page.data] == ["XDevelopers"]
    assert page.errors is not None
    (problem,) = page.errors
    assert problem.type == "https://api.x.com/2/problems/resource-not-found"
    assert problem.title == "Not Found Error"
    assert (problem.parameter, problem.value, problem.resource_type) == (
        "usernames",
        "xippiosnouser01",
        "user",
    )
    assert GetUsersByUsernamesResponse.model_validate(page.dump_upstream()) == page


async def test_users_by_usernames_wrong_key(replay_fixture: ReplayFixture) -> None:
    """X's 401 to a wrong key reaches the caller as ``AuthError``."""
    route = replay_fixture("get_users_by_usernames", "wrong_key")
    with pytest.raises(AuthError) as raised:
        await api.get_users_by_usernames(["XDevelopers"])
    assert raised.value.status == 401
    assert "GET /2/users/by" in str(raised.value)
    assert route.call_count == 1


async def test_users_by_usernames_refuses_a_long_username(replay_fixture: ReplayFixture) -> None:
    """Over 15 characters is refused before the call; X answered it with HTTP 400."""
    route = replay_fixture("get_users_by_usernames", "username_too_long")
    with pytest.raises(InvalidRequestError, match="does not match"):
        await api.get_users_by_usernames(["XDevelopers", "xippiosnosuchuser0001"])
    assert route.call_count == 0


async def test_posts_by_ids(replay_fixture: ReplayFixture) -> None:
    """With ``post.fields`` X answers ``referenced_posts`` and ``includes.posts``."""
    route = replay_fixture("get_posts_by_ids", "most_recent_three")
    ids = ["2114879022433800258", "2115806101480337475", "2115789000682180921"]
    page = await api.get_posts_by_ids(
        ids, post_fields=PLAN_POST_FIELDS, expansions=[PostExpansion.REFERENCED_POSTS]
    )
    assert sent_query(route) == recorded("get_posts_by_ids", "most_recent_three")
    assert page.data is not None
    assert [post.id for post in page.data] == ids
    first = page.data[0]
    assert first.created_at == datetime(2026, 10, 27, 0, 37, 6, tzinfo=UTC)
    assert first.conversation_id == first.id
    assert first.referenced_posts is not None
    (reference,) = first.referenced_posts
    assert reference.type is ReferencedPostType.QUOTED
    assert page.includes is not None
    assert page.includes.posts is not None
    assert [post.id for post in page.includes.posts] == [reference.id]
    assert page.data[1].edit_history_post_ids == ["2115805884466995409", "2115806101480337475"]
    assert {post.text for post in [*page.data, *page.includes.posts]} == {TEXT}
    assert page.meta is not None
    assert page.meta.result_count == 3
    assert GetPostsByIdsResponse.model_validate(page.dump_upstream()) == page


@pytest.mark.parametrize(
    ("case", "user_id", "count"),
    [
        ("xdevelopers_ten", "2244994945", 10),
        ("usda_ten", "61853389", 9),
        ("fao_ten", "19649135", 10),
    ],
)
async def test_users_posts(
    replay_fixture: ReplayFixture, case: str, user_id: str, count: int
) -> None:
    """Ten posts asked for each account; @USDA's page held nine and a ``next_token``."""
    route = replay_fixture("get_users_posts", case)
    page = await api.get_users_posts(user_id, max_results=10, post_fields=PLAN_POST_FIELDS)
    assert sent_query(route) == recorded("get_users_posts", case)
    assert httpx.URL(sent_urls(route)[-1]).path == f"/2/users/{user_id}/tweets"
    assert page.data is not None
    assert page.meta is not None
    assert len(page.data) == page.meta.result_count == count
    assert page.meta.newest_id == page.data[0].id
    assert page.meta.oldest_id == page.data[-1].id
    assert page.meta.next_token
    times = [post.created_at for post in page.data if post.created_at is not None]
    assert len(times) == count
    assert times == sorted(times, reverse=True), "newest first"
    assert all(post.public_metrics is not None and post.lang for post in page.data)
    assert {post.text for post in page.data} == {TEXT}
    assert GetUsersPostsResponse.model_validate(page.dump_upstream()) == page


async def test_users_posts_unknown_id(replay_fixture: ReplayFixture) -> None:
    """An id without a User is an HTTP 200 with a problem and no ``data``: the page."""
    route = replay_fixture("get_users_posts", "unknown_id")
    page = await api.get_users_posts(
        "9000000000000000000", max_results=10, post_fields=PLAN_POST_FIELDS
    )
    assert sent_query(route) == recorded("get_users_posts", "unknown_id")
    assert page.data is None
    assert page.errors is not None
    (problem,) = page.errors
    assert problem.type.endswith("/resource-not-found")
    assert (problem.parameter, problem.resource_id) == ("id", "9000000000000000000")


async def test_posts_counts_all_by_day(replay_fixture: ReplayFixture) -> None:
    """The first page: the 31 days up to the request, oldest first, the newest bucket
    ending at the time of the request; ``tweet_count`` read as ``post_count``, the total
    the sum of the page's buckets."""
    route = replay_fixture("get_posts_counts_all", "usda_by_day")
    page = await api.get_posts_counts_all(
        "from:USDA", granularity=Granularity.DAY, start_time=START
    )
    assert sent_query(route) == recorded("get_posts_counts_all", "usda_by_day")
    assert page.data is not None
    assert len(page.data) == 31
    *days, today = page.data
    assert all(bucket.end - bucket.start == timedelta(days=1) for bucket in days)
    assert [b.start for b in page.data] == sorted(b.start for b in page.data)
    assert today.start == datetime(2026, 10, 29, tzinfo=UTC)
    assert today.start < today.end < datetime(2026, 10, 30, tzinfo=UTC)
    assert page.meta is not None
    assert page.meta.total_post_count == sum(bucket.post_count for bucket in page.data) == 218
    assert page.meta.next_token
    assert GetPostsCountsAllResponse.model_validate(page.dump_upstream()) == page


async def test_posts_counts_all_second_page(replay_fixture: ReplayFixture) -> None:
    """``next_token`` leads to the 31 days before; core's scrub keeps the token out of
    the recorded URL and ``sent_query`` alike (a credential name by its rule)."""
    first = load_fixture(fixture_path(FIXTURES, "get_posts_counts_all", "usda_by_day"))
    token = GetPostsCountsAllResponse.model_validate_json(first.response.body).meta
    assert token is not None
    assert token.next_token is not None
    route = replay_fixture("get_posts_counts_all", "usda_by_day_page_2")
    page = await api.get_posts_counts_all(
        "from:USDA", granularity=Granularity.DAY, start_time=START, next_token=token.next_token
    )
    assert sent_query(route) == recorded("get_posts_counts_all", "usda_by_day_page_2")
    assert sent_query(route)["next_token"] == "REDACTED"
    assert page.data is not None
    assert len(page.data) == 31
    assert page.data[-1].end == datetime(2026, 9, 29, tzinfo=UTC)
    assert page.meta is not None
    assert page.meta.total_post_count == sum(bucket.post_count for bucket in page.data)


async def test_posts_counts_all_originals(replay_fixture: ReplayFixture) -> None:
    """Without reposts and replies fewer posts count over the same 31 days."""
    route = replay_fixture("get_posts_counts_all", "usda_originals_by_day")
    page = await api.get_posts_counts_all(
        "from:USDA -is:retweet -is:reply", granularity=Granularity.DAY, start_time=START
    )
    assert sent_query(route) == recorded("get_posts_counts_all", "usda_originals_by_day")
    assert page.meta is not None
    assert page.meta.total_post_count == 67


async def test_posts_counts_all_refuses_an_unknown_granularity(
    replay_fixture: ReplayFixture,
) -> None:
    """``week`` is refused before the call; X answered it with HTTP 400."""
    route = replay_fixture("get_posts_counts_all", "granularity_week")
    with pytest.raises(InvalidRequestError, match="minute, hour, day"):
        await api.get_posts_counts_all("from:USDA", granularity="week")  # type: ignore[arg-type]
    assert route.call_count == 0


@pytest.mark.parametrize(
    "call",
    [
        lambda: api.get_users_by_usernames([]),
        lambda: api.get_users_by_usernames("USDA"),
        lambda: api.get_users_by_usernames([f"user{n}" for n in range(101)]),
        lambda: api.get_users_by_usernames(["@USDA"]),
        lambda: api.get_users_by_usernames(["USDA"], user_fields=[UserField.URL, UserField.URL]),
        lambda: api.get_users_by_usernames(["USDA"], user_fields=["bio"]),  # type: ignore[list-item]
        lambda: api.get_users_by_usernames(["USDA"], expansions=[]),
        lambda: api.get_posts_by_ids(["not-an-id"]),
        lambda: api.get_posts_by_ids([str(n) for n in range(101)]),
        lambda: api.get_users_posts("61853389", max_results=4),
        lambda: api.get_users_posts("61853389", max_results=101),
        lambda: api.get_users_posts("USDA"),
        lambda: api.get_users_posts("61853389", start_time=datetime(2026, 7, 31)),
        lambda: api.get_users_posts("61853389", pagination_token=""),
        lambda: api.get_posts_counts_all(""),
        lambda: api.get_posts_counts_all("x" * 4097),
        lambda: api.get_posts_counts_all("from:USDA", next_token="a", pagination_token="b"),
    ],
)
async def test_values_outside_the_documents_bounds_are_refused_before_the_call(
    call: object,
) -> None:
    """Refused with ``InvalidRequestError``; no route is mounted, so a request would fail."""
    with pytest.raises(InvalidRequestError):
        await call()  # type: ignore[operator]


def test_instant_is_rfc3339_in_utc() -> None:
    assert instant("start_time", START) == "2026-07-31T00:00:00Z"
    later = datetime(2026, 7, 31, 2, 0, tzinfo=timezone(timedelta(hours=2)))
    assert instant("start_time", later) == "2026-07-31T00:00:00Z"
    assert instant("end_time", START.replace(microsecond=250_000)) == "2026-07-31T00:00:00.250Z"
