# -*- coding: utf-8 -*-
# 回归用例 4：布尔减 / 空心管 / 平移 / 强制独立 / 在带孔的体上命名边界
#
# 期望回读（4 个体）：
#   Plate  20.000 x 20.000 x 4.000 mm   7 面（4 侧面 + 上下各带 1 个内环 + 孔壁圆柱面）
#   Pipe   30.000 x 12.000 x 12.000 mm  4 面（两端环面 + 外柱面 + 内柱面）
#          inlet 环面 62.83 mm2 @ x=40，outlet 环面 62.83 mm2 @ x=70
#          wall = 外柱面 1130.97 + 内柱面 753.98 mm2
#   Cube   5.000 x 5.000 x 5.000 mm，x 从 60 到 65（验证 move 生效）
#   Sep    6.000 x 6.000 x 6.000 mm（与 Plate 重叠但 separate=True，验证没被并集吞掉）
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_solids.scdocx")

# 1) 带孔板：20x20x4，中心挖一个 r=2 的通孔（布尔减）
plate = box(20.0, 20.0, 4.0, origin=(0.0, 0.0, 0.0), name="Plate")
cylinder(2.0, 20.0, origin=(10.0, 10.0, -3.0), axis="z", cut=True)

# 2) 空心管：外半径 6、内半径 4、长 30，沿 X 摆放；两端命名 inlet/outlet，其余 wall
pipe = tube(6.0, 4.0, 30.0, origin=(40.0, 0.0, 0.0), axis="x", name="Pipe")
name_boundaries(pipe, bottom="inlet", top="outlet", sides="wall", axis="x")

# 3) 平移：5mm 立方体建在 y=-20 处（避开板和管），再整体平移到 x=60
#    注意：新体若与已有体重叠会被 SpaceClaim 合并，所以测试体要放到不重叠的位置
cube = box(5.0, 5.0, 5.0, origin=(0.0, -20.0, 0.0), name="Cube")
move(cube, 60.0, 0.0, 0.0)

# 4) 与板重叠但强制独立（separate=True），验证不会被并集合掉
sep = box(6.0, 6.0, 6.0, origin=(2.0, 2.0, 0.0), name="Sep", separate=True)

finish(SAVE_PATH)
