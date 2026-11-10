#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
  printf 'Usage: list-keys\n' >&2
  exit 2
fi

script_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
repo_root=${NIX_SECRETS_ROOT:-$script_root}
# shortcut: top-level simple key list only; use a YAML parser if the config structure changes.
if ! repo_root=$(cd -- "$repo_root" && pwd -P) || [[ ! -f "$repo_root/.sops.yaml" ]]; then
  printf 'Could not find nix-secrets repository root; run from the repository root.\n' >&2
  exit 1
fi
awk '
  /^keys:[[:space:]]*$/ {
    inside_keys = 1
    found_keys = 1
    print "Keys configured in .sops.yaml:"
    next
  }
  /^creation_rules:[[:space:]]*$/ { inside_keys = 0 }
  inside_keys && /^[[:space:]]*-[[:space:]]/ {
    sub(/^[[:space:]]*-[[:space:]]*/, "")
    print
    count++
  }
  END {
    if (!found_keys || count == 0) exit 1
  }
' "$repo_root/.sops.yaml"
