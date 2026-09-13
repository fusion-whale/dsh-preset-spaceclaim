# SpaceClaim API 与命令行笔记（本机实测）

来源：对 SpaceClaim 安装目录（形如 `<drive>:\Program Files\ANSYS Inc\v221\scdm`）下 `SpaceClaim.Api.V21.dll` /
`SpaceClaim.Api.V22.Scripting.dll` 做反射得到的真实签名，加上实跑验证。
脚本宿主 = SpaceClaim 2022 R1，IronPython 2.7，API 命名空间 `SpaceClaim.Api.V22`。

## 1. 脚本宿主预加载的名字（无需 import）

来自 `scdm\Scripting\UtilitiesOnLoadV22.py`，宿主在运行脚本前会导入：

- `from SpaceClaim.Api.V22 import *`（`Part/IPart/DesignBody/IDesignBody/Group/Document/...`）
- `from SpaceClaim.Api.V22.Geometry import ...`（`Point/Direction/Frame/Plane/...`）
- `from SpaceClaim.Api.V22.Scripting.Helpers import *` 与 `...Helpers.Units import *` → **`MM()` 在这里**
- `from SpaceClaim.Api.V22.Scripting.Selection import *` → `Selection`
- `from SpaceClaim.Api.V22.Scripting.Commands import *` → `BlockBody/CylinderBody/NamedSelection/DocumentOpen/DocumentSave/PartLocation`
- `from SpaceClaim.Api.V22.Scripting.Commands.CommandOptions import *` → `ExtrudeType`
- 顶层函数 `GetRootPart()` / `GetActivePart()` / `CloseWindow()` 等

## 2. 关键签名（反射所得）

```
DocumentHelper.CreateNewDocument()                       -> Document
DocumentHelper.GetRootPart()                             -> IPart
DocumentOpen.Execute(string path)                        -> CommandResult
DocumentSave.Execute(string path)                        -> CommandResult
DocumentSave.Execute(string path, ExportOptions)         -> CommandResult

BlockBody.Create(Point corner1, Point corner2,
                 ExtrudeType = …, ICommandInfo = …)      -> BlockBodyResult { CreatedBody }
CylinderBody.Create(Point center, Point start, Point end,
                    ExtrudeType = …, ICommandInfo = …)   -> … { CreatedBody }
SphereBody.Create(Point center, Point end, …)

NamedSelection.Create(ISelection primary, ISelection secondary,
                      PartLocation location, ICommandInfo)
        -> CreateNamedSelectionGroupResult { Success, CreatedNamedSelection: Group }
NamedSelection.Rename(string oldName, string newName)
NamedSelection.GetGroups()                -> ICollection<Group>
NamedSelection.Delete(string[] names)

Selection.Create(IDocObject) / (IDocObject[]) / (IEnumerable<IDocObject>)
Selection.Empty() / Selection.Clear() / Selection.GetActive()
Selection.FilterByBoundingBox(Box) / FilterByBoundingSphere(Point, double)

Group.Name { get; set; }        Group.Members -> ICollection<IDocObject>
PartLocation = { Root, Active }
ExtrudeType  = { None, Add, Cut, ForceAdd, ForceCut, ForceIndependent, ForceNewSurface }
```

`CylinderBody.Create` 的三点语义（**实测反推 + 官方 `Snippets\V21\...\Example9.snippet` 印证**）：

```
CylinderBody.Create(定义圆圆心, 另一底面圆心, 另一底面圆周上一点)
```
- 第 2 点决定**轴向与长度**（不是半径！）
- 第 3 点决定**半径**

按“第 2 点定半径”写会得到一个轴向、半径全错的圆柱（本机实测：想建 r=2.5、h=30 的 Z 向圆柱，
结果得到轴向 X、长 2.5、半径 30），而且 `name_boundaries` 会把所有面判成同一端。
Example9 的 `(0,0,0) (50,0,0) (50,0,10)` = 轴向 X、长 50、半径 10。

### 返回对象的成员并不统一

| 命令 | 结果类型 | 取体的成员 |
|---|---|---|
| `BlockBody.Create` | `BlockBodyResult` | `CreatedBody`（也有 `CreatedBodies`） |
| `SphereBody.Create` | `SphereResult` | `CreatedBody`（也有 `CreatedBodies`） |
| `CylinderBody.Create` | `CylinderBodyResult` | **只有 `CreatedBodies`** |

取 `res.CreatedBody` 建圆柱会失败，报
`Script failed: 'CylinderBodyResult' object has no attribute 'CreatedBody'`。

### 闭合圆边的端点会退化成圆心

`edge.StartPoint` / `edge.EndPoint` 对闭合圆边返回的是**圆心**，不是圆周上的点。
后果：只用这两个点算面心/包围盒时，圆柱、圆管之类的曲面测量会失真
（实测：r=2.5、h=30 的圆柱被算成 `0 x 0 x 30 mm`，而且 `name_boundaries` 把 3 个面全判成 inlet）。

正确做法：用 `edge.GetPolyline(PolylineOptions())` 离散取点再平均。
`PolylineOptions` 有默认构造函数；`scdm_lib._edge_points()` 就是这么做的。
（平面多边形的面不受影响，所以长方体用例一直是对的。）

`Geometry.Box.Create(ICollection<Point>)` 可以从点集直接造包围盒，取 `.MinCorner` / `.MaxCorner` / `.Center` / `.Size`；
`Geometry.Matrix` 没有 `Identity` 静态属性，需要单位矩阵可用 `Matrix.CreateScale(1.0)`。矩形框选面也可以用
`Selection.FilterByBoundingBox(box)`。

## 3. 包装对象 vs 真实几何

| 脚本对象 | 几何实体 | 备注 |
|---|---|---|
| `DesignBody` | `Modeler.Body` | `IDesignBody.Faces` → `ICollection<DesignFace>` |
| `DesignFace` | `Modeler.Face`（`face.Shape`） | `Modeler.Face` 有 `Edges`/`Area`/`Geometry`；`DesignFace` 没有 `Edges[i].StartPoint` |
| `DesignEdge` | `Modeler.Edge`（`edge.Shape`） | `Modeler.Edge` 有 `StartPoint`/`EndPoint`/`StartVertex`/`EndVertex` |
| `DesignFace.Shape.Geometry` | `Geometry.Plane`（平面面） | `Plane` 暴露 `Frame`（不是 `.Normal`） |

所以取面心要用 `face.Shape.Edges` → `edge.StartPoint/EndPoint` → `Point.X/Y/Z`。

## 4. 命令行参数表（官方）

语法 `SpaceClaim.exe /[option]=[value]`，大小写不敏感，路径建议加引号。

| 选项 | 说明 |
|---|---|
| `/RunScript` | 要运行的脚本文件全路径（**必须 .py**） |
| `/ScriptArgs` | 传给脚本的参数，逗号分隔 |
| `/ScriptAPI` | 与 RunScript 同用时指定脚本 API |
| `/ScriptOutput` | 脚本输出文件的完整路径（headless 下唯一的排错窗口） |
| `/ScriptAsync` | 是否异步运行脚本 |
| `/ExitAfterScript` | 脚本跑完后是否退出应用 |
| `/Headless` | 无界面批处理模式 |
| `/Splash` | 是否显示启动画面 |
| `/p` | 覆盖主/备用许可证偏好 |
| `/UseCurrentDirectory` / `/DefaultOpenDirectory` / `/DefaultSaveDirectory` | 目录控制 |
| `/WindowSize` / `/WindowLocation` / `/WindowMaximized` | 窗口控制 |

