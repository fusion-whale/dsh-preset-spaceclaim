# -*- coding: utf-8 -*-
# 第 21 个回归用例：带折流板的四层 CHT —— 自动分层检查 + 分段交界面
#
# 缩小版：壳程 60x36x24 + 1 块折流板 + 4 根管（外 r4 / 内 r3）+ 4 根管程流体
#   管位 (y,z) = (6,6) (6,18) (24,6) (24,18)；折流板 x 30..32、y 0..15、z 0..24
#
# 手算基线：
#   体数 = 1 壳 + 1 折流板 + 4 管壁 + 4 管程 = 10
#   穿过折流板的管子：y=6 那两根（y 2..10 ⊂ 0..15），y=24 那两根不穿（20..28）
#   -> 壳程侧管孔壁 = 2 根整面 + 2 根被切成 2 段 = 6 对（2 整面 + 4 分段）
#   -> 总长度 = 4*60 - 2*2 = 236 mm，面积 = 2*pi*4*236 = 5930.97
#   管壁外表面（去重）= 4 * 2*pi*4*60 = 6031.86
#   折流板管孔 = 2 孔 * 2*pi*4*2 = 100.53
#   壳程<->折流板 = 2 张板面 * (15*24 - 2*pi*16) = 2 * 259.47 = 518.94
#   管壁<->管程 = 4 * 2*pi*3*60 = 4523.89
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "selftest_cht_baffled.scdocx")
PI = 3.14159265358979

L, H, D = 60.0, 36.0, 24.0
R_OUT, R_IN = 4.0, 3.0
BAFFLE_T = 2.0
B_X = 30.0
B_H = 15.0
TUBES = [(6.0, 6.0), (6.0, 18.0), (24.0, 6.0), (24.0, 18.0)]

new_model()

# --- 1) 壳程流体 + 折流板槽 ---------------------------------------------
shell = box(L, H, D, origin=(0.0, 0.0, 0.0), name="ShellFluid")
box(BAFFLE_T, B_H, D, origin=(B_X, 0.0, 0.0), cut=True)

# --- 2) 折流板固体塞进槽里 ---------------------------------------------
baffle = box(BAFFLE_T, B_H, D, origin=(B_X, 0.0, 0.0), name="Baffle", separate=True)

# --- 3) 这一轮挖管孔：同时把壳体与折流板都挖穿 --------------------------
for (y, z) in TUBES:
    cylinder(R_OUT, L + 10.0, origin=(-5.0, y, z), axis="x", cut=True)

# --- 4) 管壁 + 管程流体（必须最后建） -----------------------------------
tube_walls = []
tube_side = []
for (y, z) in TUBES:
    tube_walls.append(tube(R_OUT, R_IN, L, origin=(0.0, y, z), axis="x",
                           name="TubeWall", separate=True))
    tube_side.append(cylinder(R_IN, L, origin=(0.0, y, z), axis="x",
                              name="TubeSide", separate=True))

print("[cb] bodies=%d（手算 1 + 1 + %d + %d = %d）"
      % (len(all_bodies()), len(TUBES), len(TUBES), 2 + 2 * len(TUBES)))

# --- 5) 自动分层检查 ----------------------------------------------------
rep = cht_check([
    ("shell_fluid", [shell]),
    ("baffle_solid", [baffle]),
    ("tube_wall", tube_walls),
    ("tube_fluid", tube_side),
])
print("[cb] cht_check ok=%s" % str(rep["ok"]))
for (na, nb, cnt, arc) in rep["touching"]:
    r = rep["pairs"][(na, nb)]
    print("[cb]   相接 %-13s <-> %-12s 整面%3d 分段%3d 面积%9.2f"
          % (na, nb, r["pairs"], r["split_pairs"], arc))
print("[cb]   没接触的层对 = %s" % str(rep["not_touching"]))
print("[cb]   孤立体 = %s ; 覆盖不足 = %s"
      % (str(rep["isolated_bodies"]), str(rep["low_coverage"])))
print("[cb] hand-calc:")
print("[cb]   壳程<->管壁 整面 2 分段 4（合计 6）、面积 %.2f = 4*%.0f*%.0f - 2*%.0f*%.0f"
      % (2 * PI * R_OUT * (4 * L - 2 * BAFFLE_T), PI, 2 * R_OUT, PI, 2 * R_OUT * BAFFLE_T))
print("[cb]   壳程<->折流板 3 对：2 张板面各 %.2f + 1 张板底 %.2f（折流板焊在壳体底面上）"
      % (B_H * D - 2 * PI * R_OUT * R_OUT, BAFFLE_T * D))
print("[cb]   折流板<->管壁 %.2f = 2 * 2*pi*%.0f*%.0f"
      % (2 * 2 * PI * R_OUT * BAFFLE_T, R_OUT, BAFFLE_T))
print("[cb]   管壁<->管程 %.2f = 4 * 2*pi*%.0f*%.0f"
      % (4 * 2 * PI * R_IN * L, R_IN, L))
print("[cb]   壳程<->管程 必须**不在**相接列表里（中间隔着管壁）")

# --- 6) 命名交界面与其余边界（分段也要命名） ---------------------------
n_st = name_interfaces_multi(shell, tube_walls, "shell_tube", allow_split=True)
n_sb = name_interfaces_multi(shell, baffle, "shell_baffle", allow_split=True)
n_bt = name_interfaces_multi(baffle, tube_walls, "baffle_tube", allow_split=True)
n_tf = name_interfaces_multi(tube_walls, tube_side, "tube_fluid", allow_split=True)
print("[cb] 命名的交界面: shell_tube=%d shell_baffle=%d baffle_tube=%d tube_fluid=%d"
      % (n_st, n_sb, n_bt, n_tf))

name_faces_by_rules(shell, [
    ("shell_inlet",  {"kind": "plane", "normal": "x", "sign": -1, "at": ("x", 0.0)}),
    ("shell_outlet", {"kind": "plane", "normal": "x", "sign": +1, "at": ("x", L)}),
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

g = group_summary()
print("[cb] zones=%d" % len(g))
for nm, cnt in g:
    print("[cb]   %-16s %2d face(s)" % (_ascii(nm), cnt))
print("[cb] hand-calc: shell_tube_a=6（2 整 + 4 段）shell_tube_b=4（去重）"
      "shell_baffle_a/b=2 baffle_tube_a/b=2 tube_fluid_a/b=4")

finish(OUT, shell)
