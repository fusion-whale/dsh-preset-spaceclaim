# -*- coding: utf-8 -*-
# =====================================================================
#  verify_model.py —— 独立校验：全新会话打开产物，回读几何与命名选择
#
#  由 Invoke-Scdm.ps1 -Verify 调用，运行器会注入 SCDM_VERIFY_TARGET。
#  目的是不信任建模脚本自己的输出：从磁盘上的文件重新读一遍。
#  测量统一复用 scdm_lib.py 里的 face_center / face_area / body_size。
# =====================================================================

import traceback

_verify_ok = True

try:
    DocumentOpen.Execute(SCDM_VERIFY_TARGET)
    part = GetRootPart()

    print("[verify] file: " + str(SCDM_VERIFY_TARGET))
    print("[verify] bodies = %d" % part.Bodies.Count)
    print("[verify] assembly = %s" % str(assembly_summary()))

    def dump(prefix, bi, body):
        _safe_print("[verify] %s name=%s faces=%d"
                    % (prefix, _ascii(body.Name), len(list(body.Faces))))
        dx, dy, dz = body_size(body)
        print("[verify] %s size = %.3f x %.3f x %.3f mm" % (prefix, dx, dy, dz))
        es = list(body.Edges)
        ek = {}
        for e in es:
            k = edge_kind(e)
            ek[k] = ek.get(k, 0) + 1
        print("[verify] %s edges = %d %s" % (prefix, len(es), str(sorted(ek.items()))))

    for bi in range(part.Bodies.Count):
        dump("body[%d]" % bi, bi, part.Bodies[bi])

    # 组件里的体（GetRootPart().Bodies 看不到它们）
    for ci in range(len(components(part))):
        bodies = component_bodies(components(part)[ci])
        print("[verify] comp[%d] bodies=%d" % (ci, len(bodies)))
        for bi in range(len(bodies)):
            dump("comp[%d].body[%d]" % (ci, bi), bi, bodies[bi])

    groups = group_summary()
    print("[verify] named selections = %d" % len(groups))
    for nm, cnt in groups:
        _safe_print("[verify]   %s -> %d face(s)" % (nm, cnt))

    for g in NamedSelection.GetGroups():
        for m in g.Members:
            c = face_center(m)
            _safe_print("[verify]   %-10s center=(%.3f, %.3f, %.3f) mm  area=%.2f mm2"
                        % (str(g.Name), c[0], c[1], c[2], face_area(m)))

except:
    print("!!! VERIFY EXCEPTION !!!")
    print(traceback.format_exc())
    _verify_ok = False

# 关键：**失败时不要打成功哨兵**。老版本无论如何都打 <<<SCDM_VERIFY_OK>>>，
# 于是 group_summary / NamedSelection.GetGroups() 抛异常（比如文档里留着空组件时抛
# 中文 SystemError）会被静默吞掉，校验看着是绿的、实际上根本没读到命名选择。
if _verify_ok:
    print("<<<SCDM_VERIFY_OK>>>")
else:
    print("<<<SCDM_VERIFY_FAILED>>>")
