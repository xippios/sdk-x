# sdk-x — instructions for Claude Code

`xippios-x` wraps X API v2 as a typed Python client, an MCP server
and FastAPI routes, built on `xippios-core`. This file holds the facts of this package;
the family rules every source shares are in `.claude/family.md`, which the next line imports.

@.claude/family.md

## What this package wraps

| | |
| --- | --- |
| Upstream | X API v2, https://x.com |
| API base URL | `https://api.x.com/2` |
| Documentation | https://docs.x.com/x-api/introduction, snapshotted in `docs/upstream/`; an OpenAPI or Swagger document a page names is kept beside it, its URL in `SPEC_URL` of `scripts/refresh_upstream.py` (`/refresh-upstream`) |
| Credentials | `X_API_KEY` from the environment, sent as `Authorization: Bearer`: the app's Bearer Token, which X calls the App only Access Token (`docs/upstream/pages/application-only.md`), not the console's "API Key", the OAuth 1.0a consumer key that only obtains a Bearer Token through `POST oauth2/token` |
| Rate limit | 60 requests per minute, burst 1; a self-imposed pace (ADR-0010 decision 1), enforced client-side in `_client.py`. X documents no per-minute limit but per-endpoint windows of 15 minutes, per app with a Bearer Token (`docs/upstream/pages/rate-limits.md`): 300 on `GET /2/users/by` and on both counts endpoints, 3,500 on `GET /2/tweets`, 10,000 on `GET /2/users/:id/tweets`, 450 on `GET /2/tweets/search/recent`, 900 on `GET /2/lists/:id/tweets` and on `GET /2/lists/:id/members`, 50 on `GET /2/usage/tweets`; a 1/sec limit only on `GET /2/tweets/search/all` and `GET /2/spaces/by/creator_ids`, which this package does not wrap. The windows are spent, never rationed ahead by the limiter (ADR-0010 decision 2; coordination row 304): a 429, whose `x-rate-limit-reset` is a Unix timestamp, is answered by `_client.py`'s `classify` alone, no `QuotaPolicy` (Johannes, 2026-10-29); see Paths, names and errors below. X reported `x-rate-limit-limit: 2000` on `GET /2/users/by` on 2026-10-29, where the page lists 300 |
| Write tools | no, this package is read-only |

The snapshot listed in `docs/upstream/FETCHED.md` is the reference for names, parameters and semantics.

## Layout

```
src/xippios/x/
  __init__.py      public surface: __version__ and re-exported task functions
  py.typed         PEP 561 marker; consumers' mypy --strict needs it
  _version.py      __version__ from distribution metadata
  _client.py       the one configured AsyncClient (base URL, key, rate limit) and classify,
                   upstream's documented error shapes
  errors.py        the package's own error classes, where conventions §5 calls for one
  models.py        pydantic models mirroring upstream payloads (UpstreamModel): the OpenAPI
                   document's User, Post, Expansions, Problem, the four responses, and its
                   enums (UserField, PostField, UserExpansion, PostExpansion, Granularity)
  api/             endpoint wrappers, one module per upstream operation: get_users_by_usernames,
                   get_posts_by_ids, get_users_posts, get_posts_counts_all; _query.py turns
                   parameters into the text X takes and refuses values outside the bounds
  tasks.py         task functions; __all__ is what the adapters register, but BULK_TASKS,
                   the Python-only ones; MCP_CAPS any per-tool result caps
  mcp.py           xippios-x-mcp entry point
  http.py          FastAPI router
  params.py        the packaged reference lists, read from reference/
  enums.py         StrEnums (IntEnums for integer ids) generated from the packaged lists;
                   never edited by hand
  reference/       packaged code lists (CSV/JSON) plus README with provenance
scripts/
  refresh_reference.py   fetches the packaged lists through api/ and regenerates enums.py
  refresh_upstream.py    captures docs/upstream/ and writes FETCHED.md (/refresh-upstream)
  record_fixture.py      records one exchange of the four wrappers, X Content rewritten (D1);
                         Recording fixtures below
tests/
  conftest.py      enables xippios.core.testing.plugin, which keeps the run offline
  fixtures/        recorded responses, <wrapper>/<case>.json, the directory named after the
                   wrapper function (conventions §10), never hand-written
  test_family.py   core's family check, one line: namespace levels, py.typed, __version__,
                   the adapters serving exactly the tasks, task shapes and docstrings, the
                   README status table, the template tag, the core bound
  test_api.py      the endpoint wrappers' replay tests, one per recorded case
  test_client.py   classify against the recorded refusals and built 429, usage cap and 404
  test_record_fixture.py  the recorder's rewrite, verify, account guards and estimate
  test_tasks.py    per-task replay tests
  test_live.py     @pytest.mark.live smoke tests, one per task
docs/upstream/     documentation snapshot and FETCHED.md
.github/workflows/ ci.yml (the required ci check, with the CHANGELOG and fixture-size steps),
                   publish.yml (the release train: tag, build, PyPI), live.yml (nightly live
                   tests), gates.yml (the merge gates as jobs, off until GATES_CALLER is 1)
.claude/family.md  the family rules, the template's, imported above
.claude/commands/  add-endpoint, record-fixture, refresh-upstream, refresh-reference-data, release-prep,
                   adopt-release
```

