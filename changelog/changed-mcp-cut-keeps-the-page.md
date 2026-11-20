- A tool's page past its byte bound keeps the rows that fit, its other fields whole, its
  `next_token` among them, with a note that counts the rows: minute counts over more than
  about 14 hours keep 200 buckets, and 100 posts of mostly non-Latin text the posts that
  fit in 128,000 bytes. It came back as a note and a preview of its text that lost the
  `next_token`. That `next_token` leads past the rows the cut left out, which a call with
  fewer posts or a shorter range shows. (https://github.com/xippios/sdk-core/issues/131)
