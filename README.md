# dsh-preset-spaceclaim

**给 DeepSeek Harness（DSH）加一个「SpaceClaim 建模」预设**：装上之后，任何人的 DSH 会话都能按你的要求建 SpaceClaim 几何、倒圆角/倒角、做真圆截面弯头、抽壳、命名边界（`inlet` / `outlet` / `wall` / `interface` / `baffle`…），而且每一步都有独立校验。

> Give the DeepSeek Harness an agent preset that can build Ansys SpaceClaim geometry and name its boundary zones from a plain-language request. Docs are in Chinese.

## 它是什么

DSH 里"给 AI 加能力"有两种载体，这个仓库**两样都装**：

| 载体 | 内容 | 作用 |
|---|---|---|
| **Cordis 插件**（`plugin/`） | 原生工具 `scdm_build` | AI 直接调用，不用走 shell 工具 |
| **技能**（`skills/spaceclaim-modeling/`） | 说明书 + 已验证脚本 + 回归用例 | 告诉 AI 怎么建模、哪些路走不通 |

两者包在一个 **agent preset** 里——DSH 官方支持的"一个目录丢进去就能用"的分发单位。

## 安装

### 换一台电脑要准备什么

| 前提 | 说明 |
|---|---|
| **Windows** | 运行器是 PowerShell 脚本，SpaceClaim 本身也只有 Windows 版 |
| **已安装 Ansys SpaceClaim** | 脚本会自动探测 `SpaceClaim.exe`。装在非默认位置时用环境变量 `DSH_SCDM_EXE` 指定完整路径，或用 `-SpaceClaimExe` 参数 |
| PowerShell 5.1+ | Windows 自带。下面的示例用 `powershell -File`（本机实测 `pwsh` 不一定在 PATH 里） |
| 已装 DSH | 这一步只是给现有 DSH 加一个预设，不装 DSH 的话请改用上面那个独立工具包 |

一条命令走完：

```powershell
git clone https://github.com/fusion-whale/dsh-preset-spaceclaim.git
cd dsh-preset-spaceclaim
powershell -ExecutionPolicy Bypass -File .\spaceclaim\install.ps1
```

安装脚本做两件事：

1. 把 `spaceclaim\` 复制到 `%USERPROFILE%\.dsh\.agent-presets\spaceclaim\`
2. 在目标目录里建一个目录联接 `node_modules` → `%USERPROFILE%\.dsh\profiles\node_modules`

> 第 2 步不是可有可无的。插件内部要 `import "@deepseek-ai/dsh-tools"`，而 Node 解析一个模块自己的 import 是从**该文件所在位置**向上找 `node_modules`。实测：不建这个联接，从预设目录加载插件会直接 `ERR_MODULE_NOT_FOUND`；建了之后就正常。

装完**重启 DSH**，在预设选择器里选「SpaceClaim 建模」。

## 怎么用

切到该预设后，直接说需求就行，例如：

> 建一个 8 mm × 8 mm 截面、200 mm 长的方管流道，两端分别是入口和出口，四周是壁面。

AI 会写一个模型脚本并调用 `scdm_build`。也可以自己写脚本再让它跑——脚本就三行：

```python
body = box(8.0, 8.0, 200.0, origin=(0, 0, 0), name="Channel")
round_edges(edges_parallel(body, "z"), 1.0)
name_boundaries(body, bottom="inlet", top="outlet", sides="wall", axis="z")
finish(r"D:\cfd\channel.scdocx", body)
```

弯头、抽壳这类也是同一套写法：

```python
bend = elbow(pipe_radius=5.0, bend_radius=30.0, angle_deg=90.0, name="Bend")   # 真圆截面弯头
shell(duct, 2.0, open_faces=faces_by_normal(duct, "z", 1) + faces_by_normal(duct, "z", -1))
```

## 插件提供的工具

### `scdm_build`

| 参数 | 类型 | 说明 |
|---|---|---|
| `script` | string，必填 | IronPython 模型脚本（`.py`）的绝对路径 |
| `out` | string，必填 | 期望产出的 `.scdocx` 绝对路径，**必须和脚本里 `finish(路径)` 一致** |
| `verify` | boolean，可选 | 是否另开会话回读校验，默认 true |
| `timeout_sec` | integer，可选 | 每次 SpaceClaim 启动的超时，默认 900 |

返回 `status` / `artifact` / `artifact_size` / `verify_report` / `exit_code` / `output`。

判断成功**不看 SpaceClaim 的退出码**（脚本抛异常它也是 0），而是看运行器打印的成功哨兵 `<<<SCDM_OK>>>`；`verify` 打开的是磁盘上的文件，**不采信脚本自己说的**。

## 与本项目配套的另一个仓库

[`fusion-whale/spaceclaim-modeling`](https://github.com/fusion-whale/spaceclaim-modeling) —— 同一套能力的**独立工具包**（不含 DSH 依赖），给不用 DSH 的人、或者想在终端里直接跑的人。

本仓库的 `skills/spaceclaim-modeling/` 与它内容一致。

## 环境要求

- Windows
- 已安装 Ansys SpaceClaim（开发与验证基于 **2022 R1 / v221**；路径自动探测，可用环境变量 `DSH_SCDM_EXE` 覆盖）
- Node（DSH 自带）与 PowerShell 5.1+
- 插件调用 SpaceClaim 时会写入 `%APPDATA%\SpaceClaim\`（日志、日志文件、许可），这是 SpaceClaim 自身的行为

## 验证情况（重要，请注意哪部分验过、哪部分没验）

已经实测通过：

- 插件模块可被 Node 正常 import，导出 `name` / `inject` / `apply` 齐全，`apply` 能注册出 `scdm_build`
- 工具参数 schema 编译正确（`required: ["script","out"]`，可选参数为 boolean / integer）
- 组合文件 `agent.cordis.yml` 解析正常（18 行），插件行 `./plugin/lib/index.js` 在预设目录内可解析
- **真机跑通整条链路**：直接调用工具 → 启动 SpaceClaim → 建模 → 另开会话回读校验，38 秒，回读尺寸与命名选择与基线一致
- 冒烟测试 `node test/smoke.mjs --live` 全绿（24 项检查）

**尚未验证的一项**：插件在 DSH 里的**挂载**。挂载需要重启 DSH，而作者是在 DSH 会话内部开发的，重启等于中断自身会话，所以最后这一步需要你装完后自己确认一次（选预设 → 看工具列表里有没有 `scdm_build`）。

## 目录结构

```
spaceclaim/                        ← 预设包本体（install.ps1 复制这一个目录）
├── preset.yml                     预设元数据（名字/描述/排序）
├── agent.cordis.yml               组合文件：标准模式全部能力 + 本插件行
├── install.ps1                    安装脚本（纯 ASCII）
├── plugin/                        Cordis 插件包
│   ├── package.json
│   ├── lib/index.js               注册 scdm_build
│   └── scripts/                   运行器 + 建模库 + 校验脚本（自包含副本）
└── skills/spaceclaim-modeling/    技能：SKILL.md + 参考文档 + 17 个回归用例
test/smoke.mjs                     冒烟测试（--live 会真跑一次建模）
```

## License

[MIT](LICENSE) © 2026 fusion-whale