The import path is `xippios.x` (ADR-0006); `src/xippios/` is a namespace
package.

## Commands

```bash
uv run pytest -m live --tb=short   # needs XIPPIOS_LIVE_TESTS=1 and X_API_KEY

uv run xippios-x-mcp   # stdio; add --http for streamable HTTP
```

The offline run sends the key's placeholder, with `X_API_KEY` set to it because
`pyproject.toml` names that variable under `xippios_placeholder_key_envs`; the package
keeps no placeholder fixture of its own.

`.github/workflows/live.yml` runs the live tests nightly at 01:24 UTC, a time derived from
the slug so that sources sharing a key never start together.
Only its `uv run pytest -m live --tb=short` step sees the key, from the org secret `X_API_KEY`.

## X API v2 specifics

### Spend

Every request spends the app's prepaid credits, at the prices of
`docs/upstream/pages/pricing.md` (snapshot of 2026-10-29): a read per resource returned,
0.005 USD a post and 0.010 USD a user; post counts per request, 0.005 USD on
`GET /2/tweets/counts/recent` and 0.010 USD on `GET /2/tweets/counts/all`. Owned Reads,
0.001 USD a resource, apply only where `{id}` is the authenticated user who owns the app,
and an app-only Bearer Token has no authenticated user. A resource is billed once per UTC
day (deduplication, which the page calls a soft guarantee); a counts request is billed per
request, every time. Only successful responses that return data are billed
(`pages/usage-and-billing.md`). The pricing page states no price for `GET /2/usage/tweets`.
Pay-per-usage plans are capped at 3 million post reads per billing cycle, and the
Developer Console's spending limit per billing cycle is the hard stop: once it is reached,
X blocks every request until the next cycle. Fixture recordings and live runs spend inside
the budget line of the package's briefing, and a script that spends prints its estimate
before its first request.

### Fixtures and X content (D1)

Decided by Johannes on 2026-10-29: fixtures are recorded only from @XDevelopers, @USDA and
@FAO; the free text of posts and profiles is rewritten by key in the recorder step, before
the fixture is written; counts stay as sent (Recording fixtures below). The terms behind it:
the X Developer Agreement, section III.A (d), forbids distributing or redistributing the
Licensed Material, X Content among it, to any third party except as the Agreement permits
(`docs/upstream/terms/developer-agreement.md`, line 58), and the X Developer Policy's
"Content redistribution" limits what may be given to third parties to Post IDs, Direct
Message IDs and User IDs (`docs/upstream/terms/developer-policy.md`, lines 77 to 87).

### Recording fixtures

`scripts/record_fixture.py` is `/record-fixture` here, run with the key through direnv:
`direnv exec ~/github/sdk uv run scripts/record_fixture.py <wrapper> <case> key=value ...`,
`key=value` the query parameters under the names the wire takes (`user.fields`,
`post.fields`, `expansions`), `id=` filling the path of `get_users_posts`. It records
through the package's client with `RetryPolicy(max_attempts=1)`, so a 5xx spends no second
request, and writes `tests/fixtures/<wrapper>/<case>.json` once, never over an existing
file. Its rules, D1's (Johannes, 2026-10-29), stated in full in its docstring:

- **Three accounts.** It records the four wrappers only, and only for @XDevelopers, @USDA
  and @FAO: `usernames` among the three, `id` one of their ids, `ids` posts of theirs, as
  the recorded fixtures give them, a counts `query` naming one of them with `from:` and no
  other account. `--unknown` admits one other username or id, for an error case, and the
  answer is not written if it finds an account or posts.
- **The rewrite.** On the `Fixture` core's `fixture_from_response` returns, before the one
  write (ADR-0024, decision 4), by key at any depth: every `text` (posts, `note_tweet`,
  `note_post`) becomes `[text rewritten]`, every `description` `[description
  rewritten]`, and in every object with a `username` that is not one of the three (a user,
  a mention) `username`, `name` and `location` become `[username rewritten]`, `[name
  rewritten]` and `[location rewritten]`. Ids, times, metrics, `lang`, booleans, enum
  values and the three accounts' names, handles, locations and URLs stay as sent, and so
  does an answer with nothing to rewrite (counts, errors), byte for byte. It then verifies
  against the unrewritten body in memory that no rewritten value survives anywhere in the
  fixture, refusing the write by the key's path; the unrewritten body is never written.
