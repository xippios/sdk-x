# xippios-x

Typed Python client, MCP server and FastAPI routes for
[X API v2](https://x.com), part of the
[xippios SDK family](https://github.com/xippios). Names and semantics follow the
upstream documentation; every response carries release metadata (source, endpoint,
retrieved_at, published_at, vintage).

## Install

```bash
uv add xippios-x            # client only
uv add "xippios-x[mcp]"     # + MCP server
uv add "xippios-x[http]"    # + FastAPI router
```

Set `X_API_KEY` in the environment to your X app's Bearer Token, which X also calls the
App only Access Token (Developer Console, Keys and tokens), not the console's API Key,
the OAuth 1.0a consumer key. Nothing is read from files.

## 30-second example

```python
from xippios.x import tasks

# result = tasks.<task>(...)
# result.data, result.meta.retrieved_at, result.meta.request
```

Task functions are listed in the status table below as they are added.

## MCP

```json
{
  "mcpServers": {
    "x": {
      "command": "uvx",
      "args": ["--from", "xippios-x[mcp]", "xippios-x-mcp"],
      "env": { "X_API_KEY": "..." }
    }
  }
}
```

Tools are read-only and named `x_<verb>_<noun>`. Results are capped, at
200 rows or 64 KB unless a tool has a cap of its own, with a note on how to see the rest.
`--http` serves streamable HTTP instead of stdio.

## Status

<!-- Core's family check (tests/test_family.py) reads this table: keep the "## Status"
heading and the "Task function" column. Each row's Task function cell starts with the
task's name in backticks, alone or as its call (`get_data(code, year)`); several tasks in
one row are backticked names separated by commas; prose may follow. The tables list
exactly tasks.__all__. -->

| Upstream operation | Task function | MCP tool | Status |
| --- | --- | --- | --- |
| (none yet) | | | |

## Upstream terms and attribution

Data comes from X API v2 (https://x.com) under the
[X Developer Agreement](https://docs.x.com/developer-terms/agreement) and the
[X Developer Policy](https://docs.x.com/developer-terms/policy), which bind every app that
uses it; this package adds no rights to it. Documentation snapshot and its attribution:
`docs/upstream/FETCHED.md`.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
