# -*- coding: utf-8 -*-
# 第 17 个回归用例：抽壳（Shell / RemoveFaces）
#
# 手算基线（和打印值对照）：
#   20mm 立方体 t=2 全封闭：外 6x400 = 2400，空腔 16^3 -> 6x256 = 1536，合计 3936.00，12 面
#   20mm 立方体 t=2 开口=顶面：外 5x400 = 2000，空腔壁 4x(16x18) = 1152，空腔底 256，
#                              顶部环形口 400-256 = 144，合计 3552.00，11 面
#   20mm 立方体 t=2 开口=顶面+底面：外 4x400 = 1600，空腔壁 4x(16x20) = 1280，
#                              上下环形口 2x144 = 288，合计 3168.00，10 面
#   r10 h20 圆柱 t=2 全封闭：外柱面 1256.64 + 空腔柱面(2*pi*8*16) 804.25 + 外端面 2x314.16
#                              + 空腔端面 2x201.06 = 3091.33，6 面
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "selftest_shell.scdocx")
PI = 3.14159265358979


def show(body, tag):
    ks = {}
    tot = 0.0
    for f in body.Faces:
        k = face_kind(f)
        ks[k] = ks.get(k, 0) + 1
        tot += face_area(f)
    print("[h] %-12s faces=%d total=%.3f kinds=%s size=%s name=%s"
          % (tag, len(list(body.Faces)), tot, str(ks),
             str(tuple(round(x, 3) for x in body_size(body))), _ascii(body.Name)))
    return tot


new_model()

# --- 1) 全封闭的空腔（默认：外表面不动、壁往内长） ----------------------
cube = box(20.0, 20.0, 20.0, origin=(0, 0, 0), name="HollowCube")
shell(cube, 2.0)
show(cube, "hollow cube")
print("[h] hand-calc closed: 2400 + 1536 = %.2f" % (6 * 400.0 + 6 * 256.0))
name_faces_by_rules(cube, [
    ("hollow_outer",  {"area_min": 300.0}),
    ("hollow_cavity", {"rest": True}),
])

# --- 2) 开口壳：去掉顶面再抽壳（像个杯子） ------------------------------
cup = box(20.0, 20.0, 20.0, origin=(40, 0, 0), name="OpenCup")
shell(cup, 2.0, open_faces=faces_by_normal(cup, "z", 1))
show(cup, "open cup")
print("[h] hand-calc open top: 2000 + 1152 + 256 + 144 = %.2f" % (2000.0 + 1152.0 + 256.0 + 144.0))
name_faces_by_rules(cup, [
    ("cup_rim",   {"kind": "plane", "normal": "z", "sign": +1, "area_max": 200.0}),
    ("cup_outer", {"area_min": 350.0}),
    ("cup_inner", {"rest": True}),
])

# --- 3) 两端都开口（像一段方形风管） ------------------------------------
duct = box(20.0, 20.0, 20.0, origin=(80, 0, 0), name="OpenDuct")
open_faces = faces_by_normal(duct, "z", 1) + faces_by_normal(duct, "z", -1)
shell(duct, 2.0, open_faces=open_faces)
show(duct, "open duct")
print("[h] hand-calc two open: 1600 + 1280 + 288 = %.2f" % (1600.0 + 1280.0 + 288.0))
name_faces_by_rules(duct, [
    ("duct_rim",   {"kind": "plane", "normal": "z", "sign": +1}),
    ("duct_rim2",  {"kind": "plane", "normal": "z", "sign": -1}),
    ("duct_outer", {"area_min": 350.0}),
    ("duct_inner", {"rest": True}),
])

# --- 4) 圆柱抽壳（薄壁筒） ----------------------------------------------
cyl = cylinder(10.0, 20.0, origin=(0, 60, 0), axis="z", name="HollowCyl")
shell(cyl, 2.0)
show(cyl, "hollow cyl")
print("[h] hand-calc cylinder: %.2f + %.2f + %.2f + %.2f = %.2f"
      % (2 * PI * 10 * 20, 2 * PI * 8 * 16, 2 * PI * 100, 2 * PI * 64,
         2 * PI * 10 * 20 + 2 * PI * 8 * 16 + 2 * PI * 100 + 2 * PI * 64))

# --- 5) outward=True：壁往外长（SpaceClaim 命令的原始语义） --------------
out = box(20.0, 20.0, 20.0, origin=(40, 60, 0), name="Outward")
shell(out, 2.0, outward=True)
show(out, "outward")
print("[h] outward 语义：原表面变内壁，包围盒应为 24x24x24，面积 2400 + 3456 = %.2f"
      % (2400.0 + 3456.0))

# --- 6) 失败路径：必须抛 ASCII 的 RuntimeError ---------------------------
too_big = box(20.0, 20.0, 20.0, origin=(80, 60, 0), name="TooThick")
msg1 = "none"
try:
    shell(too_big, 11.0)
except Exception, e:
    msg1 = "%s | %s" % (type(e).__name__, str(e)[:60])
print("[h] thickness 11 -> %s" % msg1)
show(too_big, "untouched")

msg2 = "none"
try:
    shell(too_big, 0.0)
except Exception, e:
    msg2 = "%s | %s" % (type(e).__name__, str(e)[:50])
print("[h] thickness 0 -> %s" % msg2)

# --- 7) 命名选择在抽壳前后的行为（结论：必须先抽壳、后命名） ------------
pre = box(20.0, 20.0, 20.0, origin=(120, 60, 0), name="PreNamed")
name_boundaries(pre, bottom="pre_inlet", top="pre_outlet", sides="pre_wall", axis="z")
print("[h] 抽壳前: %s" % str([(_ascii(n), c) for (n, c) in group_summary()]))
shell(pre, 2.0, open_faces=faces_by_normal(pre, "z", 1))
print("[h] 抽壳后: %s" % str([(_ascii(n), c) for (n, c) in group_summary()]))
for g in NamedSelection.GetGroups():
    for m in g.Members:
        c = face_center(m)
        print("[h]   %-12s (%.1f, %.1f, %.1f) area=%.2f"
              % (_ascii(g.Name), c[0], c[1], c[2], face_area(m)))
print("[h] 结论：命名选择**跟着几何走**，但去向不确定——这里 pre_outlet 被重映射到")
print("[h]       新的顶面环（144 mm²），而换成正偏移时同一组会整组消失。")
print("[h]       所以顺序永远是：先抽壳，后命名。")

finish(OUT, cube)
