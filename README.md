# nixos-secrets

Secret management repository for nix-config using SOPS and age.

Preferred interactive environment is Flox + `direnv`, so the development shell does not depend on `flake.nix` or `shell.nix` continuing to evaluate cleanly. The Nix devshell remains available as a fallback.

## Quick Start

### Preferred: Flox + direnv

```bash
direnv allow
```

### Fallback: nix develop

```bash
nix develop
```

## Available Tools

The Flox environment includes:

- **sops**: Secret operations (edit, encrypt, decrypt)
- **age**: Modern encryption tool
- **ssh-to-age**: Convert SSH keys to age format
- **gnupg**: PGP key management
- **age-plugin-yubikey**: Yubikey support for age
- **git**: Version control

## Custom Commands

The Flox shell provides convenient functions for common operations:

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

- **SOPS_AGE_KEY_FILE**: Automatically set to `$HOME/.config/sops/age/keys.txt`

## Repository Visibility

This repository is intended to be public. Secret material stays encrypted with SOPS/age.
