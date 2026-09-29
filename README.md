# nixos-secrets

Secret management repository for nix-config using SOPS and age.

Use this repository's Nix flake devshell (`nix develop`) for its secret-management packages and helper commands. Shared workspace tools are provided by Devenv through the workspace `.envrc` and direnv.

## Quick Start

### Project shell

```bash
nix develop
```

## Available Tools

The Nix flake devshell includes:

- **sops**: Secret operations (edit, encrypt, decrypt)
- **age**: Modern encryption tool
- **ssh-to-age**: Convert SSH keys to age format
- **mkpasswd**: Password hash generation
- **gnupg**: PGP key management

Git is provided by the shared workspace Devenv environment.

## Custom Commands

The Nix flake devshell provides convenient commands for common operations:

### Secret Management

- **edit-secret** `<file>` - Edit a secret file with SOPS
  ```bash
  edit-secret hosts/nanoserver/secrets.yaml
  ```

- **new-secret** `<file>` - Create a new secret file with SOPS
  ```bash
  new-secret hosts/myhost/secrets.yaml
  ```

### Key Management

- **ssh-to-age-key** `<ssh-public-key-file>` - Convert SSH public key to age format
  ```bash
  ssh-to-age-key ~/.ssh/id_ed25519.pub
  ```

- **list-keys** - List all keys configured in .sops.yaml
  ```bash
  list-keys
  ```

## Manual Usage

### Edit Secrets

```bash
sops hosts/nanoserver/secrets.yaml
sops users/rona/secrets.yaml
```

### Generate age key from SSH key

```bash
ssh-to-age < ~/.ssh/id_ed25519.pub
```

### Add new host key

1. Generate age key from host SSH key
2. Add to `.sops.yaml` keys section
3. Add to appropriate creation rules

## Configuration

SOPS configuration is in [.sops.yaml](.sops.yaml) with encryption rules for:
- Common host secrets
- Per-host secrets
- User secrets
- Key management secrets

## Environment Variables

- **SOPS_AGE_KEY_FILE**: Set by the project shell to `$HOME/.config/sops/age/keys.txt`

## Repository Visibility

This repository is intended to be public. Secret material stays encrypted with SOPS/age.
