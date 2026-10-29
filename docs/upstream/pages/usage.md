> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Usage

> The Usage endpoints let you monitor your API usage and, for Pay-per-use (PPU) accounts, check your credit balance. Reference for the X API v2 standard tier covering usage.

The Usage endpoint lets you monitor your API usage, including the number of Posts consumed. Track your usage programmatically to manage costs and stay within limits.

> [!NOTE]
>
> Pay-per-usage plans are subject to a monthly cap of 3 million Post reads. If you need higher volume, consider an [Enterprise plan](https://docs.x.com/forms/enterprise-api-interest.md).

## Overview

> **Post usage**
>
> Track Posts consumed

> **Daily breakdown**
>
> View usage by day

> **App-level**
>
> Monitor usage across your App

***

## Endpoints

| Method | Endpoint | Description |
| :- | :- | :- |
| GET | [`/2/usage/tweets`](https://docs.x.com/x-api/usage/get-usage) | Get Post usage data |
| GET | [`/2/usage/credits`](https://docs.x.com/x-api/usage/get-usage-credits) | Get your Pay-per-use (PPU) credit balance in USD |

***

## Response data

The response includes daily Post consumption counts:

```json title="Example response" lines wrap icon="https://mintcdn.com/x-preview/Vn2KEkZaPF9LiPi3/icons/xds/icon-brackets.svg?fit=max&auto=format&n=Vn2KEkZaPF9LiPi3&q=85&s=ed2428e77bab43e57800e1a590e982fa" theme={null}
{
  "data": {
    "daily_project_usage": [
      {
        "date": "2024-01-15",
        "usage": [
          {
            "app_id": "12345678",
            "tweets_consumed": 15420
          }
        ]
      }
    ],
    "project_id": "1234567890",
    "project_cap": 10000000
  }
}
```

### Fields

| Field | Description |
| :- | :- |
| `daily_project_usage` | Array of daily usage data |
| `date` | Date in YYYY-MM-DD format |
| `app_id` | Your App's ID |
| `tweets_consumed` | Posts consumed that day |
| `project_cap` | Your monthly Post limit |

***

## Example request

```bash theme={null}
curl "https://api.x.com/2/usage/tweets" \
  -H "Authorization: Bearer $BEARER_TOKEN"
```

***

## Use cases

* **Cost monitoring** — Track consumption against your budget
* **Alerting** — Set up alerts when approaching limits
* **Optimization** — Identify high-consumption endpoints
* **Reporting** — Generate usage reports

> [!TIP]
>
> Resources are deduplicated within a 24-hour UTC window, so requesting the same resource multiple times in a day only counts as one charge. [Learn more about pricing →](https://docs.x.com/x-api/getting-started/pricing.md)

***

## Getting started

> [!NOTE]
>
> **Prerequisites**
>
> * An approved [developer account](https://developer.x.com/en/portal/petition/essential/basic-info)
> * A [Project and App](https://docs.x.com/resources/fundamentals/developer-apps.md) in the Developer Console
> * Your App's [Bearer Token](https://docs.x.com/resources/fundamentals/authentication)

> **[API Reference](https://docs.x.com/x-api/usage/post-usage.md)**
>
> Full endpoint documentation

> **[Developer Console](https://developer.x.com/en/portal/dashboard)**
>
> View usage in the dashboard
