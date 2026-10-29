> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Pagination

> Page through X API v2 results using next_token and previous_token cursors in the meta object to retrieve every result across multiple requests.

When an API response contains more results than can be returned at once, use pagination to retrieve all pages of data.

***

## How pagination works

1. Make your initial request with `max_results`
2. Check the response for a `next_token` in the `meta` object
3. If present, make another request with that token as `pagination_token`
4. Repeat until no `next_token` is returned

```bash theme={null}
# Initial request
curl "https://api.x.com/2/users/12345/tweets?max_results=100" \
  -H "Authorization: Bearer $TOKEN"

# Response includes next_token
# {"data": [...], "meta": {"next_token": "abc123", ...}}

# Next page
curl "https://api.x.com/2/users/12345/tweets?max_results=100&pagination_token=abc123" \
  -H "Authorization: Bearer $TOKEN"
```

***

## Pagination tokens

| Token | Description |
| :- | :- |
| `next_token` | In response `meta`. Use to get the next page. |
| `previous_token` | In response `meta`. Use to go back a page. |
| `pagination_token` | Request parameter. Set to `next_token` or `previous_token` value. |

***

## Response structure

```json theme={null}
{
  "data": [
    {"id": "1234", "text": "..."},
    {"id": "1235", "text": "..."}
  ],
  "meta": {
    "result_count": 100,
    "next_token": "7140w9gefhslx3",
    "previous_token": "77qp89slxjd"
  }
}
```

When there are no more results, `next_token` is omitted:

```json theme={null}
{
  "data": [...],
  "meta": {
    "result_count": 42,
    "previous_token": "77qp89abc"
  }
}
```

***

## Pagination parameters

| Parameter | Description | Default |
| :- | :- | :- |
| `max_results` | Results per page | Endpoint-specific |
| `pagination_token` | Token from previous response | None |

Check each endpoint's API reference for specific `max_results` limits.

***

## Example: Paginating through all results

**Python**

```python title="Example" lines wrap icon="python" theme={null}
import requests

def get_all_tweets(user_id, bearer_token):
    url = f"https://api.x.com/2/users/{user_id}/tweets"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {"max_results": 100}
    
    all_tweets = []
    
    while True:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        if "data" in data:
            all_tweets.extend(data["data"])
        
        # Check for next page
        next_token = data.get("meta", {}).get("next_token")
        if not next_token:
            break
            
        params["pagination_token"] = next_token
    
    return all_tweets
```

**JavaScript**

```javascript title="Example" expandable lines wrap icon="square-js" theme={null}
async function getAllTweets(userId, bearerToken) {
  const url = `https://api.x.com/2/users/${userId}/tweets`;
  const headers = { Authorization: `Bearer ${bearerToken}` };
  
  let allTweets = [];
  let paginationToken = null;
  
  do {
    const params = new URLSearchParams({ max_results: 100 });
    if (paginationToken) {
      params.set("pagination_token", paginationToken);
    }
    
    const response = await fetch(`${url}?${params}`, { headers });
    const data = await response.json();
    
    if (data.data) {
      allTweets.push(...data.data);
    }
    
    paginationToken = data.meta?.next_token;
  } while (paginationToken);
  
  return allTweets;
}
```

***

## Best practices

> **Use max results**
>
> Request the maximum allowed `max_results` to minimize API calls.

> **Handle partial pages**
>
> The last page may have fewer results than `max_results`.

> **Store tokens**
>
> Save `next_token` if you need to resume pagination later.

> **Don't poll with pagination**
>
> For new data, use `since_id` instead of paginating repeatedly.

***

## Result ordering

Results are returned in **reverse chronological order**:

* First result on first page = most recent
* Last result on last page = oldest

This applies within and across pages.

***

## Notes

* Pagination tokens are opaque strings—don't parse or modify them
* Tokens may expire after some time
* If you get fewer results than `max_results`, more may still exist (continue until no `next_token`)
* Use [SDKs](https://docs.x.com/tools-and-libraries.md) for automatic pagination handling

***

## Next steps

> **[Rate limits](https://docs.x.com/x-api/fundamentals/rate-limits.md)**
>
> Understand request limits when paginating.

> **[SDKs](https://docs.x.com/tools-and-libraries.md)**
>
> Libraries with built-in pagination.
