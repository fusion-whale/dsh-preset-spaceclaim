# -*- coding: utf-8 -*-
# 回归用例 6：面分割 + 分区命名（"一个壁面上分两段不同热流"）+ 体分割
#
# 期望回读（3 个体，4 个命名选择）：
#   Channel 100x40x40（底面在 x=50 处被切开，7 个面）
#     inlet        1 面 1600.00 mm2 @ (0,20,20)
#     outlet       1 面 1600.00 mm2 @ (100,20,20)
#     heated_wall  1 面 2000.00 mm2 @ (25,20,0)     ← 底面 x<50 的那半张
#     wall         4 面：2000.00 @ (75,20,0)（另半张）+ 4000.00 @ (50,0,20)/(50,40,20)/(50,20,40)
#   SplitMe 被 z=10 的平面切成两个 20x20x10 的体
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_split.scdocx")

body = box(100.0, 40.0, 40.0, origin=(0.0, 0.0, 0.0), name="Channel")
print("[before] faces=%d" % len(list(body.Faces)))

bottom = faces_by_normal(body, "z", -1)[0]
print("[split] bottom area before = %.2f mm2" % face_area(bottom))
split_face_by_line(bottom, axis="x", value=50.0)
print("[after ] faces=%d" % len(list(body.Faces)))
for f in faces_by_normal(body, "z", -1):
    c = face_center(f)
    print("[after ] bottom piece area=%.2f center=(%.2f,%.2f,%.2f)"
          % (face_area(f), c[0], c[1], c[2]))

counts = name_faces_by_rules(body, [
    ("inlet",       {"normal": "x", "sign": -1}),
    ("outlet",      {"normal": "x", "sign": +1}),
    ("heated_wall", {"normal": "z", "sign": -1,
                     "in_box": (None, 50.0, None, None, None, None)}),
    ("wall",        {"rest": True}),
])
for k in sorted(counts):
    print("[rule] %-12s %d face(s)" % (k, counts[k]))

# ---- 体分割 ----
extra = box(20.0, 20.0, 20.0, origin=(200.0, 0.0, 0.0), name="SplitMe")
print("[body] bodies before split = %d" % GetRootPart().Bodies.Count)
split_body_by_plane(extra, axis="z", value=10.0)
print("[body] bodies after  split = %d" % GetRootPart().Bodies.Count)

finish(SAVE_PATH)
