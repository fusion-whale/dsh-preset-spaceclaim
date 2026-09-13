# -*- coding: utf-8 -*-
# 回归用例 14（也是外流场示例）：绕圆柱的外流场流体域 + 全部边界命名
#
# 做法：先建外框（流体域），再用 cut=True 建圆柱把它挖掉 —— 圆柱被吸收成空腔，
#       流体域成为唯一实体，障碍物壁面就是那个圆柱面。
#
# 期望回读（1 个体，7 个面，6 个命名选择）：
#   Domain 60(x) x 40(y) x 40(z)
#     inlet       1 面 1600.00 mm2 @ (0,20,20)     x 负向
#     outlet      1 面 1600.00 mm2 @ (60,20,20)    x 正向
#     obstacle    1 面 1256.64 mm2 @ (30,20,20)    圆柱面（2*pi*5*40）
#     top_wall    1 面 2321.46 mm2 @ (30,20,40)    带圆孔（2400 - 78.54）
#     bottom_wall 1 面 2321.46 mm2 @ (30,20,0)     带圆孔
#     side_wall   2 面 2400.00 mm2 @ (30,0,20) / (30,40,20)
#   面积总和校验：2*1600 + 2*2400 + 2*2321.46 + 1256.64 = 13899.56
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_external_flow.scdocx")

# 1) 流体域外框
domain = box(60.0, 40.0, 40.0, origin=(0.0, 0.0, 0.0), name="Domain")

# 2) 圆柱障碍物：布尔减（圆柱被吸收成贯穿的空腔）
cylinder(5.0, 60.0, origin=(30.0, 20.0, -10.0), axis="z", cut=True)

print("[geom] bodies=%d  faces=%d" % (GetRootPart().Bodies.Count, len(list(domain.Faces))))
dx, dy, dz = body_size(domain)
print("[geom] bbox = %.3f x %.3f x %.3f" % (dx, dy, dz))

# 3) 一次命名全部边界（rest 兜底收剩下的两张侧面）
cnt = name_faces_by_rules(domain, [
    ("inlet",       {"normal": "x", "sign": -1}),
    ("outlet",      {"normal": "x", "sign": +1}),
    ("obstacle",    {"kind": "cylinder"}),
    ("top_wall",    {"normal": "z", "sign": +1}),
    ("bottom_wall", {"normal": "z", "sign": -1}),
    ("side_wall",   {"rest": True}),
])
total = 0.0
for k in sorted(cnt):
    print("[rule] %-12s %d face(s)" % (k, cnt[k]))

for f in list(domain.Faces):
    c = face_center(f)
    total += face_area(f)
    print("[face] kind=%-9s area=%9.2f center=(%.2f,%.2f,%.2f) loops=%d"
          % (face_kind(f), face_area(f), c[0], c[1], c[2], len(list(f.Shape.Loops))))
print("[check] 总面积 = %.2f (期望 13899.56)" % total)

finish(SAVE_PATH)
