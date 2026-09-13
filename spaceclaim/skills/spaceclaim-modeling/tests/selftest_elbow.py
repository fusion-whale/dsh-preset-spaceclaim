# -*- coding: utf-8 -*-
# 第 16 个回归用例：真圆截面弯头 / 圆环（圆轮廓 + 回转）
#
# 手算基线（和打印值对照）：
#   圆环  r=3 R=20 360°  -> 1 个 torus 面  面积 4*pi^2*R*r = 2368.705，包围盒 46x46x6
#   弯头  r=3 R=20  90°  -> 3 个面：torus 592.176 = 4*pi^2*R*r/4，两个整圆端面 28.274 = pi*r^2
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "selftest_elbow.scdocx")
PI = 3.14159265358979


def show(body, tag):
    ks = {}
    for f in body.Faces:
        k = face_kind(f)
        ks[k] = ks.get(k, 0) + 1
    print("[b] %-10s faces=%d kinds=%s size=%s"
          % (tag, len(list(body.Faces)), str(ks),
             str(tuple(round(x, 4) for x in body_size(body)))))
    for f in body.Faces:
        c = face_center(f)
        print("[b]    %-9s area=%10.3f center=(%.3f, %.3f, %.3f)"
              % (face_kind(f), face_area(f), c[0], c[1], c[2]))


# --- 0) torus() 单独立一个文档：整圈圆环 ---------------------------------
new_model()
ring = torus(3.0, 20.0, origin=(0.0, 0.0, 0.0), axis="z", name="Ring")
print("[b] torus() hand-calc area = %.3f, bbox = 46 x 46 x 6" % (4.0 * PI * PI * 20.0 * 3.0))
show(ring, "torus()")

# --- 1) 一批三个弯头：90°(绕Z)、45°(绕X)、180° 回转弯 --------------------
new_model()
bends = elbows([
    {"pipe_radius": 3.0, "bend_radius": 20.0, "angle_deg": 90.0,
     "origin": (0.0, 0.0, 0.0), "axis": "z", "name": "Elbow90"},
    {"pipe_radius": 2.0, "bend_radius": 15.0, "angle_deg": 45.0,
     "origin": (0.0, 60.0, 0.0), "axis": "x", "name": "Elbow45"},
    {"pipe_radius": 2.0, "bend_radius": 12.0, "angle_deg": 180.0,
     "origin": (0.0, 120.0, 0.0), "axis": "z", "name": "UTurn"},
])
print("[b] elbows() -> %d bodies" % len(bends))
for b in bends:
    show(b, _ascii(b.Name))
print("[b] elbow90 hand-calc: torus %.3f + 2 x %.3f = %.3f"
      % (4.0 * PI * PI * 20.0 * 3.0 / 4.0, PI * 9.0,
         4.0 * PI * PI * 20.0 * 3.0 / 4.0 + 2.0 * PI * 9.0))

# --- 2) 弯头 + 两段直管 -> 一个完整的 90° 弯管体 --------------------------
bend = bends[0]
cylinder(3.0, 22.0, origin=(0.0, -21.0, 0.0), axis="y", name="Bend")
cylinder(3.0, 22.0, origin=(-41.0, 20.0, 0.0), axis="x", name="Bend")
show(bend, "bend+pipe")
print("[b] hand-calc: 端面 2 x pi*r^2 = %.3f；两段直管壁各 2*pi*3*21.5 ~= 405.27；"
      "圆环面因为被直管\"过盈\"吃掉一小段，从 592.176 降到 573.889；"
      "另有 2 张 ~0.13 mm^2 的近相切小面片（并集必然产物，已归入 wall）" % (2.0 * PI * 9.0))

name_faces_by_rules(bend, [
    ("inlet",     {"kind": "plane", "normal": "y", "sign": -1}),
    ("outlet",    {"kind": "plane", "normal": "x", "sign": -1}),
    ("bend_wall", {"kind": "torus"}),
    ("wall",      {"rest": True}),
])

# --- 3) 命名边界（弯头单体的两个端口 + 圆环面） --------------------------
name_faces_by_rules(bends[1], [
    ("e45_inlet",  {"kind": "plane", "nearest": (0.0, 60.0, 0.0)}),
    ("e45_wall",   {"kind": "torus"}),
    ("e45_outlet", {"rest": True}),
])
name_faces_by_rules(bends[2], [
    ("uturn_inlet",  {"kind": "plane", "in_box": (-1.0, None, None, None, None, None)}),
    ("uturn_wall",   {"kind": "torus"}),
    ("uturn_outlet", {"rest": True}),
])

# --- 4) 失败路径：弯曲半径小于管半径必须抛 ASCII 异常 ---------------------
msg = "none"
try:
    elbows([{"pipe_radius": 5.0, "bend_radius": 3.0, "angle_deg": 90.0}])
except Exception, e:
    msg = "%s | %s" % (type(e).__name__, str(e)[:70])
print("[b] bend_radius < pipe_radius -> %s" % msg)

print("[b] body names just before save: %s"
      % str([_ascii(b.Name) for b in GetRootPart().Bodies]))

finish(OUT, bend)
