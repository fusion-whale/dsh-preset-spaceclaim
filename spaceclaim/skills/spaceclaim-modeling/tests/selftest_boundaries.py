# -*- coding: utf-8 -*-
# 回归用例 5：多种边界条件 + 选面原语自检
#
# 期望回读（7 个命名选择，2 个体）：
#   Channel 100x40x40:
#     inlet     1 面 1600.00 mm2 @ (0,20,20)     法向 -X
#     outlet    1 面 1600.00 mm2 @ (100,20,20)   法向 +X
#     symmetry  1 面 4000.00 mm2 @ (50,0,20)     y=0 那个面
#     wall      3 面 4000.00 mm2 各 @ (50,40,20)/(50,20,0)/(50,20,40)   剩下的
#   Pipe 30x12x12（沿 X，外 r6 内 r4）:
#     pipe_inlet  1 面  62.83 mm2 @ (0,100,0)
#     pipe_outlet 1 面  62.83 mm2 @ (30,100,0)
#     pipe_wall   2 面 1130.97（外柱面）+ 753.98（内柱面）
#
# 注意（重要的语义限制）：match_faces 是"整面判定、按面心定位"，
# 所以不能把一个大面切成几段分别命名。要"半段加热"必须先做面分割。
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_boundaries.scdocx")

channel = box(100.0, 40.0, 40.0, origin=(0.0, 0.0, 0.0), name="Channel")

counts = name_faces_by_rules(channel, [
    ("inlet",    {"normal": "x", "sign": -1}),
    ("outlet",   {"normal": "x", "sign": +1}),
    ("symmetry", {"at": ("y", 0.0)}),
    ("wall",     {"rest": True}),
])
for k in sorted(counts):
    print("[rule] %-12s %d face(s)" % (k, counts[k]))

# ---- 选面原语自检 ----
print("[prim] faces_by_normal(z,-1)   = %d" % len(faces_by_normal(channel, "z", -1)))
print("[prim] faces_by_kind(plane)    = %d" % len(faces_by_kind(channel, "plane")))
print("[prim] face_at_point(50,20,0)  = %d" % len(face_at_point(channel, 50.0, 20.0, 0.0)))
print("[prim] faces_by_area(>=3000)   = %d" % len(faces_by_area(channel, min_area=3000.0)))
nf = nearest_face(channel, 0.0, 20.0, 20.0)
print("[prim] nearest_face(0,20,20)   = %s" % ("found" if nf is not None else "none"))
print("[prim] faces_in_box(x<50)      = %d" % len(faces_in_box(channel, xmax=50.0)))

# ---- 曲面识别：管子 ----
pipe = tube(6.0, 4.0, 30.0, origin=(0.0, 100.0, 0.0), axis="x", name="Pipe")
print("[pipe] cylinder faces = %d, plane faces = %d"
      % (len(faces_by_kind(pipe, "cylinder")), len(faces_by_kind(pipe, "plane"))))

name_faces_by_rules(pipe, [
    ("pipe_inlet",  {"normal": "x", "sign": -1}),
    ("pipe_outlet", {"normal": "x", "sign": +1}),
    ("pipe_wall",   {"rest": True}),
])

finish(SAVE_PATH)
