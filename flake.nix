{
  description = "MeshCom UDP listener with SQLite storage and optional Apprise forwarding";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        go = pkgs.go_1_26 or pkgs.go;
        buildGoModule =
          pkgs.buildGo126Module or (pkgs.buildGoModule.override {
            inherit go;
          });
        meshcom-listener = buildGoModule {
          pname = "meshcom-listener";
          version = "0.3.0-go";

          src = ./.;
          vendorHash = "sha256-jWgjeZ8ZjlDrUK6Qlb9t67MLlvvKWLnXJ/k6WLEoE7Q=";

          subPackages = [ "cmd/meshcom-listener" ];

          ldflags = [
            "-s"
            "-w"
          ];

          meta = {
            description = "UDP listener for MeshCom LoRa nodes";
            homepage = "https://github.com/ToSMaverick/meshcom-listener";
            license = pkgs.lib.licenses.mit;
            mainProgram = "meshcom-listener";
          };
        };
      in
      {
        packages = {
          default = meshcom-listener;
          meshcom-listener = meshcom-listener;
        };

        apps.default = {
          type = "app";
          program = "${meshcom-listener}/bin/meshcom-listener";
          meta = {
            description = "Run the MeshCom UDP listener";
          };
        };

        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            git
            mise
            sqlite
          ];

          shellHook = ''
            eval "$(mise activate bash)"

            project_dir="$(pwd -P)"
            if [ -f "$project_dir/.mise.toml" ] && mise trust --show 2>/dev/null | grep -F "$project_dir: untrusted" >/dev/null; then
              echo "mise is active, but this project is not trusted yet. Run 'mise trust' and 'mise install' once if project tools are missing."
            elif ! mise current >/dev/null 2>&1; then
              echo "mise is active. Run 'mise install' once if project tools are missing."
            fi
          '';
        };

        formatter = pkgs.nixfmt;
      }
    );
}
