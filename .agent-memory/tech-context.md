---
title: Tech Context - nixos-secrets
type: note
permalink: nixos-secrets-tech-context
tags:
  - tech
  - stack
---

# Tech Context - nixos-secrets

## Technology Stack

### Core Tools

| Tool | Purpose |
|------|---------|
| sops | Secret encryption/decryption |
| gnupg | GPG encryption for user keys (Yubikey) |
| ssh-to-age | SSH to age key conversion for host keys |
| age | Age encryption backend for host keys |

### Development

- **devshell**: Development environment
- **git-hooks**: Pre-commit hooks
- **direnv**: Automatic shell activation

## Observations

- [constraint] Accessed via SSH from nixos-config
- [constraint] Age keys stored in ~/.config/sops/age/keys.txt
- [setup] SOPS_AGE_KEY_FILE environment variable
- [setup] Devshell provides all necessary tools

## Environment Variables

```bash
SOPS_AGE_KEY_FILE=$HOME/.config/sops/age/keys.txt
```

## Commands Available

| Command | Description |
|---------|-------------|
| `edit-secret <file>` | Edit secret with SOPS |
| `new-secret <file>` | Create new encrypted file |
| `ssh-to-age-key <pub>` | Convert SSH to age |
| `list-keys` | Show configured keys |
| `menu` | Show all commands |

## Relations

- uses [[SOPS]]
- uses [[age encryption]]
