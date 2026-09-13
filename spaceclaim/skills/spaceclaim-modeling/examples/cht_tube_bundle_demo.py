# -*- coding: utf-8 -*-
# 示例：管壳式换热器的**共轭传热（CHT）**三层模型
#
#   ① 壳程流体 shell_side ：长方体挖掉 12 个 r=5 的管孔
#   ② 管壁固体 tube_walls ：12 根 r5/r4 的环（外表面贴在壳程孔壁上、内表面是管程孔壁）
#   ③ 管程流体 tube_side ：12 根 r=4 的圆柱（贴在管壁内表面上）
#
# 两处流固交界面都要成对命名：
#   shell_tube_a  ↔ shell_tube_b   （壳程流体 ↔ 管壁外表面）
#   tube_fluid_a  ↔ tube_fluid_b   （管壁内表面 ↔ 管程流体）
# 命名之后用 interface_report() 做**配平自检**：两侧面积必须相等，
# 而且不能出现"面心很近但面积对不上"的可疑组合。
#
# 运行：
#   & <skill>\scripts\Invoke-Scdm.ps1 -Script cht_tube_bundle_demo.py -Out cht_tube_bundle_demo.scdocx -Verify
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "cht_tube_bundle_demo.scdocx")
PI = 3.14159265358979

L, H, D = 100.0, 50.0, 40.0     # 壳程流域 长(x) x 高(y) x 深(z)
R_OUT = 5.0                     # 管外半径
R_IN = 4.0                      # 管内半径
NTUBE = 12
PITCH = 12.0                    # 管间距 —— **必须 > 2*R_OUT**！
# 实测教训：R_OUT=5 配 10mm 间距时相邻两根管正好**外切**，布尔会静默失败，
# 12 次挖孔里有 11 次没生效、反而在孔里留下 11 个实体刀具体（未命名、长 110）。
# 这和第 18 个用例里"刀与壁面相切"是同一类坑。
Y0, Z0 = 6.0, 6.0

new_model()

# ---- ① 壳程流体：长方体挖掉 12 个管孔 ---------------------------------
# 刀还要**两端出头**（-5..105）：端面与目标体端面共面同样是危险操作。
shell = box(L, H, D, origin=(0.0, 0.0, 0.0), name="ShellSide")
for iz in range(3):
    for iy in range(4):
        cylinder(R_OUT, L + 10.0,
                 origin=(-5.0, Y0 + iy * PITCH, Z0 + iz * PITCH),
                 axis="x", cut=True)

# ---- ② 管壁固体：12 根环（外 r5 / 内 r4），恰好落在孔里 ----------------
# 必须 separate=True：管外表面和壳程孔壁尺寸完全相同，默认并集会把管子吃进孔壁
# （实测：12 根建完只剩 1 个体、管孔被填掉，CHT 三层直接塌掉）。
# 长度也必须和壳程流域**一样**（都是 L）：管壁露出壳体外会让两侧交界面面积对不上，
# interface_report() 会直接把它们报成 suspects。
tube_walls = []
for iz in range(3):
    for iy in range(4):
        t = tube(R_OUT, R_IN, L,
                 origin=(0.0, Y0 + iy * PITCH, Z0 + iz * PITCH),
                 axis="x", name="TubeWall", separate=True, overshoot=1.0)
        tube_walls.append(t)

# ---- ③ 管程流体：12 根内圆柱 ------------------------------------------
tube_side = []
for iz in range(3):
    for iy in range(4):
        f = cylinder(R_IN, L,
                     origin=(0.0, Y0 + iy * PITCH, Z0 + iz * PITCH),
                     axis="x", name="TubeSide", separate=True)
        tube_side.append(f)

print("[cht] bodies: shell=1, tube_walls=%d, tube_side=%d, total=%d"
      % (len(tube_walls), len(tube_side), len(all_bodies())))
ks = {}
for b in all_bodies():
    k = "%s|%s" % (_ascii(b.Name), str(tuple(round(v, 1) for v in body_size(b))))
    ks[k] = ks.get(k, 0) + 1
