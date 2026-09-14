# SpaceClaim 建模工具包 · 能力交接书

> **这一份文件是自包含的。** 从头读到尾，你就掌握了这套东西的全部能力、全部实测基线、
> 和全部"会翻车的地方"。所有数字都来自真实运行 + 独立回读校验（`-Verify` 另开一个
> SpaceClaim 会话从磁盘重新打开产物），不是推测。
>
> 开发与验证环境：Windows · Ansys SpaceClaim **2022 R1（v221）** · Windows PowerShell 5.1。
> 生成于一次从"建个长方体"一路做到"PCHE 共轭传热"的完整会话。

---

## 0. 30 秒上手

```powershell
# 一条命令验证整套东西在你机器上能不能用（跑 8 个示例，全过才返回 0）
& <skill>\scripts\smoke_examples.ps1

# 建一个 4x4x10 的方管流道并命名进口/出口/壁面
& <skill>\scripts\Invoke-Scdm.ps1 -Script channel.py -Out channel.scdocx -Verify
```

`channel.py` 就这么长：

```python
body = box(4.0, 4.0, 10.0, origin=(0, 0, 0), name="Channel")
name_boundaries(body, bottom="inlet", top="outlet", sides="wall", axis="z")
finish(r"channel.scdocx", body)          # 保存 + 打成功哨兵 <<<SCDM_OK>>>
```

**三个立刻要知道的点：**

1. **SpaceClaim 脚本抛异常时退出码也是 0** —— 所以成功判定靠脚本里 `finish()` 打的哨兵
   `<<<SCDM_OK>>>`，不靠退出码。
2. **`-Verify` 不是可选项。** 它会另开会话把产物从磁盘读回来，报告尺寸、面/边统计、
   每个命名选择的面心与面积。建模脚本自己打印的东西不算证据。
