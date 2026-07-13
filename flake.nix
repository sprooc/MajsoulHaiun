{
  description = "牌运 Haiun development and runtime environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in {
      devShells = forAllSystems (system:
        let pkgs = import nixpkgs { inherit system; };
        in {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python313
              uv
              nodejs_22
              playwright-driver.browsers
              sqlite
              shellcheck
            ];
            LD_LIBRARY_PATH = nixpkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib ];
            PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
            shellHook = ''
              export HAIUN_DATA_DIR="''${HAIUN_DATA_DIR:-$PWD/data}"
            '';
          };
        });

      apps = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          runtimePath = pkgs.lib.makeBinPath [ pkgs.coreutils pkgs.findutils pkgs.nodejs_22 pkgs.python313 pkgs.uv ];
          runtimeLibraries = pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib ];
        in {
          dev = {
            type = "app";
            program = toString (pkgs.writeShellScript "haiun-dev" ''
              export PATH="${runtimePath}:$PATH"
              export LD_LIBRARY_PATH="${runtimeLibraries}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
              project_root="''${HAIUN_PROJECT_ROOT:-$PWD}"
              if [ ! -x "$project_root/scripts/dev.sh" ]; then
                echo "牌运项目目录无效：$project_root（可设置 HAIUN_PROJECT_ROOT）" >&2
                exit 2
              fi
              exec "$project_root/scripts/dev.sh" "$@"
            '');
            meta.description = "Run the 牌运 development servers";
          };
          start = {
            type = "app";
            program = toString (pkgs.writeShellScript "haiun-start" ''
              export PATH="${runtimePath}:$PATH"
              export LD_LIBRARY_PATH="${runtimeLibraries}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
              project_root="''${HAIUN_PROJECT_ROOT:-$PWD}"
              if [ ! -x "$project_root/scripts/start.sh" ]; then
                echo "牌运项目目录无效：$project_root（可设置 HAIUN_PROJECT_ROOT）" >&2
                exit 2
              fi
              exec "$project_root/scripts/start.sh" "$@"
            '');
            meta.description = "Build and start 牌运";
          };
          default = self.apps.${system}.start;
        });
    };
}
