> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Post Counts

> The Post counts endpoints return the volume of Posts matching a query over time, without returning. Reference for the X API v2 standard tier covering counts.

The Post counts endpoints return the volume of Posts matching a query over time, without returning the Posts themselves. Use these endpoints to analyze trends, understand conversation size, and refine queries before searching.

## Overview

> **Volume analysis**
>
> Build trendlines and visualizations showing Post volume over time

> **Query refinement**
>
> Estimate result size before running full search queries

> **Event detection**
>
> Identify when conversations peaked around events

> **Efficient research**
>
> Understand conversation scale without retrieving all Posts

***

## Endpoints

| Endpoint | Description | Access |
| :- | :- | :- |
| GET [`/2/tweets/counts/recent`](https://docs.x.com/x-api/posts/get-count-of-recent-posts) | Count Posts from last 7 days | All developers |
| GET [`/2/tweets/counts/all`](https://docs.x.com/x-api/posts/get-count-of-all-posts) | Count Posts from complete archive | Pay-per-use, Enterprise |

***

## Granularity options

Specify how counts are grouped using the `granularity` parameter:

| Granularity | Description | Use case |
| :- | :- | :- |
| `minute` | Counts per minute | Real-time monitoring |
| `hour` | Counts per hour (default) | Daily analysis |
| `day` | Counts per day | Long-term trends |

***

## Recent counts

Count Posts from the **last 7 days**. Available to all developers.

### Features

* Counts grouped by minute, hour, or day
* Same query operators as recent search
* 512-character query length

### Example response

```json theme={null}
{
  "data": [
    { "start": "2024-01-15T00:00:00.000Z", "end": "2024-01-15T01:00:00.000Z", "tweet_count": 1523 },
    { "start": "2024-01-15T01:00:00.000Z", "end": "2024-01-15T02:00:00.000Z", "tweet_count": 1247 },
    { "start": "2024-01-15T02:00:00.000Z", "end": "2024-01-15T03:00:00.000Z", "tweet_count": 892 }
  ],
  "meta": {
    "total_tweet_count": 3662
  }
}
```

> **[Quickstart](https://docs.x.com/x-api/posts/counts/quickstart/recent-tweet-counts.md)**
>
> Make your first recent counts request

> **[API Reference](https://docs.x.com/x-api/posts/get-count-of-recent-posts.md)**
>
> Full endpoint documentation

***

## Full-archive counts

Count Posts from the **complete archive** back to 2006.

> [!NOTE]
>
> Full-archive counts are available to pay-per-use and Enterprise customers.

### Features

* Count historical Posts from any time period
* All query operators available
* 1,024-character query length (4,096 for Enterprise)

### Pagination

Results paginate at 31 days per response:

* **Day granularity**: 31 days per page
* **Hour granularity**: 744 hours (31 days) per page
* **Minute granularity**: 44,640 minutes (31 days) per page

> **[Quickstart](https://docs.x.com/x-api/posts/counts/quickstart/full-archive-tweet-counts.md)**
>
> Make your first full-archive counts request

> **[API Reference](https://docs.x.com/x-api/posts/get-count-of-all-posts.md)**
>
> Full endpoint documentation

***

## Query operators

Post counts use the same query syntax as search endpoints:

```
python lang:en -is:retweet
```

> **[Build a query](https://docs.x.com/x-api/posts/counts/integrate/build-a-query.md)**
>
> Learn query syntax and operators

***

## Important notes

> [!NOTE]
>
> **Counts vs search results**
>
> Counts may not exactly match search results. Search endpoints apply additional compliance filtering that counts endpoints do not perform.

***

## Getting started

> [!NOTE]
>
> **Prerequisites**
>
> * An approved [developer account](https://developer.x.com/en/portal/petition/essential/basic-info)
> * A [Project and App](https://docs.x.com/resources/fundamentals/developer-apps.md) in the Developer Console
> * Your App's [Bearer Token](https://docs.x.com/resources/fundamentals/authentication)

> **[Recent counts quickstart](https://docs.x.com/x-api/posts/counts/quickstart/recent-tweet-counts.md)**
>
> Count Posts from the last 7 days

> **[Full-archive quickstart](https://docs.x.com/x-api/posts/counts/quickstart/full-archive-tweet-counts.md)**
>
> Count historical Posts

> **[Integration guide](https://docs.x.com/x-api/posts/counts/integrate/overview.md)**
>
> Key concepts and best practices

> **[Sample code](https://github.com/xdevplatform/Twitter-API-v2-sample-code)**
>
> Working code examples
