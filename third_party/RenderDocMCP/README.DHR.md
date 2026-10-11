# RenderDocMCP（第三方代码，已内置）

本目录是第三方项目 **RenderDocMCP** 的源码副本，直接以文件形式放进本仓库（**不是** git submodule），
用于让 AI 客户端（Claude Code 等）通过 MCP 协议读取 RenderDoc 的抓帧数据，辅助图形调试。

> 上游仓库的 `README.md` / `CLAUDE.md` 为日文原文，本副本未做任何修改，便于与上游对照。
> 本文件是本仓库自己补充的说明。

## 来源

| 项 | 值 |
| --- | --- |
| 上游仓库 | https://github.com/halby24/RenderDocMCP.git |
| 固定 commit | `11b6b743a4c02c94eb8a1125a1e025dbd021352a`（2026-01-21） |
| 许可证 | MIT（见 `LICENSE`） |
| 副本方式 | `git archive` 导出上游被跟踪的全部文件，未改动内容 |

**升级方式**：重新从上游导出并整体覆盖本目录，然后在本文件里更新上面的 commit 值。

## 目录结构

```
mcp_server/          MCP 服务端进程（Python + FastMCP 2.0），stdio 入口
renderdoc_extension/ 装进 RenderDoc 的 UI 扩展，负责在 RenderDoc 进程内取数据
scripts/install_extension.py  把扩展装到 %APPDATA%\qrenderdoc\extensions\ 的脚本
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

   ```bash
   python third_party/RenderDocMCP/scripts/install_extension.py
   ```

2. **在 RenderDoc 里启用**：`Tools > Manage Extensions`，勾选 “RenderDoc MCP Bridge”。

3. **安装 MCP 服务端**

   ```bash
   uv tool install third_party/RenderDocMCP   # 加 --editable 可在改动源码后立即生效
   uv tool update-shell                       # 把命令目录加进 PATH
   ```

   装好后 `renderdoc-mcp` 命令即可用（等价于 `pyproject.toml` 里的
   `renderdoc-mcp = "mcp_server.server:main"`）。

4. **在客户端配置**：仓库根目录已经放了 `.mcp.json`，内容为

   ```json
   { "mcpServers": { "renderdoc": { "command": "renderdoc-mcp" } } }
   ```

   重启 Claude Code 时会提示是否信任该项目的 MCP 服务，确认即可。
   若不想全局安装，也可以把命令换成本地运行的形式：

   ```json
   { "mcpServers": { "renderdoc": { "command": "uv",
       "args": ["run", "--directory", "third_party/RenderDocMCP", "renderdoc-mcp"] } } }
   ```

5. **使用**：先让 RenderDoc/DHR 打开一个 `.rdc` 抓帧，再让 AI 客户端调用工具。

## 提供的 MCP 工具

`get_capture_status`、`get_draw_calls`、`get_draw_call_details`、`get_shader_info`、
`get_buffer_contents`、`get_texture_info`、`get_texture_data`、`get_pipeline_state`。

## 注意

- 上游自带的 `.mcp.json` 和 `.claude/settings.json` 原样保留以便对照，但**不生效**：
  Claude Code 只读取仓库根目录的 `.mcp.json` / `.claude/settings.json`，
  子目录里的这两份不会被加载。
- 该扩展运行在 RenderDoc 进程内，改动本目录的 Python 源码后需要重装扩展或重开 RenderDoc 才会生效。