3. **调用 SpaceClaim 的进程必须有完整文件权限**（它要写 `%APPDATA%\SpaceClaim\`、
   读许可）。在沙箱里被限制时它会**静默退出、什么都不做**，没有任何报错。

---

## 1. 这套工具解决什么问题

Ansys SpaceClaim 本身能写脚本，但"**从命令行把它可靠地跑起来**"这条路上几乎没有一处
文档写全。这套工具把那条路封起来了，并且把结论沉淀成文档。具体包含：

| 层 | 内容 |
|---|---|
| 运行器 | `scripts/Invoke-Scdm.ps1` —— 拼装脚本、按实测过的命令行调 SpaceClaim、按哨兵判定、可选独立校验 |
| 建模库 | `scripts/scdm_lib.py`（153 个函数）—— 建几何、倒角、阵列、装配、曲面、命名边界、CHT 交界面 |
| 校验器 | `scripts/verify_model.py` —— 全新会话回读，失败会打 `<<<SCDM_VERIFY_FAILED>>>` |
| 回归 | `tests/` 21 个用例，每个都带实测基线和手算式 |
| 示例 | `examples/` 8 个真实工程配方（管壳换热器、针翅、燃料组件、PCHE、弯管…） |
| 笔记 | `references/api-notes.md` —— 反射验证过的 API 签名 + 大量**负面结论** |

---

## 2. 能力清单与实测基线

### 2.1 基本体

| 函数 | 实测 |
|---|---|
| `box(w, d, h, origin, name, cut, separate)` | 6×5×20 → 6 面；`cut=True` 布尔减；`separate=True` 重叠也独立 |
| `cylinder(r, h, origin, axis, name, cut, separate)` | r2.5×30 → 3 面 |
| `tube(外r, 内r, h, origin, axis, name, separate)` | 30×12×12 → 4 面 |
| `sphere(r, center, name, cut)` | r5 → 1 面 314.16 mm²；**`Cut` 对球无效，要用 `ForceCut`** |
| `cone_frustum(r1, r2, h, …)` | **真**锥台（走回转体），r10→r4×20 → 3 面 |
| `polygon_prism` / `profile_prisms` | 正多边形 / 任意折线 / 椭圆截面柱体 |
| `half_round_channel(r, length, origin, axis, flat, name)` | **D 形（半圆）通道**，见 §7.3 |

### 2.2 倒圆角 / 倒角

```python
round_edges(cube, 2.0)                                 # 整个体所有边
round_edges(edges_parallel(cube, "z"), 3.0)            # 只倒四条竖边
round_edges(edges_by_kind(cube, "circle"), 1.0)        # 只倒所有圆边
round_face_edges(faces_by_normal(cube, "z", 1), 3.0)   # 顶面四周
chamfer_edges(edges_parallel(cube, "z"), 4.0, 1.0)     # 不等距倒角
round_by_rules(cube, [({"parallel": "z"}, 2.0), ({"rest": True}, 1.0)])
```

实测：20mm 立方体 12 条边全倒圆 r=2 → 面数 6→**26**，总面积 **2189.451 mm²**
= 6×256 + 12×50.265 + 8×6.283。只倒 4 条竖边 r=3 → 10 面。

**只吃"边"**：传面报 StandardError、传体报 ValueError。

### 2.3 弯头 / 圆环（真圆截面）

```python
bend = elbow(pipe_radius=3.0, bend_radius=20.0, angle_deg=90.0, name="Bend90")
ring = torus(3.0, 20.0)
bends = elbows([{...}, {...}])      # 多个必须一批建
```

实测：整圈 → 1 个 `torus` 面 **2368.705 mm² = 4π²Rr**；90° → 3 面 = 环面 592.176 + 两个整圆端面 28.274。
摆位：**起始端面圆心落在 `origin`**。`bend_radius` 必须 > `pipe_radius`。

### 2.4 抽壳

```python
shell(cube, 2.0)                                        # 全封闭空腔
shell(cup, 2.0, open_faces=faces_by_normal(cup, "z", 1))# 顶面开口
shell(solid, 2.0, outward=True)                         # 原表面当内壁、壁往外长
```

实测：20³ t=2 全封闭 → 12 面 **3936.00 mm²** = 6×400 + 6×256；开口顶面 → 11 面 3552.00。
**命令原始语义是"壁往外长"**（20³ 传 +2 得到 24³），`shell()` 默认帮你取了负号。

### 2.5 阵列 / 镜像

```python
array_linear(seed, 4, 20.0, axis="x", name="Pin")                   # 一维
array_linear(seed, 3, 20.0, axis="x", count2=2, pitch2=25.0)        # 二维
array_circular(blade, 6, axis="z", center=(0,0,0), name="Blade")    # 圆周
mirror(half, faces_by_normal(half, "x", -1)[0], merge=True)         # 镜像
```

实测：10³ 沿 X 4 个 → 4 体 24 面 2400 mm²；3×2 → 6 体 3600；6³ 叶片半径 20 整圈 6 个 → 1296；
镜像 `merge=True` → 1 体 20×10×10，`merge=False` → 2 体。

### 2.6 曲面 + 加厚 / 装配

```python
plate = rect_surface(30.0, 20.0, normal="y", name="Baffle")   # 零厚度面体
plate = thicken(plate, 1.0, direction="y")                     # 必须接返回值！
asm = component("Assembly1"); move_to_component(body, asm)
move_to_root(component_bodies(asm)); drop_empty_components()
```

实测：20×10 面 → 1 面 200 mm²、包围盒 20×10×**0**；加厚 2mm → 6 面 520 mm²。
`symmetric=True` 的**总厚度是 value 的两倍**。**嵌套组件**（组件套组件）可用，
`all_bodies()` / `all_components()` / `component_bodies()` 全部递归。

### 2.7 命名边界条件（本工具包最常用的部分）

```python
name_faces_by_rules(body, [
    ("inlet",       {"normal": "x", "sign": -1}),
    ("outlet",      {"normal": "x", "sign": +1}),
    ("symmetry",    {"at": ("y", 0.0)}),
    ("heated_wall", {"normal": "z", "sign": -1, "in_box": (30, 70, None, None, None, None)}),
    ("wall",        {"rest": True}),          # 兜底，放最后
])
```

| 你这么说 | 规则 |
|---|---|
| 入口 / 出口（沿 X） | `{"normal":"x","sign":-1}` / `{"normal":"x","sign":+1}` |
| 顶面 / 底面 | `{"normal":"z","sign":1}` / `{"normal":"z","sign":-1}` |
| 某一侧、某个坐标上的面 | `{"normal":"y",…}` 或 `{"at":("y",0.0)}` |
| z 在 50~150 那一段 | `{"between":("z",50,150)}` |
| 某个角、某一块区域 | `{"in_box":(0,50,0,20,None,None)}` |
| 包含点 / 离它最近的面 | `{"point":(x,y,z)}` / `{"nearest":(x,y,z)}` |
| 管子内壁、圆柱面、锥面、球面、平面 | `{"kind":"cylinder"}` / `"cone"` / `"sphere"` / `"plane"` |
| 带洞的面 / 简单面 | `{"loops":2}` / `{"loops":1}` |
| 剩下的都算壁面 | `{"rest":True}` |

**规则按顺序处理、先匹配先占**；`{"rest":True}` 单独用是"剩下全要"，
和别的键组合（`{"kind":"plane","rest":True}`）是"在剩下的里面再筛"。

**边界条件的"类型"不在 SpaceClaim 里设** —— 这里只决定"哪些面叫什么名字"，名字必须是 ASCII；
`velocity-inlet` / `pressure-outlet` / `symmetry` / `periodic` / `fan` / `porous-jump` /
`interface` 这些类型是在 Fluent / Mechanical 里赋给同名分区的。

---

## 3. 顺序铁律（最容易翻车的部分）

这四条是**顺序错了就一定失败**，而且失败方式往往是静默的：

1. **草图类几何必须最先建。** `polygon_prism` / `profile_prisms` / `revolve_*` / `elbow` /
   `extrude_circle` 都走草图工具，而**文档里一旦有实体，新建草图就会崩**（宿主日志里
   只有一句空的 `Script failed:`）。批量接口会先画完所有轮廓再切 Solid 模式。
2. **先倒角 / 抽壳，后命名。** 命名选择会跟着几何走但去向不确定 —— 实测抽壳后
   `outlet` 被重映射到新的顶面环，而换成正偏移时同一组整组消失。
3. **先搬回根零件，再命名。** 体一旦进组件，`GetRootPart().Bodies` 就看不到它了。
4. **`cut=True` 是全局的。** 刀会切文档里**所有**体，所以建体顺序决定一切。典型例子是
   带折流板的四层 CHT（见 §7.2）。

---

## 4. 踩坑总表（每条都有实测数字）

| # | 坑 | 表现 | 对策 |
|---|---|---|---|
| 1 | **布尔刀相切** | 3×3 管束 9 次挖孔只成功 **4** 次；12 根管时 **11/25 失败**；"棒径=栅距"时 **25 次全失败** | cutter 必须**完全落在**被减体内部；管间距 > 2×半径 |
| 2 | **刀的端面共面** | 布尔静默失败，还留下一个**实体刀具体**（壳体面数不变、多出 3 面的圆柱） | 刀两端各出头 5mm |
| 3 | **挖料后墙面的法向** | `cut=True` 挖出的空腔：x 小的一侧墙面外法向是 **+X**（背离实体）、腔顶是 **−Z** | 不能按"坐标大小"猜方向；**看实体在哪一侧** |
| 4 | **规则卡太松** | `{"at":("x",30.0)}` 还会抓走"被切断的另一半顶面"（包围盒中心也是 30） | 规则里能用几个条件就用几个（加 `normal`/`sign`） |
| 5 | **中文异常会静默中止脚本** | 倒圆角失败抛的是中文 StandardError，逃出脚本后宿主中止、**连 traceback 都没有** | 库里所有 `raise` 都是 ASCII；捕获后转 RuntimeError |
| 6 | **命令的 `Success` 不可信** | `Sweep`、`FullRound`、`Midsurface.Convert`、`Fill` 都返回 `Success=True` 却几何毫无变化 | 一律用"体数 / 面数 / 总面积"指纹判定 |
| 7 | **官方 Pattern 把体搬进 component** | 4 个阵列后 `Bodies.Count` 从 1 变 **0**、`Components` 变 **1**，命名与校验全失效 | 阵列改用 `Copy.Execute` + 平移/旋转 |
| 8 | **`Copy.Execute` 是原地复制** | 副本会并进它落点上的**别的体**（实测叶片被并成 10×13×10 的怪东西） | 先把种子搬到文档包围盒之外复制，再搬回来 |
| 9 | **空组件弄坏命名选择** | 搬空后留下的空组件让 `NamedSelection.GetGroups()` 抛中文空引用 | `drop_empty_components()` |
| 10 | **`verify` 曾经"假绿"** | 老版 `verify_model.py` 无论成败都打成功哨兵，上面那种异常被静默吞掉 | 失败打 `<<<SCDM_VERIFY_FAILED>>>` |
| 11 | **`face.Body` 是原始对象** | 逐体统计用它做归属，每一行都是 **0**（Moniker 与 DesignBody 对不上） | 自己按面的 Moniker 建"面→体"索引 |
| 12 | **分段匹配的假阳性** | 流体端面落在固体端面的**孔里**，却被"包围盒罩住"骗过（多 4 对假交界面、多算 6.28mm²） | 带内环的面（`Loops.Count != 1`）不做包含判定 |
| 13 | **`Point2D.Create(a,b)` 映射反了** | 落在全局 `(X=b, Z=a)`；写反会把圆心放到回转轴上、回转出来是**球** | 记住 a→Z、b→X |
| 14 | **`.ps1` 不能带中文** | PowerShell 5.1 把无 BOM 的 `.ps1` 按系统 ANSI 码页读，中文会把 here-string 引号吃掉 | 脚本保持 ASCII-only |
| 15 | **偶发失败** | 批量跑用例时见过一次判失败（大概率上一个进程还占着 `.scdocx`），重跑数字与基线完全一致 | 批处理留一次重试并标注 |

---

## 5. 确定性结论：这些 API 在本版本不能用

写在这里是为了让后来人**别再花时间**：

| API | 结论 |
|---|---|
| `Sweep.Execute`（扫掠 / 弯管） | **不能用**。草图曲线路径、实体边路径、直边、圆边、两个开关取值全试过：不是"面数不变"就是 `Success=False`。弯管改用 `elbow()`（草图圆 + 回转 = 真圆截面 torus 段） |
| `Loft` / `ExtrudeProfile` | 用不了（`references/api-notes.md` §7.3） |
| 实体之间布尔减（`Combine`） | `Combine.Merge` 是**并集**；`MergeBodies` 报错；**没有"把已有体从已有体上减掉"的脚本入口**。要挖料只能在建料时 `cut=True` |
| `Midsurface.Convert` | 空操作（返回 True，几何不变） |
| `Fill.Execute` | 这组参数下无效果 |
| `FullRound.Execute` | `Success=True` 但面数不变 |

---

## 6. 示例模型目录（8 个，全部独立校验过）

| 示例 | 是什么 | 关键实测 |
|---|---|---|
| `tube_bank_demo` | 管壳式换热器壳程：100×50×40 壳 + 12 根贯穿管 + 2 块弓形折流板 | 1 体 44 面；进出口各 1396.81 mm²；管壁 29405.31 |
| `pin_fin_demo` | 针翅散热器流道：120×40×30 + 10×4 根 r2 高 20 针翅 | 1 体 86 面；针壁 10053.10；底面 4297.35 = 4800−40π·2² |
| `cht_tube_bundle_demo` | **三层 CHT**：壳程流体 + 12 管壁固体 + 管程流体 | 25 体 10 zone；两处交界面各 12 对、两侧各 37699.11 / 30159.29 |
| `cht_baffled_demo` | **四层 CHT**：再加 2 块折流板固体（带管孔） | 27 体 14 zone；自动判出 4 组相接；管孔壁 37133.63 |
| `fuel_assembly_5x5` | **5×5 核反应堆燃料组件流动通道**：75×75 通道挖 25 根棒（棒径 10 / 栅距 15），长 3000 | 1 体 31 面；`wall-heated` 25 面 2.3562 m²；**Dh = 13.4937 mm** |
| `pche_demo` | **PCHE 一对冷热通道**：D 形截面、平边朝 +z、上下对齐、长 100 | 3 体；**Dh = 1.2220 mm**；交界面各 2 对 514.16 mm²；冷热薄壁 0.6mm |
| `bend90_demo` | 90° 弯管流域（真圆截面弯头 + 两段直管） | 1 体 7 面；inlet/outlet 各 78.54 |
| `surface_asm_demo` | 曲面加厚（40×30 面 → 3mm 板）+ 装配组件搬进搬出 | 加厚后 6 面 40×3×30 面积 2820 |

```powershell
& <skill>\scripts\smoke_examples.ps1                     # 全部 8 个，打印对照表
& <skill>\scripts\smoke_examples.ps1 -Only pche_demo -Retries 2
```

---

## 7. 共轭传热（CHT）专题

这是这套东西里最值钱的一块，因为多体流固交界面手工做又慢又容易漏。

### 7.1 基本用法

```python
name_interfaces_multi(fluid, solid, "shell_tube", allow_split=True)   # 打成一对 zone
r = interface_report(fluid, solid, allow_split=True)
print(r["pairs"], r["split_pairs"], r["area_a"], r["area_b"], r["balanced"])