实测结论：
- `/RunScript="<x>.py" /Headless=True /ExitAfterScript=True` 可用（本机 v221 验证通过）。
- **`.scscript` 不生效**；`/S`、`-RunScript`、`/RunScript:` 这些写法都不存在。
- 注册表里 `.scscript` 的关联命令是 `SpaceClaim.exe "%1"`（双击打开），与 CLI 运行脚本是两条路。
- `/ScriptOutput` 的编码对非 ASCII 不友好：脚本里 `print()` 尽量只用 ASCII。
- 引用路径要经 `cmd.exe` 传递（`/c ""exe" /RunScript="..."`），PowerShell 直接调用会丢引号。

## 4.5 排错：脚本输出日志为空时看哪里

如果脚本在**打印任何东西之前**就失败（API 用错、导入失败），`/ScriptOutput` 文件会是**空的**，
退出码照样是 0，从命令行看完全“成功但没结果”。

这时看 SpaceClaim 自己的应用日志：

```
%APPDATA%\SpaceClaim\Log Files\SpaceClaim_<日期>_<pid>.log
```
里面会有一行 `Script failed: <具体错误>`（例如
`Script failed: 'CylinderBodyResult' object has no attribute 'CreatedBody'`）。
`Invoke-Scdm.ps1` 在失败路径上会自动把这个文件里的 `Script failed` 抓出来打印。

## 4.6 脚本文件本身的编码

- 建模脚本（`.py`）：UTF-8 无 BOM 可用，中文注释没问题；但 `print()` 输出非 ASCII 可能触发
  `UnicodeEncodeError`，所以日志文本保持 ASCII 最稳。
- 运行器（`.ps1`）：**保持纯 ASCII**。本机 shell 是 Windows PowerShell 5.1，它把无 BOM 的 .ps1
  按系统 ANSI（GBK）读，UTF-8 中文字节被误配后可能吃掉一个引号，直接导致解析失败
  （实测报错：`The string is missing the terminator: '`）。要写中文就存成带 BOM 的 UTF-8。

## 5. 沙箱要求

SpaceClaim 启动时会写 `%APPDATA%\SpaceClaim\Log Files\*`、`Journal Files\*`、
`AcisJournals\*` 并保存 `user.config`，还要读许可。在只允许写工作区的沙箱下单靠
workspace-write 会让它**静默退出（exit 0、不产生任何日志）**。
所以调用运行器时必须放宽到 `danger-full-access`。

## 6. 面心算法：为什么用包围盒中心（曾经踩过的坑）

`face_center()` 原来用**边界采样点的平均值**，实测暴露了两个问题：

1. 采样偏差：默认 `PolylineOptions()` 离散圆边时采样点不一定落在极值位置，
   r=2.5 的圆盖面心会偏 0.061 mm。
2. **切面后失真**（更严重）：面被切分后会多出共线顶点，平均值被拉偏——
   100×40×40 的体在底面 x=50 处切开后，y=0 那张侧面的"平均点"z 从 20 变成 **16**。

改成**包围盒中心** `(min+max)/2` 后两个问题都消失：矩形面本来就精确，
圆盖面心从 0.061 回到 **0.000**，管壁面心从 0.122 回到 **0.000**（第 6 轮回归实测）。
规则表按面心定位，所以这一点必须稳。

代价：对**非凸面**（L 形面之类）包围盒中心可能落在面外——目前几何都是规则体，不受影响。

## 7. 建体命令的 ExtrudeType 与草图/放样（本轮实测）

### 7.1 ExtrudeType 的三种用法

`BlockBody.Create` / `CylinderBody.Create` 的 `ExtrudeType` 参数实测语义：

| 用法 | 效果 | 实测证据 |
|---|---|---|
| 不传（默认） | 与已有体重叠时**并集**进已有体 | 20×20×4 板上横放一个 6mm 立方体 → 只剩 1 个体，尺寸变成 20×20×6、11 个面 |
| `ExtrudeType.Cut` | 布尔减（挖掉） | 板上挖 r=2 通孔 → 1 个体 7 个面，上下端面各出现第 2 个 loop，孔壁是独立圆柱面 |
| `ExtrudeType.ForceIndependent` | 即使重叠也保持独立 | 同上的重叠立方体 → 2 个体；40³ 实体里放一个独立圆柱 → 2 个体 |

最后一条对应 CFD 里很常见的"在实体内部造流体域"。

### 7.2 草图 -> 实体 的正确姿势

录制脚本的写法（可用）：

```python
SketchCircle.Create(Point2D.Create(MM(0), MM(0)), MM(3))
ViewHelper.SetViewMode(InteractionMode.Solid, None)      # 草图才变成带面的体
faces = list(GetRootPart().Bodies[0].Faces)
ExtrudeFaces.Execute(Selection.Create(faces[0]), MM(10), ExtrudeFaceOptions())
```

坑：

- **必须用 `Point2D` 重载**。带显式 `Plane` 的重载（`Create(Point, r, Plane)`）在 Solid
  模式下**不产生面**（实测 bodies 仍是 0），没法拉伸。
- **拉伸方向是默认工作平面的法向**：本机实测为 **Y 轴**，不是 Z。所以草图拉伸出来的
  圆柱是"躺着的"，要和 `box()`/`cylinder()`（Z 向）混用就得自己 `move` 或换轴向命名。
- `ExtrudeFaces.Execute` **只能用三参形式** `(selection, 距离, 选项)`。显式补上第 5 个参数
  `ICommandInfo`（哪怕传 `None`）会让**脚本宿主直接中止整个脚本**，日志里只有一行空的
  `Script failed:`，连 traceback 都没有。同理：不要用"显式传 None 占位"的方式补可选参数，
  要换成少传参数的重载。
- 新文档里 **`DatumPlanes.Count == 0`**（默认没有基准面），所以 `SketchPlane.ActivateDatum`
  没有可激活的对象，想换草图平面得先在 GUI 里建基准面。
- 多个平行草图不可靠：实测在同一文档里画两个圆，切 Solid 后只生成 1 个面。
- `SketchCurveResult.CreatedCurve` 里的曲线在切到 Solid 模式后会**失效**
  （再拿去做选择会报 `Empty selection, trying to select a deleted object`）。

### 7.3 圆锥台（放样）在本版本做不出来

以下都试过，全部失败，别再重复：

| 尝试 | 结果 |
|---|---|
| `Loft.Create(Selection.Create(designCurve1), Selection.Create(designCurve2), LoftOptions(), None)` | `ValueError: The Loft command must include Bodies, Faces, Edges, Curves, or Points selection` |
| 选 `.ConvertToCurves()` 的结果（`ISketchCurveSelection`） | 同上 |
| 放样两张圆盘**面**（`Selection.Create(face)`） | 同上 |
| 用 `ExtrudeProfile.Execute(Geometry.Profile, …)` | `Geometry.Profile` **没有公开工厂方法**（只与钣金成形绑定），拿不到 Profile 对象 |

可行的替代：`scdm_lib.stepped_cone()` —— 用 N 段同轴圆柱近似（后续段传 `ExtrudeType.Add`
即合并成 1 个体）。实测 5 段 → 1 个体、11 个面。这是**近似**，不是真锥面。

