"""Public API: ``__version__`` and the task functions re-exported here (conventions §2).

Upstream: X API v2. Each task returns ``Result[T]``, ``T`` the page X answers with, whose
models are re-exported too, with the parameter enum ``Granularity``; the endpoint wrappers
are ``xippios.x.api``.
"""

from xippios.x._version import __version__
from xippios.x.models import (
    GetListsPostsResponse,
    GetPostsCountsAllResponse,
    GetUsageResponse,
    GetUsersByUsernamesResponse,
    GetUsersPostsResponse,
    Granularity,
    Post,
    Problem,
    SearchPostsRecentResponse,
    Usage,
    User,
)
from xippios.x.tasks import (
    count_posts,
    get_conversation_posts,
    get_list_posts,
    get_usage,
    get_user_posts,
    lookup_users,
    search_recent_posts,
)

__all__ = [
    "GetListsPostsResponse",
    "GetPostsCountsAllResponse",
    "GetUsageResponse",
    "GetUsersByUsernamesResponse",
    "GetUsersPostsResponse",
    "Granularity",
    "Post",
    "Problem",
    "SearchPostsRecentResponse",
    "Usage",
    "User",
    "__version__",
    "count_posts",
    "get_conversation_posts",
    "get_list_posts",
    "get_usage",
    "get_user_posts",
    "lookup_users",
    "search_recent_posts",
]
