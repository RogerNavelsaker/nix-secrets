# shell.nix
{ pkgs, scripts }:
pkgs.mkShell {
  name = "nix-secrets";

  packages =
    with pkgs;
    [
      nix
      python3
      git
      curl
      jq
      ripgrep
      age
      ssh-to-age
      gnupg
      mkpasswd
      sops
    ]
    ++ builtins.attrValues scripts;

  shellHook = ''
    export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
    echo "🔐 Secret Management Environment"
    $(type -p menu &>/dev/null && menu)
  '';
}
