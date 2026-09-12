# -*- coding: utf-8 -*-
# =====================================================================
#  verify_model.py —— 独立校验：全新会话打开产物，回读几何与命名选择
#
#  由 Invoke-Scdm.ps1 -Verify 调用，运行器会注入 SCDM_VERIFY_TARGET。
#  目的是不信任建模脚本自己的输出：从磁盘上的文件重新读一遍。
#  测量统一复用 scdm_lib.py 里的 face_center / face_area / body_size。
# =====================================================================

import traceback

try:
    DocumentOpen.Execute(SCDM_VERIFY_TARGET)
    part = GetRootPart()

    print("[verify] file: " + str(SCDM_VERIFY_TARGET))
    print("[verify] bodies = %d" % part.Bodies.Count)

    for bi in range(part.Bodies.Count):
        body = part.Bodies[bi]
        _safe_print("[verify] body[%d] name=%s faces=%d"
                    % (bi, str(body.Name), len(list(body.Faces))))
        dx, dy, dz = body_size(body)
        print("[verify] body[%d] size = %.3f x %.3f x %.3f mm" % (bi, dx, dy, dz))

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

print("<<<SCDM_VERIFY_OK>>>")
