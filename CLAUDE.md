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

## TODO (RenderDoc MCP bridge / mesh export)

Open work items. See `.claude/skills/dhr-mcp-mesh/SKILL.md` for how to drive the bridge from
outside the MCP server, and `third_party/RenderDocMCP/README.DHR.md` for setup.

1. **Fix the dead `get_pipeline_state` blocks.** The extension calls RenderDoc-1.x API names this fork
   does not have, and every failure is swallowed by a `try/except`, so whole sections silently vanish.
   In `third_party/RenderDocMCP/renderdoc_extension/services/pipeline_service.py`: `GetIAState()` →
   `GetPrimitiveTopology()` + `GetVertexInputs()` + `GetVBuffers()` + `GetIBuffer()`,
   `GetViewportScissor()` → `GetViewport(i)` / `GetScissor(i)`, `GetOutputMerger()` →
   `GetOutputTargets()` / `GetDepthTarget()` (`search_service.py` has `GetOutputMerger()` too). So
   `input_assembly`, `viewports` and `render_targets` are never emitted at all. Rewrite against the real
   API in `dhr/api/replay/pipestate.h` and fold in the vertex attributes and vertex-buffer bindings so a
   single call returns what the UI's VTX panel shows. Until then use `get_mesh_layout`, which has all of
   it.
2. **Fix constant-buffer *values*** — same root cause, and it is what blocks skinning. `get_pipeline_state`
   emits reflection structure only (`name` / `byte_size` / per-variable `name`+`byte_offset`+`type`, no
   values); `get_shader_info` does try to read them but calls `pipe.GetConstantBuffer(stage, i, 0)`,
   which does not exist, so every CB comes back as
   `error: "'dhr.PipeState' object has no attribute 'GetConstantBuffer'"` with `variables: []`. The real
   API is `pipe.GetConstantBlock(stage, index, arrayIdx)` (→ `UsedDescriptor`) feeding
   `controller.GetCBufferVariableContents(...)`. Until this is fixed the per-instance UBO holding the
   joint-palette base offset is unreachable.
3. **Client-side CSV export with a caller-specified column layout.** ✅ Done — `mcp_server/mesh_export.py`,
   decoding raw `get_mesh_data` streams in the server rather than the extension (a server edit needs no
   qDHR restart).
4. **CSV → OBJ.** ✅ Done, including multi-event merge; the merged OBJ is one file with one `o ev<event_id>`
   section per draw.
5. **CSV → USD `.usda`.** ✅ Done for static meshes — one `UsdGeom.Mesh` per draw with `points`, `normals`
   and `primvars:st`. Caveat: this usd-core build's Python API cannot set a primvar `role` at all
   (`UsdGeom.PrimvarsAPI.SetRole` is not bound, `UsdGeom.Tokens.textureCoordinate` does not exist,
   `SetMetadata("role", …)` is rejected), so `primvars:st` is written without one.
6. **Skinned USD (`UsdSkel`).** Deferred and partly blocked. Verified against the live capture: 7 of the 9
   draws in "Colour Pass #5" (`499`, `504`, `509`, `523`, `529`, `534`, `539`) carry per-vertex bone data
   — 4 weights (`_input5`) + 4 joint indices (`_input6`, or `_input7` when the layout has a duplicate
   location) — weights summing to 1.0 per vertex, 26–172 distinct joints per mesh. `514`/`518` bind those
   two attributes to a 20-byte default buffer, so they are effectively rigid. The joint matrices are
   readable (`ResourceId::243`, 8 MB, row-major 3×4 with no 4th row: 512 literal identity entries then
   runs of ~173 unit-rotation matrices ≈ the per-object joint count). But there is **no joint hierarchy,
   no rest pose and no inverse-bind array** anywhere in the draw's bindings — the VS binds exactly one
   matrix array — so any `UsdSkel` output is a synthetic skeleton, and selecting a draw's palette
   sub-block needs the per-instance UBO that item 2 blocks.

## Conventions

- C++ formatting is enforced by `.clang-format` at the repo root — run clang-format on changed files before committing.
- Line endings / binary attributes are governed by `.gitattributes`.
