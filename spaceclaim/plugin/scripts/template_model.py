# -*- coding: utf-8 -*-
# =====================================================================
#  template_model.py —— 建模脚本模板（也是可运行的示例）
#
#  用法：复制这个文件改成你的模型，然后
#      pwsh scripts\Invoke-Scdm.ps1 -Script 你的脚本.py -Out 你的产物.scdocx -Verify
#
# 可用的辅助函数（由 scdm_lib.py 注入，无需 import）：
#      new_model() / root_part() / box() / cylinder()
#      face_center() / face_area() / body_extent() / body_size()
#      faces_where() / faces_at() / faces_between()
#      name_faces() / name_boundaries() / name_faces_by_rules()
#      edge_summary() / edges_parallel() / edges_by_kind() / round_edges() / chamfer_edges()
#      save_model() / group_summary() / finish()
#
#  脚本里不用自己 new_model()：box()/cylinder() 会自动确保有文档
#  （没有就新建、已经有就复用）。想强制开新文档再显式调用 new_model()。
# =====================================================================

# ---------------- 参数（单位：mm） ----------------
W = 4.0        # 截面边长
L = 10.0       # 长度（流向，沿 Z 轴）
import os

SAVE_PATH = os.path.join(SCDM_SCRIPT_DIR, "channel_4x4x10.scdocx")

# ---------------- 1. 建几何 ----------------
body = box(W, W, L, origin=(0.0, 0.0, 0.0), name="Channel")

# 圆柱管（比如圆管流道）就把上面一行换成：
# body = cylinder(radius=2.0, height=100.0, origin=(0.0, 0.0, 0.0), axis="z", name="Pipe")

# 倒圆角 / 倒角（可选）。要点：倒完角以后旧的边/面对象就失效了，
# 而且必须"先倒角、后命名"，否则命名选择会对着一批已经不存在的面。
# round_edges(body, 1.0)                          # 所有边倒圆 r=1
# round_edges(edges_parallel(body, "z"), 1.0)     # 只倒四条长边
# chamfer_edges(edges_parallel(body, "z"), 0.5)   # 只倒四条长边的角

# ---------------- 2. 命名边界 ----------------
# 沿 Z 方向：z 最小的一端 = inlet，z 最大的一端 = outlet，其余侧面 = wall
name_boundaries(body, bottom="inlet", top="outlet", sides="wall", axis="z")

# 想按坐标精确控制，可以直接用底层函数：
# name_faces("inlet",  faces_at(body, axis="z", value=0.0))
# name_faces("outlet", faces_at(body, axis="z", value=L))
# name_faces("wall",   faces_where(body, lambda c, a, f: 0.0 < c[2] < L))

# 想四周分开命名 wall_1 ~ wall_4：name_boundaries(..., split_sides=True)

# ---------------- 3. 保存 + 自检 ----------------
# finish() 会：保存文件 -> 打印成功哨兵 <<<SCDM_OK>>> -> 打印尺寸和命名选择清单
finish(SAVE_PATH, body)
