# -*- coding: utf-8 -*-
# 回归用例 10：任意轮廓截面（折线梯形 + 椭圆）
#
# 期望回读（2 个体，6 个命名选择）：
#   TrapDuct  梯形 (u,v)=(0,0)(20,0)(15,10)(5,10)、长 20、沿 Z
#             bbox 20.000 x 10.000 x 20.000，6 个面
#             端面面积 (20+10)/2*10 = 150.00 mm2
#             侧面：底 20*20=400.00、顶 10*20=200.00、两斜边 sqrt(5^2+10^2)*20=223.61
#   EllipDuct 椭圆半轴 10 与 5、长 15、沿 X、底面中心 (40,0,0)
#             bbox 15.000 x 20.000 x 10.000，3 个面
#             端面面积 pi*10*5 = 157.08 mm2
#             侧面 ≈ 周长 48.44 * 15 = 726.6 mm2
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_profile.scdocx")

ducts = profile_prisms([
    {"kind": "polyline", "points": [(0.0, 0.0), (20.0, 0.0), (15.0, 10.0), (5.0, 10.0)],
     "height": 20.0, "axis": "z", "origin": (0.0, 0.0, 0.0), "name": "TrapDuct"},
    {"kind": "ellipse", "radii": (10.0, 5.0),
     "height": 15.0, "axis": "x", "origin": (40.0, 0.0, 0.0), "name": "EllipDuct"},
])
print("[batch] built %d bodies, document has %d" % (len(ducts), GetRootPart().Bodies.Count))

trap, ell = ducts[0], ducts[1]

dx, dy, dz = body_size(trap)
print("[trap] bbox = %.3f x %.3f x %.3f  faces=%d" % (dx, dy, dz, len(list(trap.Faces))))
cnt = name_faces_by_rules(trap, [
    ("trap_inlet",  {"normal": "z", "sign": -1}),
    ("trap_outlet", {"normal": "z", "sign": +1}),
    ("trap_wall",   {"rest": True}),
])
for k in sorted(cnt):
    print("[trap] %-12s %d face(s)" % (k, cnt[k]))

dx, dy, dz = body_size(ell)
print("[ell]  bbox = %.3f x %.3f x %.3f  faces=%d" % (dx, dy, dz, len(list(ell.Faces))))
cnt = name_faces_by_rules(ell, [
    ("ell_inlet",  {"normal": "x", "sign": -1}),
    ("ell_outlet", {"normal": "x", "sign": +1}),
    ("ell_wall",   {"rest": True}),
])
for k in sorted(cnt):
    print("[ell]  %-12s %d face(s)" % (k, cnt[k]))

finish(SAVE_PATH)
