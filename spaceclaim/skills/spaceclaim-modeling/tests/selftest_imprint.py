# -*- coding: utf-8 -*-
# 回归用例 13：用另一个体把面切开（墙面上的圆形补丁）+ loops/面积规则命名
#
# 期望回读（2 个体，3 个命名选择）：
#   Plate 40x40x10，底面被穿过它的 r=5 圆柱"盖章"切成两张面：
#         patch  78.54 mm2 @ (20,20,0)  loops=1   ← 圆补丁
#         rest 1521.46 mm2 @ (20,20,0)  loops=2   ← 带内环的其余部分
#   注意两张面**面心相同**，只能靠 loops 或面积区分
#   Cutter 圆柱 r=5、长 40，独立体（separate=True）
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_imprint.scdocx")

plate = box(40.0, 40.0, 10.0, origin=(0.0, 0.0, 0.0), name="Plate")
cutter = cylinder(5.0, 40.0, origin=(20.0, 20.0, -10.0), axis="z",
                  name="Cutter", separate=True)

bottom = faces_by_normal(plate, "z", -1)[0]
print("[before] bottom area = %.2f  faces=%d" % (face_area(bottom), len(list(plate.Faces))))

cf = split_face_by_body(bottom, cutter)
print("[split] cutter face used: kind=%s area=%.2f" % (face_kind(cf), face_area(cf)))
print("[after ] plate faces = %d" % len(list(plate.Faces)))

# 两张面面心相同，用 loops / 面积区分
cnt = name_faces_by_rules(plate, [
    ("patch", {"normal": "z", "sign": -1, "loops": 1}),
    ("rest",  {"normal": "z", "sign": -1, "loops": 2}),
])
for k in sorted(cnt):
    print("[rule] %-6s %d face(s)" % (k, cnt[k]))

for f in faces_by_normal(plate, "z", -1):
    c = face_center(f)
    print("[face] area=%9.2f center=(%.2f,%.2f,%.2f) loops=%d"
          % (face_area(f), c[0], c[1], c[2], len(list(f.Shape.Loops))))

finish(SAVE_PATH)
