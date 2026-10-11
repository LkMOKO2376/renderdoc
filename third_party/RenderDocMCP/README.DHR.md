# RenderDocMCP（第三方代码，已内置）

本目录是第三方项目 **RenderDocMCP** 的源码副本，直接以文件形式放进本仓库（**不是** git submodule），
用于让 AI 客户端（Claude Code 等）通过 MCP 协议读取 RenderDoc 的抓帧数据，辅助图形调试。

> 上游仓库的 `README.md` / `CLAUDE.md` 为日文原文，未做改动，便于与上游对照。
> 本文件是本仓库自己补充的说明。
> 注意：`renderdoc_extension/` 有一处必要的本地改动（宿主模块改名），见文末
> 「本仓库对扩展的本地改动」。

## 来源

| 项 | 值 |
| --- | --- |
| 上游仓库 | https://github.com/halby24/RenderDocMCP.git |
| 固定 commit | `11b6b743a4c02c94eb8a1125a1e025dbd021352a`（2026-01-21） |
| 许可证 | MIT（见 `LICENSE`） |
| 副本方式 | `git archive` 导出上游被跟踪的全部文件；仅 `renderdoc_extension/` 有本地改动，见文末 |

**升级方式**：重新从上游导出并整体覆盖本目录，然后在本文件里更新上面的 commit 值。

## 目录结构

```
mcp_server/          MCP 服务端进程（Python + FastMCP 2.0），stdio 入口
renderdoc_extension/ 装进 RenderDoc 的 UI 扩展，负责在 RenderDoc 进程内取数据
scripts/install_extension.py  把扩展装到 %APPDATA%\qrenderdoc\extensions\ 的脚本（对 qdhr 不适用，见下）
pyproject.toml       uv 工程定义，注册 `renderdoc-mcp` 命令
```

服务端与扩展之间用**基于文件的 IPC**（`%TEMP%/renderdoc_mcp/`）通信——RenderDoc 内置的 Python
没有 `socket` 模块，所以不能直接走 socket。

## 前置条件

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- RenderDoc 1.20+（本仓库构建出的 DHR 亦可，两者扩展目录一致）

> 上游只在 Windows + D3D11 上验证过。

## 使用步骤

