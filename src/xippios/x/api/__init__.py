"""Endpoint wrappers, layer 1: one async function per upstream operation (conventions §2).

``/add-endpoint`` adds them. A module and its function carry the OpenAPI document's
``operationId`` in snake case (``getUsersByUsernames`` is ``get_users_by_usernames`` in
``get_users_by_usernames.py``); the verbatim id stays in the first line of each wrapper's
docstring and in the ``endpoint=`` it passes. Each returns one answer, one page, as the
document's response model; collecting pages is the task layer's. ``_query`` turns the
parameters into the text X takes and refuses values outside the document's bounds.
"""

from xippios.x.api.get_lists_members import get_lists_members
from xippios.x.api.get_lists_posts import get_lists_posts
from xippios.x.api.get_posts_by_ids import get_posts_by_ids
from xippios.x.api.get_posts_counts_all import get_posts_counts_all
from xippios.x.api.get_posts_counts_recent import get_posts_counts_recent
from xippios.x.api.get_usage import get_usage
from xippios.x.api.get_users_by_usernames import get_users_by_usernames
from xippios.x.api.get_users_posts import get_users_posts
from xippios.x.api.search_posts_recent import search_posts_recent

__all__ = [
    "get_lists_members",
    "get_lists_posts",
    "get_posts_by_ids",
    "get_posts_counts_all",
    "get_posts_counts_recent",
    "get_usage",
    "get_users_by_usernames",
    "get_users_posts",
    "search_posts_recent",
]
