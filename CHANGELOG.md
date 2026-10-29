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

### Changed

- `CLAUDE.md`: the credential is the app's Bearer Token, not the console's API Key; the
  rate-limit row names X's documented 15-minute windows beside the self-imposed pace; the
  fixtures path is `<wrapper>/<case>.json`; the X API v2 specifics hold spend, the
  fixtures decision with the Developer Agreement's clause, the nightly live run, the
  operator-only `.local/` and the paths, names and errors the snapshot states.
- README: the Bearer Token in the key sentence, and the X Developer Agreement and
  Developer Policy as the terms data comes under.
