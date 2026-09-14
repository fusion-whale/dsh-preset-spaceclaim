# -*- coding: utf-8 -*-
# 示例：PCHE（印刷电路板式换热器）**一对**冷热通道
#
# 规格（用户给的）：
#   流动截面 D 形，流向沿 x，**D 的平边朝 z 方向**（法向 +z、弧朝 -z 鼓出），通道长 100mm
#   冷热各一条，**上下对齐**，流体域 + 固体域都建
#
# 尺寸（我定的，按真实 PCHE 量级）：
#   通道半径 R = 1.0mm（D 形在 y 向宽 2mm、在 z 向深 1mm）
#   刻槽板厚 1.6mm；冷板叠在热板上，冷热之间只剩 **0.6mm 换热薄壁**；上面再盖 0.6mm 盖板
#   板宽（y）3.2mm = 通道 2 + 两侧各 0.6 边距
#   总尺寸 100 x 3.2 x 3.8 mm，总厚 = 1.6(热板) + 1.6(冷板) + 0.6(盖板)
#
# 建体顺序（关键）：
#   ① 浇 1.6mm 热板 -> 切热通道的 D 形槽（刀心正好在板上表面 z=1.6，只切掉下半 = 真半圆）
#   ② 浇 1.6mm 冷板（与热板并成一个固体）-> 切冷通道的 D 形槽（刀心在 z=3.2）
#   ③ 浇 0.6mm 盖板 -> 固体域 1 个体、2 条封闭 D 形通道
#   ④ 流体域：half_round_channel() 在文档之外造好再 move 进来（全局 cut 会伤到固体）
#
# 运行：
#   & <skill>\scripts\Invoke-Scdm.ps1 -Script pche_demo.py -Out pche_demo.scdocx -Verify
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "pche_demo.scdocx")
PI = 3.14159265358979

L = 100.0                  # 通道长度（流向 x）
R = 1.0                    # 通道半径 -> D 形 y 向宽 2、z 向深 1
T_PLATE = 1.6              # 刻槽板厚
T_CAP = 0.6                # 盖板厚
W = 3.2                    # 板宽（y）：通道 2 + 两侧边距各 0.6
Y_C = W / 2.0              # 通道中心（y）= 1.6，冷热**对齐**
Z_HOT = T_PLATE            # 热通道平边所在的 z = 1.6
Z_COLD = 2.0 * T_PLATE     # 冷通道平边所在的 z = 3.2
Z_TOP = 2.0 * T_PLATE + T_CAP     # 总厚 3.8

A_CH = PI * R * R / 2.0
P_CH = PI * R + 2.0 * R
DH = 4.0 * A_CH / P_CH

new_model()

# ---- ① 热板 + 热通道刻槽（刀心在板上表面 -> 真半圆） -------------------
solid = box(L, W, T_PLATE, origin=(0.0, 0.0, 0.0), name="Solid")
cylinder(R, L + 10.0, origin=(-5.0, Y_C, Z_HOT), axis="x", cut=True)

# ---- ② 冷板 + 冷通道刻槽（与热板并成一个固体） -------------------------
box(L, W, T_PLATE, origin=(0.0, 0.0, T_PLATE))
cylinder(R, L + 10.0, origin=(-5.0, Y_C, Z_COLD), axis="x", cut=True)

# ---- ③ 盖板 ------------------------------------------------------------
box(L, W, T_CAP, origin=(0.0, 0.0, Z_COLD))

# ---- ④ 流体域：空白处造好 D 形半圆柱再搬进来 ---------------------------
hot = half_round_channel(R, L, origin=(0.0, Y_C, Z_HOT), axis="x",
                         flat="+z", name="HotFluid")
cold = half_round_channel(R, L, origin=(0.0, Y_C, Z_COLD), axis="x",
                          flat="+z", name="ColdFluid")

print("[pc] bodies=%d（手算 1 固体 + 1 热 + 1 冷 = 3）" % len(all_bodies()))
census = {}
for b in all_bodies():
    k = _ascii(b.Name)
    census[k] = census.get(k, 0) + 1
print("[pc] census=%s" % str(census))
print("[pc] 尺寸: 固体 %s；热流体 %s；冷流体 %s"
      % (str(tuple(round(v, 3) for v in body_size(solid))),
         str(tuple(round(v, 3) for v in body_size(hot))),
         str(tuple(round(v, 3) for v in body_size(cold)))))