print("[cht] body census: %s" % str(ks))

# ---- ④ 命名交界面（成对，全束合成一对 zone） ---------------------------
n1 = name_interfaces_multi(shell, tube_walls, "shell_tube")
n2 = name_interfaces_multi(tube_walls, tube_side, "tube_fluid")
print("[cht] shell_tube pairs = %d, tube_fluid pairs = %d" % (n1, n2))

# ---- ⑤ 配平自检 --------------------------------------------------------
r1 = interface_report(shell, tube_walls)
r2 = interface_report(tube_walls, tube_side)
print("[cht] shell_tube: pairs=%d area_a=%.2f area_b=%.2f balanced=%s suspects=%d"
      % (r1["pairs"], r1["area_a"], r1["area_b"], str(r1["balanced"]), len(r1["suspects"])))
print("[cht] tube_fluid: pairs=%d area_a=%.2f area_b=%.2f balanced=%s suspects=%d"
      % (r2["pairs"], r2["area_a"], r2["area_b"], str(r2["balanced"]), len(r2["suspects"])))

# ---- ⑥ 其余边界条件 ----------------------------------------------------
# 注意：**不要对 12 根管子分别建"同名"的命名选择**（第一版就是这么写的，
# 建出 12 组同名 zone 之后 `NamedSelection.GetGroups()` 直接崩了）。
# Fluent 里也该是"一个 zone 装多张面"，所以下面都是把 12 根的面**合起来**命名。
name_faces_by_rules(shell, [
    ("shell_inlet",  {"kind": "plane", "normal": "x", "sign": -1}),
    ("shell_outlet", {"kind": "plane", "normal": "x", "sign": +1}),
])
# 壳体的其余面（4 张侧面 + 顶底）—— 管孔的圆柱面已经归 shell_tube_a，不要重复收进来
shell_wall = []
for f in shell.Faces:
    n = face_normal(f)
    if n is None:
        continue
    if abs(n[0]) > 0.99:
        continue
    shell_wall.append(f)
name_faces("shell_wall", shell_wall)

# 12 根管壁的两个环端面合成一个 zone（管壁的内外圆柱面已经是交界面了）
tube_wall_end = []
for t in tube_walls:
    for f in t.Faces:
        if face_kind(f) == "plane":
            tube_wall_end.append(f)
name_faces("tube_wall_end", tube_wall_end)

# 12 根管程流体的进出口端面各合成一个 zone（侧面已经是 tube_fluid_b）
tube_inlet = []
tube_outlet = []
for f in tube_side:
    for fc in f.Faces:
        n = face_normal(fc)
        if n is None:
            continue
        if n[0] < -0.99:
            tube_inlet.append(fc)
        elif n[0] > 0.99:
            tube_outlet.append(fc)
name_faces("tube_inlet", tube_inlet)
name_faces("tube_outlet", tube_outlet)

# ---- ⑦ 实测值 + 手算对照 ----------------------------------------------
print("[cht] hand-calc:")
print("[cht]   shell_inlet  应 = 50*40 - %d*pi*%.0f^2 = %.2f"
      % (NTUBE, R_OUT, H * D - NTUBE * PI * R_OUT * R_OUT))
print("[cht]   shell_tube   两侧各 = %d * 2*pi*%.0f*%.0f = %.2f"
      % (NTUBE, R_OUT, L, NTUBE * 2 * PI * R_OUT * L))
print("[cht]   tube_fluid   两侧各 = %d * 2*pi*%.0f*%.0f = %.2f"
      % (NTUBE, R_IN, L, NTUBE * 2 * PI * R_IN * L))

groups = group_summary()
print("[cht] named selections=%d" % len(groups))
seen = {}
for nm, cnt in groups:
    seen[nm] = cnt
for k in sorted(seen.keys()):
    if k.startswith("shell") or k.startswith("tube"):
        print("[cht]   %-18s %d face(s)" % (k, seen[k]))

finish(OUT, shell)
