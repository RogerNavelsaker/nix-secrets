---
title: Project Brief - nixos-secrets
type: note
permalink: nixos-secrets-project-brief
tags:
  - project
  - secrets
  - sops
---

# Project Brief - nixos-secrets

## Overview

SOPS-encrypted secrets repository for nixos-config using age encryption.

## Observations

- [scope] Manages encrypted secrets for all NixOS hosts and users
- [architecture] Flat structure with per-host and per-user secret files
- [stack] SOPS, age, ssh-to-age, gnupg, age-plugin-yubikey
- [security] Age encryption with per-file key rules in .sops.yaml

## Core Requirements

1. Secure storage of secrets in git
2. Per-host and per-user secret isolation
3. Easy editing via devshell commands
4. Yubikey support for key management
5. Integration with nixos-config via flake input

## Secret Structure

- `hosts/<hostname>/secrets.yaml` - Host-specific secrets
- `users/<username>/secrets.yaml` - User-specific secrets
- `keys/` - Key management secrets

## Relations

- imported_by [[nixos-config]] (as flake input)
- uses [[sops-nix]] for NixOS integration
- uses [[age]] for encryption