1. **安装 RenderDoc 扩展**

   扩展目录跟着**应用名**走（源码里是 `ConfigFilePath("extensions")`，即
   `QStandardPaths::AppDataLocation`），所以本仓库构建的 qDHR 和官方装的 RenderDoc
   用的不是一个目录：

   | 目标 | 扩展目录 |
   | --- | --- |
   | 系统安装的 RenderDoc | `%APPDATA%\qrenderdoc\extensions\` |
   | **本仓库构建的 qDHR** | `%APPDATA%\qdhr\extensions\` ← 从 `x64\Release\qdhr.exe` 启动时看这里 |

   上游脚本写死了 `qrenderdoc`，**只对官方安装版有效**：

   ```bash
   python third_party/RenderDocMCP/scripts/install_extension.py
   ```

   要在本仓库的 qDHR 上用，手动拷到 `qdhr` 目录即可（把扩展内容更新后重复执行）：

   ```bash
   cp -r third_party/RenderDocMCP/renderdoc_extension \
         "$APPDATA/qdhr/extensions/renderdoc_mcp_bridge"
   ```

   卸载就是删掉 `%APPDATA%\qdhr\extensions\renderdoc_mcp_bridge` 整个目录。

2. **在 RenderDoc/qDHR 里启用**：`Tools > Manage Extensions`，勾选 “RenderDoc MCP Bridge”。
   勾选后会写进该应用的 `UI.config` 的 `AlwaysLoad_Extensions`，之后启动自动加载。

3. **（可选）全局安装 MCP 服务端**

   本仓库的 `.mcp.json` 走的是下面的本地运行方式，**不需要**这一步。
   只有想在任何目录下直接用 `renderdoc-mcp` 命令时才需要：

   ```bash
   uv tool install third_party/RenderDocMCP   # 加 --editable 可在改动源码后立即生效
   uv tool update-shell                       # 把命令目录加进 PATH
   ```

4. **在客户端配置**：仓库根目录的 `.mcp.json` 已经配好了，内容是免全局安装的本地形式 ——
   `uv` 会按 `pyproject.toml` 在该目录下建一个 `.venv` 并装上依赖
   （`fastmcp` / `pydantic` 等，首次启动需要联网，约需几十秒）：

   ```json
   { "mcpServers": { "renderdoc": { "command": "uv",
       "args": ["run", "--directory", "third_party/RenderDocMCP", "renderdoc-mcp"] } } }
   ```

   重启 Claude Code 时会提示是否信任该项目的 MCP 服务，确认即可。
   若已经全局装过，也可以简化成 `{ "command": "renderdoc-mcp" }`。

5. **使用**：先让 RenderDoc/DHR 打开一个 `.rdc` 抓帧，再让 AI 客户端调用工具。

## 提供的 MCP 工具

实测 `tools/list` 返回 **15 个**（上游 README 里只列了 8 个，已经过时）：

| 工具 | 说明 |
| --- | --- |
| `get_capture_status` | 抓帧的加载状态 |
| `list_captures` / `open_capture` | 列出 / 打开 `.rdc` 抓帧 |
| `get_draw_calls` | 绘制调用列表（树状） |
| `get_draw_call_details` | 单条绘制调用的详细信息 |
| `get_frame_summary` | 整帧概览 |
| `find_draws_by_shader` / `find_draws_by_texture` / `find_draws_by_resource` | 按着色器 / 纹理 / 资源反查绘制调用 |
| `get_action_timings` | 各 action 的耗时统计 |
| `get_shader_info` | 着色器源码与常量缓冲区的值 |
| `get_buffer_contents` | 缓冲区内容（Base64） |
| `get_texture_info` / `get_texture_data` | 纹理元数据 / 像素数据（Base64） |
| `get_pipeline_state` | 管线状态 |

## 本仓库对扩展的本地改动（与上游不一致）

本副本的 `renderdoc_extension/` **不是**与上游逐字节一致的：因为本仓库把 RenderDoc 重命名成了
DHR，宿主内嵌的 Python 模块名也跟着变了（`renderdoc` → `dhr`，`qrenderdoc` → `qdhr`，
构建产物是 `x64\Release\pymodules\dhr.pyd` / `qdhr.pyd`）。扩展里引用这两个宿主模块的 import
已相应改写，否则加载时会报 `No module named renderdoc`。

具体只改了这些行（其余内容与上游保持逐字节一致）：

| 文件 | 改动 |
| --- | --- |
| `services/action_service.py` | `import renderdoc as rd` → `import dhr as rd` |
| `services/capture_manager.py` | 同上 |
| `services/pipeline_service.py` | 同上 |
| `services/resource_service.py` | 同上 |
| `services/search_service.py` | 同上 |
| `utils/helpers.py` | 同上 |
| `utils/parsers.py` | 同上 |
| `utils/serializers.py` | 同上 |
| `__init__.py` | `import qrenderdoc as qrd` → `import qdhr as qrd`，并把局部标志 `_has_qrenderdoc` 改名为 `_has_qdhr`（定义处与 `if` 使用处） |

扩展用到的 C++ API 名字（`ResourceId` / `ActionFlags` / `ShaderStage` / `GPUCounter` /
`ReplayOptions` / `Subresource` / `qrd.WindowMenu` 等）都没有变，所以不需要改动。

**这些是本副本仅有的本地改动。** 若日后按上文“升级方式”从上游重新导出覆盖本目录，
必须把这些 import 改名重新应用一遍，否则扩展会在 qDHR 里加载失败。

## 注意

- 上游自带的 `.mcp.json` 和 `.claude/settings.json` 原样保留以便对照，但**不生效**：
  Claude Code 只读取仓库根目录的 `.mcp.json` / `.claude/settings.json`，
  子目录里的这两份不会被加载。
- 该扩展运行在 RenderDoc 进程内，改动本目录的 Python 源码后需要重装扩展或重开 RenderDoc 才会生效。
