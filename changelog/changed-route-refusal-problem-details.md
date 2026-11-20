- A route answers an argument that its schema refuses, `granularity=week` sent to
  `/x/count_posts` say, as problem details before the task runs: HTTP 422,
  `application/problem+json`, the title `InvalidRequestError` and the detail
  `granularity: <message>`, without the value given, where FastAPI's own 422 listed its
  error details with the input. (https://github.com/xippios/sdk-core/issues/66)
