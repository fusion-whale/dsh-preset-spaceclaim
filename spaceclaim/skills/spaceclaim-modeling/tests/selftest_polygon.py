# -*- coding: utf-8 -*-
# 回归用例 9：非圆形截面（正多边形棱柱，批量接口）
#
# 关键背景：SpaceClaim 2022 R1 里**文档中一旦有实体，再新建草图就会崩**，
# 所以所有草图必须在任何实体存在之前一次画完 —— 这就是 polygon_prisms 存在的理由。
#
# 期望回读（2 个体，6 个命名选择）：
#   HexDuct  六边形外接圆 r=5、长 20、沿 Z
#            bbox 10.000 x 8.660 x 20.000，8 个面
#            hex_inlet / hex_outlet  各 1 面 64.95 mm2 @ (0,0,0) / (0,0,20)
#            hex_wall                6 面        （端面面积 (3*sqrt(3)/2)*R^2）
#   OctDuct  八边形外接圆 r=6、长 15、沿 X、底面中心 (40,0,0)
#            bbox 15.000 x 12.000 x 12.000，10 个面
#            （顶点在 0°,45°,… → 两个方向的包围盒都是 2R=12）
#            oct_inlet / oct_outlet  各 1 面 101.82 mm2 @ (40,0,0) / (55,0,0)
#            oct_wall                8 面 各 68.88 mm2（边长 2R*sin(22.5°)=4.592 × 15）
#                                    端面面积 2*sqrt(2)*R^2 = 101.82
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_polygon.scdocx")

ducts = polygon_prisms([
    {"sides": 6, "radius": 5.0, "height": 20.0, "axis": "z",
     "origin": (0.0, 0.0, 0.0), "name": "HexDuct"},
    {"sides": 8, "radius": 6.0, "height": 15.0, "axis": "x",
     "origin": (40.0, 0.0, 0.0), "name": "OctDuct"},
])
print("[batch] built %d bodies, document has %d" % (len(ducts), GetRootPart().Bodies.Count))

hexd, octd = ducts[0], ducts[1]
dx, dy, dz = body_size(hexd)
print("[hex] bbox = %.3f x %.3f x %.3f  faces=%d" % (dx, dy, dz, len(list(hexd.Faces))))
cnt = name_faces_by_rules(hexd, [
    ("hex_inlet",  {"normal": "z", "sign": -1}),
    ("hex_outlet", {"normal": "z", "sign": +1}),
    ("hex_wall",   {"rest": True}),
])
for k in sorted(cnt):
    print("[hex] %-11s %d face(s)" % (k, cnt[k]))

dx, dy, dz = body_size(octd)
print("[oct] bbox = %.3f x %.3f x %.3f  faces=%d" % (dx, dy, dz, len(list(octd.Faces))))
cnt = name_faces_by_rules(octd, [
    ("oct_inlet",  {"normal": "x", "sign": -1}),
    ("oct_outlet", {"normal": "x", "sign": +1}),
    ("oct_wall",   {"rest": True}),
])
for k in sorted(cnt):
    print("[oct] %-11s %d face(s)" % (k, cnt[k]))

# 非草图类的体可以放心加在多边形管道之后
extra = box(10.0, 10.0, 10.0, origin=(0.0, 60.0, 0.0), name="Extra")
print("[mix] total bodies = %d" % GetRootPart().Bodies.Count)

finish(SAVE_PATH)
