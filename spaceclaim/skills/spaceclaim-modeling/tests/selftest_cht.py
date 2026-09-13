# -*- coding: utf-8 -*-
# 第 20 个回归用例：多体共轭传热（CHT）的流固交界面
#
# 三层模型（小号）：壳程流体 + 4 根管壁固体 + 4 根管程流体
#   壳程流域 60 x 36 x 24，4 根管（外 r4 / 内 r3），管间距 12
#
# 手算基线：
#   shell_inlet  = 36*24 - 4*pi*4^2 = 864 - 201.06 = 662.94
#   shell_tube   两侧各 4 * 2*pi*4*60 = 3015.93 = 4*1507.96
#   tube_fluid   两侧各 4 * 2*pi*3*60 = 2261.95 = 4*1130.97
#   tube_wall_end  2 个环面 * 4 根 = 8 张，每张 pi*(4^2-3^2) = 21.99
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "selftest_cht.scdocx")
PI = 3.14159265358979

L, H, D = 60.0, 36.0, 24.0
R_OUT, R_IN = 4.0, 3.0
PITCH = 12.0
Y0, Z0 = 6.0, 6.0
NY, NZ = 2, 2
NTUBE = NY * NZ

new_model()

# --- 1) 壳程流体：挖 4 个管孔（刀两端出头） -----------------------------
shell = box(L, H, D, origin=(0.0, 0.0, 0.0), name="ShellSide")
for iz in range(NZ):
    for iy in range(NY):
        cylinder(R_OUT, L + 10.0,
                 origin=(-5.0, Y0 + iy * PITCH, Z0 + iz * PITCH),
                 axis="x", cut=True)

# --- 2) 4 根管壁（外 r4 / 内 r3，长度与壳程一致） ------------------------
tube_walls = []
for iz in range(NZ):
    for iy in range(NY):
        tube_walls.append(tube(R_OUT, R_IN, L,
                               origin=(0.0, Y0 + iy * PITCH, Z0 + iz * PITCH),
                               axis="x", name="TubeWall", separate=True))

# --- 3) 4 根管程流体 ----------------------------------------------------
tube_side = []
for iz in range(NZ):
    for iy in range(NY):
        tube_side.append(cylinder(R_IN, L,
                                  origin=(0.0, Y0 + iy * PITCH, Z0 + iz * PITCH),
                                  axis="x", name="TubeSide", separate=True))

print("[c] bodies=%d（手算 1 + %d + %d = %d）"
      % (len(all_bodies()), NTUBE, NTUBE, 1 + 2 * NTUBE))
census = {}
for b in all_bodies():
    k = _ascii(b.Name)
    census[k] = census.get(k, 0) + 1
print("[c] census=%s" % str(census))

# --- 4) 两处流固交界面（成对、全束一个 zone） ---------------------------
n1 = name_interfaces_multi(shell, tube_walls, "shell_tube")
n2 = name_interfaces_multi(tube_walls, tube_side, "tube_fluid")
print("[c] shell_tube pairs=%d tube_fluid pairs=%d（各应为 %d）" % (n1, n2, NTUBE))

r1 = interface_report(shell, tube_walls)
r2 = interface_report(tube_walls, tube_side)
print("[c] shell_tube: pairs=%d area_a=%.2f area_b=%.2f balanced=%s"
      % (r1["pairs"], r1["area_a"], r1["area_b"], str(r1["balanced"])))
print("[c] tube_fluid: pairs=%d area_a=%.2f area_b=%.2f balanced=%s"
      % (r2["pairs"], r2["area_a"], r2["area_b"], str(r2["balanced"])))
print("[c] hand-calc: shell_tube 两侧各 %.2f；tube_fluid 两侧各 %.2f"
      % (NTUBE * 2 * PI * R_OUT * L, NTUBE * 2 * PI * R_IN * L))

# 故意造一个"一侧长出一截"的模型，验证配平自检能抓到
probe = cylinder(R_IN, L + 8.0, origin=(0.0, Y0, Z0 - 0.0), axis="x",
                 name="ProbeSide", separate=True)
r3 = interface_report(tube_walls, probe)
print("[c] 故意做一根长 8mm 的管程体：pairs=%d area_a=%.2f area_b=%.2f balanced=%s"
      % (r3["pairs"], r3["area_a"], r3["area_b"], str(r3["balanced"])))
sus = interface_report(tube_walls, probe, find_suspects=True)["suspects"]
print("[c]   它的 suspects(f=on) 条数=%d（面心近、面积差 >1%%，应能标出来）" % len(sus))

# --- 5) 其余边界条件（同名 zone 要合并，别一根一根建） -----------------
name_faces_by_rules(shell, [
    ("shell_inlet",  {"kind": "plane", "normal": "x", "sign": -1}),
    ("shell_outlet", {"kind": "plane", "normal": "x", "sign": +1}),
])
shell_wall = []
for f in shell.Faces:
    n = face_normal(f)
    if n is None or abs(n[0]) > 0.99:
        continue
    shell_wall.append(f)
name_faces("shell_wall", shell_wall)

ends = []
for t in tube_walls:
    for f in t.Faces:
        if face_kind(f) == "plane":
            ends.append(f)
name_faces("tube_wall_end", ends)

tin, tout = [], []
for f in tube_side:
    for fc in f.Faces:
        n = face_normal(fc)
        if n is None:
            continue
        if n[0] < -0.99:
            tin.append(fc)
        elif n[0] > 0.99:
            tout.append(fc)
name_faces("tube_inlet", tin)
name_faces("tube_outlet", tout)

groups = {}
for nm, cnt in group_summary():
    groups[_ascii(nm)] = cnt
print("[c] zones=%d" % len(groups))
for k in sorted(groups.keys()):
    print("[c]   %-16s %2d face(s)" % (k, groups[k]))
print("[c] hand-calc: shell_wall=4、tube_wall_end=%d、shell_tube_a/b=%d、tube_inlet/outlet=%d"
      % (2 * NTUBE, NTUBE, NTUBE))

# --- 6) 失败路径：建重名 zone 会怎样（记录现象，不让它崩掉整个脚本） ----
print("[c] shell_inlet 的面积 = %.2f（手算 %.2f）"
      % (sum([face_area(m) for g in NamedSelection.GetGroups()
              if _ascii(g.Name) == "shell_inlet" for m in g.Members]),
         H * D - NTUBE * PI * R_OUT * R_OUT))

finish(OUT, shell)
