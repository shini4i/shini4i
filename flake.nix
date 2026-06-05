{
  description = "shini4i GitHub profile page - dev environment for profilegen";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python3.withPackages (ps: [ ps.pytest ]);
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.ruff
            pkgs.go-task
            pkgs.git
          ];
        };
      });
}
