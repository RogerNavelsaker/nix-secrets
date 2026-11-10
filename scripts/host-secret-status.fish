#!/usr/bin/env fish

set -l script_dir (dirname (realpath (status filename)))
set -l repo_root (realpath "$script_dir/..")
set -l files $argv
if test (count $files) -eq 0
    set files hosts/iso/secrets.yaml
    for host in miniserver-01 miniserver-02 miniserver-03 nanoserver-01
        set -a files "hosts/$host/secrets.yaml"
    end
end

set -l failed 0
for file in $files
    if string match -rq '(^/|(^|/)\.\.(/|$))' -- "$file"
        printf 'Refusing path outside repository: %s\n' "$file" >&2
        set failed 1
        continue
    end
    if not test -f "$repo_root/$file"
        printf 'Missing secret file: %s\n' "$file" >&2
        set failed 1
        continue
    end

    set -l result (sops filestatus "$repo_root/$file" 2>/dev/null)
    if test $status -ne 0
        printf '%s encrypted=unknown (filestatus failed)\n' "$file"
        set failed 1
        continue
    end
    set -l encrypted (string join '' $result | jq -r '.encrypted // false')
    printf '%s encrypted=%s\n' "$file" "$encrypted"
    if test "$encrypted" != true
        set failed 1
    end
end

exit $failed
