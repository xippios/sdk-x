# sdk-x — instructions for Claude Code

`xippios-x` wraps X API v2 as a typed Python client, an MCP server
and FastAPI routes, built on `xippios-core`. This file holds what an agent needs to work on
the package: what it wraps, its layout, its commands and its code rules. The documents it
follows, sdk-core's conventions among them, are listed under
[`## Documents` in the README](README.md#documents); read them before you change a file.

## What this package wraps

| | |
| --- | --- |
| Upstream | X API v2, https://x.com |
| API base URL | `https://api.x.com/2` |
| Documentation | https://docs.x.com/x-api/introduction, snapshotted in `docs/upstream/`; an OpenAPI or Swagger document a page names is kept beside it, its URL in `SPEC_URL` of `scripts/refresh_upstream.py` (`/refresh-upstream`) |
| Credentials | `X_API_KEY` from the environment, sent as `Authorization: Bearer`: the app's Bearer Token, which X calls the App only Access Token (`docs/upstream/pages/application-only.md`), not the console's "API Key", the OAuth 1.0a consumer key |
| Rate limit | 60 requests per minute, burst 1; a self-imposed pace (sdk-core ADR-0033 decision 1), enforced client-side in `_client.py`. X documents no per-minute limit but per-endpoint windows of 15 minutes, per app with a Bearer Token (`docs/upstream/pages/rate-limits.md`): 300 on `GET /2/users/by` and on both counts endpoints, 3,500 on `GET /2/tweets`, 10,000 on `GET /2/users/:id/tweets`, 450 on `GET /2/tweets/search/recent`, 900 on `GET /2/lists/:id/tweets` and on `GET /2/lists/:id/members`, 50 on `GET /2/usage/tweets`; a 1/sec limit only on `GET /2/tweets/search/all` and `GET /2/spaces/by/creator_ids`, which this package does not wrap. The windows are never rationed ahead by the limiter; a spent one is answered at its 429, in `_client.py`'s `classify` alone: a `RateLimitError` whose `retry_after` comes from `x-rate-limit-reset`, a Unix timestamp, with the 15-minute window as the fallback. No `QuotaPolicy`: one policy per client cannot track windows per endpoint (https://github.com/xippios/sdk-x/pull/3; sdk-core ADR-0033 decisions 2 and 3). Observed on 2026-10-29: `x-rate-limit-limit: 2000` on `GET /2/users/by` against the page's 300, and 3,500, 10,000, 300, 450, 300, 900, 900 and 50 on the other eight wrapped operations as the page lists; the headers are the authority, the page's table the documented floor. `classify`'s whole mapping: Paths, names and errors below |
| Write tools | no, this package is read-only |

The snapshot listed in `docs/upstream/FETCHED.md` is the reference for names, parameters and
semantics; a wrapper is never written from memory of the API.

Release 0.2.0 ships under sdk-core ADR-0027, X as a metered, content-bearing source
(`docs/adr/0027-x-metered-content-source.md` in sdk-core), and conventions 1.28.

## Layout

```
src/xippios/x/
  __init__.py      public surface: __version__ and re-exported task functions
  py.typed         PEP 561 marker; consumers' mypy --strict needs it
  _version.py      __version__ from distribution metadata
  _client.py       the one configured AsyncClient (base URL, key, rate limit), ENV_VARS, the
                   cursors declared data, and classify, upstream's documented error shapes
  errors.py        the package's own error classes, where conventions §5 calls for one
  models.py        pydantic models mirroring upstream payloads (UpstreamModel); by the
                   family's precedent also an enumeration written by hand, for a value set
                   upstream documents and no packaged list renders: the OpenAPI
                   document's User, Post, Expansions, Problem, Usage, the nine responses,
                   and its enums (UserField, PostField, UserExpansion, PostExpansion,
                   UsageField, Granularity, SortOrder)
  api/             endpoint wrappers, one module per upstream operation (conventions §2):
                   get_users_by_usernames, get_posts_by_ids, get_users_posts,
                   get_posts_counts_all, search_posts_recent, get_posts_counts_recent,
                   get_lists_posts, get_lists_members, get_usage; _query.py turns
                   parameters into the text X takes and refuses values outside the bounds
  tasks.py         the seven task functions (The task layer below); __all__ is what the
                   adapters register, but BULK_TASKS (none), the Python-only ones; MCP_CAPS the
                   per-tool result caps that hold a whole page
  mcp.py           xippios-x-mcp entry point: build() the tool set, server
  http.py          FastAPI router
scripts/
  refresh_upstream.py    captures docs/upstream/ and writes FETCHED.md (/refresh-upstream): the
                         OpenAPI document, the docs.x.com pages in their Markdown form and
                         the X Developer Agreement and Policy
  adr_index.py           writes docs/adr.md and docs/adr.json from the records in docs/adr/;
                         --check fails while either is stale
  record_fixture.py      records one exchange of the nine wrappers, X Content rewritten;
                         Recording fixtures below
  probe_accounts.py      the account probe and its report (The probe below)
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
  test_probe_accounts.py  the probe replayed over the recorded fixtures, its estimate, cap,
                   waits, metrics and decision
  test_tasks.py    per-task replay tests through the sync facades, the MCP server through
                   core's in-process client, the HTTP router, the live tests' nightly rule
  test_contract.py the package contract, build() and ENV_VARS, and what the adapters and
                   the entry point answer a caller: refusals, error flags, problem details
  test_refresh_upstream.py  FETCHED.md as the capture script renders it, offline
  test_live.py     @pytest.mark.live smoke tests, one per task (Live tests below)
docs/
  upstream/        documentation snapshot and FETCHED.md
  adr/             this package's design decisions, one NNNN-<slug>.md record each, laid
                   out in its README.md
  adr.md           the index of the decisions, written by scripts/adr_index.py, never by hand
  adr.json         the same index, for machines
  reports/         dated reports, the evidence a decision cites, laid out in its README.md
changelog/         the next release's changelog entries, one fragment per change, laid out
                   in its README.md
CHANGELOG.md       the releases, each section assembled from the fragments
.github/workflows/ ci.yml (the required ci check, with the changelog and fixture-size steps),
                   publish.yml (the release train: tag, build, PyPI), live.yml (nightly live
                   tests), organization.yml (the organization's checks from xippios/.github:
                   conventions, a review of a pull request against the documents the README
                   lists, and adr-index, which runs scripts/adr_index.py --check)
.claude/commands/  add-endpoint, record-fixture, refresh-upstream, release-prep
```

The import path is `xippios.x` (sdk-core ADR-0006); `src/xippios/` is a
namespace package.
Where the API's operation ids repeat across its services, `api/` keeps one module per service
instead, named after the service, and this Layout says so (conventions §2).

## Commands

```bash
uv sync --all-extras
uv run pytest                      # offline, replays the fixtures
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pre-commit run --all-files
python3 scripts/adr_index.py --check   # the index matches the records in docs/adr/
uv run pytest -m live --tb=short --assert=plain   # needs XIPPIOS_LIVE_TESTS=1, X_API_KEY

uv run xippios-x-mcp   # stdio; add --http for streamable HTTP
```

`uv run pytest` is offline: core's plugin refuses the network and skips the rate limiter's
waits in every test not marked `live` (conventions §10, sdk-core ADR-0035). A test that
asserts a limiter wait or a quota pause is marked `rate_limited`, one that must reach the
network `network`.
It sends the key's placeholder, with `X_API_KEY` set to it because
`pyproject.toml` names that variable under `xippios_placeholder_key_envs`; the package
keeps no placeholder fixture of its own.

`.github/workflows/live.yml` runs the live tests nightly at 01:24 UTC, a time derived from
the slug so that sources sharing a key never start together, and on demand; a pull request never runs them.
Only its `uv run pytest -m live --tb=short --assert=plain` step sees the key, from the org secret `X_API_KEY`,
which the organization shares with this repository; the nightly run spends one billable
call (Live tests below).
Every live run takes `--tb=short --assert=plain`, since the log of `live.yml` is public:
the first keeps a failing test's frame arguments out of it, a raw upstream payload among
them, and the second the values a failed `assert` compares. A live test asserts on shapes
and counts, never on a raw payload.

## Code rules

- Three layers (sdk-core ADR-0001, conventions §2): endpoint wrappers in `api/`, task
  functions in `tasks.py`, adapters in `mcp.py` and `http.py`. The adapters register
  `tasks.__all__` and call only tasks, the tasks call only wrappers and reference data, and
  a wrapper returns models.
- Upstream's documented error shapes go into `classify` in `_client.py`, once, and an error
  class of the package's own into `errors.py`; a wrapper never inspects a status code
  (conventions §5, §6).
- One limiter paces each host the package sends to (conventions §2, §6). A second base URL
  on the host of the API base URL goes through the one `client` of `_client.py` by its
  absolute URL, and `classify`'s path checks name both bases. An origin or mirror that the
  publisher runs itself, where its canonical host refuses automated requests, takes that
  host's pace through the same client, and `docs/upstream/` names both hosts; a mirror that
  anyone else runs is never sent to. A host that a dependency sends to is reached through
  the dependency's tasks alone. Any other host gets a client of its own in `_client.py`,
  its base URL and its `RateLimit` beside the first's, and a row of its own in the table
  under What this package wraps, with its pace and where the pace comes from. The package
  sends to `api.x.com` alone.
- A change brings its tests, written before the code, and passes the offline checks above;
  its changelog entry is a fragment under `changelog/`, one file holding its bullet, as
  `changelog/README.md` lays it out (conventions §12). Commit subjects follow Conventional
  Commits (conventions §13): the rule binds a pull request's own commits, not the commit
  that lands the pull request on `main`, whose subject GitHub writes.
- `ruff` leaves `docs/` and `.claude/` alone (`pyproject.toml`), so the upstream snapshot
  keeps its bytes: never reformat it.
- A convention that seems wrong is followed anyway and said in the pull request; changing
  it is a change of sdk-core's `docs/conventions.md` with an ADR.

## Never

- Never hand-write a fixture, and never commit one without grepping it for key patterns
  (conventions §10).
- Never read or print `.envrc`, `.env`, the credential variable of this package,
  `X_API_KEY`, or any variable ending in `_API_KEY`, `_TOKEN` or
  `_SECRET`.
- Never write a key, a token or another credential into a file or a commit.
- Never put logic in `mcp.py` or `http.py`, and never add a route or a tool by hand: the
  adapters register `tasks.__all__` (sdk-core ADR-0001).
- Never rename or re-map an upstream concept to another source's (sdk-core ADR-0028).
- Never return a documented personal identifier in a task's projection, echo one in
  `meta.request`, or commit one in a fixture (sdk-core ADR-0017).
- Never edit `docs/upstream/` by hand but `docs/upstream/OBSERVED.md`, the notes on what
  upstream does but never documents: `/refresh-upstream` fetches the rest, and the pull
  request shows its diff (conventions §3).
- Never add `src/xippios/__init__.py`, nor an `__init__.py` at a level between it and the
  package (sdk-core ADR-0006).
- Never push a tag by hand: a release's tag comes from `publish.yml` alone (conventions §12).

## Template updates

This repository is generated from sdk-template, at the tag `.copier-answers.yml` records. A
template release reaches it in a pull request of its own, with
`uvx --from 'copier>=9.19' copier update --defaults --vcs-ref=<tag>` (conventions §15): the
update renders the template's files again and never overwrites the files this package
fills, `__init__.py`, `_client.py`, `errors.py`, `models.py`, `api/`, `parse/`, `tasks.py`,
`tasks_write.py`, `scripts/refresh_upstream.py`, `tests/test_tasks.py`, `tests/test_live.py`,
`tests/fixtures/`, `docs/upstream/`, `docs/adr.md`, `docs/adr.json`, `README.md`,
`CHANGELOG.md` and `CLAUDE.md`. sdk-template's
[CHANGELOG](https://github.com/xippios/sdk-template/blob/main/CHANGELOG.md) says, per
release, what to port into those by hand in the same pull request.

## When something is unclear

Prefer the smallest change that satisfies the documents the README lists, state the
assumption in the pull request's description, and stop rather than guess at upstream
semantics or the shape of the public API.

## X API v2 specifics

### Spend

Successful responses that return data spend the app's prepaid credits; failed requests
are not billed (`pages/usage-and-billing.md`). The prices are those of
`docs/upstream/pages/pricing.md` (snapshot of 2026-10-29): reads per resource returned,
0.005 USD a post and 0.010 USD a user; post counts per request, 0.005 USD on
`GET /2/tweets/counts/recent` and 0.010 USD on `GET /2/tweets/counts/all`. The page lists
List: Read at 0.005 USD a resource and does not say under which resource a List's posts
(`GET /2/lists/{id}/tweets`) and members (`GET /2/lists/{id}/members`) are billed; the
recorder estimates them as posts and users, the upper bound. A resource
read again within the same UTC day is deduplicated (a soft guarantee, the page says); a
counts request is not, being billed per request. Owned Reads, 0.001 USD a resource, apply
only where `{id}` is the authenticated user who owns the app, and an app-only Bearer
Token has no authenticated user. The pricing page states no price for
`GET /2/usage/tweets`. Pay-per-usage plans are capped at 3 million post reads per billing
cycle, and the Developer Console's spending limit per billing cycle is the hard stop: once
it is reached, X blocks every request until the next cycle. A fixture recording and a live
run spend credits too, so a script that spends prints its estimate before its first
request.

### Fixtures and X content

Fixtures are recorded only from @XDevelopers, @USDA and @FAO, and the recorder rewrites
`text`, `description`, and the `name`, `username` and `location` of every user other than
the recorded accounts, by key on the `Fixture` before the write (sdk-core ADR-0042
decision 4); counts stay as sent (https://github.com/xippios/sdk-x/pull/1, as
https://github.com/xippios/sdk-x/pull/4 confirmed it).

The terms behind it are the X Developer Agreement's definitions, in
`docs/upstream/terms/developer-agreement.md`:

> 4. “**Licensed Material**” means, individually or collectively, the X API and X
> Content. (I.4, line 24)
>
> 10. “**X API**” means X Application Programming Interfaces (each, an **“API”**),
> Software Development Kits (each, an **“SDK”**), and the related tools, documentation,
> data, technology, code, and other materials provided by X through the Developer Site.
> (I.10, line 30)
>
> 12. “**X Content**” means Posts, the unique identification number generated for each
> Post, X end user profile information, and any other data and information made
> available to you through the X API or by any other means authorized by X, and any
> copies and derivative works thereof. (I.12, line 32)

and its section III.A (d), by which you shall not "sell, rent, lease, sublicense,
distribute, redistribute, syndicate, create derivative works of, assign, or otherwise
transfer or provide access to, in whole or in part, the Licensed Material to any third
party except as expressly permitted in this Agreement" (line 58). The X Developer
Policy's "Content redistribution" lets X Content reach third parties only as Post IDs,
Direct Message IDs and User IDs, "except as described below": up to 500 public Post or
User objects a day to each person who uses the service, by non-automated means, and no
more than 1,500,000 Post IDs to any entity within 30 days without X's written permission
(`docs/upstream/terms/developer-policy.md`, lines 79 to 81).

By I.10 the documentation is X API, and so Licensed Material, too. The snapshot under
`docs/upstream/` is kept under sdk-core ADR-0028, decision 4, as
https://github.com/xippios/sdk-x/pull/2 decided: reproduced for reference with its
attribution and URLs in `FETCHED.md`; should X object, a PR replaces it with a summary
that keeps the names and semantics the wrappers rely on.

### Recording fixtures

`scripts/record_fixture.py` is `/record-fixture` here, run from the clone or a worktree
with the key through direnv, `direnv exec . uv run scripts/record_fixture.py <wrapper> <case> key=value ...`,
`key=value` the query parameters under the names the wire takes (`user.fields`,
`post.fields`, `expansions`), `id=` filling the path of `get_users_posts`,
`get_lists_posts` and `get_lists_members`. It records
through the package's client with `RetryPolicy(max_attempts=1)`, so a 5xx spends no second
request, and writes `tests/fixtures/<wrapper>/<case>.json` once, with core's
`write_fixture`, never over an existing file. How it holds to the rule above, in full in its docstring:

- **The accounts.** It records the nine wrappers only. Its guard covers what a request
  names, its usernames, ids and query, and refuses before the request one that names an
  account other than the three: `usernames` among them, `id` one of their ids, `ids` posts
  of theirs, as the recorded fixtures give them, a counts `query` (all or recent) naming
  one of them with `from:` and no other account. A search returns the posts its query
  matches, so the guard of `search_posts_recent` admits `from:<one of the three>` alone or
  followed by `-is:retweet`, `-is:reply` or both, operators in lower case, and nothing
  else (no `OR`, keyword or other operator); it reads parentheses as spaces, since these
  terms joined by AND only narrow `from:`, and an unbalanced one is X's 400 case. It admits
  one more query, `conversation_id:<id>` alone, the id a post of the three as the recorded
  fixtures give them (as for `ids`): the conversation a post of theirs started, whose
  replies, other accounts' among them, are recorded as the List's are (The List and the
  conversation below). A List `id` is one of `LISTS`, Lists owned by one of the three.
  `--unknown` admits one other username, user id or List id, for an error case, and the
  answer is not written if it finds an account, posts or members. `get_usage` has no
  guard: its answer holds the project's usage numbers and ids, no X Content.
- **The expansions and fields.** An expansion brings other objects into an answer, and a
  field can carry values that describe other accounts. So the recorder refuses before the
  request every `expansions`, `user.fields` and `post.fields` value outside its
  `ADMITTED`: the one expansion `most_recent_post_id`, which brings a post of the requested
  user and no user object (`referenced_posts`, which brings the posts a post reposts, quotes
  or replies to, whoever wrote them, is refused since
  https://github.com/xippios/sdk-x/pull/4); the tasks' user fields (`USER_FIELDS`) with `id`,
  `name`, `username` and `verified`, `url` among them, admitted for the requested users, the
  only users an answer holds except in `get_lists_members`' answer, whose users are the
  List's members, other accounts, whose `url` the rewrite does not cover, so that wrapper
  refuses `url` (`NOT_ADMITTED_FOR`); the tasks' post fields (`POST_FIELDS`) with `id` and
  `text`. The refusals exclude the values that describe other accounts and that the rewrite
  does not cover (`profile_image_url`, `entities`, whose URL entities' `title`,
  `expanded_url` and `display_url` can carry a handle, `withheld`, the pinned post ids),
  until the rewrite covers them. `get_posts_by_ids/most_recent_three` was re-recorded without
  `referenced_posts` on 2026-10-29, and no fixture carries another account's object but the
  two List fixtures and the conversation fixture (The List and the conversation below).
- **The rewrite**, the rule's, by key at any depth: every `text` (posts, `note_tweet`,
  `note_post`) becomes `[text rewritten]`, every `description` `[description rewritten]`,
  and in every object with a `username` that is not one of the three (a person, a
  mention) `username`, `name` and `location` become `[username rewritten]`, `[name
  rewritten]` and `[location rewritten]`. Ids, times, metrics, `lang`, booleans, enum
  values and the three accounts' names, handles, locations and URLs stay as sent, and so
  does an answer with nothing to rewrite (counts, errors), byte for byte. It then verifies
  against the unrewritten body in memory that no rewritten value survives anywhere in the
  fixture, refusing the write by the key's path; the unrewritten body is never written.
- **The spend.** It prints its estimate before the request, an upper bound at the prices
  of `pages/pricing.md` (Spend above), and for `get_usage`, which the page gives no price,
  says so; `--wrong-key` sends `Bearer not-a-valid-key` for the 401, which bills
  nothing.

The List and the conversation. The List fixtures come from one List owned by @XDevelopers, id
`715919216927322112` (`LISTS` in the recorder), whose name suggested institutional
accounts; of its eight members, four have `verified_type: government` and four
`verified_type: none` at recording. It was found on 2026-10-29 with one
`GET /2/users/2244994945/owned_lists?max_results=5&list.fields=name,member_count,private`,
@XDevelopers being the first of the three accounts read, which returned three public Lists;
`owned_lists` is not wrapped, and that answer is not kept. A List's members and posts are
other accounts' objects by nature: `get_lists_members/xdevelopers_list_ten` stays as
recorded within the rule above (an institutional List, every free text rewritten, ids,
creation dates and public metrics as sent), and so does `get_lists_posts/xdevelopers_list_ten`
(https://github.com/xippios/sdk-x/pull/7). A conversation is read the same way
(https://github.com/xippios/sdk-x/pull/8): `search_posts_recent/
usda_conversation` is the recent search `conversation_id:2115806101480337475`, @USDA's most
recent post at recording, ten posts, nine replies and the post itself,
every `text` rewritten, ids, times and public metrics as sent; no user object, since the
recorder admits no `author_id` expansion.

Every fixture recorded so far carries X's `x-transaction-id` response header, a request id
of 16 hex digits. detect-secrets flags it in every fixture but
`search_posts_recent/unbalanced_parenthesis` and `get_usage/seven_days`, whose ids'
entropies, exactly 3.0 and 2.98, do not pass the detector's limit; each flagged one has an
audited `.secrets.baseline` entry (`is_secret:
false`). Core's recorder drops the headers that only identify a request, so a
fixture recorded now carries none and adds no audited entry for it. X's cursors,
`next_token` and `pagination_token`, are data: `_client.py` declares them with core's
`register_data_name`, so a recorded URL, `sent_query` and a task's `meta.request` keep
them as sent, where core's credential rule, which takes `token` as a whole word, wrote
them `REDACTED`. The two page-2 fixtures, `search_posts_recent/usda_ten_page_2` and
`get_posts_counts_all/usda_by_day_page_2`, were recorded before, their URL reading
`next_token=REDACTED`, so a test compares the rest of their query with them and the token
with the one it sent, until a recording writes them again.

### The task layer

Seven tasks in `tasks.py`, `__all__` in this order (https://github.com/xippios/sdk-x/pull/8), each
one call of one wrapper returning X's page as sent in `Result.data`, the wrapper's
response model: nothing ranked, stored, projected or collected across pages. The nouns are
the OpenAPI document's (posts, users, Lists), never "tweet" or "account".

| Task | Wrapper | Spend per call at the snapshot's prices |
| --- | --- | --- |
| `lookup_users(usernames, most_recent_post=False)` | `get_users_by_usernames` | 0.010 USD a user found, up to 100 (1.00 USD); 0.005 USD more a user with `most_recent_post`, off by default (up to 1.50 USD) |
| `get_user_posts(id, max_results=10, pagination_token, start_time, end_time)` | `get_users_posts` | 0.005 USD a post, 5 to 100 (0.50 USD) |
| `search_recent_posts(query, max_results=10, next_token, start_time, end_time)` | `search_posts_recent` | 0.005 USD a post, 10 to 100 (0.50 USD) |
| `count_posts(query, granularity="hour", start_time, end_time, next_token)` | `get_posts_counts_all` | 0.010 USD a request, one page of up to 31 days |
| `get_list_posts(id, max_results=10, pagination_token)` | `get_lists_posts` | 0.005 USD a post, 1 to 100 (0.50 USD), counted as posts |
| `get_conversation_posts(conversation_id, max_results=10, next_token)` | `search_posts_recent` with `conversation_id:<id>` | 0.005 USD a post, 10 to 100 (0.50 USD) |
| `get_usage(days=7)` | `get_usage` | no price on the page |

The rules they share, stated in the module docstring too:

- **Fields.** Fixed: the account probe's user fields (`USER_FIELDS`) and post fields
  (`POST_FIELDS`), the sets the fixtures were recorded with, and every usage field; no
  expansion but `most_recent_post_id` behind `lookup_users`' `most_recent_post`, which
  sends the post fields with it (https://github.com/xippios/sdk-x/pull/8).
- **Counts.** One task on the full archive, `GET /2/tweets/counts/all`
  (https://github.com/xippios/sdk-x/pull/8: one counts task on the general endpoint,
  explicit names over switches); the recent counts stay a wrapper. Every granularity X takes is
  served, minutes included, and the default is upstream's, `hour` (sdk-core ADR-0028).
  Without `start_time` upstream chooses the range; the recordings all give one.
- **Queries.** `search_recent_posts` refuses a query over 512 characters before the call
  ("512 query length", `pages/rate-limits.md`), `count_posts` one over 1,024 ("1,024-character
  query length (4,096 for Enterprise)", `pages/post-counts.md`; https://github.com/xippios/sdk-x/pull/8); the
  OpenAPI document's 4,096 is Enterprise's, and the wrappers keep it. `get_conversation_posts` builds
  `conversation_id:<id>` and checks the id against the document's post id pattern.
- **Paging.** The caller's: the token parameter the operation names, given the `next_token`
  of the previous page's `meta` (`result.data.meta.next_token`).
- **Absence.** A page without `data` whose every problem is `resource-not-found` (a user id
  or a List id X does not find, no username of a lookup found) raises `NotFoundError` with
  X's words (https://github.com/xippios/sdk-x/pull/8); a partial answer is returned as the page, its problems in
  `errors`; an empty search is an empty page.
- **`meta`.** `source` the slug `x` (conventions §4), `endpoint` the operation id, `retrieved_at` the time
  the answer arrived (no cache), `request` the parameters sent under the names X takes, a
  paging token as sent, since `_client.py` declares the cursors data, `total` `None` (X
  counts only the page's items, `result_count`; sdk-core ADR-0034), `vintage` `None` (X
  has no release identifier).
- **`published_at`.** `None` for every task: X states no release time for a page, each
  post carries its own `created_at`, and a newest time the package computes across records
  is no release time (sdk-core ADR-0041, decision 1; conventions §4;
  https://github.com/xippios/sdk-x/pull/8).
- **MCP caps.** A result is one page, a model whose list, its posts, users or buckets, is
  its rows: within its byte bound it returns whole, however many rows it holds, and past
  it its rows are cut, to the row and the byte bound (`max_rows` stays 200), with the
  note, its other fields whole, `includes` among them, and its `next_token` too, which
  leads past the rows the cut left out, so asking again for fewer shows them (sdk-core
  ADR-0038, decision 4). Two pages are not cut so and come back as the note and a preview
  that loses the `next_token`: a page that carries `errors` beside `data`, two lists, a
  lookup with a username X does not find among them, and a lookup whose `includes` alone
  pass the bound (https://github.com/xippios/sdk-x/issues/35). `MCP_CAPS` sets the bytes
  so a page of 100 fits as core serialises it (compact JSON, `None` fields included;
  sdk-core ADR-0038 decisions 2 and 4; https://github.com/xippios/sdk-x/pull/8), measured on the fixtures: a post
  is about 960 bytes besides its `text` of at most 280 characters, a user about 800
  besides its free texts (160, 50 and 30 characters at most), a count bucket 77, the
  envelope about 600. The post tools take 128,000 bytes (100 x (960 + 280) + 600 =
  124,600), `lookup_users` 160,000 (100 users with the longest texts 104,600, room for
  non-ASCII text; with `most_recent_post` about 70 users and their posts fit),
  `count_posts` keeps 64 KB (744 hour buckets take 58,432; minutes pass it beyond about 14
  hours, about 840 buckets, and a cut keeps 200) and `get_usage` has no entry. The
  whole-page arithmetic holds for Latin-script text, about one byte a character; a page of
  mostly non-Latin text (CJK, Arabic, emoji) takes up to four bytes a character and can
  still be cut, with the note. Each note names the tool's own parameters.

### Live tests

`tests/test_live.py` has one smoke test per task and the rendered `test_upstream_answers`. The
nightly run of `.github/workflows/live.yml` (`GITHUB_EVENT_NAME` `schedule`) spends one billable
call, `test_lookup_users`' lookup of @XDevelopers, about 0.010 USD a night
(https://github.com/xippios/sdk-x/pull/1); the six others call `not_in_the_nightly_run()` first,
which skips them there, and run on `workflow_dispatch` and locally, about 0.14 USD together at
most (https://github.com/xippios/sdk-x/pull/8). They assert shapes and counts, never a payload.

### The probe

`scripts/probe_accounts.py` measures whether the curated accounts still post and reports go,
US-only or no-go by the thresholds of https://github.com/xippios/sdk-x/pull/1, named constants
in it. It prints its estimate first and calls nothing (`uv run scripts/probe_accounts.py`: N,
the call plan and its formula at the snapshot's prices, 9.375 USD at N=75, the whole estimate,
since its ten-post samples ask for no expansion), and the cap to pass: the formula and 0.005 USD
an account for the fallback lookups, 9.750 USD at N=75. The requests' upper bounds add up
to no more, so a cap at that figure never stops a run before its report. It spends only
with `--spend --spend-cap USD`, from the clone or a worktree with the key through direnv
(`direnv exec . uv run scripts/probe_accounts.py --spend --spend-cap 9.75`),
refuses when the estimate exceeds the cap and stops before a request that could pass it.
It reads `.local/x-accounts.yaml` (`--accounts`), keeps every page under
`.local/cache/<date>/`, so a stopped or repeated run the same UTC day pays only for what it
has not fetched, adds each run's requests and actual spend to that day's
`.local/cache/<date>/spend.json`, and writes `.local/probe-<date>.csv` and
`.local/probe-<date>.md`, whose Spend section gives the run's spend and the day's. The
list is a bare YAML list of records or a mapping whose one key `accounts:` holds it, and a
`why` or `name` with a comma is quoted, since in a one-line record, a flow mapping, an
unquoted comma starts a field of its own.
`GET /2/tweets/counts/all` allows 300 requests per 15 minutes and a run makes 6N: on X's
429 the probe prints the wait, sleeps it, 15 minutes at most, and resumes. Only aggregates
leave `.local/`: counts and the decision line, never a handle or a post's text. The wait
and stop lines quote `classify`'s method and path, which can carry a user id
(`GET /2/users/<id>/tweets`), so they are never pasted into a public record verbatim.

### Operator-only files

`.local/` holds what only the operator keeps: the curated account list, the probe cache
and its reports. Nothing under it is committed; `.gitignore` carries its line.

### Paths, names and errors

The OpenAPI document names `https://api.x.com` as its only server and writes every path
with `/2` (`docs/upstream/openapi/openapi.json`, line 21452); `BASE_URL` already holds
`https://api.x.com/2`, so a wrapper calls `/tweets`, never `/2/tweets`. The document
(version 2.173) names the field parameter `post.fields` and the field `referenced_posts`
where the guides (`pages/fields.md`) write `tweet.fields` and `referenced_tweets`, and has
`most_recent_post_id` as a users expansion, where only its streams list `most_recent_tweet_id` as a
`user.fields` value; the recordings of 2026-10-29 settled which the API takes (Wire names
below). Errors come as `application/problem+json` (the `Problem` schema; a keyless request
on 2026-10-29 was answered 401 with `title`, `type`, `status` and `detail`) or as
`{"errors": [{"code", "message"}]}`, the body the rate-limits page shows for a 429 with
`code: 88` (`pages/rate-limits.md`, lines 412 to 418). The OpenAPI document lists no 429
response and no `x-rate-limit-*` header: its read operations answer 200 or `default`.

Wire names, settled by the recordings of 2026-10-29: X takes the document's names
(`post.fields`, `expansions=most_recent_post_id`, `expansions=referenced_posts`, each
answered HTTP 200, the last in the first recording of `get_posts_by_ids/most_recent_three`,
replaced the same day without it), so the wrappers send them. It answers in the document's
names when the request carries `post.fields` (`most_recent_post_id`, `post_count` among a
user's metrics, `includes.posts`, `edit_history_post_ids`, `repost_count`, and
`referenced_posts` in that first recording) and in the guides' when it does not
(`most_recent_tweet_id`, `tweet_count`, `includes.tweets`, `edit_history_tweet_ids`;
`get_users_by_usernames/three_accounts` against `xdevelopers_post_fields`); the post
counts, which take no `post.fields`, answer `tweet_count` and `total_tweet_count`
(`pages/post-counts.md`) where the document has `post_count` and `total_post_count`. The
models carry the document's names and accept the guides' spelling through
`validation_alias` (`models.py`), so a page reads the same either way and `dump_upstream`
writes the document's names.

Query operators. The OpenAPI document describes the `query` parameter of the searches and
the counts and the `conversation_id` field of a post, not the operators a query is made
of; `pages/search-operators.md` (snapshot of 2026-10-30) lists them. The queries this
package builds or admits use four: `from:` (line 44, "Matches Posts from a specific
user"), `conversation_id:` (line 64, "Matches Posts in a conversation thread"),
`is:retweet` and `is:reply` (lines 101 and 102, "Conjunction required", negated with `-`,
line 155): `get_conversation_posts`' query, the recorder's guard and the probe's counts
queries (`from:<handle>` alone or with `-is:retweet -is:reply`).

The recorded refusals add to the shapes above: the wrong key's 401 has `type:
about:blank` and `status`, and a 400 carries both shapes, the problem and an `errors` list
of `message` and `parameters`. `classify` maps them (conventions §5), the problem type read
by the last segment of its URI, which the document writes on `api.x.com` and, for its rule
problems, on `api.twitter.com`:

- a `usage-capped` problem at any 4xx: `RateLimitError`, `retry_after` `BILLING_CYCLE`, 31
  days, the upper bound of a monthly billing cycle, since X blocks requests "until the next
  billing cycle" and its answer does not say when that is (the documented fallback of
  sdk-core ADR-0033 decision 3); `GET /2/usage/tweets` returns the exact day,
  `cap_reset_day` (29 when read on 2026-10-29);
- a 429 or a `rate-limit-exceeded` problem: `RateLimitError`, `retry_after` the seconds
  until `x-rate-limit-reset` (never negative), else `RATE_LIMIT_WINDOW`, 900 s; core's
  retries wait it out up to `backoff_max`, beyond that the error reaches the caller;
- a 400 or an `invalid-request` problem: `InvalidRequestError` with upstream's words;
- a 404 or a `resource-not-found` problem: `NotFoundError`;
- the rest to core: a 401 or 403 `AuthError`, a 5xx `UpstreamError`, retried.

A 200 is never an error: X answers a username or a post id it does not find with a
`Problem` in `errors` beside the `data` found ("Partial errors",
`pages/response-codes-and-errors.md`), and a user id or a List id it does not find with
HTTP 200, a `resource-not-found` problem and no `data` (`get_users_posts/unknown_id`,
`get_lists_posts/unknown_id`). The wrappers
return these as the page, faithful to the answer (sdk-core ADR-0028); a task raises
`NotFoundError` when `data` is absent and every problem is `resource-not-found` (The task
layer above). A query X cannot parse is a 400 with its parser's words
(`search_posts_recent/unbalanced_parenthesis`). Recent search, unlike `getUsersPosts`,
returns an edited post's earlier versions as posts of their own, each with the whole
`edit_history_post_ids` (`search_posts_recent/usda_ten`); the wrapper returns them as sent.
