# -*- coding: utf-8 -*-
# 回归用例 7：旋转（斜几何）+ 用任意向量法向命名斜面
#
# 期望回读（2 个体）：
#   Bar 40x10x10 绕 Z 轴转 45 度 → bbox 35.355 x 35.355 x 10.000
#     inlet  1 面 100.00 mm2 @ (24.749, 31.820, 5.000)   法向 ( 0.7071, 0.7071, 0)
#     outlet 1 面 100.00 mm2 @ (-3.536,  3.536, 5.000)   法向 (-0.7071,-0.7071, 0)
#     wall   4 面（两张 400.00 的侧面 + 上下两张 400.00 的 z 面）
#   Tilted 20x20x20 绕 X 轴转 30 度 → bbox 20.000 x 27.320 x 27.320
#     top_tilted 1 面 400.00 mm2，法向 (0, -0.5, 0.8660)
#     rest_wall  5 面
import os
import math

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_rotate.scdocx")

# ---- 1) 绕 Z 轴 45 度，长条变成斜的 ----
bar = box(40.0, 10.0, 10.0, origin=(0.0, 0.0, 0.0), name="Bar")
rotate(bar, 45.0, axis="z", center=(0.0, 0.0, 0.0))
dx, dy, dz = body_size(bar)
print("[rot] bar bbox = %.3f x %.3f x %.3f mm" % (dx, dy, dz))

c = math.sqrt(0.5)
counts = name_faces_by_rules(bar, [
    ("inlet",  {"normal": (c, c, 0.0)}),
    ("outlet", {"normal": (-c, -c, 0.0)}),
    ("wall",   {"rest": True}),
])
for k in sorted(counts):
    print("[rule] %-10s %d face(s)" % (k, counts[k]))

# ---- 2) 换一个旋转轴：绕 X 轴 30 度 ----
blk = box(20.0, 20.0, 20.0, origin=(0.0, 100.0, 0.0), name="Tilted")
rotate(blk, 30.0, axis="x", center=(0.0, 110.0, 10.0))
dx, dy, dz = body_size(blk)
print("[rot] tilted bbox = %.3f x %.3f x %.3f mm" % (dx, dy, dz))

counts = name_faces_by_rules(blk, [
    ("top_tilted", {"normal": (0.0, -0.5, 0.8660254)}),
    ("rest_wall",  {"rest": True}),
])
for k in sorted(counts):
    print("[rule] %-10s %d face(s)" % (k, counts[k]))

finish(SAVE_PATH)
