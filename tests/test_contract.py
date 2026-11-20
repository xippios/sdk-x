"""The package contract and what the adapters of xippios-core 0.4.0 answer a caller.

Offline, in process: the MCP server through an in-process ``mcp.client.Client``, the router
through FastAPI's ``TestClient`` and the entry point in a child process. ``mcp.build()``
is the tool set a host serves (conventions §8; sdk-core ADR-0026, amendment 2026-11-18,
points c and d), and ``_client.ENV_VARS`` the variables the package reads, for that host.
Every refusal below comes before the task runs, so nothing is sent; the one answer with
data replays ``tests/fixtures/get_users_posts/usda_ten.json``.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.client import Client
from mcp.types import TextContent
from xippios.core import EnvVar
from xippios.core.mcp import ToolSet, build_server
from xippios.core.testing import ReplayFixture

from xippios.x import mcp, tasks
from xippios.x._client import API_KEY_ENV, ENV_VARS
from xippios.x.http import router

ENTRY_POINT = "xippios-x-mcp"
USDA = "61853389"


async def call(name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    """A tool's answer through an in-process client: whether it is flagged, and its text."""
    async with Client(mcp.server) as client:
        result = await client.call_tool(name, arguments)
    content = result.content[0]
    assert isinstance(content, TextContent), content
    return result.is_error, content.text


def test_env_vars_name_the_bearer_token_secret_and_required() -> None:
    assert (EnvVar(API_KEY_ENV, secret=True, required=True),) == ENV_VARS
    assert mcp.ENV_VARS is ENV_VARS, "the template's mcp.py names the client's list"


@pytest.mark.anyio
async def test_build_is_the_tool_set_the_entry_point_serves() -> None:
    tools = mcp.build()
    assert isinstance(tools, ToolSet)
    assert tools.source == "x"
    assert tools.read_only
    assert tools.caps == tasks.MCP_CAPS
    assert tools.instructions == mcp.INSTRUCTIONS
    served = [tool.name for tool in await mcp.server.list_tools()]
    hosted = [tool.name for tool in await build_server(tools).list_tools()]
    assert hosted == served == [f"x_{name}" for name in tasks.__all__]
    assert tools.add_options is None, "no option of the package's own"
    assert tools.apply_options is None


@pytest.mark.anyio
async def test_a_tool_refuses_an_argument_it_does_not_declare(
    respx_mock: respx.MockRouter,
) -> None:
    """``maxresults`` for ``max_results``: refused, where the tool ran with its default."""
    flagged, text = await call("x_get_user_posts", {"id": USDA, "maxresults": 100})
    assert flagged
    assert text == (
        "error: InvalidRequestError: maxresults: Not an argument of this tool; it takes id, "
        "max_results, pagination_token, start_time, end_time"
    )
    assert not respx_mock.calls, "refused before the task runs, so nothing is spent"


@pytest.mark.anyio
async def test_a_tool_flags_its_error_answer(respx_mock: respx.MockRouter) -> None:
    flagged, text = await call("x_get_conversation_posts", {"conversation_id": "@USDA"})
    assert flagged
    assert text == "error: InvalidRequestError: conversation_id: '@USDA' does not match [0-9]{1,19}"
    flagged, text = await call("x_count_posts", {"query": "from:USDA", "granularity": "week"})
    assert flagged
    assert text.startswith("error: InvalidRequestError: granularity: ")
    assert not respx_mock.calls


@pytest.mark.anyio
async def test_a_tool_answer_with_data_is_not_flagged(replay_fixture: ReplayFixture) -> None:
    replay_fixture("get_users_posts", "usda_ten")
    flagged, text = await call("x_get_user_posts", {"id": USDA})
    assert not flagged
    assert text.startswith('{"data":')


@pytest.mark.parametrize(
    ("method", "path", "arguments", "detail"),
    [
        ("GET", "/x/count_posts", {"query": "from:USDA", "granularity": "week"}, "granularity: "),
        ("GET", "/x/get_user_posts", {"max_results": "10"}, "id: Field required"),
        ("POST", "/x/lookup_users", ["USDA"], "body: "),
    ],
)
def test_a_route_answers_an_argument_its_schema_refuses_as_problem_details(
    respx_mock: respx.MockRouter, method: str, path: str, arguments: Any, detail: str
) -> None:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as http:
        if method == "GET":
            answered = http.get(path, params=arguments)
        else:
            answered = http.post(path, json=arguments)
    assert answered.status_code == 422
    assert answered.headers["content-type"].startswith("application/problem+json")
    problem = answered.json()
    assert problem["title"] == "InvalidRequestError"
    assert problem["detail"].startswith(detail)
    assert "input" not in problem, "the value given is not echoed"
    assert not respx_mock.calls


def entry_point(*argv: str) -> subprocess.CompletedProcess[str]:
    """The entry point's run with ``argv``, colours off and a width of its own."""
    environment = {**os.environ, "PYTHON_COLORS": "0", "NO_COLOR": "1", "COLUMNS": "100"}
    environment.pop("FORCE_COLOR", None)
    script = Path(sys.executable).with_name(ENTRY_POINT)
    return subprocess.run(
        [str(script), *argv], capture_output=True, text=True, env=environment, timeout=60
    )


def test_the_entry_point_names_itself_in_its_usage_and_errors() -> None:
    refused = entry_point("--bogus")
    assert refused.returncode == 2
    assert refused.stderr.startswith(f"usage: {ENTRY_POINT} ")
    assert f"{ENTRY_POINT}: error: unrecognized arguments: --bogus" in refused.stderr


def test_the_entry_point_help_says_allow_remote_changes_nothing_here() -> None:
    helped = entry_point("--help")
    assert helped.returncode == 0
    assert helped.stdout.startswith(f"usage: {ENTRY_POINT} ")
    text = " ".join(helped.stdout.split())
    assert "--allow-remote changes nothing: this read server is not held to loopback" in text
