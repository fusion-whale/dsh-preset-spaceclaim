# -*- coding: utf-8 -*-
# 自检用例 1：长方体 + 命名边界（走 box / name_boundaries / finish）
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_box.scdocx")

body = box(6.0, 5.0, 20.0, origin=(0.0, 0.0, 0.0), name="Channel")
name_boundaries(body, bottom="inlet", top="outlet", sides="wall", axis="z")
finish(SAVE_PATH, body)
