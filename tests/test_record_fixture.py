"""The recorder: D1's rewrite and its verify, the accounts it refuses, its estimate.

The rewrite is tested on recorded fixtures changed in memory: their placeholders are put
back to made-up text, standing for the text X sent, which the recorder never wrote, and
one test adds a made-up user who is not one of the three accounts. The end-to-end test
records through ``respx`` into a temporary directory, never into ``tests/fixtures/``.
"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
import respx
from xippios.core.testing import Fixture, fixture_path, load_fixture

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_fixture.py"
FIXTURES = Path(__file__).parent / "fixtures"
ACCOUNT_IDS = {"2244994945", "61853389", "19649135"}
LIST_ID = "715919216927322112"
MADE_UP_KEY = "made-up-key-for-the-recorder-test"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def placeholder_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Keys resolve as the recorder resolves them: core's pin is lifted here (ADR-0013).

    ``--wrong-key`` must send its own key and the scrub must see the key in the
    environment, so ``EnvKeyAuth`` is not pinned; ``X_API_KEY`` holds a made-up key in
    place of the shell's.
    """
    monkeypatch.setenv("X_API_KEY", MADE_UP_KEY)
    return MADE_UP_KEY


@pytest.fixture(scope="module")
def recorder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("record_fixture", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def loaded(wrapper: str, case: str) -> Fixture:
    return load_fixture(fixture_path(FIXTURES, wrapper, case))


def with_body(fixture: Fixture, body: Any) -> Fixture:
    response = fixture.response.model_copy(update={"body": json.dumps(body)})
    return fixture.model_copy(update={"response": response})


def unrewritten(fixture: Fixture) -> tuple[Fixture, list[str]]:
    """``fixture`` with every placeholder made a distinct made-up text, and those texts."""
    made_up: list[str] = []

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {key: walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, str) and node.endswith(" rewritten]"):
            made_up.append(f"made-up {node[1:].split()[0]} number {len(made_up)} été")
            return made_up[-1]
        return node

    return with_body(fixture, walk(json.loads(fixture.response.body))), made_up


def test_the_rewrite_leaves_no_text_of_a_users_answer(recorder: ModuleType) -> None:
    """Three accounts with their most recent posts: descriptions and texts rewritten, the
    three accounts' names, handles and locations, ids and metrics as sent."""
    fixture, made_up = unrewritten(loaded("get_users_by_usernames", "three_accounts"))
    assert len(made_up) == 6
    rewritten, originals = recorder.rewrite(fixture)
    assert sorted(value for _, value in originals) == sorted(made_up)
    assert recorder.survivors(rewritten, originals) == []
    text = rewritten.model_dump_json()
    assert not any(value in text for value in made_up)
    body = json.loads(rewritten.response.body)
    assert body == json.loads(loaded("get_users_by_usernames", "three_accounts").response.body)
    assert {user["username"] for user in body["data"]} == {"XDevelopers", "USDA", "FAO"}


def test_the_rewrite_covers_every_answer_with_text(recorder: ModuleType) -> None:
    cases = [
        ("get_users_by_usernames", "partial_errors"),
        ("get_users_by_usernames", "xdevelopers_post_fields"),
        ("get_posts_by_ids", "most_recent_three"),
        ("get_users_posts", "xdevelopers_ten"),
        ("get_users_posts", "usda_ten"),
        ("get_users_posts", "fao_ten"),
        ("search_posts_recent", "usda_ten"),
        ("search_posts_recent", "usda_ten_page_2"),
        ("get_lists_posts", "xdevelopers_list_ten"),
        ("get_lists_members", "xdevelopers_list_ten"),
    ]
    for case in cases:
        recorded = loaded(*case)
        fixture, made_up = unrewritten(recorded)
        assert made_up, case
        rewritten, originals = recorder.rewrite(fixture)
        assert len(originals) == len(made_up), case
        assert recorder.survivors(rewritten, originals) == [], case
        assert json.loads(rewritten.response.body) == json.loads(recorded.response.body), case


def test_the_rewrite_reaches_other_users_and_mentions(recorder: ModuleType) -> None:
    """A user who is not one of the three, and a mention of one, lose handle, name,
    location; ids and metrics stay."""
    fixture, _ = unrewritten(loaded("get_users_by_usernames", "three_accounts"))
    body = json.loads(fixture.response.body)
    stranger = {
        **body["data"][0],
        "id": "12",
        "username": "made_up_handle",
        "name": "Made Up Person",
        "location": "Made Up Town",
    }
    body["includes"]["users"] = [stranger]
    body["includes"]["tweets"][0]["entities"] = {
        "mentions": [{"start": 0, "end": 15, "username": "made_up_handle", "id": "12"}]
    }
    rewritten, originals = recorder.rewrite(with_body(fixture, body))
    assert recorder.survivors(rewritten, originals) == []
    after = json.loads(rewritten.response.body)
    (user,) = after["includes"]["users"]
    assert (user["username"], user["name"], user["location"]) == (
        "[username rewritten]",
        "[name rewritten]",
        "[location rewritten]",
    )
    assert (user["id"], user["public_metrics"]) == ("12", stranger["public_metrics"])
    (mention,) = after["includes"]["tweets"][0]["entities"]["mentions"]
    assert mention == {"start": 0, "end": 15, "username": "[username rewritten]", "id": "12"}
    assert after["data"][1]["name"] == "Dept. of Agriculture"
    assert "made_up_handle" not in rewritten.model_dump_json()


@pytest.mark.parametrize(
    "case",
    [
        ("get_posts_counts_all", "usda_by_day"),
        ("get_posts_counts_all", "usda_by_day_page_2"),
        ("get_posts_counts_all", "usda_originals_by_day"),
        ("get_posts_counts_all", "granularity_week"),
        ("get_users_by_usernames", "wrong_key"),
        ("get_users_posts", "unknown_id"),
        ("get_posts_counts_recent", "usda_by_day"),
        ("get_posts_counts_recent", "granularity_week"),
        ("search_posts_recent", "unbalanced_parenthesis"),
        ("get_lists_posts", "unknown_id"),
    ],
)
def test_counts_and_errors_stay_as_sent(recorder: ModuleType, case: tuple[str, str]) -> None:
    fixture = loaded(*case)
    rewritten, originals = recorder.rewrite(fixture)
    assert originals == []
    assert rewritten.response.body == fixture.response.body


def test_the_verify_refuses_a_value_that_survives(recorder: ModuleType) -> None:
    """A description repeated in an account's location survives the rewrite: refused by
    the description's path, the value never named."""
    fixture = loaded("get_users_by_usernames", "three_accounts")
    body = json.loads(fixture.response.body)
    body["data"][1]["description"] = "Made-up bio from Washington, DC"
    body["data"][1]["location"] = "Made-up bio from Washington, DC"
    rewritten, originals = recorder.rewrite(with_body(fixture, body))
    assert recorder.survivors(rewritten, originals) == ["body.data[1].description"]


def test_the_verify_finds_a_value_behind_a_json_escape(recorder: ModuleType) -> None:
    fixture = loaded("get_users_by_usernames", "three_accounts")
    body = json.loads(fixture.response.body)
    body["data"][0]["description"] = 'Made-up "quoted" bio'
    body["data"][0]["url"] = 'Made-up "quoted" bio'
    rewritten, originals = recorder.rewrite(with_body(fixture, body))
    assert recorder.survivors(rewritten, originals) == ["body.data[0].description"]


def test_the_rewrite_reaches_every_member_of_a_list(recorder: ModuleType) -> None:
    """A List's members are other accounts: handle, name, location and bio rewritten for
    each, ids, times and metrics as sent."""
    recorded = loaded("get_lists_members", "xdevelopers_list_ten")
    fixture, made_up = unrewritten(recorded)
    members = json.loads(recorded.response.body)["data"]
    assert len(made_up) == 4 * len(members) == 32
    rewritten, originals = recorder.rewrite(fixture)
    assert {where.rsplit(".", 1)[-1] for where, _ in originals} == {
        "username",
        "name",
        "location",
        "description",
    }
    assert recorder.survivors(rewritten, originals) == []
    assert json.loads(rewritten.response.body) == json.loads(recorded.response.body)


def test_the_lists_are_owned_by_the_three_accounts(recorder: ModuleType) -> None:
    assert recorder.LISTS == {LIST_ID: "XDevelopers"}
    assert set(recorder.LISTS.values()) <= set(recorder.ACCOUNTS)


def test_the_three_accounts_ids_come_from_the_recorded_answers(recorder: ModuleType) -> None:
    assert recorder.account_ids() == ACCOUNT_IDS
    posts = recorder.account_post_ids()
    assert {"2114879022433800258", "2115806101480337475", "2115789000682180921"} <= posts


@pytest.mark.parametrize(
    ("wrapper", "params", "unknown", "refused"),
    [
        ("search_posts_all", {"query": "from:USDA"}, False, "not one of the eight wrappers"),
        ("get_users_by_usernames", {"usernames": "USDA", "bio": "x"}, False, "takes no bio"),
        ("get_users_by_usernames", {"usernames": "USDA,someone"}, False, "admits one other"),
        ("get_users_by_usernames", {"usernames": "USDA,someone,other"}, True, "2 were given"),
        ("get_users_posts", {"id": "12"}, False, "not one of the user ids"),
        ("get_users_posts", {"id": "@USDA"}, True, "needs id="),
        ("get_posts_by_ids", {"ids": "2115806101480337475,20"}, False, "1 of the ids"),
        ("get_posts_counts_all", {"query": "lang:en"}, False, "with from:"),
        ("get_posts_counts_all", {"query": "from:USDA OR from:someone"}, False, "with from:"),
        ("get_posts_counts_all", {"query": "from:FAO @someone"}, False, "with from:"),
        ("get_posts_counts_all", {"query": "to:FAO"}, False, "with from:"),
        ("get_posts_by_ids", {"ids": "1", "expansions": "author_id"}, False, "author_id is"),
        (
            "get_posts_by_ids",
            {"ids": "2115806101480337475", "expansions": "referenced_posts"},
            False,
            "referenced_posts is refused",
        ),
        (
            "get_users_posts",
            {"id": "61853389", "expansions": "referenced_posts"},
            False,
            "expansions admits most_recent_post_id",
        ),
        (
            "get_users_by_usernames",
            {"usernames": "USDA", "expansions": "pinned_post_id"},
            False,
            "pinned_post_id is refused",
        ),
        (
            "get_users_by_usernames",
            {"usernames": "USDA", "user.fields": "url,entities"},
            False,
            "entities is",
        ),
        (
            "get_users_posts",
            {"id": "61853389", "user.fields": "profile_image_url"},
            False,
            "refused",
        ),
        ("get_users_posts", {"id": "61853389", "post.fields": "lang,entities"}, False, "entities"),
        ("get_posts_by_ids", {"ids": "1", "post.fields": "note_post"}, False, "note_post is"),
        ("get_posts_by_ids", {"ids": "1", "post.fields": "withheld"}, False, "withheld is"),
        ("search_posts_recent", {"query": "from:someone"}, False, "returns the posts it matches"),
        ("search_posts_recent", {"query": "from:USDA OR from:someone"}, False, "posts it matches"),
        ("search_posts_recent", {"query": "from:USDA OR lang:en"}, False, "posts it matches"),
        ("search_posts_recent", {"query": "from:USDA wheat"}, False, "posts it matches"),
        ("search_posts_recent", {"query": "from:USDA @someone"}, False, "posts it matches"),
        ("search_posts_recent", {"query": "-is:retweet from:USDA"}, False, "posts it matches"),
        ("search_posts_recent", {"query": "FROM:USDA"}, False, "posts it matches"),
        ("search_posts_recent", {"query": "to:USDA"}, False, "posts it matches"),
        ("search_posts_recent", {"query": ""}, False, "posts it matches"),
        (
            "search_posts_recent",
            {"query": "from:USDA", "expansions": "author_id"},
            False,
            "author_id is refused",
        ),
        ("get_posts_counts_recent", {"query": "lang:en"}, False, "with from:"),
        ("get_posts_counts_recent", {"query": "from:FAO OR from:someone"}, False, "with from:"),
        ("get_lists_posts", {"id": "12"}, False, "not one of the Lists"),
        ("get_lists_members", {"id": "12"}, False, "not one of the Lists"),
        ("get_lists_posts", {"id": "list"}, True, "needs id="),
        ("get_lists_members", {"id": LIST_ID, "user.fields": "url"}, False, "url is refused"),
        (
            "get_lists_members",
            {"id": LIST_ID, "expansions": "pinned_post_id"},
            False,
            "pinned_post_id is refused",
        ),
        (
            "get_lists_posts",
            {"id": LIST_ID, "expansions": "referenced_posts"},
            False,
            "referenced_posts is refused",
        ),
        ("get_lists_posts", {"id": LIST_ID, "post.fields": "entities"}, False, "entities is"),
    ],
)
def test_requests_beyond_the_three_accounts_are_refused(
    recorder: ModuleType, wrapper: str, params: dict[str, str], unknown: bool, refused: str
) -> None:
    reason = recorder.refusal(wrapper, params, unknown=unknown)
    assert reason is not None
    assert refused in reason


@pytest.mark.parametrize(
    ("wrapper", "params", "unknown"),
    [
        ("get_users_by_usernames", {"usernames": "xdevelopers,USDA,FAO"}, False),
        ("get_users_by_usernames", {"usernames": "XDevelopers,xippiosnouser01"}, True),
        ("get_users_posts", {"id": "61853389", "max_results": "10"}, False),
        ("get_users_posts", {"id": "9000000000000000000"}, True),
        ("get_posts_by_ids", {"ids": "2115806101480337475,2115789000682180921"}, False),
        (
            "get_users_by_usernames",
            {"usernames": "XDevelopers", "expansions": "most_recent_post_id", "user.fields": "url"},
            False,
        ),
        ("get_posts_counts_all", {"query": "from:USDA -is:retweet -is:reply"}, False),
        ("search_posts_recent", {"query": "from:usda -is:retweet -is:reply"}, False),
        ("search_posts_recent", {"query": "from:XDevelopers -is:reply"}, False),
        ("search_posts_recent", {"query": "(from:USDA"}, False),
        ("search_posts_recent", {"query": "(from:FAO -is:retweet) -is:reply"}, False),
        ("get_posts_counts_recent", {"query": "from:FAO", "granularity": "day"}, False),
        ("get_lists_posts", {"id": LIST_ID, "max_results": "10"}, False),
        ("get_lists_posts", {"id": "9000000000000000000"}, True),
        (
            "get_lists_members",
            {"id": LIST_ID, "user.fields": "created_at,location,verified_type"},
            False,
        ),
        ("get_users_posts", {"id": "61853389", "user.fields": "url"}, False),
    ],
)
def test_requests_for_the_three_accounts_pass(
    recorder: ModuleType, wrapper: str, params: dict[str, str], unknown: bool
) -> None:
    assert recorder.refusal(wrapper, params, unknown=unknown) is None


def test_every_recorded_request_passes_the_guard(recorder: ModuleType) -> None:
    """The query of each recorded fixture, read back, is one the recorder admits today;
    ``most_recent_post_id`` is the one expansion any of them sends (``most_recent_three``
    re-recorded without ``referenced_posts``, Johannes, 2026-10-29)."""
    assert recorder.ADMITTED["expansions"] == {"most_recent_post_id"}
    expansions: set[str] = set()
    for path in sorted(FIXTURES.glob("*/*.json")):
        url = httpx.URL(load_fixture(path).request.url)
        params = dict(url.params)
        if path.parent.name in ("get_users_posts", "get_lists_posts", "get_lists_members"):
            params["id"] = url.path.split("/")[3]
        unknown = path.stem in ("partial_errors", "unknown_id", "username_too_long")
        assert recorder.refusal(path.parent.name, params, unknown=unknown) is None, path.stem
        expansions.update(item for item in params.get("expansions", "").split(",") if item)
    assert expansions == {"most_recent_post_id"}


@pytest.mark.parametrize(
    ("wrapper", "params", "wrong_key", "cost"),
    [
        (
            "get_users_by_usernames",
            {"usernames": "XDevelopers,USDA,FAO", "expansions": "most_recent_post_id"},
            False,
            0.045,
        ),
        ("get_posts_by_ids", {"ids": "1,2,3"}, False, 0.015),
        ("get_posts_by_ids", {"ids": "1,2,3", "expansions": "referenced_posts"}, False, 0.045),
        ("get_users_posts", {"id": "61853389"}, False, 0.05),
        ("get_posts_counts_all", {"query": "from:USDA"}, False, 0.01),
        ("get_users_by_usernames", {"usernames": "XDevelopers"}, True, 0.0),
        ("search_posts_recent", {"query": "from:USDA"}, False, 0.05),
        ("search_posts_recent", {"query": "from:USDA", "max_results": "100"}, False, 0.5),
        ("get_posts_counts_recent", {"query": "from:USDA"}, False, 0.005),
        ("get_lists_posts", {"id": LIST_ID}, False, 0.5),
        ("get_lists_posts", {"id": LIST_ID, "max_results": "10"}, False, 0.05),
        ("get_lists_members", {"id": LIST_ID}, False, 1.0),
        ("get_lists_members", {"id": LIST_ID, "max_results": "10"}, False, 0.1),
        (
            "get_lists_members",
            {"id": LIST_ID, "max_results": "10", "expansions": "most_recent_post_id"},
            False,
            0.15,
        ),
    ],
)
def test_the_estimate_is_the_snapshots_prices(
    recorder: ModuleType, wrapper: str, params: dict[str, str], wrong_key: bool, cost: float
) -> None:
    estimate, uncounted = recorder.estimate(wrapper, params, wrong_key=wrong_key)
    assert estimate == pytest.approx(cost)
    assert uncounted == []


def test_an_unknown_that_exists_is_not_written(recorder: ModuleType) -> None:
    assert (
        recorder.unknown_answered(
            "get_users_by_usernames", loaded("get_users_by_usernames", "partial_errors")
        )
        is None
    )
    assert (
        recorder.unknown_answered("get_users_posts", loaded("get_users_posts", "unknown_id"))
        is None
    )
    assert "has posts" in recorder.unknown_answered(
        "get_users_posts", loaded("get_users_posts", "usda_ten")
    )
    fixture = loaded("get_users_by_usernames", "partial_errors")
    body = json.loads(fixture.response.body)
    body["data"].append({"id": "12", "username": "made_up_handle", "name": "Made Up"})
    assert "belongs to an account" in recorder.unknown_answered(
        "get_users_by_usernames", with_body(fixture, body)
    )
    assert (
        recorder.unknown_answered("get_lists_posts", loaded("get_lists_posts", "unknown_id"))
        is None
    )
    for wrapper in ("get_lists_posts", "get_lists_members"):
        assert "names a List" in recorder.unknown_answered(
            wrapper, loaded(wrapper, "xdevelopers_list_ten")
        )


@pytest.fixture
def scratch(recorder: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The recorder writes under ``tmp_path``; the recorded fixtures stay where they are."""
    monkeypatch.setattr(recorder, "ROOT", tmp_path)
    monkeypatch.setattr(recorder, "FIXTURES", tmp_path / "tests" / "fixtures")
    return tmp_path / "tests" / "fixtures"


def test_main_records_rewrites_and_writes_once(
    recorder: ModuleType,
    scratch: Path,
    placeholder_api_key: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sent = {
        "data": [
            {
                "id": "61853389",
                "username": "USDA",
                "name": "Dept. of Agriculture",
                "description": "Made-up bio",
            }
        ],
        "includes": {
            "tweets": [{"id": "1", "text": "Made-up post", "edit_history_tweet_ids": ["1"]}]
        },
    }
    argv = ["get_users_by_usernames", "made_up", "usernames=USDA", "expansions=most_recent_post_id"]
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://api.x.com/2/users/by").mock(
            return_value=httpx.Response(
                200, json=sent, headers={"x-rate-limit-remaining": "9", "x-echo": MADE_UP_KEY}
            )
        )
        assert recorder.main(argv) == 0
        assert recorder.main(argv) == 1, "a fixture is recorded once"
    assert route.call_count == 1
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {placeholder_api_key}"
    written = (scratch / "get_users_by_usernames" / "made_up.json").read_text(encoding="utf-8")
    assert "Made-up" not in written
    assert placeholder_api_key not in written
    assert ["x-echo", "REDACTED"] in json.loads(written)["response"]["headers"]
    body = json.loads(json.loads(written)["response"]["body"])
    assert body["data"][0]["description"] == "[description rewritten]"
    assert body["includes"]["tweets"][0]["text"] == "[text rewritten]"
    out = capsys.readouterr().out
    assert "estimate: at most 0.015 USD" in out
    assert "x-rate-limit-remaining: 9" in out
    assert "2 values rewritten" in out
    assert "exists; fixtures are recorded once" in out
    assert placeholder_api_key not in out


def test_main_sends_the_wrong_key_and_records_the_401(
    recorder: ModuleType, scratch: Path, placeholder_api_key: str
) -> None:
    answer = {
        "title": "Unauthorized",
        "type": "about:blank",
        "status": 401,
        "detail": "Unauthorized",
    }
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://api.x.com/2/users/by").mock(
            return_value=httpx.Response(401, json=answer)
        )
        assert (
            recorder.main(["get_users_by_usernames", "wrong", "usernames=FAO", "--wrong-key"]) == 0
        )
    assert route.calls.last.request.headers["Authorization"] == "Bearer not-a-valid-key"
    written = json.loads((scratch / "get_users_by_usernames" / "wrong.json").read_text())
    assert written["response"]["status"] == 401


def test_main_refuses_before_any_request(
    recorder: ModuleType, scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.route()
        assert recorder.main(["get_users_by_usernames", "other", "usernames=someone"]) == 1
    assert route.call_count == 0
    assert not scratch.exists()
    assert "not recorded" in capsys.readouterr().out


def test_main_writes_nothing_when_the_unknown_exists(
    recorder: ModuleType, scratch: Path, placeholder_api_key: str
) -> None:
    found = {"data": [{"id": "12", "username": "made_up_handle", "name": "Made Up"}]}
    with respx.mock(assert_all_called=True) as router:
        router.get("https://api.x.com/2/users/by").mock(
            return_value=httpx.Response(200, json=found)
        )
        argv = ["get_users_by_usernames", "unknown", "usernames=made_up_handle", "--unknown"]
        assert recorder.main(argv) == 1
    assert not (scratch / "get_users_by_usernames" / "unknown.json").exists()


def test_main_records_a_lists_members_rewritten(
    recorder: ModuleType, scratch: Path, placeholder_api_key: str
) -> None:
    """The List id fills the path; a member who is not one of the three loses handle, name
    and location, keeps id and metrics."""
    sent = {
        "data": [
            {
                "id": "12",
                "username": "made_up_park",
                "name": "Made Up Park",
                "location": "Made Up Valley",
                "public_metrics": {
                    "followers_count": 3,
                    "following_count": 2,
                    "tweet_count": 1,
                    "listed_count": 0,
                },
            }
        ],
        "meta": {"result_count": 1},
    }
    argv = [
        "get_lists_members",
        "made_up",
        f"id={LIST_ID}",
        "max_results=1",
        "user.fields=location,public_metrics",
    ]
    with respx.mock(assert_all_called=True) as router:
        route = router.get(f"https://api.x.com/2/lists/{LIST_ID}/members").mock(
            return_value=httpx.Response(200, json=sent)
        )
        assert recorder.main(argv) == 0
    assert route.call_count == 1
    written = (scratch / "get_lists_members" / "made_up.json").read_text(encoding="utf-8")
    assert "Made Up" not in written
    assert "made_up_park" not in written
    (member,) = json.loads(json.loads(written)["response"]["body"])["data"]
    assert (member["username"], member["name"], member["location"]) == (
        "[username rewritten]",
        "[name rewritten]",
        "[location rewritten]",
    )
    assert (member["id"], member["public_metrics"]) == ("12", sent["data"][0]["public_metrics"])  # type: ignore[index]


def test_main_refuses_a_search_beyond_the_three_accounts(
    recorder: ModuleType, scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.route()
        argv = ["search_posts_recent", "other", "query=from:USDA OR wheat"]
        assert recorder.main(argv) == 1
    assert route.call_count == 0
    assert not scratch.exists()
    assert "a search returns the posts it matches" in capsys.readouterr().out
