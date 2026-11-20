- `xippios.x.params` and `xippios.x.enums` are gone, with the empty `reference/` directory
  and the script that would have filled them, since the package packages no list. They
  held none: `params.PACKAGED_LISTS` was an empty tuple and `enums` defined no
  enumeration. A caller that imported either drops the import; X's value sets stay the
  enumerations of `xippios.x.models`, `UserField`, `PostField` and `Granularity` among
  them. (https://github.com/xippios/sdk-template/issues/40,
  https://github.com/xippios/sdk-x/pull/49)
