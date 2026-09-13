# -*- coding: utf-8 -*-
# 第 19 个回归用例：曲面（零厚度面体）+ 加厚 + 装配（组件）
#
# 手算基线：
#   矩形曲面 20x10     -> 1 个体、1 个面、面积 200.00、包围盒 20x10x0
#   圆曲面 r=10        -> 1 个体、1 个面、面积 314.159 = pi*100
#   20x10 曲面 +Z 2mm  -> 1 个体 6 个面、包围盒 20x10x2、总面积 520
#                         = 2*200 + 2*(20*2) + 2*(10*2)
#   40x40 曲面 对称 4  -> 包围盒 Z 从 -4 到 +4（总厚 8），总面积
#                         = 2*1600 + 4*(40*8) = 4480
#   20³ 实体顶面 +Z 5  -> 包围盒 Z 从 0 到 25（面被"拉"出来了），仍 6 个面
#   装配：2 个体搬 1 个进组件 -> 根零件 Bodies=1、Components=1、组件里 1 个体；
#         再搬回根零件 -> Bodies=2、组件空
import os

OUT = os.path.join(SCDM_SCRIPT_DIR, "selftest_surface_asm.scdocx")
PI = 3.14159265358979


def dump(tag, body):
    print("[x] %-16s faces=%d size=%s ext_z=%s"
          % (tag, len(list(body.Faces)),
             str(tuple(round(v, 3) for v in body_size(body))),
             str(tuple(round(v, 3) for v in body_extent(body, "z")))))


def face_area_of(body):
    a = 0.0
    for f in body.Faces:
        a += face_area(f)
    return a


def body_named(nm):
    """按名字重新取一次体（跨过组件边界）——搬动/替换过的旧包装对象会失效。"""
    for b in all_bodies():
        if _ascii(b.Name) == nm:
            return b
    return None


def attempt2(fn):
    try:
        return fn()
    except:
        return "FAIL"


new_model()

# --- 1) 矩形曲面 + 加厚 -------------------------------------------------
s1 = rect_surface(20.0, 10.0, origin=(0, 0, 0), name="RectSurf")
dump("rect surface", s1)
print("[x] hand-calc: 1 面 200.00；实际 area=%.3f" % face_area_of(s1))
s1 = thicken(s1, 2.0, direction="z")
dump("thickened +Z 2", s1)
print("[x] hand-calc: 6 面、总面积 520.00；实际 %.3f" % face_area_of(s1))

# --- 2) 圆曲面 ----------------------------------------------------------
s2 = circle_surface(10.0, center=(60.0, 0.0, 0.0), normal="z", name="CircSurf")
dump("circle surface", s2)
print("[x] hand-calc: 面积 pi*100 = %.3f；实际 %.3f" % (PI * 100.0, face_area_of(s2)))

# --- 3) 对称加厚：总厚度是两倍 ------------------------------------------
s3 = rect_surface(40.0, 40.0, origin=(0.0, 60.0, 0.0), name="SymSurf")
s3 = thicken(s3, 4.0, direction="z", symmetric=True)
dump("symmetric 4", s3)
print("[x] hand-calc: 包围盒 Z 从 -4 到 +4、总面积 4480.00；实际 %.3f" % face_area_of(s3))

# --- 4) 实体面加厚 = 拉伸那张面 -----------------------------------------
sol = box(20.0, 20.0, 20.0, origin=(100.0, 0.0, 0.0), name="PullMe")
sol = thicken(faces_by_normal(sol, "z", 1)[0], 5.0, direction="z")
dump("solid pull +Z 5", sol)
print("[x] hand-calc: 包围盒 Z 0..25、仍 6 个面")

# --- 5) 曲面 + 命名（薄板作为 baffle 用） -------------------------------
baffle = rect_surface(30.0, 20.0, origin=(0.0, 150.0, 0.0), normal="y", name="Baffle")
baffle = thicken(baffle, 1.0, direction="y")
dump("baffle", baffle)
name_faces_by_rules(baffle, [
    ("baffle_a", {"normal": "y", "sign": -1}),
    ("baffle_b", {"normal": "y", "sign": +1}),
    ("baffle_edge", {"rest": True}),
])
print("[x] baffle 是一个 %.1f 厚的挡板：2 张大面 + 4 张侧面"
      % (body_extent(baffle, "y")[1] - body_extent(baffle, "y")[0]))

# --- 6) 装配：建组件、搬进去、列出来、再搬回根零件 ----------------------
c1 = box(10.0, 10.0, 10.0, origin=(300.0, 0.0, 0.0), name="CompA")
c2 = box(10.0, 10.0, 10.0, origin=(320.0, 0.0, 0.0), name="CompB")
print("[x] before: %s" % str(assembly_summary()))
asm = component("Assembly1")
print("[x] component name diagnostics: Name='%s' SetName->%s" % (
    _ascii(asm.Name) if asm.Name else "",
    str(attempt2(lambda: ComponentHelper.SetName(asm, "Assembly1")))))
try:
    print("[x]   after SetName, Name='%s' GetInstanceName='%s'"
          % (_ascii(asm.Name) if asm.Name else "", _ascii(asm.GetInstanceName())))
except Exception, e:
    print("[x]   GetInstanceName failed: %s" % str(e)[:60])
move_to_component(c1, asm)
print("[x] after moving CompA into a component: %s" % str(assembly_summary()))
print("[x] root Bodies.Count=%d（组件里的体不在这里面）" % GetRootPart().Bodies.Count)
in_comp = component_bodies(asm)
print("[x] component_bodies(asm) -> %d body/bodies: %s"
      % (len(in_comp), str([_ascii(b.Name) for b in in_comp])))
print("[x] all_bodies() -> %d: %s"
      % (len(all_bodies()), str([_ascii(b.Name) for b in all_bodies()])))
# 组件里的体照样能 measure、挑面
if in_comp:
    dump("in component", in_comp[0])

move_to_root(in_comp)
print("[x] after moving back to root: %s" % str(assembly_summary()))
print("[x] root Bodies.Count=%d" % GetRootPart().Bodies.Count)

# --- 7) 一网打尽：每个体单独成组件 --------------------------------------
live = [body_named("CompA"), body_named("CompB")]
live = [b for b in live if b is not None]
print("[x] re-acquired by name: %d body/bodies" % len(live))
comps = explode_to_components(live)
print("[x] explode_to_components -> %d components, root Bodies=%d"
      % (len(comps), GetRootPart().Bodies.Count))
print("[x] assembly: %s" % str(assembly_summary()))
flat = []
for c in comps:
    flat.extend(component_bodies(c))
move_to_root(flat)
print("[x] flattened back: root Bodies=%d, %s"
      % (GetRootPart().Bodies.Count, str(assembly_summary())))

# 搬空之后的组件必须删掉：留着它们 NamedSelection.GetGroups() 会抛中文空引用，
# 命名选择整个读不出来（verify 会报 FAILED）。
dropped = drop_empty_components()
print("[x] drop_empty_components -> 删掉 %d 个空组件，现在 %s"
      % (dropped, str(assembly_summary())))

# --- 8) 失败路径 --------------------------------------------------------
msg = "none"
try:
    thicken(s1, 0.0)
except Exception, e:
    msg = "%s | %s" % (type(e).__name__, str(e)[:50])
print("[x] thicken value=0 -> %s" % msg)

msg2 = "none"
try:
    move_to_component([], asm)
except Exception, e:
    msg2 = "%s | %s" % (type(e).__name__, str(e)[:50])
print("[x] move_to_component([]) -> %s" % msg2)

finish(OUT, baffle)
