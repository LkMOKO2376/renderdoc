# DHR 未提交改动记录

基线：`git diff HEAD`（分支 `rebrand-dhr`，HEAD = `49873da76`）。不含 RenderDoc→DHR 改名部分。
共 4 个文件、+1198 / -2 行。

---

## 1. 修复：注入到自带旧 CRT 的进程失败

**文件**：`util/WindowsSDKFix.props`

**问题**：很多游戏（如《明日方舟：终末地》）在安装目录自带一套 app-local CRT，其中
`MSVCP140.dll` 是旧版（14.29）。Windows 按 base name 复用已加载模块，所以注入的 `dhr.dll`
（VS2026 / 14.51 编译）只能绑到那份旧的。而自 VS2022 17.0 起 `std::mutex` 的构造函数是
`constexpr`，只就地填零、不再调用 `MSVCP140!_Mtx_init_in_situ`；旧运行时的内部布局不同，
于是 `dhr.dll` 静态初始化时第一次构造锁就空指针崩溃（AV `0xC0000005` @ `MSVCP140+0x13020`）。
该异常被 MSVC CRT 吞掉、`DllMain` 返回 FALSE —— 进程不崩，加载器只报 **err 1114
`ERROR_DLL_INIT_FAILED`**。

**改动**：给所有工程加预定义宏（必须放共享 props：`dhr.dll` 把各 driver 静态库整个链进同一映像，
只加在 `dhr.vcxproj` 上不生效）：

```xml
<ItemDefinitionGroup>
  <ClCompile>
    <PreprocessorDefinitions>_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR;%(PreprocessorDefinitions)</PreprocessorDefinitions>
  </ClCompile>
</ItemDefinitionGroup>
```

**验证**：重建后 `dhr.dll` 里 `_Mtx_init_in_situ` 引用数 0 → 1。在一个放了游戏那份
`MSVCP140.dll`(14.29) 的目录里 `LoadLibraryA("dhr.dll")`：改前 `FAILED err=1114`，改后
**SUCCESS**；对照目录（系统 14.51）同样正常。

---

## 2. 注入失败时记录日志

**文件**：`dhr/os/win32/win32_process.cpp`（`InjectDLL`）

**问题**：`CreateRemoteThread` 成功只代表线程跑过，不代表加载成功 —— 线程退出码才是
`LoadLibraryW` 的返回值，NULL 表示失败，原来被完全忽略。

**改动**：`WaitForSingleObject` 之后读取退出码，为 0 时 `RDCERR`，否则 `RDCLOG`。

**注**：退出码只有低 32 位。判定注入是否成功，真正看的是 `FindRemoteDLL(pid,"dhr.dll")` 是否为 0。

---

## 3. 退出时不删除日志

**文件**：`dhr/common/common.cpp`（`rdclog_closelog`）

**问题**：原来把日志名传给了 `FileIO::logfile_close()`，它在关闭时会 `DeleteFileW` 删掉日志。
一次失败的运行唯一的记录就这么没了。

**改动**：改传空文件名，保留日志。副作用：日志会累积，需自行清理。

---

## 4. `dhrcmd watch` —— 监视进程、注入子进程、拉起 GUI

**文件**：`dhrcmd/dhrcmd_win32.cpp`（唯一改动文件，+1173 行）

外部守护进程：启动/挂接一个母进程，轮询它的**直接子进程**，对匹配的自动注入 DHR 并
`qdhr.exe --targetcontrol localhost:<ident>` 拉起界面。

**用法**

```
dhrcmd watch [options] <executable> [program arguments]
dhrcmd watch [options] --pid <N>
```

| 选项 | 默认 | 说明 |
|---|---|---|
| `--pid <N>` | — | 挂接已在运行的进程（无法为它启用 Vulkan 层，会打印警告） |
| `--child <substr>` | 空 | 只处理名字包含该子串的子进程 |
| `--api <name>` | `any` | 只注入真正用某 API 的子进程：`vulkan`/`d3d12`/`d3d11`/`d3d9`/`opengl`/`any` |
| `--api-wait <ms>` | 10000 | 等 `--api` 对应 DLL 出现的上限，超时则该子进程被跳过 |
| `--poll-ms <ms>` | 1 | 轮询间隔 |
| `--no-gui` | — | 不拉起界面 |
| `--debuglog <file>` | 见下 | DHR 调试日志路径 |

另接受 dispatcher 提供的 `-d/--working-dir`、`-c/--capture-file`、`-w/--wait-for-exit`、`--opt-*`。

**行为要点**

- 1ms 轮询（`PreciseSleep`：先 `Sleep` 再 QPC 自旋补尾，绕开 Windows 15ms 计时粒度）。
- 控制台**实时显示整棵后代进程树**，按层缩进，原地重绘不滚屏；输出重定向时退化为逐次追加。
- 检测到子进程时打印 32/64 位、mitigation 策略、非 System32 的 CRT 模块，再注入。
- 调试日志默认写在 `dhrcmd.exe` 同目录，文件名 `dhrwatch_<时间戳>.log`（配合改动 3 不会丢）。
- `--api` 是延迟注入：新子进程先进待定队列，每次轮询复查，DLL 出现即注入；超时打一行说明并跳过。
- **启动母进程时会给整棵树设 `ENABLE_VULKAN_DHR_CAPTURE=1`**，否则 Vulkan 层不会在子进程里加载，
  注入也看不到 Vulkan。`CreateProcessW` 需带 `CREATE_UNICODE_ENVIRONMENT`（否则 err 87）。
- `--pid` 路径无法设置该环境变量（层必须在 `vkCreateInstance` 时就位），会打印警告。

**验证**

```bash
# 管理员权限运行；Git Bash 里传 Windows 风格参数需加 MSYS_NO_PATHCONV=1
dhrcmd.exe watch --no-gui --child __none__ "C:\Windows\System32\cmd.exe" /c set
#   → 输出应含 ENABLE_VULKAN_DHR_CAPTURE=1
dhrcmd.exe watch --no-gui --api vulkan --api-wait 1500 "<路径>\dhrwatchlauncher.exe"
#   → 子进程不加载 vulkan-1.dll：先"等待"、后"跳过"，不注入
dhrcmd.exe watch --api vulkan "<启动器路径>"
```

**已知限制**：只在**直接子进程**里找。若真正的渲染进程是孙子层，仍抓不到。
实测环境是管理员权限的游戏，`dhrcmd` 必须提权，否则 `OpenProcess` 就失败。

---

## 构建

```bat
call "E:\VS2026\Community\VC\Auxiliary\Build\vcvars64.bat"
msbuild dhr.sln -p:Configuration=Release -p:Platform=x64 -m
```

单工程需带 `-p:SolutionDir=D:\CoreCppProject\DHR\`（工程 import `$(SolutionDir)util\*.props`）。
提交前对改过的文件跑 `.clang-format`（仓库根目录）。
