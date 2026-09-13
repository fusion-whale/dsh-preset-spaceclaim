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