> **更新（第 11 个回归用例）：真锥面已经做出来了，走的是旋转体，不是放样。**
> 见 §14。上面这些"放样做不出来"的记录仍然成立——`Loft` 和 `ExtrudeProfile` 依然不可用，
> 但 `RevolveFaces` 可以：梯形轮廓旋转整圈就是真锥台，三角形轮廓就是真圆锥。
> `stepped_cone()` 现在只是备选。

### 7.4 结果对象成员速查（取错会直接中止脚本）

| 命令 | 结果类型 | 取体成员 |
|---|---|---|
| `BlockBody.Create` | `BlockBodyResult` | `CreatedBody` / `CreatedBodies` |
| `SphereBody.Create` | `SphereResult` | `CreatedBody` / `CreatedBodies` |
| `CylinderBody.Create` | `CylinderBodyResult` | **只有 `CreatedBodies`** |
| `ExtrudeFaces.Execute` | `ExtrudeFacesResult` | **只有 `CreatedBodies`** |
| `ExtrudeProfile.Execute` | `ExtrudeSolidBodyResult` | `CreatedBody` / `CreatedBodies` |
| `SketchCircle.Create` | `SketchCurveResult` | `CreatedCurve` / `CreatedCurves` |

`scdm_lib._created_body()` 依次尝试 `CreatedBody`、`CreatedBodies[0]`，最后兜底取
根零件里最后一个体。

## 8. 面的法向、类型与通用选面（第 5 个回归用例实测）

### 8.1 法向：Plane 上没有 .Normal

```python
g = face.Shape.Geometry           # 平面面 → Geometry.Plane
n = g.Frame.DirZ                  # 法向在这里（X/Y/Z 三个分量）
if face.Shape.IsReversed:         # 同一个平面可能被面反向引用，必须看这个标志
    n = (-n.X, -n.Y, -n.Z)
```

`Geometry.Plane` 暴露的是 `Frame`（含 `Origin`/`DirX`/`DirY`/`DirZ`），**没有 `.Normal`**。
非平面面拿不到法向，`scdm_lib.face_normal()` 对它们返回 `None`。

### 8.2 面类型：区分外壁和内壁

```python
type(face.Shape.Geometry).__name__   # 'Plane' / 'Cylinder' / 'Cone' / 'Sphere' / 'Torus'
```

管子外壁和内壁**都是 `Cylinder`**，靠类型分不开；这时要用 `{"rest": True}` 的先后顺序，
或者按面积/位置区分。`scdm_lib.face_kind()` 就是取这个类型名。

`Modeler.Face.ContainsPoint(Geometry.Point)` 可以判断某点是否在面上——`face_at_point()` 用它，
配合 `nearest_face()`（按面心距离）应付"点没精确落在面上"的情况。

### 8.3 选面语义：整面判定、按面心定位

`match_faces` **不做面分割**。实测一个 100×40×40 的长方体（6 个面）：

| 调用 | 结果 |
|---|---|
| `faces_by_normal(body, "z", -1)` | 1 |
| `faces_by_kind(body, "plane")` | 6 |
| `face_at_point(body, 50, 20, 0)` | 1 |
| `faces_by_area(body, min_area=3000)` | 4 |
| `faces_in_box(body, xmax=50)` | 5 |

含义：`{"between": ("x", 30, 70)}` 对一整张底面只会**整体命中或整体不命中**（看它的面心落在哪），
不能只切一段出来。要"半段加热"必须先做面分割（`SplitFace`），目前没封装。

### 8.4 第 5 个回归用例（selftest_boundaries）的基线

`Channel 100x40x40` + `Pipe 30x12x12`，7 个命名选择：

| 名字 | 面数 | 面心 | 面积 mm² |
|---|---|---|---|
| inlet | 1 | (0,20,20) | 1600.00 |
| outlet | 1 | (100,20,20) | 1600.00 |
| symmetry | 1 | (50,0,20) | 4000.00 |
| wall | 3 | (50,40,20)/(50,20,40)/(50,20,0) | 4000.00 各 |
| pipe_inlet | 1 | (0,100,0) | 62.83 |
| pipe_outlet | 1 | (30,100,0) | 62.83 |
| pipe_wall | 2 | (15,100,0) | 1130.97 + 753.98 |

## 9. 面分割与体分割（第 6 个回归用例实测）

| 调用 | 作用 | 实测结果 |
|---|---|---|
| `SplitFace.ByTwoPoints(faceSel, p1, p2)` | 用面上两点连线切面 | 100×40 的底面用 (50,0,0)-(50,40,0) 切开 → 一张变两张 2000 mm²，面心 (25,20,0) / (75,20,0)。**三参 / 四参 / 五参（含 `SplitFaceOptions()`）形式都能用** |
| `SplitBody.ByCutter(bodySel, Plane, None)` | 用平面切体 | 100×40×40 在 x=50 处切开 → **2 个体**，各 6 面 |

要点：

- 两个点必须落在被切的那张面上。
- **切完原面对象就失效**，必须重新枚举 `body.Faces` 再取（`scdm_lib.split_face_by_line` 的注释里写了）。
- 切面**不会改变相邻面的面积**（实测侧面仍是 4000 mm²），但会在相邻面的边界上多出共线顶点——
  这正是 §6 里"平均值失真"的来源，也是改用包围盒中心的原因。
- 构造平面的写法：`Plane.Create(Frame.Create(Point.Create(...), Direction.Create(nx,ny,nz)))`。
- `SplitFace` 还有 `ByCutter`（用刀具体面）、`ByParametric`、`ByCurves`，`SplitBody` 还有
  `ByCutter(sel, cutterSelection, …)`；都没用上，需要时再试。

## 10. 旋转与"异常信息陷阱"（第 7 个回归用例实测）

### 10.1 Move.Rotate 的角度是弧度

```
Move.Rotate(selection, Line.Create(Point.Create(...), Direction.Create(nx,ny,nz)),
            angle, MoveOptions())
```

**`angle` 是弧度，不是度。** 实测同一个 40×10×10 的长条绕 Z 轴旋转：

| 传入 | 实际旋转 | 包围盒 |
|---|---|---|
| `0.7853981633974483`（45° 的弧度） | 45° | **35.355 × 35.355 × 10.000** ✓ |
| `45.0`（当成度数传） | 58.3°（45 rad 对 2π 取模） | 29.522 × 39.289 × 10.000 ✗ |

第二种**看起来也像个合理结果**，不对比包围盒根本发现不了。`scdm_lib.rotate()` 对外用度，
内部 `math.radians` 转换。

### 10.2 异常信息里不能有非 ASCII —— 会让宿主静默中止整个脚本

实测：`faces_by_normal(body, (0.7, 0.7, 0.0))` 触发了 `_axis_index` 的 `ValueError`，
而那行错误信息里有中文。结果**不是**被 `try/except` 接住，而是：

- 脚本立刻停止，后面的语句一条都不执行
- `/ScriptOutput` 日志里没有任何 traceback
- SpaceClaim 自己的日志里只有一行空的 `Script failed:`

对照实验：同样机制下，ASCII 信息（`move(): body is None`）能正常出现在应用日志里，
说明问题出在**非 ASCII 的异常信息**本身，不是异常类型。
所以库里所有 `raise` 的信息都改成了纯 ASCII（中文只保留在 docstring 和注释里）。

`scdm_lib.faces_by_normal()` 现在也接受任意向量方向 `(nx,ny,nz)`，用于斜几何的法向匹配；
`match_faces` 的 `{"normal": (nx,ny,nz)}` 一直支持这一点。

