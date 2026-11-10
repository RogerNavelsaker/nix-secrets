{ pkgs, ... }:

{
  packages = with pkgs; [
    fish
    python3
    git
    curl
    jq
    ripgrep
    age
    ssh-to-age
    gnupg
    sops
  ];

  scripts = {
    edit-secret.exec = ''exec python3 "$PWD/scripts/nix-secrets.py" file edit "$@"'';
    list-keys.exec = ''exec bash "$PWD/scripts/list-keys.sh" "$@"'';
    new-secret.exec = ''exec python3 "$PWD/scripts/nix-secrets.py" file add "$@"'';
    nix-secrets.exec = ''exec python3 "$PWD/scripts/nix-secrets.py" "$@"'';
    secret-status.exec = ''exec fish "$PWD/scripts/host-secret-status.fish" "$@"'';
    ssh-to-age-key.exec = ''exec bash "$PWD/scripts/ssh-to-age-key.sh" "$@"'';
    update-secret-keys.exec = ''exec fish "$PWD/scripts/update-secret-keys.fish" "$@"'';
  };

  enterShell = ''
    export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
  '';
}
