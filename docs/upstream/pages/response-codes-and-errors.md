> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Response Codes & Errors

> Reference of HTTP status codes, error response formats, and common 400, 401, 403, 404, 429, and 500 errors returned by the X API for debugging.

The X API uses standard HTTP status codes. Successful requests return 2xx codes; errors return 4xx or 5xx codes with details in the response body.

***

## HTTP status codes

### Success codes

| Code | Meaning | Description |
| :- | :- | :- |
| **200** | OK | Request successful |
| **201** | Created | Resource created (POST requests) |
| **204** | No Content | Success with no response body (DELETE requests) |

### Client error codes

| Code | Meaning | Common causes |
| :- | :- | :- |
| **400** | Bad Request | Invalid JSON, malformed query, missing required parameters |
| **401** | Unauthorized | Invalid or missing authentication credentials |
| **403** | Forbidden | Valid auth but no permission for this resource or action |
| **404** | Not Found | Resource doesn't exist or has been deleted |
| **409** | Conflict | Stream has no rules (filtered stream only) |
| **429** | Too Many Requests | Rate limit or usage cap exceeded |

### Server error codes

| Code | Meaning | What to do |
| :- | :- | :- |
| **500** | Internal Server Error | Wait and retry; check [status page](https://developer.x.com/status) |
| **502** | Bad Gateway | Wait and retry |
| **503** | Service Unavailable | X is overloaded; wait and retry |
| **504** | Gateway Timeout | Wait and retry |

***

## Error response format

Error responses include structured details:

```json theme={null}
{
  "title": "Invalid Request",
  "detail": "The 'query' parameter is required.",
  "type": "https://api.x.com/2/problems/invalid-request"
}
```

| Field | Description |
| :- | :- |
| `type` | URI identifying the error type |
| `title` | Short error description |
| `detail` | Specific explanation for this error |

Additional fields may be present depending on the error type.

***

## Error types

| Type | Description |
| :- | :- |
| `about:blank` | Generic error (see HTTP status code) |
| `.../invalid-request` | Malformed request or invalid parameters |
| `.../resource-not-found` | Post, user, or other resource doesn't exist |
| `.../not-authorized-for-resource` | No access to private/protected content |
| `.../client-forbidden` | App not enrolled or lacks required access |
| `.../usage-capped` | Usage cap exceeded |
| `.../rate-limit-exceeded` | Rate limit exceeded |
| `.../streaming-connection` | Stream connection problem |
| `.../rule-cap` | Too many filtered stream rules |
| `.../invalid-rules` | Rule syntax error |
| `.../duplicate-rules` | Rule already exists |

***

## Partial errors

Some requests can partially succeed. A 200 response may include both `data` and `errors`:

```json title="Example response" lines wrap icon="https://mintcdn.com/x-preview/Vn2KEkZaPF9LiPi3/icons/xds/icon-brackets.svg?fit=max&auto=format&n=Vn2KEkZaPF9LiPi3&q=85&s=ed2428e77bab43e57800e1a590e982fa" theme={null}
{
  "data": [
    {"id": "123", "text": "Hello"}
  ],
  "errors": [
    {
      "resource_id": "456",
      "resource_type": "tweet",
      "title": "Not Found Error",
      "detail": "Could not find tweet with id: [456].",
      "type": "https://api.x.com/2/problems/resource-not-found"
    }
  ]
}
```

This happens when requesting multiple resources and some are unavailable.

***

## Troubleshooting common errors

> **401 Unauthorized**
>
> **Check your authentication:**
>
> * Verify you're using the correct authentication method for the endpoint
> * Ensure credentials haven't been regenerated
> * Check the `Authorization` header format
> * For OAuth 1.0a, verify signature calculation
>
> [Authentication guide →](https://docs.x.com/resources/fundamentals/authentication/overview.md)

> **403 Forbidden**
>
> **Check your access:**
>
> * Verify your app has access to this endpoint
> * Some endpoints require specific enrollment or approval
> * User-context endpoints need appropriate OAuth scopes
> * The resource may be private or protected

> **429 Too Many Requests**
>
> **Rate limited:**
>
> * Check `x-rate-limit-reset` header for when to retry
> * Implement exponential backoff
> * Consider caching responses
> * Spread requests across the time window
>
> [Rate limits guide →](https://docs.x.com/x-api/fundamentals/rate-limits.md)

> **400 Bad Request**
>
> **Fix your request:**
>
> * Validate JSON syntax
> * Check for missing required parameters
> * Verify parameter types (strings vs. numbers)
> * Escape special characters in queries

> **Missing expected posts**
>
> **Check these factors:**
>
> * Protected accounts' posts are only visible with authorization
> * Deleted posts return 404
> * Some posts are withheld in certain regions
> * Verify search query syntax is correct

> **Stream disconnections**
>
> **Handle reconnection:**
>
> * Implement automatic reconnect with backoff
> * Use recovery features for missed data
> * Check for full-buffer disconnects (client not consuming fast enough)
> * Verify at least one stream rule exists
>
> [Streaming guide →](https://docs.x.com/x-api/fundamentals/handling-disconnections.md)

***

## Rate limit headers

Every response includes rate limit information:

```
x-rate-limit-limit: 900
x-rate-limit-remaining: 847
x-rate-limit-reset: 1705420800
```

| Header | Description |
| :- | :- |
| `x-rate-limit-limit` | Max requests in current window |
| `x-rate-limit-remaining` | Requests remaining |
| `x-rate-limit-reset` | Unix timestamp when window resets |

***

## Best practices

> **Check status codes**
>
> Always check HTTP status before parsing the response body.

> **Handle partial errors**
>
> Check for `errors` array even in 200 responses.

> **Implement retry logic**
>
> Use exponential backoff for 429 and 5xx errors.

> **Log request details**
>
> Include request ID and timestamp for debugging.

***

## Getting help

When posting questions about errors, include:

* The API endpoint URL
* Request headers (sanitize credentials)
* Full error response
* What you expected to happen
* Steps you've tried

> **[Developer Forum](https://devcommunity.x.com)**
>
> Ask questions and search solutions.

> **[API Status](https://developer.x.com/status)**
>
> Check for known issues.
