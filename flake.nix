# flake.nix
{
  description = "Secret management tools for nixos-config";

  inputs = {
    # FlakeHub URLs for version management and caching
    nixpkgs.url = "https://flakehub.com/f/NixOS/nixpkgs/0.1.*.tar.gz";

    flake-utils.url = "https://flakehub.com/f/numtide/flake-utils/0.1.*.tar.gz";

    devshell = {
      url = "https://flakehub.com/f/numtide/devshell/0.1.*.tar.gz";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    git-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pog = {
      url = "github:jpetrucciani/pog";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      devshell,
      git-hooks,
      pog,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ devshell.overlays.default ];
        };

        hooks = git-hooks.lib.${system}.run {
          src = ./.;
          hooks = import ./githooks.nix { inherit pkgs; };
        };

        scripts = import ./scripts {
          inherit pkgs;
          inherit (pog.packages.${system}) pog;
        };
      in
      {
        checks.pre-commit = hooks;

        devShells.default = import ./shell.nix {
          inherit pkgs hooks scripts;
        };
      }
    );
}
