#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: ssh-to-age-key <ssh-public-key-file>\n' >&2
  exit 2
fi

public_key=$1
if [[ ! -f "$public_key" || ! -r "$public_key" ]]; then
  printf 'SSH public key is not a readable file: %s\n' "$public_key" >&2
  exit 1
fi

key_type=''
IFS=' ' read -r key_type _ < "$public_key" || key_type=''
if [[ "$key_type" != ssh-ed25519 ]]; then
  printf 'Expected an SSH Ed25519 public key file: %s\n' "$public_key" >&2
  exit 1
fi

exec ssh-to-age < "$public_key"
