---
title: Progress - nixos-secrets
type: note
permalink: nixos-secrets-progress
tags:
  - progress
  - status
---

# Progress - nixos-secrets

## Current Status

Repository configured with SOPS encryption and devshell commands.

## What Works

- [x] SOPS configuration in .sops.yaml
- [x] Devshell with editing commands
- [x] SSH-to-age key conversion
- [x] Yubikey support available
- [x] Git hooks for quality checks

## What's Left

- [ ] Document all creation rules in .sops.yaml
- [ ] Add secrets for new hosts as created
- [ ] Set up key rotation procedures

## Known Issues

None currently.

## Blockers

None currently.

## Relations

- tracks [[nixos-secrets]]