rows = interface_pairing_by_body(tube_walls, shell)   # 逐体："是哪一根没配上"
gap  = interface_gaps(tube_walls, shell)              # 孤立体，直接点名

rep = cht_check([("hot_fluid", hot), ("solid", [solid]), ("cold_fluid", cold)])
print(rep["ok"], rep["touching"], rep["not_touching"], rep["isolated_bodies"])
```

- `cht_check` 对**每一对层**自动算交界面——**不用指定哪两层相接**，还会正确判定
  "热↔冷不接触"（中间隔着固体）这种拓扑。
- **判平以 `balanced`（两侧配对面积相等）为准。** 实测把一侧做长 10mm 立刻 `balanced=False`。
- `allow_split=True` 处理"一侧一张面、另一侧被切成几段"（带折流板的模型必须开）。
- `suspects` 默认关：同心圆盘与圆环天然造成假阳性（实测一个完全正确的模型里报了 36 条）。

### 7.2 四层带折流板的灵魂是**建体顺序**

折流板做固体域时，它上面得有管孔，而 `cut=True` 是全局的：

```
① 建壳程流体（box）
② 挖折流板槽（box cut=True）          <- 此时文档里只有壳体
③ 折流板固体塞进槽里（box separate=True）
④ 挖管孔（cylinder cut=True）          <- 刀同时穿透壳体和折流板，折流板天然带管孔
⑤ 最后才建管壁与管程流体               <- 否则会被④的刀切到
```

**折流板边缘要放在管排之间的空档里**：压在管排中心线上会切出 4 片 2~11 mm² 的碎面。

### 7.3 D 形（半圆）通道与 PCHE

PCHE 的通道是"板上刻半圆槽 + 上面板压合"，截面就是 D 形。

```python
ch = half_round_channel(radius=1.0, length=100.0, origin=(0, 1.6, 1.6),
                        axis="x", flat="+z", name="HotFluid")
