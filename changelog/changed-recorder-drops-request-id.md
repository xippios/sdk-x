- `scripts/record_fixture.py` writes a fixture with xippios-core's own writer and without
  the headers that only identify a request, X's `x-transaction-id` among them, so a new
  fixture needs no audited entry of the secret scan for it, where every recording carried
  one. The fixtures recorded before keep theirs.
  (https://github.com/xippios/sdk-core/issues/161,
  https://github.com/xippios/sdk-core/issues/125)
