# -*- coding: utf-8 -*-
# 示例：PCHE（印刷电路板式换热器）一层冷通道 + 一层热通道
#
# 规格（用户给的）：
#   流动截面 D 形，流向沿 x，D 的平边在 z 方向、朝上，通道长 100mm
#   冷热各一层，流体域 + 固体域都要
#
# 尺寸（我定的，按真实 PCHE 量级）：
#   通道半径 R = 1.0mm（D 形宽 2mm、深 1mm）
#   刻槽板厚 1.6mm，盖板 0.6mm；热板 0..1.6、冷板 1.6..3.2、盖 3.2..3.8（总厚 3.8）
#   同层通道栅距 2.4mm（相邻通道壁厚 0.4mm）
#   冷热两层**错开半个栅距 = 1.2mm**，使中间那层 0.6mm 的薄壁正好是换热面
#   每层 2 条通道，板宽 6.8mm
#
# 建体顺序（关键）：
#   ① 先浇 1.6mm 热板 -> 切热通道的 D 形槽（刀心正好落在板上表面，只切掉下半 = 真半圆）
#   ② 再浇 1.6mm 冷板（与热板并成一个固体）-> 切冷通道的 D 形槽
#   ③ 再浇 0.6mm 盖板把冷通道盖住  -> 固体域 1 个体、4 条 D 形封闭通道
#   ④ 流体域：D 形半圆柱没法在固体旁边直接造（全局 cut 会伤到固体），
#      用 half_round_channel() 在文档之外造好再 move 进来（move 不会并集）
#
# 运行：
#   & <skill>\scripts\Invoke-Scdm.ps1 -Script pche_demo.py -Out pche_demo.scdocx -Verify
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "pche_demo.scdocx")
PI = 3.14159265358979

L = 100.0                 # 通道长度（流向 x）
R = 1.0                   # 通道半径 -> D 形宽 2、深 1
T_HOT = 1.6               # 热板厚
T_COLD = 1.6              # 冷板厚
T_CAP = 0.6               # 盖板厚
PITCH = 2.4               # 同层通道栅距
STAGGER = PITCH / 2.0     # 冷热错开的距离
W = 6.8                   # 板宽（z）
Y_HOT = T_HOT             # 热通道的平面 = 热板上表面
Y_COLD = T_HOT + T_COLD   # 冷通道的平面 = 冷板上表面
Z_HOT = [1.6, 4.0]        # 热通道中心
Z_COLD = [1.6 + STAGGER, 4.0 + STAGGER]   # 冷通道中心（错开半栅距）

A_CH = PI * R * R / 2.0            # D 形截面积
P_CH = PI * R + 2.0 * R            # D 形湿周
DH = 4.0 * A_CH / P_CH             # 水力直径

new_model()

# ---- ① 热板 + 热通道刻槽 -----------------------------------------------
solid = box(L, T_HOT, W, origin=(0.0, 0.0, 0.0), name="Solid")
for z in Z_HOT:
    # 刀心正好落在热板上表面 -> 只切掉下半，得到**真半圆**槽
    cylinder(R, L + 10.0, origin=(-5.0, Y_HOT, z), axis="x", cut=True)

# ---- ② 冷板 + 冷通道刻槽（与热板并成一个固体） -------------------------
box(L, T_COLD, W, origin=(0.0, T_HOT, 0.0))
for z in Z_COLD:
    cylinder(R, L + 10.0, origin=(-5.0, Y_COLD, z), axis="x", cut=True)

# ---- ③ 盖板把冷通道盖住 ------------------------------------------------
box(L, T_CAP, W, origin=(0.0, Y_COLD, 0.0))

# ---- ④ 流体域：在空白处造好 D 形半圆柱再搬进来 -------------------------
hot = []
cold = []
for z in Z_HOT:
    hot.append(half_round_channel(R, L, origin=(0.0, Y_HOT, z), axis="x",
                                  flat="+y", name="HotFluid"))
for z in Z_COLD:
    cold.append(half_round_channel(R, L, origin=(0.0, Y_COLD, z), axis="x",
                                   flat="+y", name="ColdFluid"))

print("[pc] bodies=%d（手算 1 固体 + %d 热 + %d 冷 = %d）"
      % (len(all_bodies()), len(hot), len(cold), 1 + len(hot) + len(cold)))
census = {}
for b in all_bodies():
    k = _ascii(b.Name)
    census[k] = census.get(k, 0) + 1
print("[pc] census=%s" % str(census))
print("[pc] solid faces=%d（应为 6 外表面 + %d 条通道 x 2 面 = %d）"
      % (len(list(solid.Faces)), len(hot) + len(cold), 6 + 2 * (len(hot) + len(cold))))
