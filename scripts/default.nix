{ pkgs, ... }:

let
  lifecycle =
    name: args:
    pkgs.writeShellScriptBin name ''
      export NIX_SECRETS_ROOT="''${NIX_SECRETS_ROOT:-$PWD}"
      exec ${pkgs.python3}/bin/python3 "$PWD/scripts/nix-secrets.py" ${args} "$@"
    '';
in
{
  nix-secrets = lifecycle "nix-secrets" "";
  edit-secret = lifecycle "edit-secret" "file edit";
  list-keys = pkgs.writeShellScriptBin "list-keys" ''
    exec ${pkgs.bash}/bin/bash "$PWD/scripts/list-keys.sh" "$@"
  '';
  new-secret = lifecycle "new-secret" "file add";
  ssh-to-age-key = pkgs.writeShellScriptBin "ssh-to-age-key" ''
    exec ${pkgs.bash}/bin/bash "$PWD/scripts/ssh-to-age-key.sh" "$@"
  '';
}
