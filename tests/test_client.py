"""``classify``: X's recorded refusals, and the answers no recording holds.

The 401, the two 400s and the unknown id's 200 are recorded (``tests/fixtures/``). No 429,
no usage cap and no 404 was recorded, since none can be provoked without spending a
window or the budget: those tests build an ``httpx.Response`` in the shapes
``pages/response-codes-and-errors.md`` and ``pages/rate-limits.md`` show. They test the
mapping, not a fixture.
"""

import dataclasses
import json
import time
from pathlib import Path

import httpx
import pytest
import respx
from xippios.core import (
    AsyncClient,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    RetryPolicy,
    error_from_response,
)
from xippios.core.testing import CLOCK_SLACK, fixture_path, load_fixture, response_from_fixture

from xippios.x._client import (
    BILLING_CYCLE,
    RATE_LIMIT_WINDOW,
    auth,
    classify,
    config,
)

pytestmark = pytest.mark.anyio

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://api.x.com/2/users/by?usernames=USDA"
PROBLEM = "application/problem+json"
SLACK = CLOCK_SLACK.total_seconds()
"""This host's clock steps back about two seconds (``CLAUDE.md`` of the workspace)."""


def recorded(wrapper: str, case: str) -> httpx.Response:
    return response_from_fixture(load_fixture(fixture_path(FIXTURES, wrapper, case)))


def answer(
    status: int, body: object, *, headers: dict[str, str] | None = None, kind: str = PROBLEM
) -> httpx.Response:
    return httpx.Response(
        status,
        content=json.dumps(body).encode(),
        headers={"content-type": kind, **(headers or {})},
        request=httpx.Request("GET", URL),
    )


def problem(name: str, status: int) -> dict[str, object]:
    return {
        "title": name.replace("-", " ").title(),
        "detail": f"A {name} problem.",
        "type": f"https://api.x.com/2/problems/{name}",
        "status": status,
    }


def test_the_wrong_keys_401_falls_through_to_cores_auth_error() -> None:
    response = recorded("get_users_by_usernames", "wrong_key")
    assert classify(response) is None
    error = error_from_response(response, source="x")
    assert type(error).__name__ == "AuthError"


@pytest.mark.parametrize(
    ("case", "words"),
    [
        (("get_users_by_usernames", "username_too_long"), "does not match ^[A-Za-z0-9_]{1,15}$"),
        (("get_posts_counts_all", "granularity_week"), "is not one of [minute,hour,day]"),
    ],
)
def test_a_recorded_400_is_an_invalid_request(case: tuple[str, str], words: str) -> None:
    error = classify(recorded(*case))
    assert isinstance(error, InvalidRequestError)
    assert "HTTP 400" in str(error)
    assert "Invalid Request" in str(error)
    assert words in str(error)
    assert "?" not in str(error), "the query is never quoted"


def test_a_200_with_errors_is_the_page_not_an_error() -> None:
    """The unknown id's answer: a resource-not-found problem and no data, in an HTTP 200."""
    assert classify(recorded("get_users_posts", "unknown_id")) is None
    assert classify(recorded("get_users_by_usernames", "partial_errors")) is None


def test_successes_are_never_errors() -> None:
    for case in ("three_accounts", "xdevelopers_post_fields"):
        assert classify(recorded("get_users_by_usernames", case)) is None


def test_a_404_is_not_found() -> None:
    error = classify(answer(404, problem("resource-not-found", 404)))
    assert isinstance(error, NotFoundError)
    assert "GET /2/users/by" in str(error)


def test_a_resource_not_found_problem_is_not_found_at_any_4xx() -> None:
    assert isinstance(classify(answer(410, problem("resource-not-found", 410))), NotFoundError)


def test_an_invalid_request_problem_is_an_invalid_request_at_any_4xx() -> None:
    error = classify(answer(422, problem("invalid-request", 422)))
    assert isinstance(error, InvalidRequestError)


def test_the_problem_type_is_read_on_either_host() -> None:
    body = problem("invalid-request", 409)
    body["type"] = "https://api.twitter.com/2/problems/invalid-request"
    assert isinstance(classify(answer(409, body)), InvalidRequestError)


