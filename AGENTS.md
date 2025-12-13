# nixos-secrets

SOPS-encrypted secrets for nixos-config using age encryption.

## Repository Structure

```
nixos-secrets/
├── flake.nix          # Flake with devshell
├── flake.lock         # Pinned dependencies
├── .sops.yaml         # SOPS configuration and key rules
├── hosts/             # Per-host secrets
│   └── <hostname>/
│       └── secrets.yaml
├── users/             # Per-user secrets
│   └── <username>/
│       └── secrets.yaml
├── keys/              # Key-related secrets
├── scripts/           # Helper scripts
├── docs/              # Documentation
├── githooks.nix       # Git hooks
└── shell.nix          # Development shell
```

## Tools Available in DevShell

- **sops**: Edit/encrypt/decrypt secrets
- **age**: Encryption backend
- **ssh-to-age**: Convert SSH keys to age format
- **gnupg**: PGP support
- **age-plugin-yubikey**: Hardware key support

## Custom Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `edit-secret` | `edit-secret <file>` | Edit secret with SOPS |
| `new-secret` | `new-secret <file>` | Create new secret |
| `ssh-to-age-key` | `ssh-to-age-key <ssh-pub>` | Convert SSH to age |
| `list-keys` | `list-keys` | List configured keys |

## Encryption Rules

SOPS configuration in `.sops.yaml` defines:
- Which age keys can decrypt which files
- Creation rules for new secrets
- Path-based key assignments

## Protected Repository

**Main branch is PROTECTED.** Use feature branches and PRs.

## Related Repositories

- `nixos-config`: Main system configuration (imports this repo)
- `nixos-keys`: Local-only SSH/deploy key generation

## Environment Variables

- `SOPS_AGE_KEY_FILE`: Points to age private key (~/.config/sops/age/keys.txt)

## Recommended MCP Servers

This is a Nix repository. For AI assistants with MCP support:

**Project-specific** (configure in `.mcp.json`):
- `nixos` - NixOS/Home Manager/nix-darwin option lookups via `uvx mcp-nixos`

**Global** (user's global config):
- `basic-memory` - Knowledge management
- `modern-cli` - Modern CLI tools, fetch, github
- `sequentialthinking` - Complex reasoning

`.mcp.json` is gitignored - each user configures their own.
