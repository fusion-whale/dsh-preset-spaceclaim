# -*- coding: utf-8 -*-
# 回归用例 3：4 mm x 4 mm 截面、10 mm 长的长方体流道
# 期望回读：4.000 x 4.000 x 10.000 mm
#   inlet  1 面 16.00 mm2 @ z=0
#   outlet 1 面 16.00 mm2 @ z=10
#   wall   4 面 各 40.00 mm2
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_channel_4x4x10.scdocx")

body = box(4.0, 4.0, 10.0, origin=(0.0, 0.0, 0.0), name="Channel")
name_boundaries(body, bottom="inlet", top="outlet", sides="wall", axis="z")
finish(SAVE_PATH, body)