def test_a_429_waits_until_x_rate_limit_reset() -> None:
    reset = int(time.time()) + 120
    body = {"errors": [{"code": 88, "message": "Rate limit exceeded"}]}
    error = classify(
        answer(429, body, headers={"x-rate-limit-reset": str(reset)}, kind="application/json")
    )
    assert isinstance(error, RateLimitError)
    assert error.retry_after is not None
    assert 120 - SLACK <= error.retry_after <= 120 + SLACK
    assert "Rate limit exceeded" in str(error)


def test_a_429_past_its_reset_waits_nothing() -> None:
    reset = int(time.time()) - 60
    error = classify(
        answer(429, problem("rate-limit-exceeded", 429), headers={"x-rate-limit-reset": str(reset)})
    )
    assert isinstance(error, RateLimitError)
    assert error.retry_after == 0.0


@pytest.mark.parametrize("headers", [{}, {"x-rate-limit-reset": "soon"}])
def test_a_429_without_a_readable_reset_waits_the_window(headers: dict[str, str]) -> None:
    error = classify(answer(429, problem("rate-limit-exceeded", 429), headers=headers))
    assert isinstance(error, RateLimitError)
    assert error.retry_after == RATE_LIMIT_WINDOW == 900.0


def test_a_rate_limit_exceeded_problem_is_a_rate_limit_at_another_status() -> None:
    error = classify(answer(403, problem("rate-limit-exceeded", 403)))
    assert isinstance(error, RateLimitError)
    assert error.retry_after == RATE_LIMIT_WINDOW


def test_a_rate_limit_exceeded_problem_at_a_5xx_falls_through_to_core() -> None:
    assert classify(answer(503, problem("rate-limit-exceeded", 503))) is None


def test_a_usage_cap_waits_the_billing_cycle() -> None:
    error = classify(answer(429, problem("usage-capped", 429), headers={"x-rate-limit-reset": "1"}))
    assert isinstance(error, RateLimitError)
    assert error.retry_after == BILLING_CYCLE == 31 * 86_400
    assert "next billing cycle" in str(error)


def test_a_5xx_falls_through_to_core() -> None:
    assert classify(answer(503, {"title": "Service Unavailable"}, kind="application/json")) is None


def test_a_body_that_is_not_json_maps_by_status() -> None:
    response = httpx.Response(400, content=b"<html>bad</html>", request=httpx.Request("GET", URL))
    assert isinstance(classify(response), InvalidRequestError)


async def test_retries_wait_out_a_short_reset() -> None:
    """A 429 whose window resets now is retried at once (ADR-0010, decision 3)."""
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    client = AsyncClient(
        dataclasses.replace(config, retry=RetryPolicy(jitter=False)), auth=auth, sleep=sleep
    )
    reset = str(int(time.time()) - 60)  # past by more than the clock's step back
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://api.x.com/2/users/by").mock(
            side_effect=[
                httpx.Response(
                    429,
                    json=problem("rate-limit-exceeded", 429),
                    headers={"x-rate-limit-reset": reset},
                ),
                httpx.Response(200, json={"data": []}),
            ]
        )
        assert await client.get_json("/users/by", params={"usernames": "USDA"}) == {"data": []}
    assert route.call_count == 2
    assert waits == [0.5], "the policy's own first backoff, the reset being past"


async def test_a_reset_beyond_backoff_max_reaches_the_caller() -> None:
    """A window that resets in an hour is not waited for: one request, ``retry_after`` set."""
    client = AsyncClient(config, auth=auth)
    reset = str(int(time.time()) + 3600)
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://api.x.com/2/users/by").mock(
            return_value=httpx.Response(
                429,
                json=problem("rate-limit-exceeded", 429),
                headers={"x-rate-limit-reset": reset},
            )
        )
        with pytest.raises(RateLimitError) as raised:
            await client.get_json("/users/by", params={"usernames": "USDA"})
    assert route.call_count == 1
    assert raised.value.retry_after is not None
    assert 3600 - SLACK <= raised.value.retry_after <= 3600 + SLACK
    assert "(HTTP 429 from GET /2/users/by)" in str(raised.value)


async def test_a_usage_cap_is_not_retried() -> None:
    client = AsyncClient(config, auth=auth)
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://api.x.com/2/users/by").mock(
            return_value=httpx.Response(429, json=problem("usage-capped", 429))
        )
        with pytest.raises(RateLimitError):
            await client.get_json("/users/by", params={"usernames": "USDA"})
    assert route.call_count == 1
