# ADR-0001: X as a metered, content-bearing source

Status: Accepted · Date: 2026-10-30 · Decided by https://github.com/xippios/sdk-core/pull/36

## Context

This record was sdk-core's ADR-0027 until https://github.com/xippios/sdk-core/issues/484
moved it to this repository, and where it cites a record of sdk-core that a later one
superseded there, it cites the record in force.

sdk-x wraps X API v2 (`https://api.x.com/2`, whose OpenAPI document is the snapshot's
spec) as a secondary, read-only source: posts point at primary data the family already
wraps and are never data themselves. It is the family's first upstream that bills in
money rather than by quota. sdk-x's snapshot (`docs/upstream/`, of 2026-10-29, refreshed
2026-10-30) states:

- Reads bill per resource returned, 0.005 USD a post and 0.010 USD a user; post counts
  bill per request, 0.005 USD on `GET /2/tweets/counts/recent` and 0.010 USD on
  `GET /2/tweets/counts/all`. A resource read again within the same UTC day is not
  billed again, a soft guarantee; a counts request is priced per request, and the
  deduplication is stated for resources (read here as billed every time). Creating a
  post costs 0.015 USD, 0.200 USD with a URL. Only successful responses that return
  data are billed. Pay-per-usage plans are capped at 3 million post reads a billing
  cycle, and once the console's spending limit per cycle is reached, requests are
  blocked until the next cycle (`pages/pricing.md`, `pages/usage-and-billing.md`).
- The rate limits are windows of 15 minutes, per endpoint and per app: 300 requests on
  `GET /2/users/by`, 3,500 on `GET /2/tweets`, 10,000 on `GET /2/users/:id/tweets`,
  and so on for each operation. A spent window is answered with a 429 carrying
  `x-rate-limit-limit`, `x-rate-limit-remaining` and `x-rate-limit-reset`, the last a
  Unix timestamp; the page documents no `Retry-After`, and no per-second or per-minute
  limit applies to the operations sdk-x wraps (`pages/rate-limits.md`).
- An app-only Bearer Token, which X calls the App only Access Token, covers public
  reads (`pages/application-only.md`); posting and owned reads need user context,
  OAuth 2.0 with PKCE or OAuth 1.0a.
- Posts, their ids and profile information are X Content (the Developer Agreement,
  I.12), the documentation is X API (I.10), both are Licensed Material (I.4), and
  III.A (d) forbids distributing Licensed Material to any third party, in whole or in
  part, except as the Agreement permits; the Developer Policy's "Content
  redistribution" lets X Content reach third parties as Post, Direct Message and User
  IDs (`terms/`).

