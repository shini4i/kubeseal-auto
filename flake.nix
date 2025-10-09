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
    in
    {
      packages = perSystem (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ poetry2nix.overlays.default ];
          };
        in
        {
          default = pkgs.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            python = pkgs.python312;
            buildInputs = [ pkgs.kubectl ];
          };
        });

      homeManagerModules.default = { pkgs, ... }: {
        home.packages = [ self.packages.${pkgs.system}.default ];
      };
    };
}
