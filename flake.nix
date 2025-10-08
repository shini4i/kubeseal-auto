{
  description = "An interactive wrapper for kubeseal binary";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ poetry2nix.overlays.default ];
        };

        kubeseal-auto = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          python = pkgs.python312;
        };

      in
      {
        packages = {
          kubeseal-auto = kubeseal-auto;
          default = self.packages.${system}.kubeseal-auto;
        };

        devShells.default = pkgs.mkShell {
          inputsFrom = [ kubeseal-auto ];
          packages = with pkgs; [
            poetry
            pre-commit
            kubectl
          ];
        };

        homeManagerModules.default = {
          home.packages = [ self.packages.${system}.kubeseal-auto ];
        };
      });
}
