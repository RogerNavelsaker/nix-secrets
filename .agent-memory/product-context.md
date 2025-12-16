---
title: Product Context - nixos-secrets
type: note
permalink: nixos-secrets-product-context
tags:
  - context
  - secrets
---

# Product Context - nixos-secrets

## Why This Project Exists

- [problem] Secrets cannot be stored in plain text in git
- [problem] Manual secret management is error-prone
- [problem] Different hosts/users need different secrets

## Observations

- [solution] SOPS provides git-friendly encrypted secret files
- [solution] GPG (Yubikey) for user keys, age (ssh-to-age) for host keys
- [solution] .sops.yaml defines which keys decrypt which files
- [solution] Devshell provides convenient editing commands

## User Experience Goals

- [ux] Single command to edit any secret file
- [ux] New secrets automatically use correct keys
- [ux] Easy key management via devshell

## How It Works

1. Secrets stored as YAML encrypted with age
2. .sops.yaml defines encryption rules per path
3. Edit with `edit-secret <file>` command
4. nixos-config imports repo as flake input
5. sops-nix decrypts at build/activation time

## Relations

- implements [[Secret Management Pattern]]
- follows [[SOPS Best Practices]]
