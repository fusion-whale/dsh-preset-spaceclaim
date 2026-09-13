# 示例模型

这些都是**真跑过、独立校验过**的配方（用 `-Verify` 另开一个 SpaceClaim 会话从磁盘回读）。
数字都是实测值，可以拿来对照自己建出来的结果。

```powershell
$S = "<skill-dir>"
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\tube_bank_demo.py"    -Out "$S\examples\tube_bank_demo.scdocx"    -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\pin_fin_demo.py"      -Out "$S\examples\pin_fin_demo.scdocx"      -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\surface_asm_demo.py"  -Out "$S\examples\surface_asm_demo.scdocx"  -Verify
& "$S\scripts\Invoke-Scdm.ps1" -Script "$S\examples\bend90_demo.py"       -Out "$S\examples\bend90_demo.scdocx"       -Verify
```

| 示例 | 是什么 | 用到的能力 | 实测结果 |
|---|---|---|---|
| `tube_bank_demo.py` | 管壳式换热器**壳程流域**：100×50×40 的壳 + 12 根贯穿换热管 + 2 块弓形折流板 | `box` / `cylinder(cut=True)` / `box(cut=True)` / 规则命名 | 44 个面（20 平面 + 24 圆柱面）；进口/出口各 1396.81 mm²、折流板 4 面各 823.01、管壁合计 29405.31、壁面 14 面 17664.00 |
| `pin_fin_demo.py` | **针翅散热器流道**：120×40×30 的流道 + 10×4=40 根 r2 高 20 的针翅 | 同上（针翅是从底板立起来的小圆柱，挖掉体积就是流体域） | 86 个面（46 平面 + 40 圆柱面）；进口/出口各 1200.00、顶面 4800.00、底面 4297.35、针翅侧面 10053.10、针翅顶面 502.65 |
| `surface_asm_demo.py` | **曲面加厚 + 装配**：一张 40×30 的零厚度面 → 3mm 导流板；两个体进组件再搬回根零件 | `rect_surface` / `thicken` / `component` / `move_to_component` / `move_to_root` / `drop_empty_components` | 面 1 个面 1200.00 → 加厚后 6 面、40×3×30、2820.00；装配：根零件 3 → 2（1 个进组件）→ 搬回 3 |
| `bend90_demo.py` | **90° 弯管流域**：真圆截面弯头 + 两段直管拼成一个体 | `elbow` / `cylinder` / 规则命名 | 1 个体 7 面；inlet/outlet 各 78.54、bend_wall 1449.95、wall 4 面 |

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
