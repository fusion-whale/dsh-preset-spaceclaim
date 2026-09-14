# 示例模型

这些都是**真跑过、独立校验过**的配方（用 `-Verify` 另开一个 SpaceClaim 会话从磁盘回读）。
数字都是实测值，可以拿来对照自己建出来的结果。

**一条命令跑完全部 5 个并打印对照表：**

```powershell
& "<skill-dir>\scripts\smoke_examples.ps1"                # 全过才返回 0
& "<skill-dir>\scripts\smoke_examples.ps1" -Only pin_fin_demo
& "<skill-dir>\scripts\smoke_examples.ps1" -Retries 2     # 偶发失败自动重试
```

实测输出（SpaceClaim 2022 R1，本机）：

```
Example              Status Bodies Zones Faces Seconds
tube_bank_demo       ok     1      8     44       41.5
pin_fin_demo         ok     1      7     86       40.7
surface_asm_demo     ok     3      3     6        89.1
bend90_demo          ok     1      4     7        51.4
cht_tube_bundle_demo ok     25     10    18       41.3
total 5, failed 0
```

也可以逐个手动跑：

```powershell
$S = "<skill-dir>"
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\tube_bank_demo.py"    -Out "$S\examples\tube_bank_demo.scdocx"    -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\pin_fin_demo.py"      -Out "$S\examples\pin_fin_demo.scdocx"      -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\surface_asm_demo.py"  -Out "$S\examples\surface_asm_demo.scdocx"  -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\bend90_demo.py"       -Out "$S\examples\bend90_demo.scdocx"       -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\cht_tube_bundle_demo.py" -Out "$S\examples\cht_tube_bundle_demo.scdocx" -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\cht_baffled_demo.py"      -Out "$S\examples\cht_baffled_demo.scdocx"      -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\fuel_assembly_5x5.py"    -Out "$S\examples\fuel_assembly_5x5.scdocx"    -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\pche_demo.py"            -Out "$S\examples\pche_demo.scdocx"            -Verify
```

| 示例 | 是什么 | 用到的能力 | 实测结果 |
|---|---|---|---|
| `pche_demo.py` | **PCHE 一层冷 + 一层热**：D 形（半圆槽）通道，流向沿 x、平边朝上，长 100mm；固体域 = 刻槽板 + 盖板，流体域 = 4 条 D 形通道 | `half_round_channel`（空白处造好再 move）/ 逐层浇注切槽 / `cht_check` | **5 个体**：固体 14 面、4 条流体各 4 面；**Dh = 1.2220 mm**；hot/cold 交界面各 4 对、两侧各 **1028.32 mm²**、balanced=True；冷热薄壁 0.6mm；`cht_check ok=True` |
| `fuel_assembly_5x5.py` | **5×5 核反应堆燃料组件流动通道**：75×75 通道挖 25 根棒（棒径 10 / 栅距 15，P/D=1.5），长 3000mm；边界条件 `wall-heated`（棒表面）/ `sym`（四周）/ `inlet`（底面）/ `outlet`（顶面）。脚本里还留了"棒径=栅距"为什么建不出来的反面教材 | `box(cut=True)` 循环 / 规则命名 | 1 个体 **31 面**（6 平面 + 25 圆柱面）；inlet/outlet 各 **3661.50 mm²**、`wall-heated` **2356194.49 mm² = 2.3562 m²**（25×2π·5×3000）、`sym` **900000 mm² = 0.9 m²**；**流通面积 3661.50 mm²、湿周 1085.40 mm、Dh = 13.4937 mm** |
| `cht_baffled_demo.py` | **带折流板的四层 CHT**：壳程流体 100×50×40 + 2 块折流板固体 + 12 根管壁 + 12 根管程流体；折流板上的管孔是同一轮 `cut` 挖穿的 | `box(cut=True)` 顺序技巧 / `tube(separate=True)` / `cht_check` / `name_interfaces_multi(allow_split=True)` | **27 个体**；`cht_check ok=True`，自动判定 4 组相接（壳程↔折流板 6 / 壳程↔管壁 3整+18分段 / 折流板↔管壁 9分段 / 管壁↔管程 12），并正确判定壳程↔管程不接触 |
| `cht_tube_bundle_demo.py` | **共轭传热三层模型**：壳程流体 100×50×40 + 12 根管壁固体（外 r5/内 r4）+ 管程流体 12 根 r4 | `box` / `cylinder(cut=True)` / `tube(separate=True)` / `name_interfaces_multi` / `interface_report` | **25 个体、10 个 zone**；`shell_tube_a/b` 各 12 面、两侧各 37699.11 mm²；`tube_fluid_a/b` 各 12 面、两侧各 30159.29；两处 `balanced=True` |
| `tube_bank_demo.py` | 管壳式换热器**壳程流域**：100×50×40 的壳 + 12 根贯穿换热管 + 2 块弓形折流板 | `box` / `cylinder(cut=True)` / `box(cut=True)` / 规则命名 | 44 个面（20 平面 + 24 圆柱面）；进口/出口各 1396.81 mm²、折流板 4 面各 823.01、管壁合计 29405.31、壁面 14 面 17664.00 |
| `pin_fin_demo.py` | **针翅散热器流道**：120×40×30 的流道 + 10×4=40 根 r2 高 20 的针翅 | 同上（针翅是从底板立起来的小圆柱，挖掉体积就是流体域） | 86 个面（46 平面 + 40 圆柱面）；进口/出口各 1200.00、顶面 4800.00、底面 4297.35、针翅侧面 10053.10、针翅顶面 502.65 |
| `surface_asm_demo.py` | **曲面加厚 + 装配**：一张 40×30 的零厚度面 → 3mm 导流板；两个体进组件再搬回根零件 | `rect_surface` / `thicken` / `component` / `move_to_component` / `move_to_root` / `drop_empty_components` | 面 1 个面 1200.00 → 加厚后 6 面、40×3×30、2820.00；装配：根零件 3 → 2（1 个进组件）→ 搬回 3 |
| `bend90_demo.py` | **90° 弯管流域**：真圆截面弯头 + 两段直管拼成一个体 | `elbow` / `cylinder` / 规则命名 | 1 个体 7 面；inlet/outlet 各 78.54、bend_wall 1449.95、wall 4 面 |

