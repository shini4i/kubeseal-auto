{
  description = "An interactive wrapper for kubeseal binary";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python313;

        pythonDependencies = with python.pkgs; [
          pyyaml
          requests
          kubernetes
          click
          icecream
          questionary
          colorama
        ];

        checkDependencies = with python.pkgs; [
          pytest
          pytest-cov
        ];

        allPythonPackages = pythonDependencies ++ checkDependencies;

      in
      {
        packages = {
          kubeseal-auto = python.pkgs.buildPythonPackage {
            pname = "kubeseal-auto";
            version = "0.6.0";
            src = self;

            format = "pyproject";

            nativeBuildInputs = with python.pkgs; [
              poetry-core
            ];

            propagatedBuildInputs = pythonDependencies;

            buildInputs = [
              pkgs.kubectl
            ];

            checkInputs = checkDependencies;

            doCheck = false;

            meta = with pkgs.lib; {
              description = "An interactive wrapper for kubeseal binary";
              homepage = "https://github.com/shini4i/kubeseal-auto";
              license = licenses.mit;
              maintainers = with maintainers; [ { name = "shini4i"; email = "github@shini4i.dev"; github = "shini4i"; } ];
            };
          };

          default = self.packages.${system}.kubeseal-auto;
        };

        devShells.default = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [
            poetry
            pre-commit
            kubectl
            (python.withPackages (ps: allPythonPackages))
          ];
        };

        homeManagerModules.default = {
          home.packages = [ self.packages.${system}.kubeseal-auto ];
        };
      });
}
