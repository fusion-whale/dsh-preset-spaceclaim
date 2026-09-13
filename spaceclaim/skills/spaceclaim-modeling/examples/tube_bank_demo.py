# -*- coding: utf-8 -*-
# 示例：管壳式换热器壳程流域（12 根换热管 + 2 块弓形折流板）
#
# 这是"管束"类 CFD 几何的完整配方：
#   1) 先建壳程流域（一个长方体）
#   2) 用 cylinder(..., cut=True) 把 12 根管子挖掉（管子贯穿，两端出头）
#   3) 用 box(..., cut=True) 挖出两块弓形折流板的位置（下挡 + 上挡，让流体蛇形绕流）
#   4) 按规则按顺序命名边界
#
# 运行：
#   & <skill>\scripts\Invoke-Scdm.ps1 -Script tube_bank_demo.py -Out tube_bank_demo.scdocx -Verify
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "tube_bank_demo.scdocx")
PI = 3.14159265358979

L, H, D = 100.0, 50.0, 40.0     # 壳程流域 长(x) x 高(y) x 深(z)
R_TUBE = 4.0                    # 换热管半径
NTUBE = 12

new_model()

# ---- 1) 壳程流域 -------------------------------------------------------
body = box(L, H, D, origin=(0.0, 0.0, 0.0), name="ShellSide")

# ---- 2) 12 根换热管贯穿（4 排 x 3 层），两端各出头 5mm ------------------
for iz in range(3):
    for iy in range(4):
        cylinder(R_TUBE, L + 10.0,
                 origin=(-5.0, 10.0 + iy * 10.0, 10.0 + iz * 10.0),
                 axis="x", cut=True)

# ---- 3) 两块弓形折流板：各挖掉半高的一块板 -----------------------------
# 下挡板（y 0..30）让流体从上方过；上挡板（y 20..50）让流体从下方过
box(2.0, 30.0, D, origin=(30.0, 0.0, 0.0), cut=True)
box(2.0, 30.0, D, origin=(60.0, 20.0, 0.0), cut=True)

# ---- 4) 命名边界条件（顺序很重要！） -----------------------------------
# 两个坑：
#  a) 挖掉一块板之后，**x 小的一侧那张面的外法向是 +X**、x 大的一侧是 −X
#     （面的朝向背离实体）。sign 写反 → 一张都匹配不到，接着 inlet/outlet
#     会把折流板面整批吃掉（第一版实测 inlet 吃到 3 张面、合计 3042.83 mm²）。
#  b) 规则按顺序处理、先匹配先占，所以折流板规则必须写在 inlet/outlet 前面。
name_faces_by_rules(body, [
    ("baffle_1a", {"kind": "plane", "normal": "x", "sign": +1, "at": ("x", 30.0)}),
    ("baffle_1b", {"kind": "plane", "normal": "x", "sign": -1, "at": ("x", 32.0)}),
    ("baffle_2a", {"kind": "plane", "normal": "x", "sign": +1, "at": ("x", 60.0)}),
    ("baffle_2b", {"kind": "plane", "normal": "x", "sign": -1, "at": ("x", 62.0)}),
    ("tubes",     {"kind": "cylinder"}),
    ("inlet",     {"kind": "plane", "normal": "x", "sign": -1}),
    ("outlet",    {"kind": "plane", "normal": "x", "sign": +1}),
    ("wall",      {"rest": True}),
])

# ---- 5) 打印实测值，和手算对照 -----------------------------------------
print("[tube] domain %.0f x %.0f x %.0f, %d tubes r=%.1f, 2 baffles"
      % (L, H, D, NTUBE, R_TUBE))
print("[tube] faces=%d" % len(list(body.Faces)))
ks = {}
for f in body.Faces:
    k = face_kind(f)
    ks[k] = ks.get(k, 0) + 1
print("[tube] kinds=%s" % str(ks))

tot = 0.0
for g in NamedSelection.GetGroups():
    a = 0.0
    for m in g.Members:
        a += face_area(m)
    tot += a
    print("[tube]   %-10s %2d face(s) %10.2f mm2" % (_ascii(g.Name), g.Members.Count, a))
print("[tube]   named total = %.2f mm2 (应等于整个体的表面积)" % tot)

mm = 0.0
for f in body.Faces:
    mm += face_area(f)
print("[tube]   body surface  = %.2f mm2" % mm)
print("[tube] hand-calc: 管壁 %d x 2*pi*%.1f*100 = %.2f（贯穿长度按 100 算是下界），"
      % (NTUBE, R_TUBE, NTUBE * 2 * PI * R_TUBE * L))
print("[tube]   进出口各应 ~= %.2f（50x40 减去 12 个 r=4 的圆孔 %0.2f）"
      % (H * D - NTUBE * PI * R_TUBE * R_TUBE, NTUBE * PI * R_TUBE * R_TUBE))

finish(OUT, body)
