# -*- coding: utf-8 -*-
# 回归用例 11：真锥台与圆锥（回转体，取代早先的阶梯近似）
#
# 期望回读（2 个体，4 个命名选择）：
#   Frustum  r1=8, r2=4, h=20, 沿 Z → bbox 16.000 x 16.000 x 20.000，3 个面
#            底 201.06 mm2 = pi*8^2
#            顶  50.27 mm2 = pi*4^2
#            侧面 768.94 mm2 = pi*(8+4)*sqrt(4^2+20^2)
#   Cone     r1=8, r2=0, h=20, 沿 X → bbox 20.000 x 16.000 x 16.000，2 个面
#            底 201.06 mm2
#            侧面 541.39 mm2 = pi*8*sqrt(8^2+20^2)
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_revolve.scdocx")

bodies = cone_frustums([
    {"radius1": 8.0, "radius2": 4.0, "height": 20.0,
     "origin": (0.0, 0.0, 0.0), "axis": "z", "name": "Frustum"},
    {"radius1": 8.0, "radius2": 0.0, "height": 20.0,
     "origin": (40.0, 0.0, 0.0), "axis": "x", "name": "Cone"},
])
print("[batch] built %d bodies, document has %d" % (len(bodies), GetRootPart().Bodies.Count))

fru, cone = bodies[0], bodies[1]

dx, dy, dz = body_size(fru)
print("[frustum] bbox = %.3f x %.3f x %.3f  faces=%d" % (dx, dy, dz, len(list(fru.Faces))))
cnt = name_faces_by_rules(fru, [
    ("fru_inlet",  {"normal": "z", "sign": -1}),
    ("fru_outlet", {"normal": "z", "sign": +1}),
    ("fru_wall",   {"rest": True}),
])
for k in sorted(cnt):
    print("[frustum] %-11s %d face(s)" % (k, cnt[k]))

dx, dy, dz = body_size(cone)
print("[cone] bbox = %.3f x %.3f x %.3f  faces=%d" % (dx, dy, dz, len(list(cone.Faces))))
cnt = name_faces_by_rules(cone, [
    ("cone_inlet",  {"normal": "x", "sign": -1}),
    ("cone_wall",   {"rest": True}),
])
for k in sorted(cnt):
    print("[cone] %-11s %d face(s)" % (k, cnt[k]))

finish(SAVE_PATH)
