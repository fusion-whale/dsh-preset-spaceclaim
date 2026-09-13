# -*- coding: utf-8 -*-
# 回归用例 8：成对边界条件（交界面 / 内部挡板 / 周期面对应性）
#
# 期望回读（4 个体，4 个命名选择）：
#   Solid 50x40x40 (x 0~50)   · Fluid 50x40x40 (x 50~100，separate=True 保持独立)
#   Bar 被 x=50 切开 → 2 个 50x40x40 的体
#   interface_a 1 面 1600.00 @ (50,20,20)     ← 固体侧的耦合面
#   interface_b 1 面 1600.00 @ (50,20,20)     ← 流体侧的耦合面
#   baffle_a    1 面 1600.00 @ (50,120,20)    ← 切开后的内部面（挡板/多孔跳变/风扇面）
#   baffle_b    1 面 1600.00 @ (50,120,20)
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_pairs.scdocx")

# ---- A) 共轭传热交界面：流体域与固体域相邻，共享 x=50 那张面 ----
solid = box(50.0, 40.0, 40.0, origin=(0.0, 0.0, 0.0), name="Solid")
fluid = box(50.0, 40.0, 40.0, origin=(50.0, 0.0, 0.0), name="Fluid", separate=True)
print("[iface] bodies = %d" % GetRootPart().Bodies.Count)

pairs = find_coincident_pairs(solid, fluid)
print("[iface] coincident pairs = %d" % len(pairs))
n = name_interfaces(solid, fluid, "interface")
print("[iface] named pairs = %d" % n)

# ---- B) 内部挡板：长条切开后把两张内表面成对命名 ----
bar = box(100.0, 40.0, 40.0, origin=(0.0, 100.0, 0.0), name="Bar")
print("[baffle] bodies before = %d" % GetRootPart().Bodies.Count)
name_internal_baffle(bar, axis="x", value=50.0, name="baffle")
print("[baffle] bodies after  = %d" % GetRootPart().Bodies.Count)

# ---- C) 周期面对应性检查：形状面积一致、位置不同 ----
c1 = faces_at(solid, axis="x", value=0.0)[0]
c2 = faces_at(fluid, axis="x", value=100.0)[0]
cc = face_center(c1)
cd = face_center(c2)
print("[periodic] face_a center=(%.2f,%.2f,%.2f) area=%.2f" % (cc[0], cc[1], cc[2], face_area(c1)))
print("[periodic] face_b center=(%.2f,%.2f,%.2f) area=%.2f" % (cd[0], cd[1], cd[2], face_area(c2)))
print("[periodic] faces_match = %s" % str(faces_match(c1, c2)))

finish(SAVE_PATH)