## 11. 成对边界条件（第 8 个回归用例实测）

三类边界条件的难点不在命名，而在**几何前提**；`scdm_lib` 里对应的函数一次做完。

### 11.1 交界面（共轭传热 / 流固耦合）

前提：两个体在**同一位置各有一张面**。用 `separate=True` 让相邻的两个体保持独立
（默认重叠/相接会被并集，见 §7.1）。

实测：`Solid 50x40x40 (x 0~50)` + `Fluid 50x40x40 (x 50~100, separate=True)`
→ `find_coincident_pairs(solid, fluid)` 返回 **1 对**；两张面都是中心 (50,20,20)、面积 1600 mm²。
`name_interfaces(solid, fluid, "interface")` → `interface_a` / `interface_b` 各 1 面。

配对判据：面心三轴坐标吻合 + 面积相对误差在容差内。

### 11.2 内部面（baffle / porous-jump / fan / radiator）

前提：**面必须存在于体内部**，而实心体内部本来没有面——必须先切开。
`name_internal_baffle(body, axis, value, name)` = `split_body_by_plane` + 找那两张重合面 + 成对命名。

实测：`Bar 100x40x40` 在 x=50 切开 → 体数 3→4，两张内表面都是中心 (50,120,20)、面积 1600 mm²，
命名为 `baffle_a` / `baffle_b`。

扫描时**限定在切分前那个体的包围盒内**，否则同一坐标上别的体的面会被误抓
（本例里 Solid/Fluid 的交界面也在 x=50，靠包围盒排除掉了）。

### 11.3 周期面（periodic）

前提：两侧面**形状必须对应**。`faces_match(f1, f2)` 比对面积与包围盒三向尺寸
（位置允许不同）；实测 x=0 与 x=100 的两张 1600 mm² 面 → `True`。

配对命名用 `name_face_pair("periodic_hot", "periodic_cold", f1, f2)`。

### 11.4 体名即 cell zone

SpaceClaim 里"一个体"在 Fluent Meshing 里通常就是一个 cell zone，所以
`box(..., name="Fluid")` / `box(..., name="Solid")` 里的体名也要按 cell zone 命名规范起
（这条是工作流惯例，本仓库未做端到端验证）。

## 12. 草图工具的限制与非圆形截面（第 9 个回归用例实测）

### 12.1 硬限制：文档里一旦有实体，新建草图就崩

| 场景 | 结果 |
|---|---|
| 空文档 → `SketchPolygon.Create` → Solid → 拉伸 | ✅ 正常 |
| 空文档 → `box()` → `SketchPolygon.Create` | ❌ **崩**（`SketchPolygon.Create` 处抛 .NET 空引用，脚本直接中止） |
| 两个**重叠**的草图画在同一位置 → Solid | 只得到 **1 张面**（合并了） |
| 两个**不重叠**的草图 → Solid | ✅ **1 个体带 2 张面**，各自独立 |
| 逐张拉伸这些面 | ✅ 两次拉伸都成功，各自成体 |

所以可靠用法是：**先把所有草图一次画完（互不重叠，拉开间距），切一次 Solid，再逐个拉伸**。
这就是 `scdm_lib.polygon_prisms()` 的由来，`polygon_prism()` 只是它的单元素包装。
`box` / `cylinder` / `tube` / `stepped_cone` 不走草图，**不受这个限制**。

### 12.2 ExtrudeFacesResult 不可靠，改用"体集合之差"

拉伸一张面时，`ExtrudeFacesResult.CreatedBodies[0]` 在多面表面体的情况下可能给回一个
**DesignFace**（实测报 `'DesignFace' object has no attribute 'Faces'`）。
`scdm_lib._extrude_face()` 因此不看结果对象，而是比较拉伸前后的体集合：

- 出现新体 → 多轮廓情形（草图体留着剩下的面，新体是拉出来的棱柱）
- 没有新体 → 单轮廓情形（草图体自己变成了实体），此时用 `DesignFace.Parent` 反查

### 12.3 非圆形截面的实测数值

`polygon_prisms` 里 radius 是**外接圆半径**（`SketchPolygon.Create` 第二个点定义顶点）：

| 截面 | 端面面积 | 包围盒（沿轴向长度已知时） |
|---|---|---|
| 正六边形 R=5 | 64.95 mm² = (3√3/2)R² | 10.000 × 8.660 |
| 正八边形 R=6 | 101.82 mm² = 2√2·R² | 12.000 × 12.000 |

八边形的顶点在 0°/45°/…，两个方向的包围盒都是 2R（不是 2R·cos22.5°）；侧面每片面积
= 边长 × 长度 = 2R·sin(22.5°) × L（R=6, L=15 时 68.88 mm²）。

### 12.4 草图平面的法向是 Y

草图拉出来的棱柱先沿 **+Y**。`polygon_prisms` 随后用 `rotate` 摆到目标轴向：
`axis="z"` → 绕 X 转 +90°；`axis="x"` → 绕 Z 转 −90°；`axis="y"` → 不转。
最后用 `_anchor_prism()` 把底面中心对齐到 origin（与 `cylinder()` 的约定一致）。

## 13. 任意轮廓：折线与椭圆（第 10 个回归用例实测）

### 13.1 两个可用的画法

| 轮廓 | 调用 | 实测 |
|---|---|---|
| 任意折线 | `SketchLine.CreatePolyLine(List[Point], False, False)` | 梯形 (0,0)(20,0)(15,10)(5,10) → 端面 **150.00 mm²**（=(20+10)/2×10）；拉伸 20 后 6 个面，侧面 400.00 / 200.00 / 223.61×2 |
| 椭圆 | `SketchEllipse.Create(Point, Direction, Direction, Double, Double)` | 半轴 10 与 5 → 端面 **157.08 mm²**（=π·10·5）；拉伸 15 后 3 个面，侧面 **726.63 mm²**（≈周长 48.44×15） |

折线要**显式闭合**（末点 = 首点），点用 3D `Point.Create(MM(u), MM(0), MM(v))`——
草图平面是 **y=0 的 XZ 平面**，u 沿世界 X、v 沿世界 Z。

`List[Point]` 由脚本宿主预加载（`from System.Collections.Generic import List`），
直接写 `lst = List[Point]()` 即可。

`SketchLine` 还有 `Create(Point, Point, bool, bool)`、`CreateChain(IList[Point], bool)`；
`SketchArc` 有 `Create3PointArc` / `Create` / `CreateSweepArc`——都还没试。

### 13.2 profile_prisms 的通用化

三种轮廓（polygon / polyline / ellipse）共用同一套批量机制：
所有草图先画完（互不重叠）→ 一次 Solid → 逐个拉伸 → rotate 摆正 → 按包围盒中心锚定。

轮廓坐标是**局部**的，批量接口按每个轮廓的半宽自动算间距（`spacing = max(最大半宽)*3`），
拉完再用"离哪个偏移最近"把 Solid 之后的面分配给对应轮廓。

### 13.3 案例数值（selftest_profile）

| 体 | bbox | 面数 | 端面 | 侧面 |
|---|---|---|---|---|
| TrapDuct | 20.000 × 10.000 × 20.000 | 6 | 150.00 ×2 | 400.00 / 200.00 / 223.61 ×2 |
| EllipDuct | 15.000 × 20.000 × 10.000 | 3 | 157.08 ×2 | 726.63 |

## 14. 回转体：真锥台/圆锥做出来了（第 11 个回归用例实测）

