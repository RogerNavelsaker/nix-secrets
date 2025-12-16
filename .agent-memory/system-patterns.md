---
title: System Patterns - nixos-secrets
type: note
permalink: nixos-secrets-system-patterns
tags:
  - patterns
  - architecture
---

# System Patterns - nixos-secrets

## Architecture Overview

```
nixos-secrets/
├── .sops.yaml          # Encryption rules
├── hosts/
│   └── <hostname>/
│       └── secrets.yaml
├── users/
│   └── <username>/
│       └── secrets.yaml
└── keys/
    └── <key-related>.yaml
```

## Observations

- [pattern] Path-based key assignment in .sops.yaml
- [pattern] Host secrets match nixos-config host names
- [pattern] User secrets match home-manager usernames
- [pattern] Devshell commands wrap sops for convenience

## Key Patterns

### SOPS Configuration Pattern

```yaml
# .sops.yaml
keys:
  - &host_key age1...      # ssh-to-age converted host key
  - &user_key 0xABC123...  # GPG key ID (Yubikey)

creation_rules:
  - path_regex: hosts/nanoserver/.*
    key_groups:
      - age:
        - *host_key
      - pgp:
        - *user_key
```

### Secret Editing Pattern

```bash
# Edit existing secret
edit-secret hosts/nanoserver/secrets.yaml

# Create new secret (uses creation_rules)
new-secret hosts/newhost/secrets.yaml
```

### Key Management Pattern

```bash
# Convert SSH key to age format
ssh-to-age-key ~/.ssh/id_ed25519.pub

# List all configured keys
list-keys
```

## Relations

- defines [[SOPS Configuration Pattern]]
- defines [[Secret Editing Pattern]]
