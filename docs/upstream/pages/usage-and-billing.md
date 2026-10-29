> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Usage and Billing

> X API v2 uses pay-per-usage pricing. You're charged based on actual API consumption, tracked at the app level. Pay-per-usage plans are subject to a monthly.

X API v2 uses **pay-per-usage** pricing. You're charged based on actual API consumption, tracked at the app level.

***

## How billing works

| Concept | Description |
| :- | :- |
| **Credit-based** | Purchase credits upfront, deducted as you use the API |
| **Per-request pricing** | Different endpoints have different costs |
| **Real-time tracking** | Monitor usage in the Developer Console |

> [!NOTE]
>
> Pay-per-usage plans are subject to a monthly cap of 3 million Post reads. If you need higher volume, consider an [Enterprise plan](https://docs.x.com/forms/enterprise-api-interest.md).

***

## Tracked endpoints

Posts retrieved from these endpoints count toward usage:

| Category | Endpoints |
| :- | :- |
| **Post lookup** | [GET /2/tweets](https://docs.x.com/x-api/posts/lookup/introduction.md) |
| **Search** | [Recent search](https://docs.x.com/x-api/posts/search/introduction.md), [Full-archive search](https://docs.x.com/x-api/posts/search/introduction.md) |
| **Streaming** | [Filtered stream](https://docs.x.com/x-api/posts/filtered-stream/introduction.md), [Filtered stream webhooks](https://docs.x.com/x-api/webhooks/stream/introduction.md) |
| **Timelines** | [User posts](https://docs.x.com/x-api/posts/timelines/introduction.md), [User mentions](https://docs.x.com/x-api/posts/timelines/introduction.md) |
| **Engagement** | [Liked posts](https://docs.x.com/x-api/posts/likes/introduction.md), [Bookmarks](https://docs.x.com/x-api/posts/bookmarks/introduction.md) |
| **Lists** | [List posts](https://docs.x.com/x-api/lists/list-tweets/introduction.md) |
| **Spaces** | [Spaces lookup](https://docs.x.com/x-api/spaces/lookup/introduction.md) |

***

## Deduplication

> [!NOTE]
>
> **Daily deduplication**: If the same post is returned from multiple queries within a day, it only counts once for billing.

This means:

* Retrieving the same post multiple times in one day = 1 charge
* Retrieving a post again the next day = 1 additional charge
* Different posts in the same request = each counts separately

***

## Monitoring usage

Track your usage in the [Developer Console](https://console.x.com):

| Metric | Description |
| :- | :- |
| **Total usage** | Posts retrieved in the billing period |
| **By endpoint** | Breakdown by endpoint type |
| **By app** | Usage per developer app |
| **Cost tracking** | Real-time cost calculations |
| **Credit balance** | Remaining prepaid credits |

***

## Managing costs

> **Set budgets**
>
> Configure spending limits in the Developer Console.

> **Monitor alerts**
>
> Get notified before hitting budget thresholds.

> **Use caching**
>
> Cache responses to avoid re-fetching the same posts.

> **Optimize queries**
>
> Use precise filters to retrieve only needed posts.

***

## Pricing details

For current pricing per endpoint and operation, visit the [Developer Console](https://console.x.com).

Pricing may vary by:

* Endpoint type (search vs. lookup vs. stream)
* Operation (read vs. write)
* Data scope (recent vs. full-archive)

***

## Enterprise options

For high-volume needs with custom pricing:

* Dedicated support
* Volume discounts
* Custom rate limits
* Complete data access

> **[Contact Enterprise Sales](https://docs.x.com/enterprise/forms/enterprise-api-interest.md)**
>
> Discuss custom solutions for your needs.

***

## FAQs

> **What happens if I run out of credits?**
>
> API requests will fail until you purchase more credits. Set up balance alerts to avoid interruption.

> **Are there monthly minimums?**
>
> No. Pay only for what you use. You can have months with zero usage and zero cost.

> **How is streaming billed?**
>
> Each unique post delivered through filtered stream counts toward usage, subject to daily deduplication.

> **Do failed requests count?**
>
> No. Only successful responses that return data are billed.

***

## Next steps

> **[Developer Console](https://console.x.com)**
>
> View pricing and purchase credits.

> **[Rate limits](https://docs.x.com/x-api/fundamentals/rate-limits.md)**
>
> Understand request limits (separate from billing).