### 14.1 命令与角度单位

```
RevolveFaces.Execute(面选择, Line.Create(点, 方向), 角度, RevolveFaceOptions())
```

**角度是弧度**（与 `Move.Rotate` 一致）：传 `2*pi` 得到整圈；传 `360` **也**得到整圈，
因为 360 rad 已远超一圈，推测底层会归一化到整圈——所以别拿这两个数去判断单位，
要看形状：矩形轮廓整圈转出来必须是完整圆柱（实测 bbox 10×10×10、3 个面、
端面 78.54 = π·5²、柱面 314.16 = 2π·5·10）。

偏角旋转（如 90° 扇形）用 `math.radians(90)`，未实测。

### 14.2 真锥台取代阶梯近似

| 做法 | 结果 |
|---|---|
| 梯形轮廓 (0,0)(8,0)(4,20)(0,20) 旋转整圈 | **真锥台**：16×16×20，3 个面，底 201.06、顶 50.27、侧面 768.91 |
| 三角形轮廓 (0,0)(8,0)(0,20) 旋转整圈 | **真圆锥**：20×16×16，2 个面，底 201.06、侧面 541.38 |

这推翻了 §7.3 的结论：**放样确实不可用，但旋转体可用**，所以真锥面是有办法的。
`stepped_cone()` 从"唯一方案"降级为"备选"。

圆锥轮廓只能给 3 个点（一端半径为 0 时若给 4 个点，末两点重合会让轮廓退化）。

### 14.3 测量：必须用面解析包围盒，不能用边采样

这一段是本轮最值钱的教训。用边采样法测圆锥：

```
body_extent(cone, "z") = (0.0, 0.0)      ← 完全错，圆锥长度是 20
```

原因有两层：

1. 圆锥**顶点是孤立顶点**——它不在任何边的 `GetPolyline` 采样点上；
2. 圆锥面**没有缝边**，所以也不存在一条从顶点到底面的边让顶点“顺带”被采到。

换句话说，任何"极值只是一个点而不是一条边"的面（圆锥、球面、圆环面）都会被测错，
连带 `name_boundaries` 失效（`lo == hi` → 所有面判成同一端）。

修法：改用 `Face.GetBoundingBox(Matrix.CreateScale(1.0))`，它返回**解析**包围盒
（`Center` / `Size` / `MinCorner` / `MaxCorner`），圆锥面正确给出 z = 0..20。
`body_extent` 现在是所有面解析包围盒的并集，既准确又快。

另一个坑：`Face.GetExtremePoint(d, d, d)`（三个方向相同）**会抛 `ValueError`**，
不要用；我在 §6 那一轮曾想用它兜底，结果异常被 `try/except` 吞掉、问题更隐蔽。

### 14.4 案例数值（selftest_revolve）

| 体 | bbox | 面数 | 面心 / 面积 |
|---|---|---|---|
| Frustum | 16.000 × 16.000 × 20.000 | 3 | 底 201.06 @ (0,0,0) · 顶 50.27 @ (0,0,20) · 侧面 768.91 @ (0,0,10) |
| Cone | 20.000 × 16.000 × 16.000 | 2 | 底 201.06 @ (40,0,0) · 侧面 541.38 @ (50,0,0) |

## 15. 扫掠（弯管/弯头）：**没打通，别再从头试**（本轮实测记录）

目标：沿一条路径扫掠圆形轮廓 → 弯管/弯头。签名是现成的：

```
Sweep.Execute(轮廓选择, 路径选择, SweepCommandOptions(), ICommandInfo)
```

路径曲线**可以**拿到：在切 Solid 模式**之前**抓住 `SketchCurveResult.CreatedCurve[0]`，
切完之后它仍然可选（实测 `Selection.Create(curve).Count == 1`）。注意
`DesignCurve.Shape` 是 `CurveSegment`，**没有 `.Edges`**（想用边采样测路径包围盒会 AttributeError），
但它有 `GetBoundingBox(Matrix.CreateScale(1.0))` 可用。

试过的四种组合：

| # | 轮廓 | 路径 | `Success` | 实际结果 |
|---|---|---|---|---|
| 1 | 圆 r=3（XZ 平面，法向 Y） | 两段折线（XZ 平面） | True | **什么都没发生**（还是那张平面圆，1 个面） |
| 2 | 同上 | 三点弧，**误放**在 XY 平面 | True | 生成了 1 个体 3 个面（procedural 侧面 2281.27 + 两个 28.27 端面），但包围盒 54.918×54.918×6 与手算不符 |
| 3 | 同上 | 三点弧，改到 XZ 平面（与轮廓垂直） | True | **什么都没发生**（1 个面） |
| 4 | 同上 | — | — | — |

**两条结论**：

1. **`Sweep.Execute` 返回的 `Success=True` 完全不可信** —— 第 1、3 种情况下它报成功却
   一个实体都没生成。判成功必须看几何（体数 / 面数变化），不能看 `Success`。
2. 我还没找到"能稳定扫出正确弯管"的参数组合。第 2 种虽然出了体，但尺寸对不上，
   说明要么路径/轮廓的相互关系不是我以为的那样，要么 `SweepCommandOptions` 里有必须设置的项
   （还没查它的成员）。

**下次从哪里接着做**：先反射 `SweepCommandOptions` 的成员（可能有 profile 对齐 / 保持法向之类的开关），
再考虑把路径做成"实体的边"而不是草图曲线（草图曲线只在文档无实体时能创建，这个限制见 §12.1）。

### 15.1 顺带确认的平面约定（有用，容易踩）

| 命令 | 曲线/轮廓落在哪个平面 |
|---|---|
| `SketchCircle.Create(Point2D, r)` | **默认工作平面**（本机是 XZ，法向 Y） |
| `SketchPolygon.Create(Point, Point, ...)` | 同上（给了 3D 点也仍投影到工作平面） |
| `SketchEllipse.Create(Point, Dir, Dir, r1, r2)` | 由**显式方向**决定，可任意 |
| `SketchLine.CreatePolyLine(List[Point], ...)` | **直接用原始 3D 坐标** |
| `SketchArc.Create3PointArc(Point, Point, Point)` | **直接用原始 3D 坐标** |

所以想让路径弧落在 XZ 平面里，点必须写成 `(u, 0, v)`；写成 `(u, v, 0)` 就会跑到 XY 平面去
（本轮的坑就在这：中点写成 (20,10,0) 导致整条弧偏出轮廓平面）。

补充（第 12 轮）：`SweepCommandOptions` 的成员只有
`SweepNormalTrajectory` / `ExtrudeType` / `KeepMirror` / `KeepLayoutSurfaces` /
`KeepCompositeFaceRelationships` / `Select`；`SweepCommandResult` **只有 `Success` 和
`IsActiveDoc`**（没有 `CreatedBodies`）。把 `SweepNormalTrajectory` 分别设 False / True
重试上面第 3 种（几何上正确的）配置：**两种都返回 `Success=False` 且毫无几何变化**。
也就是说这个返回值两种情况都不可信，只能靠体数/面数变化判成败。

### 15.2 最后一条没试过的路也试完了：路径用「实体的边」（第 17 轮，仍然不通）

第 15 节末尾留的"下次接着做"是"把路径做成实体的边而不是草图曲线"。已经做完，**结论一样：不通。**

精确签名（反射）：

