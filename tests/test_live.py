"""Live smoke tests, one per task, skipped unless XIPPIOS_LIVE_TESTS=1 (conventions §10).

``/add-endpoint`` adds them.

Each keyed test spends X credits, at the prices of ``docs/upstream/pages/pricing.md``
(snapshot of 2026-10-29). The nightly run (``GITHUB_EVENT_NAME`` ``schedule``) spends one
billable call, ``test_lookup_users``' lookup of @XDevelopers, about 0.010 USD (D3); the
other six skip there (``not_in_the_nightly_run``) and run on ``workflow_dispatch`` and
locally, together at most about 0.14 USD: five posts of @XDevelopers' (0.025), a recent
search of ten posts at most (0.050), one full-archive count (0.010), one post of a List
(0.005), a conversation's page of ten posts at most (0.050) and the usage (no price).
They assert shapes and counts, never a payload, which ``--tb=short`` keeps out of a public
log only in part.
"""

import os

import httpx
import pytest

from xippios.x import tasks
from xippios.x._client import BASE_URL, config

pytestmark = [pytest.mark.live, pytest.mark.anyio]

XDEVELOPERS = "2244994945"
"""@XDevelopers' user id, as ``get_users_by_usernames/three_accounts`` records it."""
LIST_ID = "715919216927322112"
"""A List @XDevelopers owns, the List fixtures' (``scripts/record_fixture.py``, ``LISTS``)."""
CONVERSATION = "2115806101480337475"
"""A post of @USDA's of 2026-10-29 that started a conversation; once its replies are older
than seven days, the search answers an empty page, which the test accepts."""


def not_in_the_nightly_run() -> None:
    """Skip in the scheduled run, which spends one billable call (D3); run otherwise."""
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
        pytest.skip(
            "D3: the nightly run spends one billable call, test_lookup_users'; this test "
            "runs on workflow_dispatch and locally (gap, row 337)"
        )


async def test_upstream_answers() -> None:
    """The base URL answers without a server error.

    A plain request, not the package's client, so no key goes out and it spends no keyed
    call; a keyed gateway's answer to it (a 403 or a 404, say) still shows the host is up.
    """
    async with httpx.AsyncClient(
        headers={"User-Agent": config.user_agent},
        timeout=config.timeouts.to_httpx(),
        follow_redirects=True,
    ) as http:
        response = await http.get(BASE_URL)
    assert response.status_code < 500


def test_lookup_users() -> None:
    """The nightly call: one user, about 0.010 USD."""
    result = tasks.lookup_users(["XDevelopers"])
    assert result.meta.endpoint == "getUsersByUsernames"
    assert result.data.data is not None
    assert [user.id for user in result.data.data] == [XDEVELOPERS]
    assert result.data.data[0].public_metrics is not None


def test_get_user_posts() -> None:
    not_in_the_nightly_run()
    result = tasks.get_user_posts(XDEVELOPERS, max_results=5)
    assert result.meta.endpoint == "getUsersPosts"
    assert result.data.meta is not None
    assert len(result.data.data or []) <= 5
    assert all(post.created_at is not None for post in result.data.data or [])


def test_search_recent_posts() -> None:
    not_in_the_nightly_run()
    result = tasks.search_recent_posts("from:XDevelopers")
    assert result.meta.endpoint == "searchPostsRecent"
    assert result.data.meta is not None
    assert len(result.data.data or []) <= 10


def test_count_posts() -> None:
    not_in_the_nightly_run()
    result = tasks.count_posts("from:XDevelopers")
    assert result.meta.endpoint == "getPostsCountsAll"
    assert result.data.data is not None
    assert 30 <= len(result.data.data) <= 32
    assert result.data.meta is not None
    assert result.data.meta.total_post_count == sum(b.post_count for b in result.data.data)


def test_get_list_posts() -> None:
    not_in_the_nightly_run()
    result = tasks.get_list_posts(LIST_ID, max_results=1)
    assert result.meta.endpoint == "getListsPosts"
    assert len(result.data.data or []) <= 1


def test_get_conversation_posts() -> None:
    not_in_the_nightly_run()
    result = tasks.get_conversation_posts(CONVERSATION)
    assert result.meta.endpoint == "searchPostsRecent"
    assert result.data.meta is not None
    assert {post.conversation_id for post in result.data.data or []} <= {CONVERSATION}


def test_get_usage() -> None:
    not_in_the_nightly_run()
    result = tasks.get_usage(days=1)
    assert result.meta.endpoint == "getUsage"
    assert result.data.data is not None
    assert result.data.data.cap_reset_day is not None
