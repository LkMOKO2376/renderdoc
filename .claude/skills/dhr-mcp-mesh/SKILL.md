---
name: dhr-mcp-mesh
description: Use when reading data out of a DHR capture through the vendored RenderDocMCP bridge (third_party/RenderDocMCP) — checking the bridge is alive, calling bridge methods, dumping a draw call's vertex-input layout, dumping a shader, or debugging why an MCP tool returns nothing. Also covers the direct file-IPC path that bypasses the MCP server so new extension methods can be tested without restarting Claude Code.
---

# DHR 抓帧取数（RenderDocMCP 桥接）

本文件只讲**怎么用**。具体的顶点格式、shader 语义、属性布局因抓帧而异，不要写进来。

宿主内嵌 Python 模块名是 `dhr` / `qdhr`（不是 `renderdoc` / `qrenderdoc`）。

## 0. 先决条件：探活

qDHR 必须开着且**加载了抓帧**。用下面的 `dhr_call.py` 调 `get_capture_status`：

```bash
cd /d/CoreCppProject/DHR/third_party/RenderDocMCP
.venv/Scripts/python.exe /tmp/dhr_call.py get_capture_status
```

返回 `{"loaded": true, "api": ..., "filename": ...}` 即正常。
报 `RenderDoc MCP Bridge` 相关错误 = qDHR 没开 / 扩展没启用 / 没开抓帧。

## 1. 改完扩展必须重装 + 重启 qDHR

否则跑的还是旧代码。扩展目录跟着**应用名**走（不是 `qrenderdoc`）：

```bash
cp -r third_party/RenderDocMCP/renderdoc_extension/. \
      "$APPDATA/qdhr/extensions/renderdoc_mcp_bridge/"
find "$APPDATA/qdhr/extensions/renderdoc_mcp_bridge" -name __pycache__ -type d -exec rm -rf {} +
```

这是 qDHR 的既定机制，绕不开也重定向不了。**每次扩展改动都要走一遍**，所以尽量攒着改。

## 2. 直连桥接，绕开 MCP server（核心技巧）

**问题**：MCP server 进程的工具表在 Claude Code 会话启动时就固定了。往
`mcp_server/server.py` 加 `@mcp.tool` 后**必须重启 Claude Code** 才调得到，
而扩展侧改一次又要重启 qDHR，两边来回太慢。

**办法**：桥接是**基于文件的 IPC**（`%TEMP%\renderdoc_mcp\request.json` + `response.json`），
`mcp_server/bridge/client.py` 只依赖标准库，可以**直接用仓库 venv 跑它调任意方法** ——
不受 MCP server 工具表限制，不用重启 Claude Code。

`/tmp/dhr_call.py`：

```python
import sys, json
sys.path.insert(0, r"D:\CoreCppProject\DHR\third_party\RenderDocMCP")
from mcp_server.bridge.client import RenderDocBridge
b = RenderDocBridge()
method = sys.argv[1]
params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
print(json.dumps(b.call(method, params), indent=2, ensure_ascii=False))
```

```bash
.venv/Scripts/python.exe /tmp/dhr_call.py <method> '<params-json>'
```

**输出很大时一律重定向到 `Output/`，再用脚本提取，别整个读进上下文。**

## 3. 可用方法

现有：`get_capture_status`、`list_captures`、`open_capture`、`get_draw_calls`、
`get_draw_call_details`、`get_frame_summary`、`get_pipeline_state`、`get_shader_info`、
`get_action_timings`、`get_buffer_contents`、`get_texture_info`、`get_texture_data`、
`find_draws_by_shader`、`find_draws_by_texture`、`find_draws_by_resource`、
`get_mesh_layout`。

### `get_mesh_layout(event_id)`
该事件绘制调用的顶点输入布局：图元拓扑、绑定的顶点/索引缓冲、顶点属性声明、
以及一份供"点菜"的扁平列 token 列表。落盘看：

```bash
.venv/Scripts/python.exe /tmp/dhr_call.py get_mesh_layout '{"event_id": 499}' > Output/layout.json
```

⚠️ `vertex_buffers[].byte_size` / `index_buffer.byte_size` 可能是**哨兵值**（表示"整条缓冲"），
**不可信**；真实长度要用 `byte_stride × 数量` 算。多个 slot 可能指向同一 resource 的不同 offset。

### `get_shader_info(event_id, stage)`
`stage` ∈ `vertex|hull|domain|geometry|pixel|compute`。返回 **SPIR-V 反汇编**、常量缓冲、资源绑定。

```bash
for st in vertex pixel; do
  .venv/Scripts/python.exe /tmp/dhr_call.py get_shader_info \
    "{\"event_id\": 499, \"stage\": \"$st\"}" > Output/shader_$st.json
done
```

⚠️ 输出很大（常量缓冲变量可能上百个），**一定落盘**。
反汇编开头自带反射签名（`Input`/`Output` 带 `[[Location(n)]]`、`[[BuiltIn(...)]]`、
`Uniform` 带 `[[DescriptorSet(s), Binding(b)]]`），比裸读 SPIR-V 好认。

## 4. 已知陷阱

| 现象 | 原因 / 处理 |
| --- | --- |
| `Method not found: xxx` | 扩展没重装，或 qDHR 没重启 |
| `Buffer not found` | `get_buffer_contents` 的既知问题：**所有缓冲都读不出**。绕法：扩展里直接用 `controller.GetBufferData(resourceId, offset, size)`，它不依赖 `GetBuffers()` |
| 大 JSON 撑爆上下文 | 一律重定向到 `Output/` 再用脚本提取 |
| `import dhr` 在 venv 里失败 | 正常。扩展代码只能在 DHR 进程内跑；venv 里只做 `-m py_compile` 语法检查 |
| 想要 SPIRV-Cross/GLSL | Python API 够不着。`GetDisassemblyTargets()` 在 Vulkan 下只有 `"SPIR-V (DHR)"`；spirv-cross 只是外部插件，本机默认没有 exe |

## 5. 约定

- 输出统一放 `D:\CoreCppProject\DHR\Output\`，注意别把大文件提交进去。
- 扩展是**内嵌 Python 3.6**：不用 f-string / 海象 / dataclass，用 `%` 格式化，跟现有 service 风格一致。
- API 一律**对着仓库头文件核实**再写：`dhr/api/replay/pipestate.h`、`common_pipestate.h`、
  `control_types.h`、`shader_types.h`、`replay_enums.h`。**别照搬上游 RenderDoc 的 API 名** ——
  本仓库有改动（例如没有 `GetIAState` / `GetIndexBuffer`，用的是 `GetPrimitiveTopology()` / `GetIBuffer()`）。
- 官方取网格示例：`docs/python_api/examples/mesh_output.py`。