```
Sweep.Execute(ISelection selection, ISelection trajectories, SweepCommandOptions options, ICommandInfo info)
Sweep.Execute(ISelection selection, ISelection trajectories, Double distance, SweepCommandOptions options, ICommandInfo info)
SweepCommandOptions : GeometryCommandOptions     // 自己声明的只有 SweepNormalTrajectory / ExtrudeType
```

试过的组合（判定一律看体数/面数变化，不看 `Success`）：

| # | 轮廓 | 路径 | `Success` | 实际结果 |
|---|---|---|---|---|
| 5 | 圆柱端面（法向 X） | 长方体的直边（沿 X，起点与轮廓同平面） | True | **面数 8→8，毫无变化** |
| 6 | 同上 | 同上，`SweepNormalTrajectory=True` | True | 同上，无变化 |
| 7 | 圆柱端面（法向 Z） | 圆柱的一圈**圆边**（torus 式弯管） | **False** | 面数 5→5 |
| 8 | 圆盘面（x=+1 那侧） | 长方体的直边 | True | 面数 9→9 |

**最终结论：这个版本（2022 R1 / v221）的 `Sweep` 在脚本里就是不能用**——
草图曲线路径、实体边路径、直边、圆边、两个 `SweepNormalTrajectory` 取值、
轮廓给面/给草图区域都试过了，结果不是"无变化"就是 `Success=False`。
**弯管请直接用 §20 的 `elbow()` / `torus()`（草图圆 + 回转），不要再碰 Sweep。**

## 16. 球体与布尔减的差异（第 12 个回归用例实测）

```
SphereBody.Create(Point center, Double radius)                      # 无 ExtrudeType
SphereBody.Create(Point center, Double radius, ExtrudeType, ICommandInfo)
SphereBody.Create(Point center, Point onSphere, ExtrudeType, ICommandInfo)
```

**球体本身**：`SphereBody.Create(中心, r)` 可用。实测 r=5、球心 (10,10,10) →
1 个体、1 个面（`face_kind` = `sphere`）、面积 **314.16 mm² = 4πr²**、包围盒 10×10×10。

**关键差异：球做布尔减必须用 `ForceCut`。**

| ExtrudeType | 结果 |
|---|---|
| `Cut` | **没挖掉**：球变成第三个独立体，目标方块仍是 6 个面 |
| `ForceCut` | ✅ 挖出来了：20³ 方块变成 **7 个面**（6 平面 + 1 球面），球面面积 **452.39 mm² = 4πr²**、面心正是球心 |

注意 `box` / `cylinder` 的 `cut=True`（用 `ExtrudeType.Cut`）是**验证过可用**的
（第 4 个用例：板上挖通孔 → 7 个面），所以不是"Cut 一律无效"，而是**球体这个命令对 Cut 不敏感**。
`scdm_lib.sphere(cut=True)` 内部已经固定用 `ForceCut`。

顺带：球面可以用 `{"kind": "sphere"}` 规则精确选中（`faces_by_kind` 直接读几何类型名）。

### 16.1 又一个名字编码的坑

没有命名的体保留的是**本地化默认名**（中文界面下是中文）。`"%s" % body.Name`
在**格式化阶段**就抛 `UnicodeEncodeError` —— 这一步发生在 `_safe_print` 的保护之前，
所以会把整个脚本干掉（第 12 轮校验脚本就是这么崩的，报错甚至出现在
`--- verify` 段落里，看起来像校验逻辑出错）。

修法：`scdm_lib._ascii(name)` 先转 ASCII 再格式化；`verify_model.py` 的体名打印已经用它。
自己写脚本时，任何 `print` 里出现 `body.Name` / 组名都要先过一遍 `_ascii`。

## 17. 按刀具体切分面：刀具体必须传"面"（第 13 个回归用例实测）

目标：在墙面/底面局部"盖章"出一个区域（比如圆形射流入口、喷嘴落点），好单独命名。

```
SplitFace.ByCutter(目标面选择, 刀具体选择, SplitFaceOptions(), ICommandInfo)
```

**关键：第二个参数必须是一张面，不能是整个体。**

| 刀具选择 | 结果 |
|---|---|
| 整个圆柱体 `Selection.Create(cylinderBody)` | `Success=False`，**什么都没切**（面数不变） |
| 圆柱的侧面 `Selection.Create(lateralFace)` | ✅ `Success=True`：40×40 的板底 1600 mm² 变成两张 |

切分结果（Plate 40×40×10，r=5 的圆柱穿过底面）：

| 面 | 面积 | 面心 | loops |
|---|---|---|---|
| 圆补丁 | 78.54 mm² = π·5² | (20,20,0) | 1 |
| 其余部分 | 1521.46 mm² = 1600 − 78.54 | (20,20,0) | 2 |

两条可直接用上的经验：

1. **切完的两张面面心相同**，所以 `at` / `in_box` / `point` 这类位置规则区分不了它们；
   要用**面积**或**边界环数**。`match_faces` 因此新增了 `loops` 键：
   `{"normal":"z","sign":-1,"loops":1}` 取补丁，`{"loops":2}` 取带内环的那张。
   `loops` 读的是 `face.Shape.Loops.Count`。
2. 不知道刀具的哪张面能切时，`scdm_lib.split_face_by_body()` 会依次拿刀具的每张面去试，
   返回第一张成功的（失败的调用是无害的：`Success=False` 且不改几何）。

`SplitBody.ByCutter(体, 体)` 试过两种参数个数都抛 `ValueError`，没继续深挖——需要切体时
用已验证的 `split_body_by_plane()`。

## 18. 外流场配方（第 14 个回归用例，一次跑通）

绕圆柱的外流场流体域，**只有 4 行**：

```python
domain = box(60.0, 40.0, 40.0, origin=(0, 0, 0), name="Domain")     # 1) 先建外框
cylinder(5.0, 60.0, origin=(30, 20, -10), axis="z", cut=True)       # 2) 再布尔减掉障碍物
name_faces_by_rules(domain, [                                       # 3) 一次命名全部边界
    ("inlet",  {"normal": "x", "sign": -1}), ("outlet", {"normal": "x", "sign": 1}),
    ("obstacle", {"kind": "cylinder"}),
    ("top_wall", {"normal": "z", "sign": 1}), ("bottom_wall", {"normal": "z", "sign": -1}),
    ("side_wall", {"rest": True}),
])
```

关键点：

- **顺序是先外框、后障碍物**。`cut=True` 是"把这个体的体积从已有实体上减掉"，所以障碍物必须
  在流体域之后创建。减完之后文档里**只剩流体域一个体**，障碍物壁面就是那个圆柱面。
- `{"kind": "cylinder"}` 精确抓到障碍物壁面（读几何类型名，不依赖位置）。
- `{"rest": True}` 兜底收掉剩下的两张侧面，避免了"同一个名字建两次命名选择"的问题。

实测（Domain 60×40×40、圆柱 r=5 贯穿）：

| 名称 | 面数 | 面积 mm² | 面心 | loops |
|---|---|---|---|---|
| inlet | 1 | 1600.00 | (0,20,20) | 1 |
| outlet | 1 | 1600.00 | (60,20,20) | 1 |
| obstacle | 1 | 1256.64 = 2π·5·40 | (30,20,20) | 2 |
| top_wall | 1 | 2321.46 = 2400 − 78.54 | (30,20,40) | 2 |
| bottom_wall | 1 | 2321.46 | (30,20,0) | 2 |
| side_wall | 2 | 2400.00 各 | (30,0,20) / (30,40,20) | 1 |

