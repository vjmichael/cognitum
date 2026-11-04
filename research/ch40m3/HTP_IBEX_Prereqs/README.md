# HTP IBEX Linux build tool dependencies

Windows download-only helper; Python 3.10+. Double-click `Run-IBEX-Build-Tools.cmd` and upload the output ZIP and checksum from `Documents\Cognitum_Offline_Solver_Libraries\Build_Prerequisites` into `/Cognitum/Packages`.

Downloads official Debian 13 x64 `.deb` files for **Flex 2.6.4** and **Bison 3.8.2**, checking their published SHA-256 values. These are Linux executables, not Windows tools. Does not install packages or touch the active development environment.

Later, in an isolated Debian Linux test container, the .deb files can be extracted via `dpkg-deb -x` to a local prefix and used to configure/build IBEX. Need `m4`, CMake, Ninja and g++ (already available in the current research environment). IBEX's bundled Filib is selected (`-DINTERVAL_LIB=filib -DLP_LIB=none`) for initial research. This is not the final performance/licensing backend decision.

References: https://packages.debian.org/trixie/amd64/flex/download and https://packages.debian.org/trixie/amd64/bison/download .

