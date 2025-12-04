{
  description = "An interactive wrapper for kubeseal binary";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, poetry2nix }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      perSystem = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: import nixpkgs {
        inherit system;
        overlays = [ poetry2nix.overlays.default ];
      };
    in
    {
      packages = perSystem (system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            python = pkgs.python312;
            buildInputs = [ pkgs.kubectl ];
          };
        });

      devShells = perSystem (system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.mkShell {
            buildInputs = with pkgs; [
              python312
              poetry
              kubectl
              kubeseal
              pre-commit
              ruff
              mypy
            ];
            shellHook = ''
              export POETRY_VIRTUALENVS_IN_PROJECT=true
              echo "kubeseal-auto development environment"
              echo "Run 'poetry install' to install dependencies"
              echo "Run 'pre-commit install' to set up git hooks"
            '';
          };
        });

      homeManagerModules.default = { pkgs, ... }: {
        home.packages = [ self.packages.${pkgs.system}.default ];
      };
    };
}
