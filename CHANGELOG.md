# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: breaking changes bump the minor).

## [Unreleased]

### Added

- Scaffold from [sdk-template](https://github.com/xippios/sdk-template): configured
  client for X API v2, empty task layer, MCP server and FastAPI router
  wired to it, test harness with core's family check, CI, the nightly live tests and
  the release train, in which a release PR's merge tags and publishes.
- The upstream documentation snapshot in `docs/upstream/`, fetched 2026-10-29: X API v2's
  OpenAPI document (version 2.173), the docs.x.com pages on pricing, usage and billing,
  the usage endpoint, rate limits, response codes and errors, fields, pagination, post
  counts and app-only Bearer Token authentication, and the X Developer Agreement and
  Developer Policy, each kept as served; `scripts/refresh_upstream.py` reproduces it
  and regenerates `FETCHED.md`.
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
- `scripts/probe_accounts.py`, the account probe: it reads the operator's account list,
  prints its spend estimate and call plan without a request, and only with `--spend
  --spend-cap` looks the accounts up, counts their posts and original posts by day over
  90 days and samples ten posts each, waiting out X's rate-limit windows and keeping every
  page in a same-day cache with a ledger of the day's spend; it writes a CSV and a
  Markdown report with the go, US-only or no-go decision under `.local/`, which git now
  ignores.

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