- **The spend.** It prints its estimate before the request, an upper bound at the prices
  of `pages/pricing.md` (Spend above); `--wrong-key` sends `Bearer not-a-valid-key` for
  the 401, which bills nothing. A recording session counts its calls against the budget
  line of its briefing.

Every fixture carries X's `x-transaction-id` response header, a request id of 16 hex
digits that detect-secrets flags; each has an audited `.secrets.baseline` entry (`is_secret:
false`). Core's scrub writes `next_token=REDACTED` and `pagination_token=REDACTED` in a
recorded URL, since its credential rule takes `token` as a whole word, and `sent_query`
reads them the same way, so a test cannot match on them; the tokens in `meta` stay as sent.

### Live tests (D3)

`.github/workflows/live.yml` runs keyless until gate P's go; after it, the nightly run
spends one billable lookup a night.

### Operator-only files

`.local/` holds what only the operator keeps: the curated account list, the probe cache
and its reports. Nothing under it is committed; the probe PR adds its line to
`.gitignore`.

### Paths, names and errors

The OpenAPI document names `https://api.x.com` as its only server and writes every path
with `/2` (`docs/upstream/openapi/openapi.json`, line 21380); `BASE_URL` already holds
`https://api.x.com/2`, so a wrapper calls `/tweets`, never `/2/tweets`.

Wire names. The document (version 2.173) names the field parameter `post.fields`, the
expansions `most_recent_post_id` and `referenced_posts`, and the fields `post_count`,
`repost_count`, `edit_history_post_ids`, `referenced_posts`, `includes.posts` and
`total_post_count`, where the guides (`pages/fields.md`, `pages/post-counts.md`) write
`tweet.fields`, `referenced_tweets.id`, `tweet_count`, `retweet_count`,
`edit_history_tweet_ids`, `referenced_tweets`, `includes.tweets` and `total_tweet_count`.
The recordings of 2026-10-29 settled it: X takes the document's names (`post.fields`,
`expansions=most_recent_post_id`, `expansions=referenced_posts`, each answered HTTP 200), so
the wrappers send them; and X answers in the document's names when the request carries
`post.fields` and in the guides' when it does not (`get_users_by_usernames/three_accounts`
against `xdevelopers_post_fields`; the post counts, which take no `post.fields`, answer
`tweet_count` and `total_tweet_count`). The models carry the document's names and accept
the guides' spelling through `validation_alias` (`models.py`), so a page reads the same
either way and `dump_upstream` writes the document's names.

Errors come as `application/problem+json` (the `Problem` schema: `type`, `title`,
`detail`; the wrong key's 401 has `type: about:blank` and `status`) or as `{"errors":
[{"code", "message"}]}`, the body the rate-limits page shows for a 429 with `code: 88`
(`pages/rate-limits.md`, lines 412 to 418); a 400 carries both, the problem and an
`errors` list of `message` and `parameters`. The OpenAPI document lists no 429 response and
no `x-rate-limit-*` header: its operations answer 200 or `default`. `classify` maps them
(conventions §5), the problem type read by the last segment of its URI, which the document
writes on `api.x.com` and, for its rule problems, on `api.twitter.com`:

- a `usage-capped` problem at any 4xx: `RateLimitError`, `retry_after` `BILLING_CYCLE`
  (31 days, the longest monthly cycle, since X blocks requests "until the next billing
  cycle" and does not say when it starts);
- a 429 or a `rate-limit-exceeded` problem: `RateLimitError`, `retry_after` the seconds
  until `x-rate-limit-reset` (never negative), else `RATE_LIMIT_WINDOW`, 900 s; core's
  retries wait it out up to `backoff_max`, beyond that the error reaches the caller;
- a 400 or an `invalid-request` problem: `InvalidRequestError` with upstream's words;
- a 404 or a `resource-not-found` problem: `NotFoundError`;
- the rest to core: a 401 or 403 `AuthError`, a 5xx `UpstreamError`, retried.

A 200 is never an error: X answers a username or a post id it does not find with a
`Problem` in `errors` beside the `data` found ("Partial errors",
`pages/response-codes-and-errors.md`), and a user id it does not find with HTTP 200, a
`resource-not-found` problem and no `data` (`get_users_posts/unknown_id`); the wrappers
return these as the page, and whether absence is `NotFoundError` is the task layer's to
decide.