## CHT 那几个坑（做共轭传热必看）

1. **管壁要 `tube(..., separate=True)`**：管外表面与壳程孔壁尺寸完全相同时，默认并集会把管子吃进孔壁（实测 12 根建完只剩 1 个管状体）。
2. **刀的端面别跟目标体端面共面**：共面时布尔静默失败、还留下一个实体刀具体。
3. **管间距 > 2×管外半径**：R=5 配 10mm 间距 = 相邻管外切，实测 12 次挖孔只成功 1 次。
4. **同名 zone 要合并着建**：逐根 `name_faces_by_rules(t, [("tube_wall_end", …)])` 会建出 12 组同名 zone，随后 `NamedSelection.GetGroups()` 直接崩。
5. **折流板会把壳程的管孔壁切成几段**：整面面积对不上，自动配对会是 0 —— 这时要 `allow_split=True`（分段接触），见 `cht_check`。
6. **`cut=True` 是全局的**：刀会切文档里所有体，所以顺序决定一切。带折流板模型的正确顺序是"建壳 → 挖折流板槽 → 塞折流板 → 这一轮挖管孔同时穿透壳与折流板 → 最后才建管壁和管程流体"。

## 三个反复踩到的坑（示例里都留了注释）
1. **面的朝向要看实体在哪一侧，不是看坐标大小。**
   用 `cut=True` 挖掉一块料之后，x 小的那侧那面墙的外法向是 **+X**（背离实体，指向空腔），
   不是 −X。针翅顶面同理是 **−Z**。sign 写反 → 一张都匹配不到，接着后面的规则会把它们吃掉。
   （实测：`tube_bank_demo` 第一版 `inlet` 吃到了 3 张面、合计 3042.83 mm² =
   1396.81 + 823.01 + 823.01，正好是"进出口 + 两块折流板"。）
2. **规则按顺序处理、先匹配先占。** 折流板那类"位置 + 朝向"要卡死的规则必须写在
   `inlet` / `outlet` 前面。
3. **给某个名字卡得太松就会多吃面。** 判断是否吃错了最快的办法是把每个命名选择的
   **面数 + 面积合计**打出来，和手算对照 —— 上面的表格就是这么来的。
