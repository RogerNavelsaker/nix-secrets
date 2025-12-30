# shell.nix
{
  pkgs,
  hooks,
  ...
}:

pkgs.devshell.mkShell {
  name = "nixos-secrets";

  motd = ''
    {202}🔐 Secret Management Environment{reset}
    $(type -p menu &>/dev/null && menu)
  '';

  # Central provides: git, fd, rg, bat, eza, jq, nixfmt, deadnix, statix, nix-tree, nixd
  packages = with pkgs; [
    sops
    age
    ssh-to-age
    mkpasswd
    gnupg
  ];

  commands = [
    {
      category = "secret management";
      name = "edit-secret";
      help = "Edit a secret file with SOPS";
      command = ''
        if [ -z "''${1:-}" ]; then
          echo "Usage: edit-secret <file>"
          echo "Example: edit-secret hosts/nanoserver/secrets.yaml"
          exit 1
        fi
        sops "$1"
      '';
    }
    {
      category = "secret management";
      name = "new-secret";
      help = "Create a new secret file with SOPS";
      command = ''
        if [ -z "''${1:-}" ]; then
          echo "Usage: new-secret <file>"
          echo "Example: new-secret hosts/myhost/secrets.yaml"
          exit 1
        fi
        touch "$1"
        sops "$1"
      '';
    }
    {
      category = "key management";
      name = "ssh-to-age-key";
      help = "Convert SSH public key to age format";
      command = ''
        if [ -z "''${1:-}" ]; then
          echo "Usage: ssh-to-age-key <ssh-public-key-file>"
          echo "Example: ssh-to-age-key ~/.ssh/id_ed25519.pub"
          exit 1
        fi
        ssh-to-age < "$1"
      '';
    }
    {
      category = "key management";
      name = "list-keys";
      help = "List all keys configured in .sops.yaml";
      command = ''
        echo "=== Keys in .sops.yaml ==="
        ${pkgs.yq-go}/bin/yq '.keys[]' .sops.yaml
      '';
    }
    {
      category = "utilities";
      package = "gnupg";
    }
  ];

  env = [
    {
      name = "SOPS_AGE_KEY_FILE";
      eval = "$HOME/.config/sops/age/keys.txt";
    }
  ];

  devshell.startup = {
    git-hooks.text = hooks.shellHook;
  };
}