总面积 13899.56 mm²，与手算（盒子表面积 12800 + 孔壁 1256.64 − 两个圆口 157.08）一致 ✓。

## 19. 倒圆角 / 倒角：边这套 API（第 15 个回归用例）

### 19.1 命令签名（反射所得，全部实测可用）

```
ConstantRound.Execute(ISelection selectObject, Double roundRadius, ICommandInfo info)          <- 用这个
ConstantRound.Execute(ISelection selection, Double radius, ConstantRoundOptions options, ICommandInfo info)
ConstantRound.Modify(ISelection selection, Double radiusOffset, ICommandInfo info)

Chamfer.Execute(ISelection selection, Double distance, ICollection chamferStops, ICommandInfo info)   <- distance2=None 走这个
Chamfer.Execute(ISelection selection, Double d1, Double d2, ICollection chamferStops, ICommandInfo info)
Chamfer.Execute(ISelection selection, Double distance, Boolean copy, ICommandInfo info)
Chamfer.Execute(ISelection selection, Double d1, Double d2, Boolean copy, ICommandInfo info)

FullRound.Execute(ISelection selFaces, ICommandInfo info)      <- 实测 Success=True 但面数不变，没用起来
RoundInfo.Create(DesignFace desFace) -> RoundInfoResult        <- 试出来 Success=False（对立方体面）
```

`ICommandInfo` 在这两处传 `None` 是安全的（3 参 / 4 参形式都跑通了）。注意这和
`ExtrudeFaces` 不一样：那里的可选参数位传 `None` 会让宿主静默中止整个脚本。

结果对象有两套名字：

- `ConstantRoundResult` / `ChamferResult` 都有 `CreatedFaces` / `CreatedEdges` / `CreatedSurfaces`，
  但**实测 `CreatedSurfaces.Count == 0`，哪怕倒角明明成功了**。别拿它当判据，看面数/总面积。
- 参数类 `ConstantRoundOptions`（只有一个 `Copy` 属性）、`ChamferOptions`（空的）、`Chamfer.ChamferStop`。

### 19.2 三条硬约束

1. **只吃边。** `Selection.Create(face)` → `StandardError`；`Selection.Create(body)` → `ValueError`。
   体不会自动展开成边。选择对象用 `Selection.Create(edge_list)`（普通 Python list 就行）。
2. **失败信息是中文。** 半径超出局部可达范围、边集里混了切向边或已倒过角的边时，
   抛的是中文 `StandardError`（"无法对边倒圆角"）。非 ASCII 的异常信息一旦逃出脚本，
   宿主会**静默中止整个流程**（见 §10.2），所以 scdm_lib 一律先 `except` 再抛 ASCII 的
   `RuntimeError`。实测会失败的情况：20mm 立方体给 r=9；把倒角前的 `body.Edges` 列表
   在倒角后再用一次。
3. **每次倒完，旧的 `DesignEdge` / `DesignFace` 包装对象全部失效。** 必须重新
   `body.Edges` / `body.Faces` 取。这是 `round_by_rules` 每条规则都重新枚举的原因，
   也意味着规则表里的 `{"rest": True}` 看到的是**当前**体（实测 20mm 立方体先倒 4 条竖边，
   `rest` 拿到 16 条边：8 条原始边 + 8 条倒圆新长出来的切向直线边）。

### 19.3 边的几何怎么读

`DesignEdge` 是包装对象，几何在 `.Shape` 上（`SpaceClaim.Api.V22.Modeler.Edge`）：

| 成员 | 说明 |
|---|---|
| `.Length` | **米**，乘 1000 得 mm |
| `.StartPoint` / `.EndPoint` | 在外壳 `Edge` 上**是可用的**（`DesignEdge` 上才没有）。闭合圆边两端都退化成圆心 |
| `.GetBoundingBox(Matrix.CreateScale(1.0))` | 解析包围盒：`.Center` / `.MinCorner` / `.MaxCorner`，米 |
| `.Geometry` | `Geometry.Line` / `Geometry.Circle` / `Geometry.Ellipse` / … **类型名就是边类型** |
| `.IsSmooth` / `.IsConcave` | 相切软边 / 凹边 |
| `.GetPolyline(PolylineOptions())` | 离散点，量闭合圆边长度、算点到边距离时用 |

`Geometry.Line` 有 `.Direction` 和 `.Origin`；**曲线类型上没有 `.Direction`**，所以
`edge_direction()` 先看 `edge_kind() == "line"`，否则会把圆的某个轴向错当成边的方向。

### 19.4 倒圆之后的面数与面积（重要，容易算错）

20mm 立方体 12 条边全倒圆 r=2：面数 **6 → 26**，边数 12 → 48（24 条直线 + 24 条圆）。

- 6 张平面面：**缩成 (20−2r)² = 16×16 = 256 mm² 的方块**，edges=4 全直线。
- 12 张倒圆面：`cylinder`，`(πr/2)(20−2r) = 50.265 mm²`，edges=4（2 圆 + 2 直线）。
- 8 张球角面：`sphere`，`4πr²/8 = 2π = 6.283 mm²`，edges=3 全圆。
- 总面积 2189.451 mm² = 6×256 + 12×50.265 + 8×6.283 ✓（手算一致）。

**别按"20×20 去四角 = 396.57"去算平面面**：平面面和外圈之间是**相切**的，SpaceClaim
不生成相切边，所以平面面就是那个内缩方块，角上那部分由球角面覆盖。切开看就是

```
实心体 = { p : dist(p, 内缩立方体 [2,18]³) <= 2 }
```

自己拿手算核面积时用这个定义，别用"圆角矩形"的公式。

其它实测数值：

| 情形 | 面数 | 关键面积 |
|---|---|---|
| 20³ 全倒圆 r=2 | 26 | 平面 6×256.00 · 圆柱 12×50.27 · 球 8×6.28 |
| 20³ 只倒 4 条竖边 r=3 | 10 | 端面 392.27 = 400−(4−π)·9 · 圆柱 4×94.25 = (π·3/2)·20 · 侧壁 4×280.00 = (20−6)·20 |
| 20³ 全倒角 d=2 | 26 | 6 平面 + 12 斜面 + 8 三角面，边全是直线 48 条 |
| 20³ 只倒 4 条竖边、不等距 d1=4 d2=1 | 10 | 边 24 条全直线 |
| 4×4×10 方管四条长边倒圆 r=1 | 10 | 端面 15.142 = 16−(4−π) · 圆柱 4×15.708 = (π/2)·10 · 平面壁 4×20.00 |
| tube(10,6,20) 四个管口圆边倒圆 r=1 | 8 | 4 张平面环 + 4 张圆环面（torus 段） |

注意对比第 5、6 行和第 2 行：**端面面积什么时候是"圆角矩形"、什么时候是"内缩方块"，
取决于相邻的边有没有被一起倒圆**。只倒竖边时端面还是 4×4 去四角（15.14）；
12 条边全倒时平面面就已经内缩了。

## 20. 弯头 / 圆环：真圆截面的 torus 段（第 16 个回归用例）

### 20.1 结论：弯管不要走 Sweep，走"草图圆 + 回转"

`revolve_profiles` 原来只吃折线轮廓。给它加上 `kind="circle"` 之后，
**一个真正的圆轮廓绕共面轴回转就能得到真圆截面的圆环段**——这就是弯头，
而且是解析曲面（`torus`），不是多面体近似。§15 里 Sweep 那条死路可以彻底绕开了。

