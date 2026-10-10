# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DHR — a frame-capture based graphics debugger for Vulkan, D3D11, D3D12, OpenGL and OpenGL ES.
MIT licensed. Sources are laid out as:

- `dhr/` — the core library (API capture/replay backends, replay drivers, serialisation)
- `qdhr/` — Qt-based GUI
- `dhrcmd/` — command-line frontend (`dhrcmd.exe`)
- `dhrshim/` — small shim loaded into target processes on some platforms
- `util/` — build helpers (Python scripts, `util/test/` run the test suite)
- `docs/` — sphinx documentation source; see `docs/CONTRIBUTING/Compiling.md` for build instructions

## MSVC redistributable

The Visual Studio 2026 Community MSVC redistributable directory on this machine is:

```
E:\VS2026\Community\VC\Redist\MSVC
```

Available toolset versions under it: `14.44.35112`, `14.51.36231`, `v145`.

## Building

Windows uses the checked-in `dhr.sln` + `*.vcxproj` (MSBuild); `CMakeLists.txt` deliberately
errors on Windows and is for Linux/macOS only.

```bat
call "E:\VS2026\Community\VC\Auxiliary\Build\vcvars64.bat"
msbuild dhr.sln -p:Configuration=Release -p:Platform=x64 -m
```

Configurations are `Debug` / `Development` / `Release`. Building a single `.vcxproj` directly
requires `-p:SolutionDir=<repo root>` because the projects import `$(SolutionDir)util\*.props`.

## Conventions

- C++ formatting is enforced by `.clang-format` at the repo root — run clang-format on changed files before committing.
- Line endings / binary attributes are governed by `.gitattributes`.