print("[pc] solid faces=%d（手算 6 外表面 + 2 条通道 x 2 面 = 10）" % len(list(solid.Faces)))
print("[pc] 通道位置：热平边 z=%.1f（弧到 z=%.1f）、冷平边 z=%.1f（弧到 z=%.1f）"
      % (Z_HOT, Z_HOT - R, Z_COLD, Z_COLD - R))
print("[pc] 冷热**对齐**：两者 y 中心都是 %.1f、x 都是 0..%.0f" % (Y_C, L))
print("[pc] 冷热之间的薄壁 = %.1f mm（z %.1f..%.1f，就是换热面）"
      % ((Z_COLD - R) - Z_HOT, Z_HOT, Z_COLD - R))

# ---- ⑤ 交界面配对 + 自动分层检查 ---------------------------------------
n_hot = name_interfaces_multi([hot], [solid], "hot_interface")
n_cold = name_interfaces_multi([cold], [solid], "cold_interface")
r_hot = interface_report([hot], [solid])
r_cold = interface_report([cold], [solid])
print("[pc] hot 交界面 %d 对，两侧 %.2f / %.2f  balanced=%s"
      % (n_hot, r_hot["area_a"], r_hot["area_b"], str(r_hot["balanced"])))
print("[pc] cold 交界面 %d 对，两侧 %.2f / %.2f  balanced=%s"
      % (n_cold, r_cold["area_a"], r_cold["area_b"], str(r_cold["balanced"])))

rep = cht_check([("hot_fluid", [hot]), ("solid", [solid]), ("cold_fluid", [cold])])
print("[pc] cht_check ok=%s" % str(rep["ok"]))
for (na, nb, cnt, arc) in rep["touching"]:
    r = rep["pairs"][(na, nb)]
    print("[pc]   相接 %-10s <-> %-10s 整面%2d 分段%2d 面积%9.2f"
          % (na, nb, r["pairs"], r["split_pairs"], arc))
print("[pc]   没接触的层对 = %s（热/冷之间隔着固体，必须不接触）" % str(rep["not_touching"]))
print("[pc]   孤立体 = %s" % str(rep["isolated_bodies"]))

# ---- ⑥ 其余命名 --------------------------------------------------------
def by_normal(body, sign):
    out = []
    for f in body.Faces:
        n = face_normal(f)
        if n is None:
            continue
        if (sign < 0 and n[0] < -0.99) or (sign > 0 and n[0] > 0.99):
            out.append(f)
    return out

name_faces("hot_inlet", by_normal(hot, -1))
name_faces("hot_outlet", by_normal(hot, +1))
name_faces("cold_inlet", by_normal(cold, -1))
name_faces("cold_outlet", by_normal(cold, +1))

already = {}
for grp in NamedSelection.GetGroups():
    nm = _ascii(grp.Name)
    if nm.startswith("hot_interface") or nm.startswith("cold_interface"):
        for m in grp.Members:
            already[_face_key(m)] = 1
solid_outer = []
for f in solid.Faces:
    if face_normal(f) is None or _face_key(f) in already:
        continue
    solid_outer.append(f)
name_faces("solid_outer_wall", solid_outer)

# ---- ⑦ 数据 ------------------------------------------------------------
print("[pc] D 形截面：面积 %.4f mm2、湿周 %.4f mm、水力直径 Dh = %.4f mm"
      % (A_CH, P_CH, DH))
solid_vol = L * W * Z_TOP - 2.0 * A_CH * L
print("[pc] 单条通道体积 %.2f mm3；换热面积(单个流体域) %.2f mm2 = 弧面 %.2f + 平面 %.2f"
      % (A_CH * L, (PI * R + 2 * R) * L, PI * R * L, 2 * R * L))
print("[pc] 固体域体积 %.2f mm3（外形 %.2f 减去 2 条通道 %.2f）"
      % (solid_vol, L * W * Z_TOP, 2.0 * A_CH * L))

g = group_summary()
print("[pc] zones=%d" % len(g))
for nm, cnt in g:
    print("[pc]   %-18s %2d face(s)" % (_ascii(nm), cnt))

finish(OUT, solid)
