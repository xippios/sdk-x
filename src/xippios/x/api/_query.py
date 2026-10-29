"""Query values as the wrappers send them, checked against the OpenAPI document's bounds.

Each helper turns one parameter into the text X takes (a list comma-separated, as the
document's ``style: form`` with ``explode: false`` has it; a time in RFC 3339 with
``Z``) and refuses, before any request, a value outside the bounds the document gives
the parameter (``minItems``, ``maxItems``, ``pattern``, ``enum``, ``uniqueItems``,
``minimum``, ``maximum``, ``minLength``, ``maxLength``), or two parameters given where the
document allows "at most one of" them, with ``InvalidRequestError`` naming the parameter
(conventions §5).
"""

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum

from xippios.core import InvalidRequestError

from xippios.x._client import SOURCE

__all__ = ["at_most_one", "bounded", "chosen", "instant", "listed", "matching", "text"]


def _refuse(message: str) -> InvalidRequestError:
    return InvalidRequestError(message, source=SOURCE)


def listed(name: str, values: Sequence[str], *, max_items: int, pattern: re.Pattern[str]) -> str:
    """``values`` comma-separated: between 1 and ``max_items``, each matching ``pattern``.

    Raises:
        InvalidRequestError: ``values`` is one string, empty, too long, or holds a value
            that does not match.
    """
    if isinstance(values, str):
        raise _refuse(f"{name} is a list of values, e.g. [{values!r}], not one string")
    items = list(values)
    if not 1 <= len(items) <= max_items:
        raise _refuse(f"{name} takes 1 to {max_items} values, not {len(items)}")
    wrong = [item for item in items if not pattern.fullmatch(item)]
    if wrong:
        raise _refuse(f"{name}: {wrong[0]!r} does not match {pattern.pattern}")
    return ",".join(items)


def matching(name: str, value: str, pattern: re.Pattern[str]) -> str:
    """``value`` when it is a string matching ``pattern``, e.g. a User id for the path.

    Raises:
        InvalidRequestError: ``value`` is not a string or does not match.
    """
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise _refuse(f"{name}: {value!r} does not match {pattern.pattern}")
    return value


def chosen[E: StrEnum](name: str, values: Sequence[E], kind: type[E]) -> str:
    """``values``, members of ``kind``, comma-separated: at least one, none twice.

    Raises:
        InvalidRequestError: ``values`` is one string, empty, repeats a value, or holds
            one ``kind`` does not have; the message lists the valid values.
    """
    if isinstance(values, str):
        raise _refuse(f"{name} is a list of values, e.g. [{values!r}], not one string")
    items: list[str] = []
    for value in values:
        try:
            member = kind(value)
        except ValueError:
            valid = ", ".join(member.value for member in kind)
            raise _refuse(f"{name}: {value!r} is not one of {valid}") from None
        if member.value in items:
            raise _refuse(f"{name}: {member.value!r} is given twice")
        items.append(member.value)
    if not items:
        raise _refuse(f"{name} takes at least one value")
    return ",".join(items)


def bounded(name: str, value: int, *, low: int, high: int) -> str:
    """``value`` as text, when it lies between ``low`` and ``high``.

    Raises:
        InvalidRequestError: ``value`` is not an integer in that range.
    """
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise _refuse(f"{name} takes an integer from {low} to {high}, not {value!r}")
    return str(value)


def text(name: str, value: str, *, max_length: int | None = None) -> str:
    """``value`` when it is a non-empty string, at most ``max_length`` characters.

    Raises:
        InvalidRequestError: ``value`` is empty or too long.
    """
    if not isinstance(value, str) or not value:
        raise _refuse(f"{name} takes a non-empty string")
    if max_length is not None and len(value) > max_length:
        raise _refuse(f"{name} takes at most {max_length} characters, not {len(value)}")
    return value


def instant(name: str, value: datetime) -> str:
    """``value`` in UTC as RFC 3339 with ``Z``, e.g. ``2026-07-31T00:00:00Z``.

    Seconds when the time has no fraction of a second, else milliseconds
    (``2026-07-31T00:00:00.250Z``), the precision of X's own times.

    Raises:
        InvalidRequestError: ``value`` is not a datetime with a zone.
    """
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise _refuse(
            f"{name} takes a datetime with a zone, e.g. datetime(2026, 7, 31, tzinfo=UTC)"
        )
    moment = value.astimezone(UTC)
    if moment.microsecond:
        return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def at_most_one(**given: object) -> None:
    """Refuse two of ``given`` set where the document says "At most one of" them.

    E.g. ``at_most_one(next_token=..., pagination_token=...)``: the description of
    ``searchPostsRecent``, ``getPostsCountsRecent`` and ``getPostsCountsAll`` says "At most
    one of ``pagination_token``, ``next_token`` may be provided".

    Raises:
        InvalidRequestError: More than one of ``given`` is not ``None``.
    """
    if sum(value is not None for value in given.values()) > 1:
        raise _refuse(f"give {' or '.join(given)}, not both: at most one may be provided")
