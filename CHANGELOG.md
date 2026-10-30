# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: breaking changes bump the minor).

## [Unreleased]

## [0.1.0] - 2026-10-30

First release, on xippios-core 0.3.0 from PyPI (`~=0.3.0`), sdk-template v0.3.0 and
conventions 1.24, under ADR-0027, which sets the rules for X, the family's first
upstream that bills in money rather than by quota. It reads X API v2 with the app's
Bearer Token and posts nothing: seven read tasks, `lookup_users`, `get_user_posts`,
`search_recent_posts`, `count_posts`, `get_list_posts`, `get_conversation_posts` and
`get_usage`, each one request returning one page as X sends it, served as MCP tools and
HTTP routes over nine endpoint wrappers. Each call that returns data spends X credits at
the prices of X's pricing page, which each task's docstring names (the page states none
for `get_usage`), and the spending limit set in X's Developer Console is the hard stop:
a post task reads at most 100 posts a call, 0.50 USD, `lookup_users` at most 100 users,
1.00 USD (1.50 USD with their most recent posts), a count costs 0.010 USD a request, and
the nightly live run spends one lookup, about 0.010 USD. Posting and reads in a user's
context are not part of it. Nothing was published before, so the entries under Changed
record steps on the way to this release.

### Added

- Scaffold from [sdk-template](https://github.com/xippios/sdk-template): configured
  client for X API v2, empty task layer, MCP server and FastAPI router
  wired to it, test harness with core's family check, CI, the nightly live tests and
  the release train, in which a release PR's merge tags and publishes.
- The upstream documentation snapshot in `docs/upstream/`, fetched 2026-10-29: X API v2's
  OpenAPI document (version 2.173), the docs.x.com pages on pricing, usage and billing,
  the usage endpoint, rate limits, response codes and errors, fields, pagination, post
  counts and app-only Bearer Token authentication, and the X Developer Agreement and
  Developer Policy, each kept as served, refreshed on 2026-10-30 with the search
  operators page, which documents the query operators the tasks use;
  `scripts/refresh_upstream.py` reproduces it and regenerates `FETCHED.md`.
- The four read wrappers the account probe needs, one page each as the OpenAPI
  document's response model (`data`, `includes`, `errors`, `meta`):
  `api.get_users_by_usernames`, `api.get_posts_by_ids`, `api.get_users_posts` and
  `api.get_posts_counts_all`. Their parameters carry the document's names, which X takes
  (`post.fields`, `expansions=most_recent_post_id`, `referenced_posts`), and values outside
  the document's bounds are refused before the call. The models read both spellings X
  answers in, the document's and the guides' (`most_recent_tweet_id`, `tweet_count`,
  `includes.tweets`).
- `classify` maps X's answers to the error taxonomy: a 429 to `RateLimitError` with the
  wait until `x-rate-limit-reset` (15 minutes when it is missing), a usage cap to
  `RateLimitError` until the next billing cycle, a 400 to `InvalidRequestError`, a 404 to
  `NotFoundError`. A 200 that carries errors is returned as the page.
- `scripts/record_fixture.py`, the fixture recorder: it records from @XDevelopers, @USDA
  and @FAO only, prints its spend estimate first, and rewrites `text`, `description`, and
  the `name`, `username` and `location` of every user other than those three accounts
  before the fixture is written, counts as sent, within what the X Developer Agreement
  allows of content given to third parties; the recorded fixtures of the four wrappers.
- Four more read wrappers, one page each as the OpenAPI document's response model:
  `api.search_posts_recent` (recent search, with `SortOrder`), `api.get_posts_counts_recent`
  (post counts over the last seven days), `api.get_lists_posts` (the posts of a List's
  members) and `api.get_lists_members`, under the document's parameter names, values
  outside its bounds and two parameters of which it allows one refused before the call.
  Their fixtures are recorded from @USDA's posts and from a List @XDevelopers owns, the
  members' names, handles, locations and bios rewritten.
- `scripts/record_fixture.py` records the four new wrappers: a recent search only for
  `from:` one of @XDevelopers, @USDA and @FAO, alone or without reposts and replies, since
  a search returns the posts it matches; a List only when one of the three owns it; a
  List's members without their profile URL, which the rewrite does not cover.
- `scripts/probe_accounts.py`, the account probe: it reads the operator's account list,
  prints its spend estimate and call plan without a request, and only with `--spend
  --spend-cap` looks the accounts up, counts their posts and original posts by day over
  90 days and samples ten posts each, waiting out X's rate-limit windows and keeping every
  page in a same-day cache with a ledger of the day's spend; it writes a CSV and a
  Markdown report with the go, US-only or no-go decision under `.local/`, which git now
  ignores.
- The task layer, seven read tasks, each one request returning X's page as sent with its
  release metadata: `lookup_users` (users by username, with their most recent post on
  request), `get_user_posts`, `search_recent_posts` (512 characters of query at most),
  `count_posts` (post counts over the full archive by hour, upstream's default, day or
  minute, 1,024 characters of query at most), `get_list_posts`, `get_conversation_posts`
  (a conversation's posts of the last seven days) and `get_usage` (the project's post
  usage). Paging is the caller's, with the `next_token` of the previous page;
  `max_results` defaults to 10 and goes up to 100, and each docstring names the price per
  post, user or request. `meta.published_at` stays empty: X states no release time for a
  page, and each post carries its own creation time. A user or List id X does not find,
  or a lookup that finds nobody, raises `NotFoundError`.
- The MCP read server `xippios-x-mcp` and the FastAPI router serve the seven tasks as the
  tools `x_lookup_users`, `x_get_user_posts`, `x_search_recent_posts`, `x_count_posts`,
  `x_get_list_posts`, `x_get_conversation_posts` and `x_get_usage` and the routes under
  `/x/`. The post tools' results are capped at 128,000 bytes and `x_lookup_users`' at
  160,000, so a whole page of 100 posts or users comes back where its text is
  Latin-script (mostly non-Latin text can still be cut); the other tools keep the family's
  64 KB, which a month of hourly counts fits and minute counts over more than about 14
  hours pass. A cut's note names the tool's own parameters.
- `api.get_usage`, the wrapper of `GET /2/usage/tweets`, with the `Usage` models and
  `UsageField`; X answers in the OpenAPI document's shape, its counts as digit strings,
  read as numbers.
- `scripts/record_fixture.py` records `get_usage`, which has no price on X's pricing page,
  and a recent search for a conversation started by a post of @XDevelopers, @USDA or @FAO,
  its replies' text rewritten; the fixtures of one @USDA conversation and of seven days of
  usage.
- One live smoke test per task; the nightly run spends one billable call, the lookup of
  @XDevelopers, and the other six run on demand and locally.

### Changed

- `CLAUDE.md`: the credential is the app's Bearer Token, not the console's API Key; the
  rate-limit row names X's documented 15-minute windows beside the self-imposed pace; the
  fixtures path is `<wrapper>/<case>.json`; the X API v2 specifics hold spend, the
  fixtures decision with the Developer Agreement's clause, the nightly live run, the
  operator-only `.local/` and the paths, names and errors the snapshot states; then the
  names the wire takes and answers in, the recorder's rules and `classify`'s mapping; then
  the probe, and the nightly run keyless until the probe's go.
- README: the Bearer Token in the key sentence, and the X Developer Agreement and
  Developer Policy as the terms data comes under.
- The fixture `get_posts_by_ids/most_recent_three` is recorded again for the same three
  posts without the `referenced_posts` expansion: it holds the three accounts' posts only,
  and no fixture carries a post or profile of another account. The recorder admits one
  expansion, `most_recent_post_id`, which brings a post of the requested user and no
  profile; the wrappers keep every expansion the OpenAPI document lists.
- The hand-written enums (`UserField`, `PostField`, `UserExpansion`, `PostExpansion`,
  `Granularity` and the schemas' value lists) name in their docstrings, which an MCP
  tool's input schema shows, the OpenAPI document's list they come from, its version and
  the snapshot's date.
- The account probe reads its list bare or under the one key `accounts:`, and refuses any
  other shape by its type. Its list errors print no value from the list: an entry with
  unknown fields is named by its position and their count, and where an unquoted comma
  split a value in a one-line record, by the field to quote, `why` say; a list that is not
  UTF-8 text is refused by its path, without a traceback. `CLAUDE.md` says how the list is
  written.
- `CLAUDE.md`: the task layer (the tasks, their spend per call, fields, query limits,
  paging, absence, metadata, the `published_at` rule and the MCP caps), the nightly live
  run's rule and the recorder's conversation guard; README: the example, the MCP notes and
  the status table of the seven tasks.
