# -*- coding: utf-8 -*-
# 第 15 个回归用例：倒圆角 / 倒角（ConstantRound / Chamfer）
#
# 覆盖：全体倒圆、只倒某一方向的立边、全体倒角、等距/不等距倒角、
#       圆管口倒圆、规则表批量倒角、失败路径必须抛 ASCII 异常。
# 手算基线（和脚本打印的值对照）：
#   20mm 立方体全部 12 条边倒圆 r=2：
#     平面面   6 x (20-2r)^2      = 6 x 256.00 = 1536.00
#     倒圆面  12 x (pi*r/2)*(20-2r) = 12 x  50.27 =  603.19
#     球角面   8 x (4*pi*r^2/8)   =  8 x   6.28 =   50.27
#     合计 2189.45 mm^2，面数 6+12+8 = 26
#   4x4x10 方管四条长边倒圆 r=1：
#     端面 4x4 去四角 = 16 - (4-pi) = 15.14
#     倒圆面 4 x (pi*1/2)*10        = 15.71
#     平面壁 4 x (4-2)*10           = 20.00
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "selftest_fillet.scdocx")
PI = 3.14159265358979

new_model()

# --- 1) 20mm 立方体，12 条边全部倒圆 r=2 --------------------------------
cube = box(20.0, 20.0, 20.0, origin=(0, 0, 0), name="RoundCube")
print("[f] cube before: faces=%d edges=%s"
      % (len(list(cube.Faces)), str(edge_summary(cube))))
submitted = round_edges(cube, 2.0)
print("[f] cube round: submitted=%d faces=%d edges=%s"
      % (submitted, len(list(cube.Faces)), str(edge_summary(cube))))

kinds = {}
for f in cube.Faces:
    k = face_kind(f)
    kinds[k] = kinds.get(k, 0) + 1
print("[f] cube face kinds: %s" % str(kinds))
print("[f] cube hand-calc total = %.3f mm2" % (6 * 256.0 + 12 * (PI * 2.0 / 2.0) * 16.0
                                               + 8 * (4.0 * PI * 4.0 / 8.0)))
name_faces_by_rules(cube, [
    ("cu_inlet",       {"kind": "plane", "normal": "z", "sign": -1}),
    ("cu_outlet",      {"kind": "plane", "normal": "z", "sign": +1}),
    ("cu_side",        {"kind": "plane"}),
    ("cu_edge_fillet", {"kind": "cylinder"}),
    ("cu_corner",      {"kind": "sphere"}),
])

# --- 2) 20mm 立方体，只倒 4 条平行于 Z 的立边 r=3 ------------------------
cubez = box(20.0, 20.0, 20.0, origin=(30, 0, 0), name="RoundCubeZ")
zed = edges_parallel(cubez, "z")
print("[f] cubez z-edges=%d" % len(zed))
round_edges(zed, 3.0)
print("[f] cubez after: faces=%d edges=%s"
      % (len(list(cubez.Faces)), str(edge_summary(cubez))))
name_faces_by_rules(cubez, [
    ("cz_inlet",  {"normal": "z", "sign": -1}),
    ("cz_outlet", {"normal": "z", "sign": +1}),
    ("cz_fillet", {"kind": "cylinder"}),
    ("cz_side",   {"rest": True}),
])

# --- 3) 20mm 立方体，12 条边全部倒角 d=2 --------------------------------
cham = box(20.0, 20.0, 20.0, origin=(60, 0, 0), name="ChamferCube")
submitted = chamfer_edges(cham, 2.0)
print("[f] chamfer: submitted=%d faces=%d edges=%s"
      % (submitted, len(list(cham.Faces)), str(edge_summary(cham))))

# --- 4) 圆管的管口两圈圆边倒圆 r=1 --------------------------------------
tb = tube(10.0, 6.0, 20.0, origin=(0, 40, 0), axis="z", name="RoundTube")
rims = edges_along_axis(tb, "z")
print("[f] tube rims=%d kinds=%s" % (len(rims), str([edge_kind(e) for e in rims])))
round_edges(rims, 1.0)
print("[f] tube after: faces=%d edges=%s"
      % (len(list(tb.Faces)), str(edge_summary(tb))))

# --- 5) CFD 场景：4x4x10 方管四条长边倒圆 r=1，然后命名边界 -------------
duct = box(4.0, 4.0, 10.0, origin=(0, 80, 0), name="RoundedDuct")
round_edges(edges_parallel(duct, "z"), 1.0)
print("[f] duct after: faces=%d edges=%s"
      % (len(list(duct.Faces)), str(edge_summary(duct))))
print("[f] duct hand-calc: end=%.3f fillet=%.3f wall=%.3f"
      % (16.0 - (4.0 - PI), (PI * 1.0 / 2.0) * 10.0, 2.0 * 10.0))
name_faces_by_rules(duct, [
    ("duct_inlet",  {"normal": "z", "sign": -1}),
    ("duct_outlet", {"normal": "z", "sign": +1}),
    ("duct_fillet", {"kind": "cylinder"}),
    ("duct_wall",   {"rest": True}),
])

# --- 6) 规则表批量倒圆 + 不等距倒角 --------------------------------------
rb = box(20.0, 20.0, 20.0, origin=(40, 40, 0), name="RuleBox")
counts = round_by_rules(rb, [
    ({"parallel": "z"}, 2.0),
    ({"rest": True}, 1.0),
])
print("[f] rulebox counts=%s faces=%d edges=%s"
      % (str(counts), len(list(rb.Faces)), str(edge_summary(rb))))

cb = box(20.0, 20.0, 20.0, origin=(80, 40, 0), name="ChamferTwo")
chamfer_edges(edges_parallel(cb, "z"), 4.0, 1.0)
print("[f] chamfer two-dist: faces=%d edges=%s"
      % (len(list(cb.Faces)), str(edge_summary(cb))))

# --- 7) "把这个面的四周倒圆"：按面的边界边取边 --------------------------
fr = box(20.0, 20.0, 20.0, origin=(120, 40, 0), name="FaceRound")
top = faces_by_normal(fr, "z", 1)
top_edges = edges_of_faces(top)
print("[f] faceround top edges=%d kinds=%s"
      % (len(top_edges), str([edge_kind(e) for e in top_edges])))
round_face_edges(top, 3.0)
print("[f] faceround after: faces=%d edges=%s"
      % (len(list(fr.Faces)), str(edge_summary(fr))))

# --- 8) 失败路径：必须抛 ASCII 的 RuntimeError，而不是静默成功 -----------
big = box(10.0, 10.0, 10.0, origin=(80, 80, 0), name="TooBig")
big_msg = "none"
try:
    round_edges(big, 9.0)
except Exception, e:
    big_msg = "%s | %s" % (type(e).__name__, str(e)[:48])
print("[f] oversized radius -> %s" % big_msg)

stale = box(20.0, 20.0, 20.0, origin=(120, 80, 0), name="Stale")
stale_edges = list(stale.Edges)
round_edges(stale_edges, 1.0)
stale_msg = "none"
try:
    round_edges(stale_edges, 1.0)
except Exception, e:
    stale_msg = "%s | %s" % (type(e).__name__, str(e)[:48])
print("[f] stale edge re-use -> %s" % stale_msg)
print("[f] stale body now: faces=%d edges=%s"
      % (len(list(stale.Faces)), str(edge_summary(stale))))

finish(OUT, duct)
