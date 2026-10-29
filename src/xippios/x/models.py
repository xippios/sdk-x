"""Pydantic models mirroring upstream's payloads, one ``UpstreamModel`` per object.

Conventions §3 and ``/add-endpoint`` give the rules.

The models mirror the schemas of the OpenAPI document in ``docs/upstream/openapi/
openapi.json`` (version 2.173) under its names: ``User``, ``Post``, ``Expansions``,
``Problem``, the four operations' responses and their parts. Every field the document
gives is a field here, optional unless the document requires it (``id`` of a ``User`` and
a ``Post`` is required too: it is the object's identifier, sent in every recorded answer).
Times parse to ``datetime``; the document's enumerations are ``StrEnum`` (ADR-0008),
written by hand below since ``enums.py`` holds only what the refresh script generates. An
object the document gives no properties for (``article``, ``non_public_metrics``), or
that no wrapper here requests yet (``entities``, ``context_annotations``, the ``media``,
``places``, ``polls``, ``topics`` and ``calls`` of ``includes``), is kept as sent, JSON
values under upstream's keys, so a page dumped with ``dump_upstream`` reads back whole.

Two spellings. The document writes ``post`` where X's guides write ``tweet``, and the wire
answers in either (recorded 2026-10-29, ``tests/fixtures/``): a request that carries
``post.fields`` is answered in the document's names (``most_recent_post_id``,
``includes.posts``, ``edit_history_post_ids``, ``repost_count``), one without it in the
guides' (``most_recent_tweet_id``, ``includes.tweets``, ``edit_history_tweet_ids``,
``tweet_count`` of a user's metrics; ``tweet_count`` and ``total_tweet_count`` of the
post counts, which take no ``post.fields``). Each such field carries the document's name
and accepts the guides' spelling through ``validation_alias`` (``AliasChoices``), the
document's first, so the fields keep one name whichever the wire sent and
``dump_upstream`` writes the document's. The guides' spellings are those of
``pages/fields.md``, ``pages/post-counts.md`` and the document's own older operations
(``note_tweet``, ``pinned_tweet_id``, ``referenced_tweets``).
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, Field
from xippios.core import UpstreamModel

__all__ = [
    "ConnectionStatus",
    "Expansions",
    "GetPostsByIdsResponse",
    "GetPostsByIdsResponseMeta",
    "GetPostsCountsAllResponse",
    "GetPostsCountsAllResponseData",
    "GetPostsCountsAllResponseMeta",
    "GetUsersByUsernamesResponse",
    "GetUsersPostsResponse",
    "GetUsersPostsResponseMeta",
    "Granularity",
    "Post",
    "PostAttachments",
    "PostEditControls",
    "PostExpansion",
    "PostField",
    "PostGeo",
    "PostNotePost",
    "PostPublicMetrics",
    "PostReferencedPost",
    "PostScopes",
    "PostWithheld",
    "PostWithheldScope",
    "Problem",
    "ReferencedPostType",
    "User",
    "UserAffiliation",
    "UserExpansion",
    "UserField",
    "UserPublicMetrics",
    "UserSubscription",
    "UserWithheld",
    "UserWithheldScope",
]


def _either(name: str, guides: str) -> AliasChoices:
    """The document's name first, then the guides' spelling the wire may answer in."""
    return AliasChoices(name, guides)


# The enumerations below are the OpenAPI document's, written by hand: the parameters'
# enums (components.parameters UserFieldsParameter, UserExpansionsParameter,
# PostFieldsParameter, PostExpansionsParameter, the granularity of getPostsCountsAll) and
# the schemas' (PostReferencedPosts, UserWithheld, PostWithheld, UserConnectionStatus).
# The adapters publish each class docstring as the schema's description, so it names the
# upstream list and the snapshot it comes from (conventions §8, ADR-0008).


class UserField(StrEnum):
    """A field of a User for ``user.fields``, e.g. "created_at", "public_metrics".

    Values of ``UserFieldsParameter`` in X API v2's OpenAPI document, version 2.173, snapshot of
    2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    ACTIVE_FOLLOWER_COUNT = "active_follower_count"
    CONFIRMED_EMAIL = "confirmed_email"
    CONNECTION_STATUS = "connection_status"
    CREATED_AT = "created_at"
    DESCRIPTION = "description"
    ENTITIES = "entities"
    ID = "id"
    IS_IDENTITY_VERIFIED = "is_identity_verified"
    LOCATION = "location"
    NAME = "name"
    PARODY = "parody"
    PROFILE_BANNER_URL = "profile_banner_url"
    PROFILE_IMAGE_URL = "profile_image_url"
    PROTECTED = "protected"
    PUBLIC_METRICS = "public_metrics"
    RECEIVES_YOUR_DM = "receives_your_dm"
    SUBSCRIBER_COUNT = "subscriber_count"
    SUBSCRIBES_TO_YOU = "subscribes_to_you"
    SUBSCRIPTION = "subscription"
    SUBSCRIPTION_TYPE = "subscription_type"
    URL = "url"
    USERNAME = "username"
    VERIFIED = "verified"
    VERIFIED_FOLLOWERS_COUNT = "verified_followers_count"
    VERIFIED_TYPE = "verified_type"
    WITHHELD = "withheld"


