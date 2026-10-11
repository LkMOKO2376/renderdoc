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

## RenderDoc MCP bridge (reading a live capture)

`third_party/RenderDocMCP/` is a vendored copy of
[RenderDocMCP](https://github.com/halby24/RenderDocMCP) — an MCP server plus a qDHR UI extension that
exposes a *live* qDHR instance's capture data as tools. The root `.mcp.json` registers it, so they
appear as `mcp__renderdoc__*`. Full setup notes live in `third_party/RenderDocMCP/README.DHR.md`.

Machine-local prerequisites — none of this is in git, so a fresh clone will not have it:

- **PySide2 must exist at build time.** The extension imports `PySide2.QtCore`, and
  `qdhr/qdhr_local.vcxproj` only defines `PYSIDE2_ENABLED=1` when
  `qdhr/3rdparty/pyside/include/PySide2/pyside.h` is present. Get it from
  `https://renderdoc.org/qrenderdoc_3rdparty.zip`, extracted into the repo root — but the zip's
  top-level directory is `qrenderdoc/`, so its `3rdparty/pyside` and `3rdparty/qt/**/bin/lib{ssl,crypto}*`
  have to land under `qdhr/3rdparty/`. Rebuild `qdhr` afterwards. Without this the extension fails
  to load with `No module named PySide2`.
- **Install the extension into qDHR's own extension directory**, which follows the application name:
  `%APPDATA%\qdhr\extensions\renderdoc_mcp_bridge`, *not* `%APPDATA%\qrenderdoc\extensions\` (that
  belongs to the separately installed RenderDoc). `scripts/install_extension.py` hardcodes
  `qrenderdoc` and is useless here — copy `renderdoc_extension/` by hand. Then enable it once in qDHR
  under `Tools > Manage Extensions` (which records it in that app's `UI.config`
  `AlwaysLoad_Extensions`).
- The vendored extension is **not** byte-identical to upstream: its host module imports were renamed
  (`renderdoc`→`dhr`, `qrenderdoc`→`qdhr`) to match this rebrand, since the built modules are
  `pymodules/dhr.pyd` / `qdhr.pyd`. Re-apply those renames if the tree is ever refreshed from upstream.

To use it: launch `x64\Release\qdhr.exe`, open a `.rdc`, then call the tools. `get_capture_status` is
the cheap "is the bridge alive" probe. An error mentioning `RenderDoc MCP Bridge` means qDHR isn't
running or the extension isn't enabled — nothing to fix on the Claude side. Tools cover capture
management (`list_captures`, `open_capture`, `get_capture_status`), inspection (`get_draw_calls`,
`get_draw_call_details`, `get_frame_summary`, `get_pipeline_state`, `get_shader_info`,
`get_action_timings`), resource reads (`get_buffer_contents`, `get_texture_info`, `get_texture_data`),
and reverse lookups (`find_draws_by_shader`, `find_draws_by_texture`, `find_draws_by_resource`).

## Conventions

- C++ formatting is enforced by `.clang-format` at the repo root — run clang-format on changed files before committing.
- Line endings / binary attributes are governed by `.gitattributes`.
