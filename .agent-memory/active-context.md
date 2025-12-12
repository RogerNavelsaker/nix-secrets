---
title: Active Context - nixos-secrets
type: note
permalink: nixos-secrets-active-context
tags:
  - active
  - context
---

# Active Context - nixos-secrets

## Current Focus

Setting up Claude Code integration with CLAUDE.md and memory-bank.

## Recent Events

1. [2025-12-12] Renamed memory-bank/ to .agent-memory/ with kebab-case files
2. [2025-12-12] Re-registered project with Basic Memory at new path
3. [2025-12-11] Sanitized git history - squashed to single commit
4. [2025-12-11] Fixed remote URL (was nixos-secrets → now nix-secrets)
5. [2025-12-11] Removed nested memory-bank/memory-bank/ directory
6. [2025-12-11] Force-pushed sanitized history to GitHub
7. [2025-12-08] Created CLAUDE.md project documentation

## Active Decisions

- Using age for encryption (not GPG)
- Per-host and per-user secret isolation
- Yubikey support via age-plugin-yubikey

## Next Steps

- Complete Basic Memory project registration
- Document .sops.yaml configuration patterns
- Update progress.md with current status

## Relations

- part_of [[nixos-secrets]]
