# -*- coding: utf-8 -*-
# 示例：针翅散热器流道（40 根针翅，矩形流道内绕流）
#
# CFD 域的做法：流道 = 长方体，针翅 = 从底板立起来的小圆柱，
# 把针翅的**体积**从流道里挖掉，剩下的就是流体域；针翅的侧面和顶面自然成为壁面。
#
# 运行：
#   & <skill>\scripts\Invoke-Scdm.ps1 -Script pin_fin_demo.py -Out pin_fin_demo.scdocx -Verify
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "pin_fin_demo.scdocx")
PI = 3.14159265358979

L, W, H = 120.0, 40.0, 30.0     # 流道 长(x) x 宽(y) x 高(z)
NX, NY = 10, 4                  # 针翅排布 10 x 4 = 40 根
R_PIN = 2.0                     # 针翅半径
PIN_H = 20.0                    # 针翅高度（从 z=0 立到 z=20）

new_model()

# ---- 1) 流道 -----------------------------------------------------------
body = box(L, W, H, origin=(0.0, 0.0, 0.0), name="PinFinChannel")

# ---- 2) 40 根针翅：挖掉它们的体积（从底板下方 1mm 起，保证切透底板面） --
for ix in range(NX):
    for iy in range(NY):
        cylinder(R_PIN, PIN_H + 1.0,
                 origin=(10.0 + ix * 10.0, 5.0 + iy * 10.0, -1.0),
                 axis="z", cut=True)

# ---- 3) 命名边界条件 ---------------------------------------------------
# 注意针翅顶面（z=20 那个腔顶）的**外法向是 −Z**：实体在上方、空腔在下方，
# 面的朝向是背离实体的。用 +Z 会一张都匹配不到（第一版就是这么错的，
# 结果 floor 把 40 张针翅顶面全吃了：41 个面、4800.00 = 4297.35 + 502.65）。
name_faces_by_rules(body, [
    ("fin_tips", {"kind": "plane", "normal": "z", "sign": -1, "at": ("z", PIN_H)}),
    ("floor",    {"kind": "plane", "normal": "z", "sign": -1, "at": ("z", 0.0)}),
    ("fins",     {"kind": "cylinder"}),
    ("inlet",    {"kind": "plane", "normal": "x", "sign": -1}),
    ("outlet",   {"kind": "plane", "normal": "x", "sign": +1}),
    ("top_wall", {"kind": "plane", "normal": "z", "sign": +1}),
    ("side_wall", {"rest": True}),
])

# ---- 4) 实测值 + 手算 --------------------------------------------------
nf = NX * NY
print("[pin] channel %.0f x %.0f x %.0f, %d pins r=%.1f h=%.1f"
      % (L, W, H, nf, R_PIN, PIN_H))
print("[pin] faces=%d (手算 6 + %d 侧面 + %d 顶面 = %d)"
      % (len(list(body.Faces)), nf, nf, 6 + 2 * nf))
ks = {}
for f in body.Faces:
    k = face_kind(f)
    ks[k] = ks.get(k, 0) + 1
print("[pin] kinds=%s" % str(ks))

for g in NamedSelection.GetGroups():
    a = 0.0
    for m in g.Members:
        a += face_area(m)
    print("[pin]   %-10s %2d face(s) %10.2f mm2" % (_ascii(g.Name), g.Members.Count, a))

print("[pin] hand-calc:")
print("[pin]   inlet/outlet  各 %10.2f = %.0f x %.0f" % (W * H, W, H))
print("[pin]   top_wall      %10.2f = %.0f x %.0f" % (L * W, L, W))
print("[pin]   floor         %10.2f = %.0f - %d*pi*%.1f^2" % (L * W - nf * PI * R_PIN * R_PIN, L * W, nf, R_PIN))
print("[pin]   fins          %10.2f = %d * 2*pi*%.1f*%.1f" % (nf * 2 * PI * R_PIN * PIN_H, nf, R_PIN, PIN_H))
print("[pin]   fin_tips      %10.2f = %d * pi*%.1f^2" % (nf * PI * R_PIN * R_PIN, nf, R_PIN))

finish(OUT, body)
