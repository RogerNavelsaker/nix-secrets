# nixos-secrets

Secret management repository for nix-config using SOPS and age.

Use this repository's Nix flake devshell (`nix develop`) for secret-management packages and helper commands. Shared workspace tools are provided by Devenv through the workspace `.envrc` and direnv. From the repo root, use `devenv shell -- fish` interactively or `devenv shell -- <command>` for one-shot operations.

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

Run lifecycle commands from the repository root inside nix develop or the shared Devenv shell. Running nix-secrets with no arguments prints help and makes no changes.

### Encrypted files and entries

- nix-secrets file add <path> creates an encrypted YAML file containing an empty mapping ({}). It refuses overwrite and path escapes; the path must match a SOPS creation rule.
- nix-secrets file edit <path> opens an existing encrypted file in the SOPS editor.
- nix-secrets file remove <path> deletes only the local encrypted file after exact typed confirmation. This does not remove Git history.
- nix-secrets entry add|update <file> <json-index> sets a value through sops set. Supply JSON on stdin or enter it at the hidden prompt; values are not accepted as command-line arguments.
- nix-secrets entry remove <file> <json-index> removes an entry through sops unset after exact typed confirmation.

Examples:

    nix-secrets file add agents/new-agent/secrets.yaml
    nix-secrets file edit agents/new-agent/secrets.yaml
    printf '%s' '"token-value"' | nix-secrets entry add agents/new-agent/secrets.yaml '["service"]["token"]'
    nix-secrets entry remove agents/new-agent/secrets.yaml '["service"]["token"]'

### Recipient and rule management

- recipient list lists configured aliases and key types.
- recipient add <host|vessel|user|agent> <name> accepts --age-recipient or --pgp-fingerprint; --ssh-public-key accepts an SSH Ed25519 public key and converts it locally. It adds a scoped creation rule.
- recipient update <kind> <name> changes the public recipient behind an alias after typed confirmation.
- recipient link|unlink <kind> <name> --path-regex <regex> adds or removes an association. Unlink requires typed confirmation.
- recipient remove <kind> <name> [--replace-with <alias>] removes an alias after typed confirmation and refuses to leave a creation-rule key group empty.
- recipient sync <file ...> runs interactive sops updatekeys on each explicitly named encrypted file. Paths are required to avoid changing unrelated ciphertext.

Recipient configuration edits do not re-encrypt existing ciphertext. After adding, updating, unlinking, or removing recipients, run recipient sync while the old decryption key is still available. Do not retire a key until affected files have been re-encrypted and verified. These commands manage public SOPS aliases/rules only; SSH private-key lifecycle remains in nix-keys.

### Compatibility and key helpers

- edit-secret <file> and new-secret <file> are aliases for nix-secrets file edit|add.
- ssh-to-age-key <ssh-public-key-file> converts a public SSH Ed25519 key to an age recipient.
- list-keys prints the public age/PGP recipient entries configured in .sops.yaml; recipient list prints aliases and types without recipient values.

ssh-to-age-key accepts public keys only. The CLI does not print secret values; file edit delegates to the SOPS editor. Never send decrypted values to terminal logs, chat, /nix/store, or source control.

## Safe Rescue Operations

The Devenv shell exposes two additional commands:

- `secret-status [file ...]` runs only `sops filestatus`; it reports encryption status without decrypting values. With no arguments it checks ISO and host secret files.
- `update-secret-keys <file ...>` runs interactive `sops updatekeys`. Keep the SOPS confirmation prompt; it does not auto-approve or commit changes.
- Use `edit-secret <file>` for an intentional interactive change. Never send decrypted values to terminal logs, chat, `/nix/store`, or source control.

Example:

```fish
devenv shell -- secret-status hosts/nanoserver-01/secrets.yaml
```

## Manual Usage

### Edit Secrets

```bash
sops hosts/nanoserver-01/secrets.yaml
sops users/rona/secrets.yaml
```

### Generate age key from SSH key

```bash
ssh-to-age < ~/.ssh/id_ed25519.pub
```

### Add a host recipient

Run nix-secrets recipient add host <name> --ssh-public-key <public-key-file> to add its public age recipient and scoped rule. Run nix-secrets recipient sync <encrypted-file> ... explicitly for existing ciphertext; keep old decryption access until sync is verified. Manage host SSH private keys separately with nix-keys.

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
