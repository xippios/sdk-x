- A tool refuses an argument that it does not declare before it runs, whatever its value,
  where the argument was dropped and the tool ran without it: `x_get_user_posts` called
  with `maxresults` answers `error: InvalidRequestError: maxresults: Not an argument of
  this tool`, then names the five it takes, where it returned the default page of 10 posts
  and spent their credits. (https://github.com/xippios/sdk-core/issues/84)
