- A paged task's `meta.request` keeps the paging token as sent, `next_token` of
  `search_recent_posts`, `count_posts` and `get_conversation_posts` and `pagination_token`
  of `get_user_posts` and `get_list_posts`, where it read `REDACTED`, so a page's meta says
  which page it is. The token is X's cursor, not a credential.
  (https://github.com/xippios/sdk-core/issues/184)
