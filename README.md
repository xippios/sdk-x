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

users = tasks.lookup_users(["USDA", "FAO"])  # 0.010 USD a user found
usda = next(user for user in users.data.data if user.username == "USDA")

page = tasks.get_user_posts(usda.id, max_results=10)  # 0.005 USD a post returned
for post in page.data.data or []:
    print(post.created_at, post.public_metrics.like_count, post.text)
print(page.meta.retrieved_at, page.meta.request, page.data.meta.result_count)

older = tasks.get_user_posts(usda.id, pagination_token=page.data.meta.next_token)
```

Every task returns one page as X sends it, in `result.data`; a call that returns data
spends X credits at the prices of X's pricing page, which each task's docstring names (the
page states none for `get_usage`). Paging is the caller's, with the `next_token` of the
previous page's `meta`. Underneath the tasks, `xippios.x.api` wraps nine X API v2
operations one page at a time (users by username, posts by id, a user's posts, post counts
over the archive, recent search, post counts over the last seven days, a List's posts, a
List's members and the project's usage).

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

`xippios-x-mcp` serves stdio; `--http` serves streamable HTTP instead. Tools are read-only
and named `x_<verb>_<noun>`; every call that returns data spends X credits, and each
tool's description gives its price (the pricing page states none for `x_get_usage`). A
tool returns one page, which its result cap holds whole for Latin-script text: up to 100
posts in 128,000 bytes, 100 users in 160,000, and 64 KB for the counts, which a month of
hourly buckets fits. A page of mostly non-Latin text, or minute counts over more than
about 14 hours, can be cut, with a note on how to see the rest.

## Status

<!-- Core's family check (tests/test_family.py) reads this table: keep the "## Status"
heading and the "Task function" column. Each row's Task function cell starts with the
task's name in backticks, alone or as its call (`get_data(code, year)`); several tasks in
one row are backticked names separated by commas; prose may follow. The tables list
exactly tasks.__all__. -->

| Upstream operation | Task function | MCP tool | Status |
| --- | --- | --- | --- |
| `GET /2/users/by` (`getUsersByUsernames`) | `lookup_users(usernames, most_recent_post)` | `x_lookup_users` | alpha; 0.010 USD a user, 0.005 USD more with `most_recent_post` |
| `GET /2/users/{id}/tweets` (`getUsersPosts`) | `get_user_posts(id, max_results, pagination_token, start_time, end_time)` | `x_get_user_posts` | alpha; 0.005 USD a post |
| `GET /2/tweets/search/recent` (`searchPostsRecent`) | `search_recent_posts(query, max_results, next_token, start_time, end_time)` | `x_search_recent_posts` | alpha; 0.005 USD a post; query of 512 characters at most |
| `GET /2/tweets/counts/all` (`getPostsCountsAll`) | `count_posts(query, granularity, start_time, end_time, next_token)` | `x_count_posts` | alpha; 0.010 USD a request; query of 1,024 characters at most |
| `GET /2/lists/{id}/tweets` (`getListsPosts`) | `get_list_posts(id, max_results, pagination_token)` | `x_get_list_posts` | alpha; 0.005 USD a post |
| `GET /2/tweets/search/recent` (`searchPostsRecent`, `conversation_id:`) | `get_conversation_posts(conversation_id, max_results, next_token)` | `x_get_conversation_posts` | alpha; 0.005 USD a post |
| `GET /2/usage/tweets` (`getUsage`) | `get_usage(days)` | `x_get_usage` | alpha; no price stated |

Prices are those of X's pricing page in the snapshot of 2026-10-29
(`docs/upstream/pages/pricing.md`); a post or user read again the same UTC day is not billed
again, a counts request always is.

## Upstream terms and attribution

Data comes from X API v2 (https://x.com) under the
[X Developer Agreement](https://docs.x.com/developer-terms/agreement) and the
[X Developer Policy](https://docs.x.com/developer-terms/policy), which bind every app that
uses it; this package adds no rights to it. Documentation snapshot and its attribution:
`docs/upstream/FETCHED.md`.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
