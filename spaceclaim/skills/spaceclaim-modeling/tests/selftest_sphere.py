# -*- coding: utf-8 -*-
# 回归用例 12：球体 + 用球挖球腔
#
# 期望回读（2 个体，3 个命名选择）：
#   Ball   球 r=5，球心 (0,0,0) → bbox 10.000 x 10.000 x 10.000，1 个面
#          ball_surface 1 面 314.16 mm2 = 4*pi*5^2 @ (0,0,0)
#   Cavity 方块 20x20x20（中心在 (60,0,0)）挖掉 r=6 的球 → 7 个面
#          （6 个平面 + 1 个球面 452.39 mm2 = 4*pi*6^2）
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_sphere.scdocx")

# ---- 1) 球体本身 ----
ball = sphere(5.0, center=(0.0, 0.0, 0.0), name="Ball")
dx, dy, dz = body_size(ball)
print("[ball] bbox = %.3f x %.3f x %.3f  faces=%d" % (dx, dy, dz, len(list(ball.Faces))))
name_faces("ball_surface", list(ball.Faces))
for f in list(ball.Faces):
    c = face_center(f)
    print("[ball] %s area=%.2f center=(%.2f,%.2f,%.2f)" % (face_kind(f), face_area(f), c[0], c[1], c[2]))

# ---- 2) 用球挖球腔 ----
blk = box(20.0, 20.0, 20.0, origin=(50.0, -10.0, -10.0), name="Cavity")
sphere(6.0, center=(60.0, 0.0, 0.0), cut=True)
print("[cavity] bodies=%d" % GetRootPart().Bodies.Count)
for b in list(GetRootPart().Bodies):
    if b.Name == "Cavity" or len(list(b.Faces)) > 1:
        dx, dy, dz = body_size(b)
        print("[cavity] bbox = %.3f x %.3f x %.3f  faces=%d" % (dx, dy, dz, len(list(b.Faces))))
        cnt = name_faces_by_rules(b, [("cavity_wall", {"kind": "sphere"})])
        for k in sorted(cnt):
            print("[cavity] %s -> %d face(s)" % (k, cnt[k]))

finish(SAVE_PATH)
