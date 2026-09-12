# -*- coding: utf-8 -*-
# 自检用例 2：圆柱管 + 四周分开命名（走 cylinder / split_sides / finish）
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "selftest_cylinder.scdocx")

body = cylinder(radius=2.5, height=30.0, origin=(0.0, 0.0, 0.0), axis="z", name="Pipe")
name_boundaries(body, bottom="inlet", top="outlet", sides="wall",
                axis="z", split_sides=True)
finish(SAVE_PATH, body)
