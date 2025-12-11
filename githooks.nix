# githooks.nix - Git hooks configuration using cachix/git-hooks.nix
{ pkgs }:
{
  # Formatting
  nixfmt-rfc-style.enable = true;

  # Linting
  deadnix.enable = true;
  statix.enable = true;

  # Syntax validation
  nix-syntax = {
    enable = true;
    name = "nix-syntax";
    description = "Validate Nix syntax with nix-instantiate --parse";
    entry = "${pkgs.nix}/bin/nix-instantiate --parse";
    files = "\\.nix$";
    pass_filenames = true;
  };

  # Block private keys from being committed
  block-private-keys = {
    enable = true;
    name = "block-private-keys";
    description = "Block commits containing private keys";
    entry = toString (
      pkgs.writeShellScript "block-private-keys" ''
        for file in "$@"; do
          if ${pkgs.gnugrep}/bin/grep -l -E '^-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----' "$file" 2>/dev/null; then
            echo "ERROR: Private key detected in: $file"
            echo "Remove the private key before committing!"
            exit 1
          fi
        done
      ''
    );
    files = ".*";
    pass_filenames = true;
  };

  # Verify secrets are SOPS-encrypted
  sops-verify = {
    enable = true;
    name = "sops-verify";
    description = "Verify secrets.yaml files are SOPS-encrypted";
    entry = toString (
      pkgs.writeShellScript "sops-verify" ''
        for file in "$@"; do
          if ! ${pkgs.gnugrep}/bin/grep -q '^sops:' "$file" 2>/dev/null; then
            echo "ERROR: $file is not SOPS-encrypted!"
            echo "Encrypt with: sops -e -i $file"
            exit 1
          fi
        done
      ''
    );
    files = "secrets\\.yaml$";
    pass_filenames = true;
  };

  # Post-merge notification for secrets/config changes
  secrets-changed-notify = {
    enable = true;
    name = "secrets-changed-notify";
    description = "Notify when secrets or SOPS config changed after merge";
    stages = [ "post-merge" ];
    entry = toString (
      pkgs.writeShellScript "secrets-changed-notify" ''
        changed=$(git diff-tree -r --name-only ORIG_HEAD HEAD 2>/dev/null | grep -E '^(.*secrets\.yaml|\.sops\.yaml|flake\.nix|flake\.lock)$' || true)
        if [ -n "$changed" ]; then
          echo ""
          echo "╔════════════════════════════════════════════════════════════╗"
          echo "║  NOTE: Secret/config files changed after merge             ║"
          echo "╠════════════════════════════════════════════════════════════╣"
          echo "$changed" | while read -r f; do echo "║  - $f"; done
          echo "╠════════════════════════════════════════════════════════════╣"
          echo "║  Consider: re-encrypting or updating dependent systems     ║"
          echo "╚════════════════════════════════════════════════════════════╝"
          echo ""
        fi
      ''
    );
    always_run = true;
    pass_filenames = false;
  };
}
