# v6 Update Lifecycle

v6 treats every update as evidence first and mutation second:

`check -> diff -> analyze -> approve -> snapshot -> apply -> health -> commit`

`SOURCE` and `HYBRID` records may now compare a declared remote branch tip through bounded `git ls-remote`; this does not fetch objects or change a checkout. A result of `UPDATE_AVAILABLE` is only a recommendation. `LOW` risk is metadata/documentation-only, `MEDIUM` requires explicit approval, and `HIGH` runtime/toolchain/permission changes are blocked from unattended execution.

Legacy v5 Registry records remain valid. A v6 manifest is additive and may be introduced beside a legacy record; migration must preserve the old record until the new manifest validates and the before/after hashes are archived.
