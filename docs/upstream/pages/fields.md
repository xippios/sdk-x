> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Fields

> The X API v2 returns minimal data by default. Use fields parameters to request additional data for each object type. By default, a post lookup returns only.

The X API v2 returns minimal data by default. Use **fields parameters** to request additional data for each object type.

***

## How fields work

By default, a post lookup returns only `id`, `text`, and `edit_history_tweet_ids`. To get more data, add field parameters to your request:

```bash theme={null}
# Default response - minimal fields
curl "https://api.x.com/2/tweets/1234567890" \
  -H "Authorization: Bearer $TOKEN"

# With additional fields
curl "https://api.x.com/2/tweets/1234567890?tweet.fields=created_at,public_metrics,author_id" \
  -H "Authorization: Bearer $TOKEN"
```

***

## Available field parameters

Each object type has its own fields parameter:

| Object | Parameter | Documentation |
| :- | :- | :- |
| Post (Tweet) | `tweet.fields` | [Post fields](https://docs.x.com/x-api/fundamentals/data-dictionary/reference.md#tweet) |
| User | `user.fields` | [User fields](https://docs.x.com/x-api/fundamentals/data-dictionary/reference.md#user) |
| Media | `media.fields` | [Media fields](https://docs.x.com/x-api/fundamentals/data-dictionary/reference.md#media) |
| Poll | `poll.fields` | [Poll fields](https://docs.x.com/x-api/fundamentals/data-dictionary/reference.md#poll) |
| Place | `place.fields` | [Place fields](https://docs.x.com/x-api/fundamentals/data-dictionary/reference.md#place) |

***

## Example: Post fields

Request specific post fields with `tweet.fields`:

```bash theme={null}
curl "https://api.x.com/2/tweets/1234567890?tweet.fields=created_at,public_metrics,lang" \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json title="Example response" lines wrap icon="https://mintcdn.com/x-preview/Vn2KEkZaPF9LiPi3/icons/xds/icon-brackets.svg?fit=max&auto=format&n=Vn2KEkZaPF9LiPi3&q=85&s=ed2428e77bab43e57800e1a590e982fa" theme={null}
{
  "data": {
    "id": "1234567890",
    "text": "Hello world!",
    "edit_history_tweet_ids": ["1234567890"],
    "created_at": "2024-01-15T12:00:00.000Z",
    "lang": "en",
    "public_metrics": {
      "retweet_count": 10,
      "reply_count": 5,
      "like_count": 100,
      "quote_count": 2,
      "bookmark_count": 3,
      "impression_count": 1500
    }
  }
}
```

***

## Example: User fields

Request specific user fields with `user.fields`:

```bash theme={null}
curl "https://api.x.com/2/users/by/username/xdevelopers?user.fields=created_at,description,public_metrics" \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json title="Example response" lines wrap icon="https://mintcdn.com/x-preview/Vn2KEkZaPF9LiPi3/icons/xds/icon-brackets.svg?fit=max&auto=format&n=Vn2KEkZaPF9LiPi3&q=85&s=ed2428e77bab43e57800e1a590e982fa" theme={null}
{
  "data": {
    "id": "2244994945",
    "name": "X Developers",
    "username": "xdevelopers",
    "created_at": "2013-12-14T04:35:55.000Z",
    "description": "The voice of the X Developer Platform",
    "public_metrics": {
      "followers_count": 570842,
      "following_count": 2048,
      "tweet_count": 14052,
      "listed_count": 1672
    }
  }
}
```

***

## Fields for related objects

To get fields on related objects (like the author of a post), you need two things:

1. An **expansion** to include the related object
2. The **fields parameter** for that object type

```bash theme={null}
# Get post with author details
curl "https://api.x.com/2/tweets/1234567890?expansions=author_id&user.fields=description,public_metrics" \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json title="Example response" lines wrap icon="https://mintcdn.com/x-preview/Vn2KEkZaPF9LiPi3/icons/xds/icon-brackets.svg?fit=max&auto=format&n=Vn2KEkZaPF9LiPi3&q=85&s=ed2428e77bab43e57800e1a590e982fa" theme={null}
{
  "data": {
    "id": "1234567890",
    "text": "Hello world!",
    "author_id": "2244994945"
  },
  "includes": {
    "users": [{
      "id": "2244994945",
      "name": "X Developers",
      "username": "xdevelopers",
      "description": "The voice of the X Developer Platform",
      "public_metrics": {
        "followers_count": 570842,
        "following_count": 2048
      }
    }]
  }
}
```

[Learn more about expansions →](https://docs.x.com/x-api/fundamentals/expansions.md)

***

## Common field combinations

**Post analytics**

```
tweet.fields=created_at,public_metrics,possibly_sensitive
```

**User profiles**

```
user.fields=created_at,description,location,public_metrics,verified
```

**Full post context**

```
tweet.fields=created_at,author_id,conversation_id,in_reply_to_user_id,referenced_tweets
expansions=author_id,referenced_tweets.id
user.fields=username,name
```

**Media details**

```
tweet.fields=attachments
expansions=attachments.media_keys
media.fields=url,preview_image_url,alt_text,public_metrics
```

***

## Important notes

> [!WARNING]
>
> **You cannot request subfields.** When you request `public_metrics`, you get all metrics (likes, reposts, replies, quotes, bookmarks, impressions). You can't request just `public_metrics.like_count`.

* Field order in responses may differ from request order
* Missing fields in responses mean the value is `null` or empty
* Some fields require specific authentication (e.g., private metrics need user context)
* Check each endpoint's API reference for available fields

***

## Next steps

> **[Expansions](https://docs.x.com/x-api/fundamentals/expansions.md)**
>
> Include related objects in responses.

> **[Data Dictionary](https://docs.x.com/x-api/fundamentals/data-dictionary.md)**
>
> Complete field reference for all objects.
