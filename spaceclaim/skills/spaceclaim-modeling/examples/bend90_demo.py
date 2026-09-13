# -*- coding: utf-8 -*-
# 演示：90 度弯管流体域（真圆截面弯头 + 两段直管），命名好边界条件
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "bend90_demo.scdocx")

R_PIPE = 5.0        # 管半径
R_BEND = 30.0       # 弯曲半径
LEG = 40.0          # 直管段长度

new_model()

# 1) 弯头（草图类必须最先建）
bend = elbow(R_PIPE, R_BEND, angle_deg=90.0, origin=(0.0, 0.0, 0.0), axis="z",
             name="BendFlow")

# 2) 两段直管：起始端面在原点、管朝 +Y；末端面在 (-R_BEND, R_BEND, 0)、管朝 -X
cylinder(R_PIPE, LEG + 1.0, origin=(0.0, -LEG, 0.0), axis="y", name="BendFlow")
cylinder(R_PIPE, LEG + 1.0, origin=(-(R_BEND + LEG), R_BEND, 0.0), axis="x", name="BendFlow")

# 3) 命名边界条件
name_faces_by_rules(bend, [
    ("inlet",     {"kind": "plane", "normal": "y", "sign": -1}),
    ("outlet",    {"kind": "plane", "normal": "x", "sign": -1}),
    ("bend_wall", {"kind": "torus"}),
    ("wall",      {"rest": True}),
])

print("[demo] faces=%d" % len(list(bend.Faces)))
for f in bend.Faces:
    c = face_center(f)
    print("[demo]   %-9s area=%9.2f center=(%.2f, %.2f, %.2f)"
          % (face_kind(f), face_area(f), c[0], c[1], c[2]))
print("[demo] expect: 端面 pi*5^2 = %.2f each; 直管壁 2*pi*5*40 = %.2f each; "
      "环面 4*pi^2*R*r/4 = %.2f"
      % (3.14159265358979 * 25.0, 2.0 * 3.14159265358979 * 5.0 * 40.0,
         3.14159265358979 ** 2 * 30.0 * 5.0))

finish(OUT, bend)
