# -*- coding: utf-8 -*-
# 示例：曲面加厚 + 装配组件（一块导流挡板 + 一组组装件）
#
# 演示两类东西：
#   1) 曲面：一张零厚度的矩形面 -> thicken 成 3mm 导流板 -> 命名正反两面
#   2) 装配：把两个体放进组件、列结构、再搬回根零件并删掉空组件
#
# 运行：
#   & <skill>\scripts\Invoke-Scdm.ps1 -Script surface_asm_demo.py -Out surface_asm_demo.scdocx -Verify
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "surface_asm_demo.scdocx")
PI = 3.14159265358979

new_model()

# ---- 1) 曲面 -> 加厚成导流挡板 -----------------------------------------
# 一张 40x30 的矩形面，法向朝 Y（也就是一块竖着的板），摆在 y=20 处
surf = rect_surface(40.0, 30.0, origin=(0.0, 20.0, 0.0), normal="y", name="BafflePlate")
print("[srf] surface: faces=%d size=%s area=%.2f"
      % (len(list(surf.Faces)),
         str(tuple(round(v, 3) for v in body_size(surf))),
         sum([face_area(f) for f in surf.Faces])))

# thicken 会**替换**掉原来的面体，必须接返回值
plate = thicken(surf, 3.0, direction="y")
print("[srf] plate:   faces=%d size=%s area=%.2f"
      % (len(list(plate.Faces)),
         str(tuple(round(v, 3) for v in body_size(plate))),
         sum([face_area(f) for f in plate.Faces])))

name_faces_by_rules(plate, [
    ("baffle_up",   {"normal": "y", "sign": +1}),
    ("baffle_down", {"normal": "y", "sign": -1}),
    ("baffle_edge", {"rest": True}),
])
print("[srf] hand-calc: 40x30 面加厚 3 -> 6 面、包围盒 40x3x30、"
      "总面积 2*1200 + 2*(40*3) + 2*(30*3) = %.2f" % (2 * 1200.0 + 2 * 120.0 + 2 * 90.0))

# ---- 2) 装配：两个体，一个进组件，再搬回来 -----------------------------
a = box(20.0, 20.0, 20.0, origin=(100.0, 0.0, 0.0), name="InletBox")
b = box(20.0, 20.0, 20.0, origin=(140.0, 0.0, 0.0), name="OutletBox")
print("[asm] start:    %s" % str(assembly_summary()))

asm = component("Shell")
move_to_component(a, asm)
print("[asm] InletBox 进组件后: %s" % str(assembly_summary()))
print("[asm]   根零件 Bodies=%d（组件里的体不在这里）" % GetRootPart().Bodies.Count)
print("[asm]   全部体（含组件）= %s" % str([_ascii(x.Name) for x in all_bodies()]))

inside = component_bodies(asm)
print("[asm]   组件里 %d 个体: %s" % (len(inside), str([_ascii(x.Name) for x in inside])))

move_to_root(inside)
dropped = drop_empty_components()
print("[asm] 搬回根零件 + 删掉 %d 个空组件: %s" % (dropped, str(assembly_summary())))
print("[asm]   根零件 Bodies=%d" % GetRootPart().Bodies.Count)

finish(OUT, plate)
