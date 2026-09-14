# -*- coding: utf-8 -*-
# 示例：5x5 核反应堆燃料组件流动通道（棒束）
#
# 规格：
#   棒径 10mm、栅距 15mm（P/D = 1.5）、5x5 = 25 根、全长 3000mm（3 米）
#   通道截面按**对称面约定**取 5xPITCH = 75x75mm ——
#   四壁正好落在相邻棒之间的对称面上（壁到棒表面 = 栅距/2 - 半径 = 2.5mm），
#   这样四周的 symmetry 边界条件才在几何上说得通。
#
# 边界条件命名（Fluent 里的 zone 名）：
#   wall-heated  25 根棒的表面（发热壁）
#   sym          长方体四周那 4 张侧面（对称面）
#   inlet        底面（z 最小端）
#   outlet       顶面（z 最大端）
#
# 运行：
#   & <skill>\scripts\Invoke-Scdm.ps1 -Script fuel_assembly_5x5.py -Out fuel_assembly_5x5.scdocx -Verify
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "fuel_assembly_5x5.scdocx")
PI = 3.14159265358979

ROD_D = 10.0                  # 棒径
PITCH = 15.0                  # 栅距（必须 > 棒径，否则相邻棒外切，布尔会静默失败）
N = 5                         # 5x5
L = 3000.0                    # 长度 3 米
ROD_R = ROD_D / 2.0
BOX = N * PITCH               # 75：四壁落在对称面上
C0 = BOX / 2.0 - (N - 1) / 2.0 * PITCH      # 第一个棒心 = 7.5

new_model()

# ---------------- A) 反面教材：棒径 = 栅距 建不出来 ----------------
# 同一份脚本先按"棒径 10 + 栅距 10"试一次，把现象记录下来：
# 相邻棒**外切**时 25 次挖孔**一次都没生效**，25 把刀全部留成实体棒。
new_model()
lit = box(60.0, 60.0, 300.0, origin=(0.0, 0.0, 0.0), name="LiteralCase")
for iy in range(N):
    for ix in range(N):
        cylinder(5.0, 400.0, origin=(5.0 + ix * 10.0, 5.0 + iy * 10.0, -50.0),
                 axis="z", cut=True)
lit_faces = len(list(lit.Faces))
lit_bodies = len(all_bodies())
print("[fa] A) 棒径=栅距 时：bodies=%d（应为 1）、壳体 faces=%d（应为 %d）"
      % (lit_bodies, lit_faces, 6 + N * N))
print("[fa]    -> 壳体一次都没被切，%d 把刀全留下来成了实体棒；棒径必须小于栅距"
      % (lit_bodies - 1))

# ---------------- B) 正式模型：棒径 10 / 栅距 15 ----------------
new_model()
body = box(BOX, BOX, L, origin=(0.0, 0.0, 0.0), name="RodBundleChannel")
for iy in range(N):
    for ix in range(N):
        cylinder(ROD_R, L + 100.0,
                 origin=(C0 + ix * PITCH, C0 + iy * PITCH, -50.0),
                 axis="z", cut=True)

# ---- 边界条件命名 ------------------------------------------------------
name_faces_by_rules(body, [
    ("inlet",       {"kind": "plane", "normal": "z", "sign": -1}),   # 底面
    ("outlet",      {"kind": "plane", "normal": "z", "sign": +1}),   # 顶面
    ("wall-heated", {"kind": "cylinder"}),                           # 25 根棒表面
    ("sym",         {"rest": True}),                                 # 四周 4 张侧面
])

# ---- 实测值 + 手算对照 + 水力学参数 ------------------------------------
A = BOX * BOX - N * N * PI * ROD_R * ROD_R
P_wet = N * N * 2 * PI * ROD_R + 4 * BOX
Dh = 4.0 * A / P_wet

print("[fa] B) 正式模型：%dx%d 棒束，棒径 %.0f，栅距 %.0f，P/D=%.2f，长 %.0f mm"
      % (N, N, ROD_D, PITCH, PITCH / ROD_D, L))
print("[fa]    通道截面 %.0f x %.0f，棒心 %s"
      % (BOX, BOX, str([round(C0 + i * PITCH, 1) for i in range(N)])))
print("[fa]    体数=%d，面数=%d（手算 6 + %d = %d）"
      % (len(all_bodies()), len(list(body.Faces)), N * N, 6 + N * N))

g = 0
for grp in NamedSelection.GetGroups():
    area = 0.0
    for m in grp.Members:
        area += face_area(m)
    g += 1
    print("[fa]    %-12s %3d face(s)  %12.2f mm2  = %10.6f m2"
          % (_ascii(grp.Name), grp.Members.Count, area, area / 1.0e6))
print("[fa]    zones=%d" % g)

print("[fa] 水力学:")
print("[fa]   流通面积 A   = %.2f mm2 = %.4f cm2" % (A, A / 100.0))
print("[fa]   湿周    P   = %.2f mm" % P_wet)
print("[fa]   水力直径 Dh = %.4f mm" % Dh)
print("[fa] 手算对照:")
print("[fa]   inlet/outlet 各 %.2f = %.0f^2 - %d*pi*%.1f^2"
      % (A, BOX, N * N, ROD_R))
print("[fa]   wall-heated %.2f = %d*2*pi*%.1f*%.0f（%.4f m2）"
      % (N * N * 2 * PI * ROD_R * L, N * N, ROD_R, L,
         N * N * 2 * PI * ROD_R * L / 1.0e6))
print("[fa]   sym %.2f = 4*%.0f*%.0f（%.4f m2）"
      % (4 * BOX * L, BOX, L, 4 * BOX * L / 1.0e6))

finish(OUT, body)
