#!/usr/bin/env fish

if test (count $argv) -eq 0
    printf 'Usage: update-secret-keys <encrypted-file> [encrypted-file ...]\n' >&2
    exit 2
end

#!/usr/bin/env fish

set -l script_dir (dirname (realpath (status filename)))
set -l repo_root (realpath "$script_dir/..")
exec python3 "$repo_root/scripts/nix-secrets.py" recipient sync $argv
