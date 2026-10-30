# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Refresh the upstream documentation snapshot in ``docs/upstream/`` (``/refresh-upstream``).

X documents API v2 on docs.x.com, which serves every page as Markdown when ``.md`` is
appended to its URL, and in an OpenAPI document, ``SPEC_URL``, which the API serves itself.
The script writes, each file the body as fetched, byte for byte:

- ``openapi/openapi.json``: the OpenAPI document of X API v2, ``SPEC_URL``;
- ``pages/*.md``: the pages on pricing, usage and billing, the usage endpoint, rate limits,
  response codes and errors, fields, pagination, post counts, the search operators (the
  query syntax of recent search and of the post counts), and OAuth 2.0 with app-only
  Bearer Token authentication, in their Markdown form;
- ``terms/developer-agreement.md`` and ``terms/developer-policy.md``: the X Developer
  Agreement and the X Developer Policy, the terms that bind the X API and X Content, kept
  whole;
- ``FETCHED.md``: regenerated whole.

The HTML page at ``DOCS_URL`` is read without a file, for its site footer alone, which the
Markdown form leaves out: the footer states no copyright line and links X's Terms of
Service (``ATTRIBUTION``). Its row records the size and sha256 of the footer's text as
read, not of the page, whose HTML changes with every build of the site. A page whose
title is not the one recorded in ``PAGES``, a terms page that no longer prints what
``ATTRIBUTION`` quotes from it, or a document that is not X API v2's OpenAPI document
stops the run, before anything is written.

Everything is fetched before anything is written, one request at a time after a pause,
each URL retried at most once after a network error or a 5xx. Files the run does not
produce are removed from the subdirectories it writes to; nothing else under
``docs/upstream/`` is touched. Every run stops, before writing, when a page states a
copyright, a licence or terms of use that ``ATTRIBUTION`` does not record: the Markdown
pages are searched whole, the two terms pages not at all (they are the terms), the OpenAPI
document whole but for ``info``'s licence and terms, which must be the recorded ones, and
for the words of ``VOCABULARY``, a field of the API. No key, token or credential is needed,
sent or read. Run from the repository root::

    uv run scripts/refresh_upstream.py            # fetch, then write the snapshot
    uv run scripts/refresh_upstream.py --check    # fetch and compare; write nothing

``--check`` exits 1 when the snapshot differs from what upstream serves now, ``Fetched``
aside. X serves the OAuth 2.0 scope lists of the document's ``security`` requirements in a
new order on each request, so ``--check`` compares the OpenAPI document as text with those
lists sorted and nothing else changed (``canonical``): where the file or the fetched body is
not exactly the document written with ``json.dumps(indent=2, ensure_ascii=False)``, as X
serves it, their bytes are compared instead, so any other difference counts. A write run
writes the body as fetched, in that request's order, so a refresh's diff shows reordered
scope lists. Nothing is converted: the script declares no dependency.
"""

import argparse
import hashlib
import html
import http.client
import json
import re
import textwrap
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import IO, Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs/upstream"
COMMAND = "uv run scripts/refresh_upstream.py"
SOURCE_NAME = "X API v2"
DOCS_URL = "https://docs.x.com/x-api/introduction"
"""Where the documentation lives: ``upstream_docs_url`` in ``.copier-answers.yml``."""
USER_AGENT = "xippios-x refresh_upstream (+https://github.com/xippios)"
TIMEOUT = 60.0
PAUSE = 2.0
"""Seconds before every request; requests never run in parallel."""
RETRY_PAUSE = 10.0
"""Seconds before the one retry after a network error or a 5xx."""


@dataclass(frozen=True)
class Page:
    """One page the snapshot records, and the file it is kept as, if any.

    Attributes:
        url: Where the page is fetched from.
        file: Its path under ``docs/upstream/`` (``pages/guide.md``,
            ``openapi/openapi.json``), or ``None`` for a page recorded without a file.
        status: The HTTP status it must answer with: 200, or the 403 or 404 of a page
            recorded by its status.
        note: The row's note in ``FETCHED.md``: how the file was made, or why there is none.
        stable: ``False`` for a body that changes on every request (a per-request
            reference in a refusal page): its row records no size, sha256 or validators.
        excerpt: The file is this source's part of a shared document (conventions §3);
            the row keeps the whole document's size and sha256, and its note says so.
        title: A Markdown page's title, its ``# `` heading as printed; another stops the
            run, so a moved or replaced page is not taken for this one.
        terms: The page is terms that bind the API (``ATTRIBUTION``): kept whole, checked
            for what ``ATTRIBUTION`` quotes from it, and not searched further.
        footer: An HTML page read for its site footer alone: checked there, and its row
            records the size and sha256 of the footer's text as read, and no validators.
    """

    url: str
    file: str | None = None
    status: int = 200
    note: str = ""
    stable: bool = True
    excerpt: bool = False
    title: str = ""
    terms: bool = False
    footer: bool = False


DOCS = "https://docs.x.com"
MARKDOWN = "the page's Markdown form, verbatim"


def _markdown(path: str, file: str, title: str, *, terms: bool = False) -> Page:
    """A docs.x.com page in its Markdown form: its URL with ``.md`` appended."""
    return Page(f"{DOCS}/{path}.md", file, note=MARKDOWN, title=title, terms=terms)


PAGES: tuple[Page, ...] = (
    _markdown(
        "x-api/getting-started/pricing",
        "pages/pricing.md",
        "X API pay-per-usage pricing and credits",
    ),
    _markdown("x-api/fundamentals/post-cap", "pages/usage-and-billing.md", "Usage and Billing"),
    _markdown("x-api/usage/introduction", "pages/usage.md", "Usage"),
    _markdown("x-api/fundamentals/rate-limits", "pages/rate-limits.md", "X API Rate Limits"),
    _markdown(
        "x-api/fundamentals/response-codes-and-errors",
        "pages/response-codes-and-errors.md",
        "Response Codes & Errors",
    ),
    _markdown("x-api/fundamentals/fields", "pages/fields.md", "Fields"),
    _markdown("x-api/fundamentals/pagination", "pages/pagination.md", "Pagination"),
    _markdown("x-api/posts/counts/introduction", "pages/post-counts.md", "Post Counts"),
    _markdown(
        "x-api/posts/search/integrate/operators", "pages/search-operators.md", "Search Operators"
    ),
    _markdown("fundamentals/authentication/oauth-2-0/overview", "pages/oauth-2-0.md", "OAuth 2.0"),
    _markdown(
        "fundamentals/authentication/oauth-2-0/application-only",
        "pages/application-only.md",
        "App only authentication and OAuth 2.0 Bearer Token",
    ),
    _markdown(
        "developer-terms/agreement",
        "terms/developer-agreement.md",
        "X Developer Agreement",
        terms=True,
    ),
    _markdown(
        "developer-terms/policy", "terms/developer-policy.md", "X Developer Policy", terms=True
    ),
    Page(
        DOCS_URL,
        note="the HTML page, read for its site footer alone (Attribution); Bytes and sha256 "
        "are those of the footer's text as read, its tags dropped and its whitespace "
        "collapsed, and no validators are kept, since the page's HTML changes with every "
        "build of the site",
        footer=True,
    ),
)
"""Every page the snapshot records, in the order of ``FETCHED.md``'s rows."""

SPEC_URL: str | None = "https://api.x.com/2/openapi.json"
"""The machine-readable API document: X API v2's OpenAPI document, which the API serves.

docs.x.com's llms.txt index names an OpenAPI specification as the API's machine-readable
contract; the API serves the document itself at this URL, and the script keeps it verbatim
as ``SPEC_FILE``, after ``PAGES``.
"""
SPEC_FILE = "openapi/openapi.json"
"""The document's path under ``docs/upstream/``, with the extension it is served with."""
SPEC_TITLE = "X API v2"
"""``info.title`` of the document; another stops the run."""
SPEC_NOTE = (
    "SPEC_URL, verbatim; the scope lists of its security requirements come in a new order "
    "on each request (How this is captured)"
)
"""The OpenAPI document's note in ``FETCHED.md``."""


@dataclass(frozen=True)
class Statement:
    """A copyright line, licence or terms of use the documentation states, as printed.

    Attributes:
        text: The statement as printed: a line of a terms page, the name of the OpenAPI
            document's licence, or the text of a link.
        source: Where it is printed: a file under ``docs/upstream/``, or the URL of a page
            read without a file.
        where: What it is and where it stands, for ``FETCHED.md``'s Attribution.
        link: The URL the statement links to: the licence's ``url`` (and
            ``termsOfService``) in the OpenAPI document, or a link's target in a footer.
    """

    text: str
    source: str
    where: str
    link: str | None = None


ATTRIBUTION: tuple[Statement, ...] = (
    Statement(
        "X Developer Agreement",
        "terms/developer-agreement.md",
        f"the title of {DOCS}/developer-terms/agreement, the binding agreement that governs "
        "access to and use of the X API and X Content, kept whole",
    ),
    Statement(
        "Last Updated: April 27, 2026",
        "terms/developer-agreement.md",
        "the date printed under the X Developer Agreement's title",
    ),
    Statement(
        "X Developer Policy",
        "terms/developer-policy.md",
        f"the title of {DOCS}/developer-terms/policy, part of the contract that governs the "
        "X API and X Content as its first section says, kept whole",
    ),
    Statement(
        "X Developer Agreement and Policy",
        SPEC_FILE,
        "the name of the OpenAPI document's `info.license`, whose url `info.termsOfService` "
        "gives as well; developer.x.com redirects it (307) to "
        f"{DOCS}/developer-terms/agreement-and-policy.html, which answered 404 when checked "
        "on 2026-10-29",
        "https://developer.x.com/en/developer-terms/agreement-and-policy.html",
    ),
    Statement(
        "Terms of Service",
        DOCS_URL,
        "a link in the site footer of the docs.x.com pages, under Legal, beside Privacy "
        "Policy, Cookies and Developer Terms; the footer prints no copyright line",
        "https://x.com/en/tos",
    ),
)
"""Every copyright line, licence or terms of use the documentation states, as printed.

``FETCHED.md`` lists them under Attribution. Each is checked where it is printed: a terms
page must print it as a line, the OpenAPI document's ``info`` must name it, a footer must
link it; and every run stops when a page states one that is not here.
"""

VOCABULARY: tuple[str, ...] = ('"copyright"', "withheld due to a copyright claim")
"""Words of the API that the statement search would read as statements: the OpenAPI
document's ``withheld`` object has a boolean field ``copyright``, described as "Indicates
whether this content is withheld due to a copyright claim."; removed before the search."""

CAPTURE = (
    "docs.x.com serves each page as Markdown when `.md` is appended to its URL, the form "
    "its index for agents, https://docs.x.com/llms.txt, points to; the script fetches that "
    "form and keeps it verbatim, the notice of the documentation index at its top included. "
    "Nothing is converted, so every table is the page's own pipe table and none is kept as "
    "HTML. The Markdown form carries no site chrome: the HTML page at "
    f"{DOCS_URL} is read for its footer alone, and its text is not kept. The OpenAPI "
    f"document is the one the API serves at {SPEC_URL}, kept byte for byte as fetched; its "
    "`info` names the X Developer Agreement and Policy as its licence and terms, the two "
    "documents kept whole under `terms/`. X serves the OAuth 2.0 scope lists of the "
    "document's `security` requirements in a new order on each request (two fetches on "
    "2026-10-29 differed in nothing else). A write run writes the body as fetched, in that "
    "request's order, so a refresh's diff shows reordered scope lists. `--check` compares "
    "the document as text with those lists sorted and nothing else changed: where the file "
    "or the fetched body is not exactly the document written with `json.dumps(indent=2, "
    "ensure_ascii=False)`, as X serves it, it compares their bytes, so a difference in key "
    "order, whitespace, escapes or numbers still counts. docs.x.com sends no ETag, and a "
    "Last-Modified that does not look like a page's last change: on 2026-10-29 the OAuth 2.0 "
    "overview reported Last-Modified 14:20:07 UTC beside an Age of 44,585 s at 14:38 UTC. "
    "Taken, as an inference, for the time a cache rendered the page, it can move without "
    "the page changing, and `--check` then reports `FETCHED.md`. The API sends neither "
    "validator for the OpenAPI document."
)
"""``FETCHED.md``'s "How this is captured": what is converted, cut or left out, and why."""

_STATEMENT = re.compile(
    r"\N{COPYRIGHT SIGN}|copyright|licen[cs]e|terms of (?:use|service)|public domain",
    re.IGNORECASE,
)
_FETCHED = re.compile(r"\| (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) \|")


@dataclass(frozen=True)
class Response:
    """One GET as served: status, body and validators, and the redirects on the way."""

    url: str
    status: int
    body: bytes
    etag: str | None
    last_modified: str | None
    redirects: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class Row:
    """One row of ``FETCHED.md``: the page, its response and its file's content, if any."""

    page: Page
    response: Response
    content: bytes | None


class _RetryableError(Exception):
    """A network error or a 5xx: worth one more attempt."""


class _RecordRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects as urllib does, remembering each status and target."""

    def __init__(self) -> None:
        super().__init__()
        self.hops: list[tuple[int, str]] = []

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Record the hop, then let urllib build the follow-up request."""
        self.hops.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _log(message: str) -> None:
    print(message, flush=True)  # noqa: T201


def _get(url: str, expect: int) -> Response:
    redirects = _RecordRedirects()
    opener = urllib.request.build_opener(redirects)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            body: bytes = response.read()
            status: int = response.status
            headers = response.headers
    except urllib.error.HTTPError as error:
        if error.code >= 500:
            raise _RetryableError(f"HTTP {error.code} {error.reason}") from None
        if error.code != expect:
            raise SystemExit(f"GET {url}: HTTP {error.code} {error.reason}") from None
        body, status, headers = error.read(), error.code, error.headers
    except (http.client.HTTPException, OSError) as error:  # URLError is an OSError
        raise _RetryableError(str(error)) from None
    if status != expect:
        raise SystemExit(f"GET {url}: expected HTTP {expect}, got {status}")
    encoding = headers.get("Content-Encoding", "identity").strip().lower()
    if encoding != "identity":
        raise SystemExit(f"GET {url}: unexpected Content-Encoding {encoding!r}")
    return Response(
        url,
        status,
        body,
        headers.get("ETag"),
        headers.get("Last-Modified"),
        tuple(redirects.hops),
    )


def fetch(url: str, expect: int = 200) -> Response:
    """GET ``url`` after a polite pause; retry once on a network error or a 5xx."""
    time.sleep(PAUSE)
    try:
        response = _get(url, expect)
    except _RetryableError as error:
        _log(f"  {url}: {error}; retrying once in {RETRY_PAUSE:g} s")
        time.sleep(RETRY_PAUSE)
        try:
            response = _get(url, expect)
        except _RetryableError as error:
            raise SystemExit(f"GET {url}: {error} (after one retry)") from None
    digest = hashlib.sha256(response.body).hexdigest()
    hops = "".join(f", {code} to {target}" for code, target in response.redirects)
    _log(
        f"  {url}: HTTP {response.status}{hops}, {len(response.body)} bytes, sha256 {digest}, "
        f"Last-Modified {response.last_modified or '-'}, ETag {response.etag or '-'}"
    )
    return response


def changed(url: str, what: str) -> SystemExit:
    """The error that stops the run on a page the script does not recognise."""
    return SystemExit(
        f"{url} changed: {what}.\nLook at the page by hand and update "
        "scripts/refresh_upstream.py. Nothing was written."
    )


def decode(response: Response) -> str:
    """The body as UTF-8 text; a body that is not UTF-8 stops the run."""
    try:
        return response.body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise changed(response.url, f"the body is not UTF-8 ({error})") from None


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    counts = Counter(key for key, _ in pairs)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate keys {duplicates}")
    return dict(pairs)


def dump_json(value: Any, indent: int = 2) -> bytes:
    """``value`` as JSON in the order it holds, ``ensure_ascii=False``, with a final newline."""
    return (json.dumps(value, indent=indent, ensure_ascii=False) + "\n").encode("utf-8")


def load_json(response: Response, indent: int = 2) -> Any:
    """The JSON document of ``response``, once re-serialising it reproduces the fetched text.

    A source that keeps a JSON document cut to its part writes the part with ``dump_json``;
    this check makes sure that the whole document, written the same way, is the fetched
    text up to line endings, so the part is an excerpt of upstream's text. A duplicate key,
    which ``json.loads`` would drop silently, stops the run too.
    """
    try:
        document = json.loads(response.body, object_pairs_hook=_no_duplicates)
    except ValueError as error:
        raise SystemExit(f"GET {response.url}: not usable JSON ({error})") from None
    fetched = response.body.replace(b"\r\n", b"\n").rstrip(b"\n")
    if dump_json(document, indent).rstrip(b"\n") != fetched:
        raise SystemExit(
            f"GET {response.url}: re-serialised with json.dumps(indent={indent}, "
            "ensure_ascii=False), the document no longer reproduces the fetched text up to "
            "line endings, so a part cut from it would not be an excerpt of upstream's text."
            "\nLook at the document by hand and update scripts/refresh_upstream.py. Nothing "
            "was written."
        )
    return document


def spec_document(response: Response) -> dict[str, Any]:
    """The OpenAPI document as parsed; another document, or a duplicate key, stops the run."""
    try:
        document = json.loads(response.body, object_pairs_hook=_no_duplicates)
    except ValueError as error:
        raise changed(response.url, f"not usable JSON ({error})") from None
    if not isinstance(document, dict) or not str(document.get("openapi", "")).startswith("3."):
        raise changed(response.url, "it is not an OpenAPI 3 document")
    info = document.get("info")
    if not isinstance(info, dict) or info.get("title") != SPEC_TITLE:
        raise changed(response.url, f"its info.title is not {SPEC_TITLE!r}")
    return document


def _sort_scopes(node: Any) -> None:
    """Sort, in place, the scope lists of every ``security`` requirement under ``node``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "security" and isinstance(value, list):
                for requirement in value:
                    if isinstance(requirement, dict):
                        for scheme, scopes in requirement.items():
                            if isinstance(scopes, list):
                                requirement[scheme] = sorted(scopes, key=json.dumps)
            else:
                _sort_scopes(value)
    elif isinstance(node, list):
        for item in node:
            _sort_scopes(item)


def canonical(body: bytes) -> bytes | None:
    """The OpenAPI document's text with the scope lists of its security requirements sorted.

    X serves those lists in a new order on each request; ``--check`` compares this form.
    ``None`` where ``body`` is not exactly ``json.dumps(indent=2, ensure_ascii=False)`` of
    the document it parses to, as X serves it: then only the bytes compare, so nothing
    but the order of the scope lists is ever ignored.
    """
    try:
        document = json.loads(body, object_pairs_hook=_no_duplicates)
    except ValueError:
        return None
    if json.dumps(document, indent=2, ensure_ascii=False).encode("utf-8") != body:
        return None
    _sort_scopes(document)
    return json.dumps(document, indent=2, ensure_ascii=False).encode("utf-8")


_FOOTER = re.compile(r"<footer\b[^>]*>(.*?)</footer>", re.DOTALL)
_LINK = re.compile(r'<a\b[^>]*?\bhref="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


def _text(markup: str) -> str:
    """The text of an HTML fragment, its tags dropped, entities decoded, whitespace collapsed."""
    return " ".join(html.unescape(_TAG.sub(" ", markup)).split())


def _statements(source: str) -> tuple[Statement, ...]:
    return tuple(statement for statement in ATTRIBUTION if statement.source == source)


def _stop(page: Page, found: str, text: str, start: int, end: int) -> SystemExit:
    around = " ".join(text[max(start - 60, 0) : end + 60].split())
    return SystemExit(
        f"GET {page.url}: the page states {found!r} ({around!r}), a copyright, licence or "
        "terms of use that ATTRIBUTION does not record.\nRead it by hand, record it in "
        "ATTRIBUTION and update scripts/refresh_upstream.py. Nothing was written."
    )


def _search(page: Page, text: str) -> None:
    """Stop when ``text`` states a copyright, licence or terms of use."""
    match = _STATEMENT.search(text)
    if match:
        raise _stop(page, match.group(0), text, match.start(), match.end())


def _check_markdown(page: Page, response: Response) -> None:
    """A Markdown page: its title; a terms page prints its statements, any other none."""
    text = decode(response)
    titles = [line[2:].strip() for line in text.splitlines() if line.startswith("# ")]
    if not titles or titles[0] != page.title:
        raise changed(page.url, f"its title is {titles[:1]!r}, not {page.title!r}")
    if not page.terms:
        _search(page, text)
        return
    lines = {line.lstrip("#").strip() for line in text.splitlines()}
    for statement in _statements(page.file or ""):
        if statement.text not in lines:
            raise changed(page.url, f"it no longer prints {statement.text!r} as a line")


def _check_spec(page: Page, response: Response) -> None:
    """The OpenAPI document: its licence and terms as recorded, nothing else stated."""
    document = spec_document(response)
    info = dict(document["info"])
    for statement in _statements(SPEC_FILE):
        license_ = {"name": statement.text, "url": statement.link}
        if info.pop("license", None) != license_:
            raise changed(page.url, f"info.license is no longer {license_!r}")
        if info.pop("termsOfService", None) != statement.link:
            raise changed(page.url, f"info.termsOfService is no longer {statement.link!r}")
    text = json.dumps({**document, "info": info}, ensure_ascii=False)
    for word in VOCABULARY:
        text = text.replace(word, "")
    _search(page, text)


def _footer(page: Page, response: Response) -> str:
    """The site footer of an HTML page, as markup; a page without exactly one stops the run."""
    footers = _FOOTER.findall(decode(response))
    if len(footers) != 1:
        raise changed(page.url, f"{len(footers)} footers, not one")
    footer: str = footers[0]
    return footer


def _check_footer(page: Page, response: Response) -> None:
    """An HTML page read for its site footer: the recorded links, and nothing else stated."""
    footer = _footer(page, response)
    for statement in _statements(page.url):
        links = [
            link
            for link in _LINK.finditer(footer)
            if link.group(1) == statement.link and _text(link.group(2)) == statement.text
        ]
        if not links:
            raise changed(page.url, f"the footer no longer links {statement.text!r}")
        for link in links:
            footer = footer.replace(link.group(0), " ")
    _search(page, _text(footer))


def check_attribution(page: Page, response: Response) -> None:
    """Stop when the page states a copyright, licence or terms that ``ATTRIBUTION`` lacks.

    Also stop on a page the script does not recognise: a Markdown page with another title,
    a terms page that no longer prints a statement recorded from it, another API document
    or a footer without its recorded link. A Markdown page is searched whole, a terms page
    not at all, the OpenAPI document whole but for ``info``'s licence and terms and the
    words of ``VOCABULARY``, and the HTML page at ``DOCS_URL`` in its footer alone.
    """
    if page.file == SPEC_FILE:
        _check_spec(page, response)
    elif page.footer:
        _check_footer(page, response)
    else:
        _check_markdown(page, response)


def reduce(page: Page, response: Response) -> bytes:
    """The content ``page``'s file is written with: the body as fetched, byte for byte.

    docs.x.com serves its pages as Markdown and the API its OpenAPI document as JSON, so
    nothing is converted or cut (module docstring).
    """
    return response.body


def capture(page: Page) -> Row:
    """Fetch ``page``, check its attribution and make its file's content; write nothing.

    A page read for its footer keeps, as its row's body, the footer's text as read and no
    validators (``Page.footer``).
    """
    response = fetch(page.url, page.status)
    check_attribution(page, response)
    if page.footer:
        text = _text(_footer(page, response)).encode("utf-8")
        response = replace(response, body=text, etag=None, last_modified=None)
    return Row(page, response, reduce(page, response) if page.file else None)


def _iso_http_date(value: str | None) -> str:
    if value is None:
        return "-"
    return parsedate_to_datetime(value).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cell(value: str) -> str:
    return value.replace("|", r"\|")


def _paragraph(*sentences: str) -> list[str]:
    text = " ".join(sentences)
    wrapped = textwrap.fill(text, width=88, break_long_words=False, break_on_hyphens=False)
    return [*wrapped.splitlines(), ""]


def _note(row: Row) -> str:
    parts = [f"redirected ({code}) to {target}" for code, target in row.response.redirects]
    if row.page.excerpt:
        parts.append("excerpt of a shared document; Bytes and sha256 are the whole document's")
    if not row.page.stable:
        parts.append("the body changes on every request, so no size, sha256 or validators")
    if row.page.note:
        parts.append(row.page.note)
    return "; ".join(parts) or "-"


def _bullet(text: str) -> list[str]:
    wrapped = textwrap.fill(
        text,
        width=88,
        initial_indent="- ",
        subsequent_indent="  ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped.splitlines()


def _attribution() -> list[str]:
    """``FETCHED.md``'s Attribution: every recorded statement, as printed, and where."""
    lines = _paragraph(
        "Neither the pages nor the OpenAPI document print a copyright line. They state",
        "these terms, recorded as printed in `ATTRIBUTION` of",
        "`scripts/refresh_upstream.py`:",
    )
    for statement in ATTRIBUTION:
        linked = f", a link to {statement.link}," if statement.link else ""
        printed = f"`{statement.text}`{linked} printed in {statement.source}"
        lines += _bullet(f"{printed}: {statement.where}.")
    return [*lines, ""]


def render_fetched(rows: Sequence[Row], fetched: str) -> str:
    """The whole of ``FETCHED.md``, ``fetched`` being the UTC time the run started."""
    lines = [
        f"# Upstream documentation snapshot \N{EM DASH} {SOURCE_NAME}",
        "",
        *_paragraph(
            "Source of truth for every endpoint wrapper (ADR-0003). The files in this",
            "directory are written by `scripts/refresh_upstream.py` (`/refresh-upstream`)",
            "from the pages in the table below and refreshed deliberately by PR, so that",
            "changes show up as diffs. This file is generated by the same script; nothing",
            "here is edited by hand.",
        ),
        "## Attribution",
        "",
        *_attribution(),
        *_paragraph(
            "The script stops when a page it reads states one it does not record. The",
            "documentation's text is reproduced here as this package's reference",
            "(ADR-0003); the publisher's objection is met by replacing it with a summary",
            "that keeps the names and semantics the wrappers rely on.",
        ),
        "## How this is captured",
        "",
        *(_paragraph(CAPTURE) if CAPTURE else []),
        *_paragraph(
            "Fetched is the UTC time the run started, in ISO 8601 with an explicit Z, the",
            "same for every row. Bytes and sha256 are those of the body as fetched, which",
            "every file here is byte for byte; the `(no file)` row's are those of the footer",
            "text it is read for, as its note says. Last-Modified is the HTTP header in UTC,",
            "ETag as sent, `-` where none is sent. A page recorded without",
            "a file is `(no file)`, and a body that changes on every request records no",
            f"size, sha256 or validators. Requests go one at a time, {PAUSE:g} s apart,",
            f"each retried at most once, identified as `{USER_AGENT}`; no API key is sent",
            "or read.",
        ),
        "## Files and pages",
        "",
        "| File | URL | Fetched | HTTP | Bytes | sha256 | ETag | Last-Modified | Note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        response, kept = row.response, row.page.stable
        cells = [
            row.page.file or "(no file)",
            response.url,
            fetched,
            str(response.status),
            str(len(response.body)) if kept else "-",
            hashlib.sha256(response.body).hexdigest() if kept else "-",
            (response.etag or "-") if kept else "-",
            _iso_http_date(response.last_modified) if kept else "-",
            _note(row),
        ]
        lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    lines += ["", f"Regenerate: `{COMMAND}`"]
    return "\n".join(lines) + "\n"


def _files(rows: Sequence[Row]) -> dict[str, bytes]:
    return {row.page.file: row.content for row in rows if row.page.file and row.content is not None}


def _stale(out: Path, files: dict[str, bytes]) -> list[str]:
    """The files under the subdirectories the run writes to that it does not produce."""
    subdirs = sorted({name.split("/", 1)[0] for name in files if "/" in name})
    found = [path for subdir in subdirs for path in sorted((out / subdir).rglob("*"))]
    names = [path.relative_to(out).as_posix() for path in found if path.is_file()]
    return [name for name in names if name not in files]


def write_snapshot(out: Path, rows: Sequence[Row], fetched_md: str) -> None:
    """Write every file as ``reduce`` made it, then ``FETCHED.md``; remove the stale files."""
    if out.exists() and any(out.iterdir()) and not (out / "FETCHED.md").is_file():
        raise SystemExit(f"{out} is neither empty nor a snapshot (no FETCHED.md); not writing")
    files = _files(rows)
    for name in _stale(out, files):
        (out / name).unlink()
        _log(f"  removed {name}: no longer produced")
    for name, content in files.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(content)
    (out / "FETCHED.md").write_bytes(fetched_md.encode("utf-8"))


def _as_recorded(out: Path, row: Row) -> Row:
    """The OpenAPI document's row with the snapshot's file, where the two differ in order only.

    ``canonical`` sorts the scope lists that X serves in a new order on each request and
    changes nothing else; where the fetched document and the file have the same canonical
    text, the row takes the file's body, so neither the file nor ``FETCHED.md``'s row
    counts as changed. Any other difference, or a body that is not X's serialisation,
    leaves the row as fetched.
    """
    kept = out / SPEC_FILE
    if row.page.file != SPEC_FILE or row.content is None or not kept.is_file():
        return row
    recorded = kept.read_bytes()
    old, new = canonical(recorded), canonical(row.content)
    if old is None or new is None or old != new:
        return row
    return Row(row.page, replace(row.response, body=recorded), recorded)


def compare(out: Path, rows: Sequence[Row]) -> list[str]:
    """The snapshot's files that differ from this run's, ``FETCHED.md``'s ``Fetched`` aside.

    The OpenAPI document is compared as text with its scope lists sorted (``_as_recorded``).
    """
    rows = [_as_recorded(out, row) for row in rows]
    files = _files(rows)
    differ = [
        name
        for name, content in files.items()
        if not (out / name).is_file() or (out / name).read_bytes() != content
    ]
    differ += [f"{name} (no longer produced)" for name in _stale(out, files)]
    current = out / "FETCHED.md"
    old = current.read_bytes().decode("utf-8") if current.is_file() else ""
    match = _FETCHED.search(old, max(old.find("| --- |"), 0))
    if not match or render_fetched(rows, match.group(1)) != old:
        differ.append("FETCHED.md")
    return differ


def main(argv: Sequence[str] | None = None) -> int:
    """Fetch every page, then write the snapshot, or with ``--check`` compare it."""
    parser = argparse.ArgumentParser(description="Refresh docs/upstream/ from upstream.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="snapshot directory")
    parser.add_argument(
        "--check", action="store_true", help="fetch and compare with the snapshot; write nothing"
    )
    args = parser.parse_args(argv)
    out: Path = args.out
    pages = list(PAGES)
    if SPEC_URL:
        pages.append(Page(SPEC_URL, SPEC_FILE, note=SPEC_NOTE))
    if not pages:
        raise SystemExit(
            "Nothing to fetch: fill PAGES, and SPEC_URL where the documentation names an "
            "API document, as /refresh-upstream says."
        )
    fetched = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    _log(f"Fetching {len(pages)} pages; nothing is written before the last")
    rows = [capture(page) for page in pages]
    if args.check:
        differ = compare(out, rows)
        for name in differ:
            _log(f"  differs: {name}")
        _log(
            f"{len(differ)} of the snapshot's files differ from upstream; run without --check"
            if differ
            else "The snapshot is current: upstream serves what it records."
        )
        return 1 if differ else 0
    write_snapshot(out, rows, render_fetched(rows, fetched))
    written = sum(1 for row in rows if row.content is not None)
    _log(f"Wrote {written} files and FETCHED.md under {out} (Fetched {fetched})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
