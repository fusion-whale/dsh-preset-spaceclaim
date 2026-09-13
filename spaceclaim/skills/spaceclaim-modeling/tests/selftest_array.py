# -*- coding: utf-8 -*-
# 第 18 个回归用例：阵列（线性/圆周）与镜像
#
# 手算基线：
#   10³ 立方体沿 X 摆 4 个、间距 20        -> 4 体、24 面、2400 mm²（每体 6 面 600）
#   10³ 立方体 3x2 阵列（间距 20 / 25）    -> 6 体、36 面、3600 mm²
#   6³ 叶片放在半径 20 处、绕 Z 整圈 6 个   -> 6 体、36 面、1296 mm²（每体 6 面 216）
#   10³ 放在 x=10..20、按自身 x=10 面镜像 merge=True  -> 1 体、包围盒 20x10x10
#   同上 merge=False                        -> 2 体、12 面、1200 mm²
#   CFD 场景：60x40x30 流域挖掉 3x3 根 r=3 的管子（管内缩 6mm）-> 6 张平面 + 9 张管壁 = 15 面
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "selftest_array.scdocx")
PI = 3.14159265358979


def total_faces():
    n = 0
    for b in GetRootPart().Bodies:
        n += len(list(b.Faces))
    return n


def total_area():
    a = 0.0
    for b in GetRootPart().Bodies:
        for f in b.Faces:
            a += face_area(f)
    return a


def group_stats(tag, items):
    nf = 0
    area = 0.0
    for b in items:
        nf += len(list(b.Faces))
        for f in b.Faces:
            area += face_area(f)
    print("[a] %-14s instances=%d faces=%d area=%.2f" % (tag, len(items), nf, area))
    for b in items:
        print("[a]      %-10s faces=%2d size=%s"
              % (_ascii(b.Name), len(list(b.Faces)),
                 str(tuple(round(x, 3) for x in body_size(b)))))


new_model()

# --- 1) 线性阵列 4 个（放在空白区域，互不重叠） -------------------------
a1 = box(10.0, 10.0, 10.0, origin=(0, 0, 0), name="Pin")
items = array_linear(a1, 4, 20.0, axis="x", name="Pin")
group_stats("linear 4", items)
print("[a] hand-calc: 4 体、24 面、2400 mm2")

# --- 2) 2D 阵列 3x2（另一块空白区域） -----------------------------------
a2 = box(10.0, 10.0, 10.0, origin=(0.0, 200.0, 0.0), name="Fin")
items2 = array_linear(a2, 3, 20.0, axis="x", count2=2, pitch2=25.0, axis2="y", name="Fin")
group_stats("linear 3x2", items2)
print("[a] hand-calc: 6 体、36 面、3600 mm2")

# --- 3) 圆周阵列 6 个（中心挪到空白区域） -------------------------------
blade = box(6.0, 6.0, 6.0, origin=(300.0, -3.0, 0.0), name="Blade")
items3 = array_circular(blade, 6, axis="z", center=(300.0, 0.0, 0.0), name="Blade")
group_stats("circular 6", items3)
print("[a] hand-calc: 6 体、36 面、1296 mm2")

# --- 4) 镜像：merge=True（半模型补成整模型） ----------------------------
half = box(10.0, 10.0, 10.0, origin=(500.0, 10.0, 0.0), name="Half")
res_m = mirror(half, faces_by_normal(half, "x", -1)[0], merge=True)
print("[a] mirror merge=True -> %d body object(s), half now faces=%d size=%s"
      % (len(res_m), len(list(half.Faces)),
         str(tuple(round(x, 3) for x in body_size(half)))))
print("[a] hand-calc: 1 体、包围盒 20x10x10")

# --- 5) 镜像：merge=False（保留两个独立体） -----------------------------
half2 = box(10.0, 10.0, 10.0, origin=(500.0, 60.0, 0.0), name="Half2")
res_m2 = mirror(half2, faces_by_normal(half2, "x", -1)[0], merge=False, name="Half2Mirror")
print("[a] mirror merge=False -> %d body object(s) -> %s"
      % (len(res_m2), str([_ascii(b.Name) for b in res_m2])))
print("[a] hand-calc: 2 体、12 面、1200 mm2")

# --- 6) CFD 场景：管束流域（域先建，再逐个 cut 掉管子） -----------------
# 注意：管子必须**完全落在**流域内部。实测 cutter 与流域壁面相切时（圆心到壁面的
# 距离正好等于半径）那一次 cut 会静默失效——9 根里只有 4 根挖出来了。
domain = box(60.0, 40.0, 30.0, origin=(700.0, 0.0, 0.0), name="BankDomain")
tubes = 0
for ix in range(3):
    for iy in range(3):
        cylinder(3.0, 40.0, origin=(706.0 + ix * 12.0, 6.0 + iy * 12.0, -5.0),
                 axis="z", cut=True)
        tubes += 1
name_faces_by_rules(domain, [
    ("bank_inlet",  {"normal": "x", "sign": -1}),
    ("bank_outlet", {"normal": "x", "sign": +1}),
    ("bank_tubes",  {"kind": "cylinder"}),
    ("bank_wall",   {"rest": True}),
])
print("[a] tube bank: cutters=%d faces=%d kinds=%s"
      % (tubes, len(list(domain.Faces)),
         str(sorted(set([face_kind(f) for f in domain.Faces])))))
print("[a] hand-calc: 6 张平面 + 9 张管壁 = 15 面；管壁合计 9 x 2*pi*3*30 = %.2f"
      % (9 * 2 * PI * 3 * 30))

# --- 7) 失败路径 --------------------------------------------------------
msg = "none"
try:
    array_linear(a1, 0, 10.0)
except Exception, e:
    msg = "%s | %s" % (type(e).__name__, str(e)[:50])
print("[a] count=0 -> %s" % msg)

msg2 = "none"
try:
    array_linear(a1, 2, 10.0, count2=2)
except Exception, e:
    msg2 = "%s | %s" % (type(e).__name__, str(e)[:60])
print("[a] count2 without pitch2 -> %s" % msg2)

msg3 = "none"
try:
    mirror(a1, None)
except Exception, e:
    msg3 = "%s | %s" % (type(e).__name__, str(e)[:60])
print("[a] mirror without a plane -> %s" % msg3)

finish(OUT, domain)