class UserExpansion(StrEnum):
    """An expansion of a User lookup, e.g. "most_recent_post_id" (the Post into includes).

    Values of ``UserExpansionsParameter`` in X API v2's OpenAPI document, version 2.173,
    snapshot of 2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    AFFILIATION = "affiliation"
    MOST_RECENT_POST_ID = "most_recent_post_id"
    PINNED_POST_ID = "pinned_post_id"


class PostField(StrEnum):
    """A field of a Post for ``post.fields``, e.g. "created_at", "lang", "public_metrics".

    Values of ``PostFieldsParameter`` in X API v2's OpenAPI document, version 2.173, snapshot of
    2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    ARTICLE = "article"
    ARTICLE_TITLE = "article_title"
    ATTACHMENTS = "attachments"
    CARD_URI = "card_uri"
    COMMUNITY_ID = "community_id"
    CONTEXT_ANNOTATIONS = "context_annotations"
    CONVERSATION_ID = "conversation_id"
    CREATED_AT = "created_at"
    DISPLAY_TEXT_RANGE = "display_text_range"
    EDIT_CONTROLS = "edit_controls"
    ENTITIES = "entities"
    GEO = "geo"
    ID = "id"
    LANG = "lang"
    MATCHED_MEDIA_NOTES = "matched_media_notes"
    MEDIA_METADATA = "media_metadata"
    NON_PUBLIC_METRICS = "non_public_metrics"
    NOTE_POST = "note_post"
    NOTE_REQUEST_SUGGESTIONS = "note_request_suggestions"
    ORGANIC_METRICS = "organic_metrics"
    PAID_PARTNERSHIP = "paid_partnership"
    POSSIBLY_SENSITIVE = "possibly_sensitive"
    PROMOTED_METRICS = "promoted_metrics"
    PUBLIC_METRICS = "public_metrics"
    REPLY_SETTINGS = "reply_settings"
    SCOPES = "scopes"
    SOURCE = "source"
    SUGGESTED_SOURCE_LINKS = "suggested_source_links"
    SUGGESTED_SOURCE_LINKS_WITH_COUNTS = "suggested_source_links_with_counts"
    TEXT = "text"
    WITHHELD = "withheld"


