---
title: Active Context - nixos-secrets
type: note
permalink: memory-bank/active-context-nixos-secrets
tags:
- active
- context
---

# Active Context - nixos-secrets

## Current Focus

AI/LLM tool-agnostic repository setup.

## Recent Events

1. [2025-12-10] Renamed CLAUDE.md to AGENTS.md for tool-agnostic naming
2. [2025-12-10] Added AI tool configs to .gitignore
3. [2025-12-10] Removed Claude-specific references from documentation
4. [2025-12-10] Removed Claude sandbox infrastructure
5. [2025-12-10] Kept scripts/ directory and pog input as scaffolding
6. [2025-12-10] Cleaned up ACLs and file permissions
7. [2025-12-08] Created AGENTS.md project documentation
8. [2025-12-08] Initialized memory-bank directory structure
9. [2025-12-08] Registered project with Basic Memory

## Active Decisions

- Using age for encryption (not GPG)
- Per-host and per-user secret isolation
- Yubikey support via age-plugin-yubikey
- AI tool configs are user-specific, not committed to git

## Next Steps

- Continue normal development workflow

## Relations

- part_of [[nixos-secrets]]
- relates_to [[nixos-config]]
