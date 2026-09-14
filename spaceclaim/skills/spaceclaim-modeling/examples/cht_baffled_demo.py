# -*- coding: utf-8 -*-
# 示例：带折流板的完整四层共轭传热模型
#
#   ① 壳程流体 shell_fluid ：长方体 -> 挖 2 个折流板槽 -> 挖 12 个管孔
#   ② 折流板固体 baffles   ：塞进槽里的两块板（**同一轮挖孔把管孔也挖穿它们**）
#   ③ 管壁固体 tube_walls  ：12 根 r5/r4 的环
#   ④ 管程流体 tube_side   ：12 根 r4 的圆柱
#
# 关键顺序（`cut=True` 是**全局**的，刀会切文档里所有体，所以顺序决定一切）：
#   建壳 -> 挖折流板槽 -> 塞折流板 -> **这一轮挖管孔同时把壳和折流板都挖穿** ->
#   最后才建管壁和管程流体。
# 这样折流板天然带着管孔（管子穿过去），而管壁又不会被误切。
#
# 运行：
#   & <skill>\scripts\Invoke-Scdm.ps1 -Script cht_baffled_demo.py -Out cht_baffled_demo.scdocx -Verify
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "cht_baffled_demo.scdocx")
PI = 3.14159265358979

L, H, D = 100.0, 50.0, 40.0
R_OUT, R_IN = 5.0, 4.0
PITCH = 12.0                      # 必须 > 2*R_OUT
Y0, Z0 = 6.0, 6.0
NY, NZ = 4, 3
NTUBE = NY * NZ
BAFFLE_T = 2.0
B1_X, B2_X = 30.0, 60.0

new_model()

# ---- ① 壳程流体 + 折流板槽 --------------------------------------------
shell = box(L, H, D, origin=(0.0, 0.0, 0.0), name="ShellFluid")
box(BAFFLE_T, 24.0, D, origin=(B1_X, 0.0, 0.0), cut=True)     # 下挡板槽（边缘 y=24，在空档里）
box(BAFFLE_T, 14.0, D, origin=(B2_X, 36.0, 0.0), cut=True)    # 上挡板槽（边缘 y=36，在空档里）

# ---- ② 折流板固体：塞满那两个槽 ---------------------------------------
baffles = [
    box(BAFFLE_T, 24.0, D, origin=(B1_X, 0.0, 0.0), name="BaffleLow", separate=True),
    box(BAFFLE_T, 14.0, D, origin=(B2_X, 36.0, 0.0), name="BaffleHigh", separate=True),
]

# ---- ③ 这一轮挖管孔：刀同时穿过壳体和两块折流板 -------------------------
# 折流板因此天然带管孔；刀两端出头，避免端面共面的静默失败。
for iz in range(NZ):
    for iy in range(NY):
        cylinder(R_OUT, L + 10.0,
                 origin=(-5.0, Y0 + iy * PITCH, Z0 + iz * PITCH),
                 axis="x", cut=True)

# ---- ④ 管壁 + 管程流体（必须最后建，否则会被上面的刀切到） -------------
tube_walls = []
tube_side = []
for iz in range(NZ):
    for iy in range(NY):
        y = Y0 + iy * PITCH
        z = Z0 + iz * PITCH
        tube_walls.append(tube(R_OUT, R_IN, L, origin=(0.0, y, z), axis="x",
                               name="TubeWall", separate=True))
        tube_side.append(cylinder(R_IN, L, origin=(0.0, y, z), axis="x",
                                  name="TubeSide", separate=True))

print("[b] bodies=%d（手算 1 壳 + 2 折流板 + %d 管壁 + %d 管程 = %d）"
      % (len(all_bodies()), NTUBE, NTUBE, 1 + 2 + 2 * NTUBE))

# ---- ⑤ 自动分层检查 ----------------------------------------------------
report = cht_check([
    ("shell_fluid", [shell]),
    ("baffle_solid", baffles),
    ("tube_wall", tube_walls),
    ("tube_fluid", tube_side),
])
print("[b] cht_check ok=%s" % str(report["ok"]))
for name in sorted(report["layer_stats"].keys()):
    st = report["layer_stats"][name]
    print("[b]   层 %-13s bodies=%2d faces=%3d area=%10.2f"
          % (name, st["bodies"], st["faces"], st["area"]))
print("[b]   相接的层对（自动判定，不用指定）:")
for (na, nb, cnt, area) in report["touching"]:
    rep = report["pairs"][(na, nb)]
    print("[b]     %-13s <-> %-13s 整面 %3d 对 / 分段 %3d 对  面积 %9.2f  coverage=%s"
          % (na, nb, rep["pairs"], rep["split_pairs"],
             rep["area_a"] + rep["split_area_a"],
             ("%.3f" % rep["coverage"]) if rep["pairs"] > 0 else "n/a"))
print("[b]   没接触的层对: %s" % str(report["not_touching"]))
print("[b]   孤立体: %s" % str(report["isolated_bodies"]))
print("[b]   接触了但覆盖不足的层对: %s" % str(report["low_coverage"]))
print("[b]   手算对照：壳程-管壁应为 %d 张管孔壁；管壁-管程两侧各 %.2f"
      % (NTUBE, NTUBE * 2 * PI * R_IN * L))

# ---- ⑥ 命名交界面与其余边界 -------------------------------------------
name_interfaces_multi(shell, tube_walls, "shell_tube", allow_split=True)
name_interfaces_multi(tube_walls, tube_side, "tube_fluid")
name_interfaces_multi(shell, baffles, "shell_baffle", allow_split=True)
name_interfaces_multi(baffles, tube_walls, "baffle_tube", allow_split=True)

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
print("[b] zones=%d" % len(g))
for nm, cnt in g:
    print("[b]   %-16s %2d face(s)" % (_ascii(nm), cnt))

finish(OUT, shell)