# origin 是**平的那一面**的中心；通道朝 flat 的反方向鼓出 radius
```

**为什么需要这个函数**：`cut=True` 是全局的，没法只切某一个体 —— 想直接造半圆柱，
就得在目标位置把整圆柱砍一半，而那一刀会把周围固体一起砍掉。绕法：
**先在文档包围盒之外的空白处造整圆柱 → 在那儿切掉一半 → `move()` 搬回目标位置**
（`move()` 是刚体变换、**不会并集**）。

**切出"真半圆"的关键**：刀心正好落在被切体的上表面，刀的上一半在体外。

PCHE 配方（实测 `pche_demo`，一对通道、上下对齐）：

```
① box(100, 3.2, 1.6)                                      # 热板，上表面 z=1.6
② cylinder(1.0, 110, (-5, 1.6, 1.6), axis="x", cut=True)  # 刀心在 z=1.6 -> 只切下半
③ box(100, 3.2, 1.6, origin=(0,0,1.6))                    # 冷板，与热板并成一个固体
④ cylinder(1.0, 110, (-5, 1.6, 3.2), axis="x", cut=True)  # 冷槽；热槽不受影响
⑤ box(100, 3.2, 0.6, origin=(0,0,3.2))                    # 盖板
⑥ half_round_channel(flat="+z") x 2                       # 流体域
```

尺寸：R=1.0（D 形 y 向宽 2、z 向深 1）、刻槽板 1.6、盖板 0.6、板宽 3.2、总厚 3.8。
实测：3 个体；固体 100×3.2×3.8（10 面）；流体各 100×2×1（4 面）；
**Dh = 1.2220 mm**；冷热交界面各 2 对、两侧各 **514.16 mm²**；冷热薄壁 **0.6 mm**。

---

## 8. 怎么自己再扩能力（工作方法）

这套东西能一路扩到 PCHE，靠的是同一套方法，你可以照搬：

1. **先反射，再动手。** 用 PowerShell 反射 `SpaceClaim.Api.V22.Scripting.dll`，
   看命令签名、选项类的属性、结果类的成员。别猜。
2. **写一个小 probe 脚本，一次只验证一件事。** 脚本里每个尝试都包 `try/except` 并打印
   ASCII 化的异常——**中文异常会让宿主静默中止**。
3. **判定成败只看几何**（体数 / 面数 / 总面积），从不看 `Success`。
4. **拿到基线就固化。** 把实测数字和手算式写进回归用例；数字漂移就是流水线坏了。
5. **把负面结论也写下来。** "这个 API 不能用、失败报什么错"和正面文档一样值钱。
6. **每次改完库，跑全套回归 + 示例冒烟**（`scripts/smoke_examples.ps1`）。

---

## 9. 文件地图

```
<skill>/
├── HANDOFF.md                  ← 你正在读的这一份（自包含）
├── SKILL.md                    ← 面向 AI 的说明书（含全部实测基线表）
├── scripts/
│   ├── Invoke-Scdm.ps1         运行器（唯一入口，纯 ASCII）
│   ├── scdm_lib.py             建模库（153 个函数，注入到模型脚本前面）
│   ├── verify_model.py         独立校验（失败打 FAILED 哨兵）
│   ├── template_model.py       模型脚本模板
│   └── smoke_examples.ps1      一条命令跑完所有示例
├── references/
│   └── api-notes.md            反射验证过的签名 + 27 节实测笔记（含大量负面结论）
├── tests/                      21 个回归用例（每个都带基线）
└── examples/                   8 个工程示例 + README
```

模型脚本里**不要 `import`** —— 运行器会把 `scdm_lib.py` 注入到你的脚本最前面。

---

## 10. 命令速查

```powershell
# 建模 + 独立校验
& <skill>\scripts\Invoke-Scdm.ps1 -Script 模型.py -Out 模型.scdocx -Verify

# 想看 GUI 过程
& <skill>\scripts\Invoke-Scdm.ps1 -Script 模型.py -Out 模型.scdocx -Gui

# 全部示例冒烟（打印体数/zone数/面数/耗时对照表）
& <skill>\scripts\smoke_examples.ps1

# 单个回归用例
& <skill>\scripts\Invoke-Scdm.ps1 -Script <skill>\tests\selftest_fillet.py -Out <skill>\tests\selftest_fillet.scdocx -Verify
```

**`-Out` 必须和脚本里 `finish(路径)` 保存的路径完全一致**，否则会被报成
`artifact is missing`（即使建模本身成功了）。

---

*本文件由一次完整的开发会话自动整理。所有数字可在 `tests/` 与 `examples/` 里用
`-Verify` 复现；负面结论集中在 `references/api-notes.md`。*