for b in hot + cold:
    print("[pc]   %-10s faces=%d size=%s"
          % (_ascii(b.Name), len(list(b.Faces)),
             str(tuple(round(v, 3) for v in body_size(b)))))

# ---- ⑤ 交界面配对命名 --------------------------------------------------
n_hot = name_interfaces_multi(hot, [solid], "hot_interface")
n_cold = name_interfaces_multi(cold, [solid], "cold_interface")
r_hot = interface_report(hot, [solid])
r_cold = interface_report(cold, [solid])
print("[pc] hot 交界面 %d 对，面积 %.2f / %.2f  balanced=%s"
      % (n_hot, r_hot["area_a"], r_hot["area_b"], str(r_hot["balanced"])))
print("[pc] cold 交界面 %d 对，面积 %.2f / %.2f  balanced=%s"
      % (n_cold, r_cold["area_a"], r_cold["area_b"], str(r_cold["balanced"])))

# ---- ⑥ 自动分层检查 ----------------------------------------------------
rep = cht_check([
    ("hot_fluid", hot),
    ("solid", [solid]),
    ("cold_fluid", cold),
])
print("[pc] cht_check ok=%s" % str(rep["ok"]))
for (na, nb, cnt, arc) in rep["touching"]:
    r = rep["pairs"][(na, nb)]
    print("[pc]   相接 %-10s <-> %-10s 整面%2d 分段%2d 面积%9.2f"
          % (na, nb, r["pairs"], r["split_pairs"], arc))
print("[pc]   没接触的层对 = %s（热/冷流体之间隔着固体，必须不接触）"
      % str(rep["not_touching"]))
print("[pc]   孤立体 = %s" % str(rep["isolated_bodies"]))

# ---- ⑦ 其余命名 --------------------------------------------------------
hi_faces, ho_faces, ci_faces, co_faces = [], [], [], []
for b in hot:
    for f in b.Faces:
        n = face_normal(f)
        if n is None:
            continue
        if n[0] < -0.99:
            hi_faces.append(f)
        elif n[0] > 0.99:
            ho_faces.append(f)
for b in cold:
    for f in b.Faces:
        n = face_normal(f)
        if n is None:
            continue
        if n[0] < -0.99:
            ci_faces.append(f)
        elif n[0] > 0.99:
            co_faces.append(f)
name_faces("hot_inlet", hi_faces)
name_faces("hot_outlet", ho_faces)
name_faces("cold_inlet", ci_faces)
name_faces("cold_outlet", co_faces)

# 固体外表面：要排除已经归给交界面的那几张通道顶面，
# 否则同一张面会同时属于两个 zone（Fluent 里会有歧义）
already = {}
for grp in NamedSelection.GetGroups():
    nm = _ascii(grp.Name)
    if nm.startswith("hot_interface") or nm.startswith("cold_interface"):
        for m in grp.Members:
            already[_face_key(m)] = 1
solid_outer = []
for f in solid.Faces:
    if face_normal(f) is None:
        continue
    if _face_key(f) in already:
        continue
    solid_outer.append(f)
name_faces("solid_outer_wall", solid_outer)
print("[pc] 固体外表面 %d 张（6 张外壳去掉通道穿出的部分后再排除已命名的 %d 张通道顶面）"
      % (len(solid_outer), len(already)))

# ---- ⑧ 数据汇总 --------------------------------------------------------
print("[pc] D 形截面：面积 %.4f mm2、湿周 %.4f mm、水力直径 Dh = %.4f mm"
      % (A_CH, P_CH, DH))
print("[pc] 单条通道：体积 %.2f mm3 = %.4f cm3；换热面积(单个流体域) %.2f mm2"
      % (A_CH * L, A_CH * L / 1000.0, (PI * R + 2.0 * R) * L))
solid_vol = L * (T_HOT + T_COLD + T_CAP) * W - (len(hot) + len(cold)) * A_CH * L
print("[pc] 固体域体积 %.2f mm3（外形 %.0f 减去 %d 条通道 %.1f）"
      % (solid_vol, L * (T_HOT + T_COLD + T_CAP) * W, len(hot) + len(cold),
         (len(hot) + len(cold)) * A_CH * L))
print("[pc] 冷热薄壁：热通道顶 y=%.1f、冷通道底 y=%.1f -> 壁厚 %.1f mm（换热面）"
      % (Y_HOT, Y_COLD - R, (Y_COLD - R) - Y_HOT))

g = group_summary()
print("[pc] zones=%d" % len(g))
for nm, cnt in g:
    print("[pc]   %-18s %2d face(s)" % (_ascii(nm), cnt))

finish(OUT, solid)