```
SketchCircle.Create(Point2D.Create(MM(v), MM(u)), MM(r))     # 圆心落在全局 (X=u, Z=v)
RevolveFaces.Execute(faceSel, Line.Create(Point(off,0,0), Direction.Create(0,0,1)),
                     radians, RevolveFaceOptions())
```

**关键坑：`Point2D` 的两个分量不是全局 X / Z。** 实测 `Point2D.Create(a, b)`
得到的是 `X=b, Z=a`（本机默认工作平面法向是 Y）。写成 `Point2D.Create(MM(20), MM(0))`
会把圆心放到 `(0, 0, 20)` —— 正好落在回转轴上，回转出来的是**球**而不是圆环
（实测：1 个 `sphere` 面、113.097 mm² = 4π·3²，转 90° 得到球八分之一 + 两个半圆盘）。
这个"看起来成功了但形状完全不对"的失败方式很容易骗过人。

另一个硬性前提：**圆必须完全避开回转轴**（`center_u > radius`），否则轴会切进轮廓。
库里直接抛 ASCII 的 `ValueError`。

### 20.2 实测数值

| 情形 | 面数 | 面积 mm² | 包围盒 |
|---|---|---|---|
| r=3、R=20、360° | 1（`torus`） | 2368.705 = 4π²Rr | 46 × 46 × 6 |
| r=3、R=20、90° | 3（torus + 2 个整圆端面） | 592.176 = 4π²Rr/4；端面各 28.274 = πr² | 23 × 23 × 6 |
| r=2、R=15、45° | 3 | 148.044 = 4π²Rr·(45/360)；端面各 12.566 | 4 × 12.021 × 7.808 |
| r=2、R=12、180° | 3 | 473.741 = 4π²Rr/2；端面各 12.566 | 28 × 14 × 4 |

摆位：起始端面（θ=0 那个横截面）的圆心落在 `origin`；`axis` 是弯曲轴，
弯头躺在垂直于它的平面里。axis 与起始方向/弯曲平面的对应（实测）：

| axis | 起始方向 | 弯曲平面 |
|---|---|---|
| `"z"` | +Y | XY |
| `"x"` | +Y | YZ |
| `"y"` | −Z | ZX |

axis 的换算是复用 `revolve_profiles` 里那套（`"x"` → 绕 Y 转 +90°、`"y"` → 绕 X 转 −90°），
换完之后再用 `move` 把起始端面圆心平移到 `origin`（位移是解析算出来的，
因为回转是在 `x = off_i` 那条轴上做的，`off_i = i × 3 × max(R+r)`）。

### 20.3 拼成完整弯管：过盈并集的小面片

直管（`cylinder`）与弯头端面**过盈 1mm** 就会并成一个体。实测 r=3、R=20 的 90° 弯头
+ 两段直管 → 1 个体 7 个面：

| 面 | 面积 mm² |
|---|---|
| inlet（端面） | 28.27 |
| outlet（端面） | 28.27 |
| 两段直管壁 | 405.27 各 |
| 圆环面 | 573.89（比纯弯头的 592.176 少，被直管的过盈吃掉一小段） |
| 两张近相切小面片 | 0.13 各 |

那两张 ~0.13 mm² 的小面片是**近相切并集的必然产物**（直管沿全局轴、管壁沿管轴，
两者在过盈段里有 ~0.025mm 的方向差）。它们不影响几何正确性，但划网格时是坏东西；
要么在 Fluent 里把它们合并，要么让直管精确止于端面、两段之间用 interface 处理。

### 20.4 顺带修掉的一个真 bug：`_created_body` 会改错体名

弯头用例暴露出 `_created_body` 的老兜底逻辑（"取根零件里最后一个体"）是错的：
新圆柱与已有体并集时结果对象里的 `CreatedBodies` 可能是空的，于是回退到"最后一个体"，
把文档里另一个毫不相干的体改了名——实测 `UTurn` 变成了默认名 `"Body"`。
现在改成三层判定：①体集合之差 → ②结果对象成员 → ③快照里唯一指纹变了的体 → ④`None`。
调用方（`box`/`cylinder`/`sphere`/`stepped_cone`）都要在命令前拍 `_snapshot_bodies()`。

## 21. 抽壳（第 17 个回归用例）

### 21.1 签名

```
Shell.ShellBodies(ISelection body, Double offset, ICommandInfo info)     -- 整体掏空
Shell.RemoveFaces(ISelection faces, Double offset, ICommandInfo info)    -- 删掉这些面再掏空
```

`ICommandInfo = None` 安全。`ShellResult` 只有 `CreatedBodies`，而且**实测是 0**——
判定结果只能看面数/总面积，和圆角一样。

### 21.2 方向：命令的原始语义是"往外长"

**offset 为正时，原来的表面变成空腔内壁、新面往外长。** 实测 20mm 立方体 `+2`：

| | 结果 |
|---|---|
| 包围盒 | **24 × 24 × 24**（从 20 长到 24） |
| 12 个面 | 原来 6 张 400 面（法向**翻转**了）成了空腔内壁；外侧新增 6 张 576 = 24×24 |
| 总面积 | 5856 = 2400 + 3456 |

想要 CAD 里常规的"外表面不动、壁往内长"，传**负值**。实测 20mm 立方体 `-2`：
12 个面、总面积 **3936 = 6×400(外) + 6×256(16³ 空腔)**、包围盒仍是 20×20×20。

库里的 `shell(body, thickness, ...)` 默认取负号，`outward=True` 才用原始语义。

### 21.3 实测数值（全部手工核对）

| 情形 | 面数 | 总面积 mm² | 明细 |
|---|---|---|---|
| 20³、t=2、全封闭 | 12 | 3936.00 | 6×400(外 20³) + 6×256(空腔 16³) |
| 20³、t=2、开口=顶面 | 11 | 3552.00 | 5×400 + 4×288(空腔壁 16×18) + 256(空腔底) + 144(顶环 400−256) |
| 20³、t=2、开口=顶+底 | 10 | 3168.00 | 4×400 + 4×320(空腔壁 16×20) + 2×144 |
| r10 h20 圆柱、t=2、全封闭 | 6 | 3091.33 | 1256.64(外柱面) + 804.25(空腔柱面 r8 h16) + 2×314.16(外端面) + 2×201.06(空腔端面) |
| 20³、t=2、`outward=True` | 12 | 5856.00 | 6×400(内) + 6×576(外 24³) |

注意圆柱那行：`ShellBodies` 会把**所有**面一起内缩，所以端面也缩了 2，
空腔是 r8×h16 的封闭腔，而不是"两端开口的管子"（想要通管用 `tube()`）。

### 21.4 失败与陷阱

- **`offset = 0` 会抛错**；**壁厚超过最小尺寸的一半**也抛错（20mm 立方体给 11 就失败），
  且失败时**几何完全不动**（实测仍是 6 个面）。抛的是**中文** StandardError，
  所以库里先 `except` 再抛 ASCII 的 `RuntimeError`。
- **命名选择会跟着几何走，但去向不确定。** 实测：先 `name_boundaries` 再"删顶面 + 抽壳(-2)"，
  `outlet` 组**没有消失**，而是被**重映射到新的顶面环**（144 mm²）；
  换成正偏移（`outward`）时同一组却**整组消失**（第 15 轮 probe9 实测）。
  结论：**先抽壳、后命名**，不要指望抽壳之后的旧命名还有意义。




