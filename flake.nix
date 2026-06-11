{
  description = "An interactive wrapper for kubeseal binary";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, pyproject-nix, uv2nix, pyproject-build-systems }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      perSystem = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: import nixpkgs { inherit system; };

      # Load the uv workspace from uv.lock and build a pyproject.nix overlay.
      # sourcePreference = "wheel" pulls prebuilt wheels, so none of the pure-Python
      # dependencies need compilation or build overrides.
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };

      # Compose the Python package set: build-system bootstrap + the workspace overlay.
      pythonSetFor = system:
        let
          pkgs = pkgsFor system;
          python = pkgs.python312;
        in
        (pkgs.callPackage pyproject-nix.build.packages { inherit python; }).overrideScope (
          nixpkgs.lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            overlay
          ]
        );
    in
    {
      packages = perSystem (system:
        let
          pkgs = pkgsFor system;
          pythonSet = pythonSetFor system;
          venv = pythonSet.mkVirtualEnv "kubeseal-auto-env" workspace.deps.default;
        in
        {
          # kubeseal and kubectl are required at runtime; wrap them onto PATH.
          default = pkgs.runCommand "kubeseal-auto"
            {
              nativeBuildInputs = [ pkgs.makeWrapper ];
              meta.mainProgram = "kubeseal-auto";
            }
            ''
              mkdir -p $out/bin
              makeWrapper ${venv}/bin/kubeseal-auto $out/bin/kubeseal-auto \
                --prefix PATH : ${nixpkgs.lib.makeBinPath [ pkgs.kubeseal pkgs.kubectl ]}
            '';
        });

      devShells = perSystem (system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.mkShell {
            buildInputs = with pkgs; [
              python312
              uv
              kubectl
              kubeseal
              bump2version
              # Security scanners, mirroring the CI security workflow so they can
              # be run locally. bandit is a Python tool and lives in the uv dev
              # group instead.
              zizmor
              trivy
              trufflehog
            ];
            env = {
              # Force uv to use the interpreter from this shell, not a downloaded one.
              UV_PYTHON_DOWNLOADS = "never";
              UV_PYTHON = "${pkgs.python312}/bin/python";
            };
            shellHook = ''
              echo "kubeseal-auto development environment"
              echo "Run 'uv sync --group dev' to install dependencies"
              echo "Run 'pre-commit install' to set up git hooks"
            '';
          };
        });

      homeManagerModules.default = { pkgs, ... }: {
        home.packages = [ self.packages.${pkgs.system}.default ];
      };
    };
}