Core's limiter and `QuotaPolicy` (sdk-core's
[ADR-0033](https://github.com/xippios/sdk-core/blob/main/docs/adr/0033-rate-limit-policy.md),
[ADR-0037](https://github.com/xippios/sdk-core/blob/main/docs/adr/0037-client-request-hooks-and-quota-policy.md))
bound calls, not spend, and a policy keeps one snapshot per client, so it cannot track
windows per endpoint. The family's fixtures live in public repositories. Posting has
cost and reputational effects a read source does not have: the account it posts as and
the automation label an automated account carries.

The maintainer answered sdk-x's eight interview questions, and with them the 429
handling and the recording accounts, on 2026-10-29. The account probe of 2026-10-29
over 59 curated accounts (345 requests) measured 49 of them, 36 active and 32 core in 9
categories, and the maintainer answered go on 2026-10-29, bounding a tool call at 0.50
USD for posts and 1.00 USD for users (decision 4). On 2026-10-30 he kept the per-tool
caps. The family drafted this record; the usage-cap fallback, the recorder's search and
List guards, the List posts fixture and `lookup_users`' `most_recent_post` are sdk-x's
own decisions, taken in its work and not by the maintainer.

## Decision

1. **App-only reads.** The first release reads with the app's Bearer Token in
   `X_API_KEY`, `api_key_location=bearer`, which core's `BearerAuth` sends as
   `Authorization: Bearer` (the maintainer, 2026-10-29; the scaffold's evidence settled
   that no prefix is missing from core). Its MCP server is read-only. Posting,
   user-context auth and owned reads wait for their own ADR, which settles the posting
   account, the automation label and the OAuth flow.
2. **Spend is bounded outside the code.** The console's per-cycle spending limit is the
   hard stop. Every piece of work that spends X credit carries a dollar budget line;
   `GET /2/usage/tweets` is logged after each spending step, and a script that spends
   prints its estimate before its first request. `live.yml` makes at most one billable
   call a night (the maintainer, 2026-10-29): the `GET /2/users/by` lookup of
   @XDevelopers, about 0.010 USD; the other smoke tests skip on the schedule and run on
   `workflow_dispatch` and locally (how conventions §10 reads a metered upstream's live
   smoke tests is an open question). The pace is self-imposed, 60 requests a minute
   with a burst of 1 (sdk-core's
   [ADR-0033](https://github.com/xippios/sdk-core/blob/main/docs/adr/0033-rate-limit-policy.md),
   decision 1). The 15-minute windows are left to `classify`, a 429's
   `x-rate-limit-reset` read as `retry_after` with the window, 900 s, as the fallback,
   and never rationed ahead; no `QuotaPolicy` is installed (sdk-core's
   [ADR-0033](https://github.com/xippios/sdk-core/blob/main/docs/adr/0033-rate-limit-policy.md),
   decision 2; a policy keyed per endpoint is an open question). X's `usage-capped`
   problem is a `RateLimitError` too, its fallback the 31-day billing cycle (sdk-x's
   own decision).
3. **Fixtures from three accounts, X Content rewritten** (the maintainer's answer of
   2026-10-29, which he extended the same day). Fixtures are recorded only from
   @XDevelopers, @USDA and @FAO. The recorder rewrites, by key on the `Fixture` before
   the write (sdk-core's
   [ADR-0042](https://github.com/xippios/sdk-core/blob/main/docs/adr/0042-the-recorder-extras-stay-the-sources.md),
   decision 4), every `text` and `description` at any depth and the `name`, `username`
   and `location` of every user other than the three, verifies that no rewritten value
   survives and never writes the unrewritten body; counts stay as sent. It refuses
   before the request what could bring in another account's content: an expansion
   other than `most_recent_post_id` (`referenced_posts` refused, the maintainer,
   2026-10-29), a search query other than `from:` one of the three, alone or with
   `-is:retweet` and `-is:reply`, a List none of them owns, a conversation not started
   by a post of theirs (the search and List guards sdk-x's own, the conversation guard
   the maintainer's, 2026-10-29). The List members and conversation fixtures keep other
   accounts' members and posts with every free text rewritten and their ids, times and
   public metrics as sent (the maintainer, 2026-10-29); the List posts fixture does the
   same, sdk-x's own decision, which the maintainer can overturn before he merges
   sdk-core's conventions 1.25 PR, https://github.com/xippios/sdk-core/pull/37. The
   snapshot of X's documentation stays under sdk-core's
   [ADR-0028](https://github.com/xippios/sdk-core/blob/main/docs/adr/0028-upstream-fidelity.md),
   decision 4: reproduced for reference with its attribution, the Developer Agreement's
   I.4, I.10, I.12 and III.A (d) cited in sdk-x's `CLAUDE.md`, and X's objection
   honoured by a summary that keeps the names and semantics the wrappers rely on (the
   maintainer, 2026-10-29); whether sdk-core's ADR-0028 takes the general rule is an
   open question.
4. **One page per call** (the account probe's go, the maintainer, 2026-10-29). A task
   returns one upstream page as X sends it: a post task's `max_results` defaults to 10
   and is bounded by the spec, at most 100, `lookup_users` takes up to 100 usernames,
   and paging is explicit, the caller passing the previous page's `next_token` to the
   token parameter the operation names. One tool call so spends at most 0.50 USD for
   posts or 1.00 USD for users, and the counts task reads one page of up to 31 days for
   0.010 USD. `lookup_users`' optional `most_recent_post`, off by default, adds up to
   0.50 USD, 1.50 USD for 100 users, above the probe's bound for users: sdk-x's own
   decision, which the maintainer can overturn before he merges sdk-core's conventions
   1.25 PR. Ranking, summarising or storing posts is the consumer's. The docstrings
   name the price per result. The per-tool byte caps stand: 128,000 bytes for the four
   post tools, so that a whole page of 100 posts returns with its `next_token` (for
   Latin-script text), and 160,000 for `lookup_users`, whose `GET /2/users/by` has no
   `next_token` and whose 100 users fit, about 70 with `most_recent_post`; the counts
   task and `get_usage` stay at the family default (sdk-core's
   [ADR-0038](https://github.com/xippios/sdk-core/blob/main/docs/adr/0038-per-tool-result-caps.md),
   decision 4; the maintainer, 2026-10-30, superseding the line of the probe's go
   "MCP_CAPS keep the family default"). The nouns are the snapshot's, posts, users and Lists, never
   tweets or accounts (sdk-core's
   [ADR-0028](https://github.com/xippios/sdk-core/blob/main/docs/adr/0028-upstream-fidelity.md)).
   How conventions §4 reads one page per call for a metered source is an open question,
   beside how it reads a list unbounded by nature.
5. **Curated account lists are product data**, never packaged (the maintainer,
   2026-10-29): the list the probe reads through `--accounts` lives in sdk-x's
   `.local/`, gitignored, and so do the probe's cache and its report.

Rejected:

- a `QuotaPolicy` on X's windows (decision 2): its one snapshot would let a spent
  `GET /2/users/by` window refuse `GET /2/tweets`, whose window is not spent, and it
  reads no Unix reset timestamp; without it a spent window costs one 429, which X does
  not bill;
- a pace rationed within the tightest window (decision 2), which a first draft
  proposed, against decision 2 of sdk-core's
  [ADR-0033](https://github.com/xippios/sdk-core/blob/main/docs/adr/0033-rate-limit-policy.md);
- collecting every page when the token is omitted (decision 4; conventions §4, and
  decision 2 of sdk-core's
  [ADR-0034](https://github.com/xippios/sdk-core/blob/main/docs/adr/0034-upstream-totals-in-the-result-envelope.md),
  by which a paginated task called without its page parameter collects every page, in a
  cursor-paginated source's own loop too), whose spend no call bounds;
- `MCP_CAPS` at the family default (decision 4), under which a page of more than about
  50 posts is cut to a preview that loses its `next_token` (the maintainer, 2026-10-30).

## Consequences

- Nothing in `xippios.core` changes: `BearerAuth` sends the token (decision 1), and the
  429 and the usage cap are `classify`'s (decision 2). A gap in core for a header
  prefix in `EnvKeyAuth` was expected; the scaffold's evidence made it unnecessary.
- Conventions 1.24: §1 lists `x` among the sources; §6 leaves per-endpoint windows
  shorter than an hour to `classify`, with no `QuotaPolicy` until one keyed per endpoint,
  as decision 2 of sdk-core's
  [ADR-0033](https://github.com/xippios/sdk-core/blob/main/docs/adr/0033-rate-limit-policy.md)
  states the reading for them; §13 gains the topic `social-media` (the maintainer,
  2026-10-29), as sdk-core's
  [ADR-0025](https://github.com/xippios/sdk-core/blob/main/docs/adr/0025-google-mail.md)
  brought `email`. Conventions 1.25: §8 gives a tool whose result is one upstream page
  that must return whole a byte bound of its own, as decision 4 of sdk-core's
  [ADR-0038](https://github.com/xippios/sdk-core/blob/main/docs/adr/0038-per-tool-result-caps.md)
  holds that case.
- Open questions: a `QuotaPolicy` keyed per endpoint group, with a reset header read as
  a Unix timestamp, waiting for a second consumer (sdk-core's
  [ADR-0059](https://github.com/xippios/sdk-core/blob/main/docs/adr/0059-core-s-scope-what-a-consumer-is-and-how-far-the-two-consumer.md));
  sdk-core's
  [ADR-0028](https://github.com/xippios/sdk-core/blob/main/docs/adr/0028-upstream-fidelity.md)
  and conventions §3 for an accepted agreement that classes documentation as Licensed
  Material; core's redaction, which writes `next_token` and `pagination_token` as
  `REDACTED` in recorded URLs and in `meta.request`; conventions §10's nightly live run
  for a metered upstream; and conventions §4 for one page per call, a cursor on
  `ResultMeta`, MCP text without `None` fields.
- sdk-x 0.1.0 is the first consumer; its release PR follows this ADR on sdk-core
  `main`.
- A write tool for X waits for the posting ADR of decision 1, which settles the
  account, OAuth 2.0 with PKCE and refresh tokens, the automation label, the 0.200 USD
  URL price and a write tool with `confirm` last.