class PostExpansion(StrEnum):
    """An expansion of a Post lookup, e.g. "referenced_posts", "author_id".

    Values of ``PostExpansionsParameter`` in X API v2's OpenAPI document, version 2.173,
    snapshot of 2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    ARTICLE_COVER_MEDIA = "article.cover_media"
    ARTICLE_MEDIA_ENTITIES = "article.media_entities"
    ATTACHMENTS_MEDIA_KEYS = "attachments.media_keys"
    ATTACHMENTS_MEDIA_SOURCE_TWEET = "attachments.media_source_tweet"
    ATTACHMENTS_POLL_IDS = "attachments.poll_ids"
    AUTHOR_ID = "author_id"
    EDIT_HISTORY_POST_IDS = "edit_history_post_ids"
    ENTITIES_MENTIONS_USERNAME = "entities.mentions.username"
    GEO_PLACE_ID = "geo.place_id"
    IN_REPLY_TO_USER_ID = "in_reply_to_user_id"
    REFERENCED_POSTS = "referenced_posts"
    USERNAME = "username"


class Granularity(StrEnum):
    """The bucket of a post count: "minute", "hour" (upstream's default) or "day".

    Values of the ``granularity`` parameter of ``getPostsCountsAll`` in X API v2's OpenAPI
    document, version 2.173, snapshot of 2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


class ReferencedPostType(StrEnum):
    """How a Post references another: "retweeted", "quoted" or "replied_to".

    Values of the ``type`` of each ``PostReferencedPosts`` item in X API v2's OpenAPI document,
    version 2.173, snapshot of 2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    RETWEETED = "retweeted"
    QUOTED = "quoted"
    REPLIED_TO = "replied_to"


class PostWithheldScope(StrEnum):
    """What a Post's withholding applies to: "post" or "user".

    Values of the ``scope`` of ``PostWithheld`` in X API v2's OpenAPI document, version 2.173,
    snapshot of 2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    POST = "post"
    USER = "user"


class UserWithheldScope(StrEnum):
    """What a User's withholding applies to: "user", the whole User.

    Values of the ``scope`` of ``UserWithheld`` in X API v2's OpenAPI document, version 2.173,
    snapshot of 2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    USER = "user"


class ConnectionStatus(StrEnum):
    """A connection between the authenticated User and a User, e.g. "following".

    Values of the items of ``UserConnectionStatus`` in X API v2's OpenAPI document, version
    2.173, snapshot of 2026-10-29 (``docs/upstream/openapi/openapi.json``).
    """

    BLOCKING = "blocking"
    FOLLOW_REQUEST_RECEIVED = "follow_request_received"
    FOLLOW_REQUEST_SENT = "follow_request_sent"
    FOLLOWED_BY = "followed_by"
    FOLLOWING = "following"
    MUTING = "muting"


class UserPublicMetrics(UpstreamModel):
    """``UserPublicMetrics``: a User's counts at the time of the request.

    Attributes:
        followers_count: Users who follow this User.
        following_count: Users this User follows.
        post_count: Posts (Reposts included) this User created; ``tweet_count`` on the
            wire when the request carries no ``post.fields``.
        listed_count: Lists that include this User.
        like_count: Posts this User liked.
        media_count: Media items this User posted.
    """

    followers_count: int
    following_count: int
    post_count: int = Field(validation_alias=_either("post_count", "tweet_count"))
    listed_count: int
    like_count: int | None = None
    media_count: int | None = None


class UserWithheld(UpstreamModel):
    """``UserWithheld``: where a User is withheld.

    Attributes:
        country_codes: ISO 3166-1 alpha-2 codes, e.g. ``["DE"]``.
        scope: ``user`` when the whole User is withheld.
    """

    country_codes: list[str] | None = None
    scope: UserWithheldScope | None = None


class UserAffiliation(UpstreamModel):
    """``UserAffiliation``: the affiliation badge on a User's profile.

    Attributes:
        badge_url: The badge image's URL.
        description: The affiliation's description.
        url: The affiliation's URL.
        user_id: Ids of the accounts this User is affiliated with.
    """

    badge_url: str | None = None
    description: str | None = None
    url: str | None = None
    user_id: list[str] | None = None


class UserSubscription(UpstreamModel):
    """``UserSubscription``: whether this User subscribes to the authenticated User.

    Attributes:
        subscribes_to_you: True when this User subscribes to you.
    """

    subscribes_to_you: bool


class User(UpstreamModel):
    """``User``: an X account as the requested ``user.fields`` describe it.

    Attributes:
        id: The User's id, e.g. ``"61853389"``.
        name: The name shown on the profile.
        username: The handle, e.g. ``"USDA"``.
        created_at: When the account was created.
        description: The profile's bio.
        location: The profile's free-form location.
        url: The URL in the profile.
        protected: True when the User's Posts are private.
        verified: True for a verified User.
        verified_type: e.g. ``"government"``, ``"business"``, ``"blue"``, ``"none"``.
        public_metrics: Followers, following, posts, lists, likes, media.
        most_recent_post_id: The id of the User's most recent Post;
            ``most_recent_tweet_id`` on the wire without ``post.fields``.
        pinned_post_id: The id of the pinned Post; ``pinned_tweet_id`` likewise.
        entities: The entities of the profile, kept as sent.
        withheld: Where the User is withheld.
        affiliation: The affiliation badge.
        connection_status: Connections to the authenticated User.
        subscription: Whether this User subscribes to you.
        subscription_type: e.g. ``"Premium"``.
        profile_image_url: The profile image's URL.
        profile_banner_url: The profile banner's URL.
        parody: True for a parody account.
        is_identity_verified: True when the User completed identity verification.
        receives_your_dm: True when you can send this User a DM.
        subscribes_to_you: True when this User subscribes to you.
        confirmed_email: The authenticated User's e-mail address.
        active_follower_count: Followers active in the last 24 hours.
        subscriber_count: Premium subscribers of this User.
        verified_followers_count: Verified followers of this User.
    """

    id: str
    name: str | None = None
    username: str | None = None
    created_at: datetime | None = None
    description: str | None = None
    location: str | None = None
    url: str | None = None
    protected: bool | None = None
    verified: bool | None = None
    verified_type: str | None = None
    public_metrics: UserPublicMetrics | None = None
    most_recent_post_id: str | None = Field(
        default=None, validation_alias=_either("most_recent_post_id", "most_recent_tweet_id")
    )
    pinned_post_id: str | None = Field(
        default=None, validation_alias=_either("pinned_post_id", "pinned_tweet_id")
    )
    entities: dict[str, Any] | None = None
    withheld: UserWithheld | None = None
    affiliation: UserAffiliation | None = None
    connection_status: list[ConnectionStatus] | None = None
    subscription: UserSubscription | None = None
    subscription_type: str | None = None
    profile_image_url: str | None = None
    profile_banner_url: str | None = None
    parody: bool | None = None
    is_identity_verified: bool | None = None
    receives_your_dm: bool | None = None
    subscribes_to_you: bool | None = None
    confirmed_email: str | None = None
    active_follower_count: int | None = None
    subscriber_count: int | None = None
    verified_followers_count: int | None = None


class PostPublicMetrics(UpstreamModel):
    """``PostPublicMetrics``: a Post's engagement at the time of the request.

    Attributes:
        repost_count: Reposts; ``retweet_count`` on the wire without ``post.fields``.
        reply_count: Replies.
        like_count: Likes.
        quote_count: Quote Posts.
        bookmark_count: Bookmarks.
        impression_count: Views.
    """

    repost_count: int = Field(validation_alias=_either("repost_count", "retweet_count"))
    reply_count: int
    like_count: int
    quote_count: int
    bookmark_count: int
    impression_count: int


class PostReferencedPost(UpstreamModel):
    """An item of ``PostReferencedPosts``: a Post this Post reposts, quotes or replies to.

    Attributes:
        id: The referenced Post's id.
        type: ``retweeted``, ``quoted`` or ``replied_to``.
    """

    id: str
    type: ReferencedPostType


class PostAttachments(UpstreamModel):
    """``PostAttachments``: the media and polls attached to a Post.

    Attributes:
        media_keys: Keys of the attached media.
        media_source_tweet_id: Ids of the Posts the media came from.
        poll_ids: Ids of the attached polls.
    """

    media_keys: list[str] | None = None
    media_source_tweet_id: list[str] | None = None
    poll_ids: list[str] | None = None


class PostGeo(UpstreamModel):
    """``PostGeo``: the location tagged on a Post.

    Attributes:
        coordinates: A GeoJSON Point, kept as sent.
        place_id: The tagged place's id.
    """

    coordinates: dict[str, Any] | None = None
    place_id: str | None = None


class PostEditControls(UpstreamModel):
    """``PostEditControls``: how much longer a Post can be edited.

    Attributes:
        editable_until: Until when the Post can be edited.
        edits_remaining: Edits still allowed.
        is_edit_eligible: True when the Post can be edited.
    """

    editable_until: datetime | None = None
    edits_remaining: int | None = None
    is_edit_eligible: bool | None = None


class PostScopes(UpstreamModel):
    """``PostScopes``: who can see a Post.

    Attributes:
        followers: True when only the author's followers can see it.
    """

    followers: bool


class PostWithheld(UpstreamModel):
    """``PostWithheld``: where a Post is withheld.

    Attributes:
        copyright: True when withheld for a copyright claim.
        country_codes: ISO 3166-1 alpha-2 codes, e.g. ``["DE"]``.
        scope: ``post`` or ``user``.
    """

    copyright: bool
    country_codes: list[str]
    scope: PostWithheldScope | None = None


class PostNotePost(UpstreamModel):
    """``PostNotePost``: the whole text of a Post longer than 280 characters.

    Attributes:
        text: The full text.
        entities: Its entities, kept as sent.
    """

    text: str
    entities: dict[str, Any] | None = None


class Post(UpstreamModel):
    """``Post``: a Post as the requested ``post.fields`` describe it.

    Attributes:
        id: The Post's id, e.g. ``"2115806101480337475"``.
        text: The Post's text.
        edit_history_post_ids: Ids of the Post's edit history, oldest first;
            ``edit_history_tweet_ids`` on the wire without ``post.fields``.
        created_at: When the Post was created.
        author_id: The author's User id.
        conversation_id: The id of the conversation's root Post.
        in_reply_to_user_id: The User this Post replies to.
        lang: The detected language, a BCP 47 tag such as ``"en"``.
        public_metrics: Reposts, replies, likes, quotes, bookmarks, views.
        referenced_posts: The Posts this Post reposts, quotes or replies to;
            ``referenced_tweets`` on the wire without ``post.fields``.
        note_post: The whole text of a long Post; ``note_tweet`` likewise.
        attachments: Media and polls attached.
        geo: The location tagged.
        edit_controls: How much longer the Post can be edited.
        scopes: Who can see the Post.
        withheld: Where the Post is withheld.
        possibly_sensitive: True when its URLs are marked sensitive.
        paid_partnership: True for a disclosed paid promotion.
        reply_settings: Who can reply.
        source: The app the Post was sent from (deprecated upstream).
        card_uri: The card's URI.
        community_id: The Community the Post belongs to.
        username: The author's handle.
        display_text_range: Start and end of the displayable text.
        entities: Hashtags, mentions and URLs in the text, kept as sent.
        context_annotations: Inferred domains and entities, kept as sent.
        matched_media_notes: Community Notes media matches, kept as sent.
        media_metadata: Metadata of the attached media, kept as sent.
        note_request_suggestions: Community Notes request suggestions, kept as sent.
        suggested_source_links: Suggested source URLs.
        suggested_source_links_with_counts: The same with counts, kept as sent.
        article: The attached Article, kept as sent.
        article_title: The Article's title metadata, kept as sent.
        non_public_metrics: Non-public metrics, kept as sent.
        organic_metrics: Organic metrics, kept as sent.
        promoted_metrics: Promoted metrics, kept as sent.
    """

    id: str
    text: str | None = None
    edit_history_post_ids: list[str] | None = Field(
        default=None, validation_alias=_either("edit_history_post_ids", "edit_history_tweet_ids")
    )
    created_at: datetime | None = None
    author_id: str | None = None
    conversation_id: str | None = None
    in_reply_to_user_id: str | None = None
    lang: str | None = None
    public_metrics: PostPublicMetrics | None = None
    referenced_posts: list[PostReferencedPost] | None = Field(
        default=None, validation_alias=_either("referenced_posts", "referenced_tweets")
    )
    note_post: PostNotePost | None = Field(
        default=None, validation_alias=_either("note_post", "note_tweet")
    )
    attachments: PostAttachments | None = None
    geo: PostGeo | None = None
    edit_controls: PostEditControls | None = None
    scopes: PostScopes | None = None
    withheld: PostWithheld | None = None
    possibly_sensitive: bool | None = None
    paid_partnership: bool | None = None
    reply_settings: str | None = None
    source: str | None = None
    card_uri: str | None = None
    community_id: str | None = None
    username: str | None = None
    display_text_range: list[int] | None = None
    entities: dict[str, Any] | None = None
    context_annotations: list[dict[str, Any]] | None = None
    matched_media_notes: list[dict[str, Any]] | None = None
    media_metadata: list[dict[str, Any]] | None = None
    note_request_suggestions: list[dict[str, Any]] | None = None
    suggested_source_links: list[str] | None = None
    suggested_source_links_with_counts: list[dict[str, Any]] | None = None
    article: dict[str, Any] | None = None
    article_title: dict[str, Any] | None = None
    non_public_metrics: dict[str, Any] | None = None
    organic_metrics: dict[str, Any] | None = None
    promoted_metrics: dict[str, Any] | None = None


class Expansions(UpstreamModel):
    """``Expansions``: the objects an answer's ``includes`` carries for its expansions.

    Attributes:
        users: Expanded Users.
        posts: Expanded Posts; ``tweets`` on the wire without ``post.fields``.
        media: Expanded media, kept as sent.
        places: Expanded places, kept as sent.
        polls: Expanded polls, kept as sent.
        topics: Expanded topics, kept as sent.
        calls: Expanded calls, kept as sent.
    """

    users: list[User] | None = None
    posts: list[Post] | None = Field(default=None, validation_alias=_either("posts", "tweets"))
    media: list[dict[str, Any]] | None = None
    places: list[dict[str, Any]] | None = None
    polls: list[dict[str, Any]] | None = None
    topics: list[dict[str, Any]] | None = None
    calls: list[dict[str, Any]] | None = None


class Problem(UpstreamModel):
    """``Problem``: one error of an answer, beside its ``data`` or instead of it.

    The document's problem types share these fields; ``type`` tells them apart, e.g.
    ``https://api.x.com/2/problems/resource-not-found`` for a username or an id X does
    not find (``pages/response-codes-and-errors.md``, "Partial errors").

    Attributes:
        type: The problem type's URI.
        title: Its short title, e.g. ``"Not Found Error"``.
        detail: What went wrong, e.g. ``"Could not find user with usernames: [...]."``.
        status: The HTTP status, when sent.
        parameter: The request parameter it concerns, e.g. ``"usernames"``.
        value: The value of that parameter it concerns.
        resource_id: The resource's id or name.
        resource_type: e.g. ``"user"``, ``"tweet"``.
        section: The answer's section it concerns.
        field: The field it concerns.
        id: An id the problem names.
        details: Further details.
    """

    type: str
    title: str
    detail: str
    status: int | None = None
    parameter: str | None = None
    value: str | None = None
    resource_id: str | None = None
    resource_type: str | None = None
    section: str | None = None
    field: str | None = None
    id: str | None = None
    details: list[str] | None = None


class GetUsersByUsernamesResponse(UpstreamModel):
    """``GetUsersByUsernamesResponse``: one answer of ``getUsersByUsernames``.

    Attributes:
        data: The Users found, in no order the document states.
        includes: The expanded objects, e.g. each User's most recent Post.
        errors: A problem for each username not found or not available.
    """

    data: list[User] | None = None
    includes: Expansions | None = None
    errors: list[Problem] | None = None


class GetPostsByIdsResponseMeta(UpstreamModel):
    """The ``meta`` of ``GetPostsByIdsResponse``.

    Attributes:
        result_count: The number of items in ``data``.
    """

    result_count: int | None = None


class GetPostsByIdsResponse(UpstreamModel):
    """``GetPostsByIdsResponse``: one answer of ``getPostsByIds``.

    Attributes:
        data: The Posts found.
        includes: The expanded objects, e.g. the Posts they reference.
        errors: A problem for each id not found or not available.
        meta: ``result_count``.
    """

    data: list[Post] | None = None
    includes: Expansions | None = None
    errors: list[Problem] | None = None
    meta: GetPostsByIdsResponseMeta | None = None


class GetUsersPostsResponseMeta(UpstreamModel):
    """The ``meta`` of ``GetUsersPostsResponse``.

    Attributes:
        result_count: The number of items in ``data``.
        newest_id: The most recent id in ``data``.
        oldest_id: The oldest id in ``data``.
        next_token: The ``pagination_token`` of the next page; absent on the last.
        previous_token: The ``pagination_token`` of the previous page.
    """

    result_count: int | None = None
    newest_id: str | None = None
    oldest_id: str | None = None
    next_token: str | None = None
    previous_token: str | None = None


class GetUsersPostsResponse(UpstreamModel):
    """``GetUsersPostsResponse``: one page of ``getUsersPosts``, newest first.

    Attributes:
        data: The User's Posts on this page.
        includes: The expanded objects.
        errors: Problems, e.g. the User not found, then without ``data``.
        meta: The page's counts, ids and tokens.
    """

    data: list[Post] | None = None
    includes: Expansions | None = None
    errors: list[Problem] | None = None
    meta: GetUsersPostsResponseMeta | None = None


class GetPostsCountsAllResponseData(UpstreamModel):
    """``GetPostsCountsAllResponseData``: the Posts matching the query in one bucket.

    Attributes:
        start: The bucket's start, inclusive.
        end: The bucket's end, exclusive.
        post_count: Posts in the bucket; ``tweet_count`` on the wire.
    """

    start: datetime
    end: datetime
    post_count: int = Field(validation_alias=_either("post_count", "tweet_count"))


class GetPostsCountsAllResponseMeta(UpstreamModel):
    """The ``meta`` of ``GetPostsCountsAllResponse``.

    Attributes:
        next_token: The ``next_token`` of the next page, 31 days earlier; absent on the last.
        total_post_count: Posts across this page's buckets; ``total_tweet_count`` on the wire.
    """

    next_token: str | None = None
    total_post_count: int | None = Field(
        default=None, validation_alias=_either("total_post_count", "total_tweet_count")
    )


class GetPostsCountsAllResponse(UpstreamModel):
    """``GetPostsCountsAllResponse``: one page of ``getPostsCountsAll``.

    Attributes:
        data: The buckets, oldest first within the page.
        errors: Problems, when X sends any beside the counts.
        meta: The page's total and the token of the next page.
    """

    data: list[GetPostsCountsAllResponseData] | None = None
    errors: list[Problem] | None = None
    meta: GetPostsCountsAllResponseMeta | None = None
