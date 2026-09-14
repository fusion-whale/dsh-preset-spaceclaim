# -*- coding: utf-8 -*-
# =====================================================================
#  scdm_lib.py —— SpaceClaim 建模辅助库
#
#  这个文件不会单独运行：Invoke-Scdm.ps1 会把它的内容“注入”到你的建模脚本
#  最前面，所以建模脚本里可以直接调用下面的函数，不需要 import。
#
#  单位约定：对外接口一律用毫米(mm)，内部自动换算成 SpaceClaim 的米。
#
#  在 SpaceClaim 脚本宿主里，MM / Point / BlockBody / NamedSelection /
#  Selection / DocumentSave 等名字已经由宿主预加载，无需 import。
# =====================================================================

# ---------------------------------------------------------------------------
# 文档
# ---------------------------------------------------------------------------

def new_model():
    """新建一个空文档，返回根零件。想在会话里强制开新文档时调用。"""
    DocumentHelper.CreateNewDocument()
    return GetRootPart()


def root_part():
    """当前文档的根零件。"""
    return GetRootPart()


def ensure_document():
    """确保有可用的文档：已经有就复用，没有就新建。

    box()/cylinder() 会先调用它，所以脚本里不写 new_model() 也能跑起来。
    """
    try:
        part = GetRootPart()
        if part is not None:
            return part
    except:
        pass
    return new_model()


# ---------------------------------------------------------------------------
# 建几何体（单位：mm）
# ---------------------------------------------------------------------------

def _extrude_type(cut, separate=False):
    """把 cut/separate 两个开关翻译成 ExtrudeType，都不用时返回 None。

    cut=True      -> ExtrudeType.Cut             布尔减（挖掉这块）
    separate=True -> ExtrudeType.ForceIndependent 即使与已有体重叠也单独成一个体

    实测行为：默认（不传 ExtrudeType）时，新建的体如果与已有体重叠，会被**合并**
    （并集）进已有体——所以"在一个实体内部再建一个流体域"必须用 separate=True。

    注意：不能用“显式传 None 占位”的写法——把 None 塞进带默认值的参数位，
    实测会让 SpaceClaim 脚本宿主直接中止整个脚本（连 traceback 都没有）。
    所以这里返回 None 时，调用方要换成一个少传参数的重载。
    """
    if cut and separate:
        raise ValueError("cut and separate cannot both be True")
    if cut:
        return ExtrudeType.Cut
    if separate:
        return ExtrudeType.ForceIndependent
    return None


def _body_signature(body):
    """体的廉价指纹（面数 + 总面积），用来判断某个体是不是被并集改过了。"""
    n = 0
    area = 0.0
    try:
        for f in body.Faces:
            n += 1
            try:
                area += float(_shape_of(f).Area)
            except:
                pass
    except:
        pass
    return (n, round(area, 9))


def _snapshot_bodies():
    """建体之前先给文档里现有的每个体拍一张指纹快照。"""
    snap = []
    for b in GetRootPart().Bodies:
        snap.append((_body_key(b), b, _body_signature(b)))
    return snap


def _created_body(res=None, before=None):
    """找出"这次建体命令"真正新建（或被并进去）的那个体。

    按可靠性分三层：
      1. **新出现的体**（key 不在 before 快照里）—— 不与已有体重叠时的正常情况；
      2. 结果对象自带的 `CreatedBody` / `CreatedBodies[0]`；
      3. **唯一一个指纹变了的旧体** —— 新体和已有体重叠被并进去时没有新体，
         被改动的那个就是目标体。

    三条都不成立就返回 None。**绝不退回"取根零件里最后一个体"**：
    实测那会把文档里另一个毫不相干的体改名——弯头用例里 `UTurn` 被改成了默认名
    "Body"，原因就是并集时 `CreatedBodies` 是空的、而它恰好排在最后。

    调用方（box / cylinder / sphere / stepped_cone）都要在命令前 `_snapshot_bodies()`
    并把快照传进来，否则第 1、3 层用不上。
    """
    if before is not None:
        keys = {}
        for item in before:
            keys[item[0]] = 1
        for b in GetRootPart().Bodies:
            if _body_key(b) not in keys:
                return b
    if res is not None:
        try:
            b = res.CreatedBody
            if b is not None:
                return b
        except:
            pass
        try:
            bodies = res.CreatedBodies
            if bodies is not None and bodies.Count > 0:
                return bodies[0]
        except:
            pass
    if before is not None:
        changed = []
        for item in before:
            try:
                if _body_signature(item[1]) != item[2]:
                    changed.append(item[1])
            except:
                pass
        if len(changed) == 1:
            return changed[0]
    return None


def box(width, depth=None, height=None, origin=(0.0, 0.0, 0.0), name="Body",
        cut=False, separate=False):
    """长方体。

    width  -> X 方向尺寸
    depth  -> Y 方向尺寸（省略则与 width 相同）
    height -> Z 方向尺寸（省略则与 width 相同）
    origin -> 起始角点坐标 (x, y, z)，单位 mm
    cut    -> True 时做布尔减（从已有实体上挖掉这块长方体）
    separate -> True 时即使与已有体重叠也保持独立（默认重叠会被合并）
    """
    if depth is None:
        depth = width
    if height is None:
        height = width
    ensure_document()
    x0, y0, z0 = origin
    p1 = Point.Create(MM(x0), MM(y0), MM(z0))
    p2 = Point.Create(MM(x0 + width), MM(y0 + depth), MM(z0 + height))
    et = _extrude_type(cut, separate)
    snap = _snapshot_bodies()
    res = BlockBody.Create(p1, p2) if et is None else BlockBody.Create(p1, p2, et)
    body = _created_body(res, snap)
    if name and not cut and body is not None:
        try:
            body.Name = name
        except:
            pass
    return body


def cylinder(radius, height, origin=(0.0, 0.0, 0.0), axis="z", name="Body",
             cut=False, separate=False):
    """圆柱：底面圆心在 origin，轴向沿 axis（"x"/"y"/"z"），高 height。单位 mm。

    CylinderBody.Create 的三个点（实测反推 + 官方 Example9 印证）：
        定义圆圆心 / 另一底面圆心（决定轴向与长度） / 另一底面圆周上一点（决定半径）
    注意不是“圆周上一点定半径、另一点定端点”，弄反会得到一个轴向和半径都错的圆柱。

    cut=True 时做布尔减：这个圆柱会从已有实体上被挖掉（实测可挖出通孔，
    孔壁会成为一个独立的圆柱面，端面上出现第 2 个 loop）。
    """
    x0, y0, z0 = origin
    a = axis.lower()
    ensure_document()
    c = Point.Create(MM(x0), MM(y0), MM(z0))
    if a == "x":
        start = Point.Create(MM(x0 + height), MM(y0), MM(z0))
        end = Point.Create(MM(x0 + height), MM(y0 + radius), MM(z0))
    elif a == "y":
        start = Point.Create(MM(x0), MM(y0 + height), MM(z0))
        end = Point.Create(MM(x0), MM(y0 + height), MM(z0 + radius))
    else:
        start = Point.Create(MM(x0), MM(y0), MM(z0 + height))
        end = Point.Create(MM(x0 + radius), MM(y0), MM(z0 + height))
    et = _extrude_type(cut, separate)
    snap = _snapshot_bodies()
    res = CylinderBody.Create(c, start, end) if et is None else CylinderBody.Create(c, start, end, et)
    # 注意：CylinderBodyResult 只有 CreatedBodies，没有 CreatedBody
    #（BlockBodyResult / SphereResult 才两个都有），取错会得到
    # "Script failed: 'CylinderBodyResult' object has no attribute 'CreatedBody'"
    body = _created_body(res, snap)
    if name and not cut and body is not None:
        try:
            body.Name = name
        except:
            pass
    return body


def sphere(radius, center=(0.0, 0.0, 0.0), name="Body", cut=False):
    """球体。center 是球心，单位 mm。

    cut=True 时用这个球做布尔减——可以在一块实体里挖出球腔/球缺
    （实测：20x20x20 的方块挖掉 r=6 的球后是 1 个体、7 个面，
    球面面积 452.39 mm² = 4*pi*6^2）。

    实测：r=5、球心 (10,10,10) → 1 个体 1 个面（kind=sphere）、
    面积 314.16 mm²、包围盒 10 x 10 x 10。
    """
    ensure_document()
    c = Point.Create(MM(center[0]), MM(center[1]), MM(center[2]))
    # 实测 ExtrudeType.Cut 对球无效（球会变成独立体、目标体没被挖），改用 ForceCut
    et = ExtrudeType.ForceCut if cut else None
    snap = _snapshot_bodies()
    res = SphereBody.Create(c, MM(radius)) if et is None else SphereBody.Create(c, MM(radius), et)
    body = _created_body(res, snap)
    if name and not cut and body is not None:
        try:
            body.Name = name
        except:
            pass
    return body


def move(body, dx=0.0, dy=0.0, dz=0.0):
    """把实体整体平移 (dx, dy, dz)，单位 mm。返回同一个体对象。

    实测：Move.Translate(Selection.Create(body), Vector.Create(...), MoveOptions())
    可用（Vector.Create 接受内部单位，所以外面套 MM()）。
    """
    if body is None:
        raise ValueError("move(): body is None")
    if dx == 0.0 and dy == 0.0 and dz == 0.0:
        return body
    vec = Vector.Create(MM(dx), MM(dy), MM(dz))
    Move.Translate(Selection.Create(body), vec, MoveOptions())
    return body


def rotate(body, angle_deg, axis="z", center=(0.0, 0.0, 0.0)):
    """绕"过 center、方向为 axis"的直线旋转实体。对外角度单位是**度**，右手定则。

    实测要点：底层 `Move.Rotate` 的角度参数是**弧度**——传 45（当成度）会得到
    58.3 度的结果（45 rad 对 2*pi 取模），所以这里内部做换算。
    实测：40x10x10 的长条绕 Z 轴转 45 度 → 包围盒 35.355 x 35.355 x 10.000。
    """
    import math
    d = _dir_vector(axis)
    line = Line.Create(Point.Create(MM(center[0]), MM(center[1]), MM(center[2])),
                       Direction.Create(d[0], d[1], d[2]))
    Move.Rotate(Selection.Create(body), line, math.radians(angle_deg), MoveOptions())
    return body


def tube(outer_radius, inner_radius, height, origin=(0.0, 0.0, 0.0), axis="z",
         name="Pipe", overshoot=1.0, separate=False):
    """空心圆管：外圆柱 + 内圆柱布尔减。

    overshoot 是内圆柱两端各多伸出的长度(mm)，保证把管壁切穿干净。
    separate=True 时外圆柱用 `ForceIndependent` —— **共轭传热里必须这样**：
    管壁要插在一个尺寸完全相同的管孔里，默认的并集会把管子吃进孔壁（实测：
    12 根管子建完只剩 1 个体、管孔被填掉），设了 separate 之后 12 根各自独立。
    返回外圆柱那个体（布尔减之后它就是管体本身）。
    """
    if inner_radius >= outer_radius:
        raise ValueError("tube(): inner_radius must be smaller than outer_radius")
    a = axis.lower()
    outer = cylinder(outer_radius, height, origin=origin, axis=a, name=name,
                     separate=separate)
    x0, y0, z0 = origin
    if a == "x":
        cut_origin = (x0 - overshoot, y0, z0)
    elif a == "y":
        cut_origin = (x0, y0 - overshoot, z0)
    else:
        cut_origin = (x0, y0, z0 - overshoot)
    key = _body_key(outer)
    cylinder(inner_radius, height + 2.0 * overshoot, origin=cut_origin, axis=a, cut=True)
    # 切完内孔之后，之前拿到的包装对象**可能已经失效**（实测在 CHT 场景里就是这样，
    # 后面拿它取 Faces 会 "The object is deleted."），所以按 Moniker 重新取一次。
    for b in GetRootPart().Bodies:
        if _body_key(b) == key:
            return b
    return outer


def stepped_cone(radius1, radius2, height, segments=8, origin=(0.0, 0.0, 0.0),
                 axis="z", name="Cone"):
    """阶梯锥：用 segments 段同轴圆柱近似一个圆锥台。

    半径从 radius1（起点端）线性变到 radius2（终点端），单位 mm。
    实测可用：5 段时合并成 1 个体、11 个面（5 个柱面 + 2 个端面 + 4 个内部台阶环面）。
    真锥台（放样）在脚本 API 里做不出来，见 references/api-notes.md。
    """
    segs = int(segments)
    if segs < 1:
        raise ValueError("stepped_cone(): segments must be at least 1")
    a = axis.lower()
    x0, y0, z0 = origin
    step = float(height) / segs

    def base_pt(t):
        return Point.Create(MM(x0 + (t if a == "x" else 0.0)),
                            MM(y0 + (t if a == "y" else 0.0)),
                            MM(z0 + (t if a == "z" else 0.0)))

    def rim_pt(t, r):
        return Point.Create(MM(x0 + (t if a == "x" else 0.0) + (r if a == "y" else 0.0)),
                            MM(y0 + (t if a == "y" else 0.0) + (r if a == "z" else 0.0)),
                            MM(z0 + (t if a == "z" else 0.0) + (r if a == "x" else 0.0)))

    ensure_document()
    body = None
    snap = _snapshot_bodies()
    for i in range(segs):
        rr = radius1 + (radius2 - radius1) * (i / float(segs))
        p1 = base_pt(i * step)
        p2 = base_pt((i + 1) * step)
        p3 = rim_pt((i + 1) * step, rr)
        if i == 0:
            body = _created_body(CylinderBody.Create(p1, p2, p3), snap)
        else:
            # 关键：后续段必须用 ExtrudeType.Add 才会和上一段合并成一个体
            CylinderBody.Create(p1, p2, p3, ExtrudeType.Add)
    if name and body is not None:
        try:
            body.Name = name
        except:
            pass
    return body


def _body_key(body):
    """体的稳定标识（Moniker 字符串；重复枚举可能给出不同的包装对象）。"""
    try:
        return str(body.Moniker)
    except:
        return str(id(body))


def _sketch_region_body(before_keys):
    """找出 Solid 模式之后**新出现**的那个体（即闭合草图轮廓变成的面）。

    不能用"根零件里最后一个体"：文档里已经有别的体时会抓错对象——
    实测这样第二个草图会让 SpaceClaim 直接抛空引用。
    """
    for b in GetRootPart().Bodies:
        if _body_key(b) not in before_keys:
            return b
    return None


def _extrude_face(face, height, cut=False):
    """把**一张面**拉伸成体，返回结果体。

    用"拉伸前后体集合之差"判定，不依赖 ExtrudeFacesResult（它给回的成员在多面
    表面体的情况下不可靠，实测会拿到 DesignFace）。没有新体出现时，说明这张面
    所在的体自己变成了实体，于是用 face.Parent 反查。
    """
    if face is None:
        raise RuntimeError("_extrude_face: no face to extrude")
    before = {}
    for b in GetRootPart().Bodies:
        before[_body_key(b)] = 1
    opts = ExtrudeFaceOptions()
    opts.ExtrudeType = ExtrudeType.Cut if cut else ExtrudeType.Add
    ExtrudeFaces.Execute(Selection.Create(face), MM(height), opts)
    new_body = _sketch_region_body(before)
    if new_body is not None:
        return new_body
    try:
        parent = face.Parent
        if parent is not None:
            return parent
    except:
        pass
    raise RuntimeError("_extrude_face: could not determine the extruded body")


def _extrude_sketch_body(sketch_body, height, cut=False):
    """把草图轮廓那张面拉伸成体，返回结果**体**。

    不要用 ExtrudeFacesResult.CreatedBodies 取结果：草图体上有多张面时，
    它可能给回一个 DesignFace（实测报 `'DesignFace' object has no attribute 'Faces'`）。
    这里用"拉伸前后体集合之差"来判定：

      * 出现新体  -> 多轮廓情形（草图体留着剩下的面，新体是拉出来的棱柱）
      * 没有新体  -> 单轮廓情形（草图体自己变成了实体）
    """
    if sketch_body is None:
        raise RuntimeError("_extrude_sketch_body: no sketch region body")
    faces = list(sketch_body.Faces)
    if not faces:
        raise RuntimeError("_extrude_sketch_body: the sketch body has no face")
    before = {}
    for b in GetRootPart().Bodies:
        before[_body_key(b)] = 1
    opts = ExtrudeFaceOptions()
    opts.ExtrudeType = ExtrudeType.Cut if cut else ExtrudeType.Add
    ExtrudeFaces.Execute(Selection.Create(faces[0]), MM(height), opts)
    new_body = _sketch_region_body(before)
    if new_body is not None:
        return new_body
    return sketch_body


def _anchor_prism(body, axis, origin):
    """把棱柱摆正：沿 axis 的底面落在 origin 的该轴坐标上，另两向按**中心**对齐 origin。

    与 cylinder() 的约定一致（origin 是底面中心），而不是 box() 的"最小角点"。
    """
    i = _axis_index(axis)
    ext = [body_extent(body, k) for k in range(3)]
    d = [0.0, 0.0, 0.0]
    d[i] = origin[i] - ext[i][0]
    for k in range(3):
        if k != i:
            d[k] = origin[k] - (ext[k][0] + ext[k][1]) / 2.0
    return move(body, d[0], d[1], d[2])


def polygon_prism(sides, radius, height, origin=(0.0, 0.0, 0.0), axis="z",
                  name="Body", rotation_deg=0.0):
    """正多边形棱柱（单个）。是 polygon_prisms 的包装。

    注意：**必须在文档还没有任何实体时调用**（见 profile_prisms 的说明）。
    """
    return polygon_prisms([{
        "sides": sides, "radius": radius, "height": height,
        "origin": origin, "axis": axis, "name": name,
        "rotation_deg": rotation_deg,
    }])[0]


def polygon_prisms(profiles):
    """一次建多个正多边形棱柱（polygon_prism 的批量形式）。"""
    out = []
    for p in profiles:
        q = dict(p)
        q["kind"] = "polygon"
        out.append(q)
    return profile_prisms(out)


def profile_prisms(profiles):
    """一次建多个「任意轮廓」棱柱——这是非圆形截面的通用入口。

    profiles 里每个元素是 dict，公共键：
        kind         "polygon" / "polyline" / "ellipse"（默认 "polygon"）
        height       长度 mm
        axis         "x"/"y"/"z"（棱柱轴向）
        origin       摆正后**轮廓包围盒中心**所在的坐标（沿轴方向是底面）
        name         体名
        rotation_deg 绕自身轴额外旋转（可选）

    各 kind 的专属键：
        polygon   sides（边数）, radius（外接圆半径）
        polyline  points=[(u,v), ...]  轮廓顶点，自动闭合（u 沿世界 X、v 沿世界 Z）
        ellipse   radii=(a,b)          两个半轴

    轮廓坐标是**局部**的，批量接口会自动把各草图沿 X 拉开间距避免重叠。

    为什么必须批量（这几条都是实测）：
      * 文档里一旦有实体，再新建草图会让 SpaceClaim 抛空引用、脚本直接中止，
        所以所有草图必须在任何实体之前一次画完；
      * 互不重叠的草图在 Solid 模式下各成一张面（一个表面体带 N 张面），重叠的会合并；
      * 逐张拉伸可行，草图体上剩下的面依然可用。

    实测数值：梯形折线 (0,0)(20,0)(15,10)(5,10) → 端面 150.00 mm²、6 个面；
    椭圆 (10,5) → 端面 157.08 mm²、3 个面、侧面 242.21 mm²。
    """
    ensure_document()
    existing = GetRootPart().Bodies.Count
    if existing:
        raise RuntimeError(
            "profile_prisms: the document already has %d body/bodies. Sketch-based profiles "
            "must be created before any solid exists (SpaceClaim 2022 R1 crashes on a new "
            "sketch once a solid is present). Build the profile ducts first, then add "
            "box/cylinder/tube bodies." % existing)
    if not profiles:
        return []

    # 1) 算间距：按每个轮廓的半宽留 1.5 倍余量，保证互不重叠
    half = []
    for p in profiles:
        k = str(p.get("kind", "polygon")).lower()
        if k == "polyline":
            pts = p.get("points") or [(0.0, 0.0)]
            w = max(max(abs(u) for u, v in pts), max(abs(v) for u, v in pts))
        elif k == "ellipse":
            a, b = p.get("radii", (1.0, 1.0))
            w = max(abs(a), abs(b))
        else:
            w = abs(float(p.get("radius", 1.0)))
        half.append(max(w, 1.0))
    widest = max(half)
    spacing = widest * 3.0

    # 2) 画草图（全部在任何实体之前）
    offsets = []
    for i in range(len(profiles)):
        p = profiles[i]
        k = str(p.get("kind", "polygon")).lower()
        off = i * spacing
        offsets.append(off)
        if k == "polyline":
            pts = p.get("points") or []
            if len(pts) < 3:
                raise ValueError("profile_prisms: polyline needs at least 3 points")
            lst = List[Point]()
            for (u, v) in pts:
                lst.Add(Point.Create(MM(off + u), MM(0), MM(v)))
            first = pts[0]
            lst.Add(Point.Create(MM(off + first[0]), MM(0), MM(first[1])))
            SketchLine.CreatePolyLine(lst, False, False)
        elif k == "ellipse":
            a, b = p.get("radii", (1.0, 1.0))
            SketchEllipse.Create(Point.Create(MM(off), MM(0), MM(0)),
                                 Direction.Create(1, 0, 0), Direction.Create(0, 0, 1),
                                 MM(a), MM(b))
        else:
            n = int(p.get("sides", 6))
            r = float(p.get("radius", 1.0))
            if n < 3:
                raise ValueError("profile_prisms: polygon sides must be at least 3")
            SketchPolygon.Create(Point.Create(MM(off), MM(0), MM(0)),
                                 Point.Create(MM(off + r), MM(0), MM(0)),
                                 False, n)

    ViewHelper.SetViewMode(InteractionMode.Solid, None)
    sketch_body = _sketch_region_body({})
    if sketch_body is None:
        raise RuntimeError("profile_prisms: the sketches did not produce a region body")

    # 3) 逐个拉伸 + 摆正（按"离哪个偏移最近"把面分给对应轮廓）
    out = []
    for i in range(len(profiles)):
        p = profiles[i]
        target = None
        best = None
        for f in list(sketch_body.Faces):
            d = abs(face_center(f)[0] - offsets[i])
            if best is None or d < best:
                best = d
                target = f
        if target is None:
            raise RuntimeError("profile_prisms: no sketch face left for profile %d" % i)
        body = _extrude_face(target, float(p.get("height", 10.0)))
        if body is None:
            raise RuntimeError("profile_prisms: extrude produced no body for profile %d" % i)
        a = str(p.get("axis", "z")).lower()
        if a == "z":
            rotate(body, 90.0, axis="x")
        elif a == "x":
            rotate(body, -90.0, axis="z")
        elif a != "y":
            raise ValueError("profile_prisms: axis must be 'x'/'y'/'z'")
        rd = float(p.get("rotation_deg", 0.0))
        if rd:
            rotate(body, rd, axis=a)
        _anchor_prism(body, a, tuple(p.get("origin", (0.0, 0.0, 0.0))))
        nm = p.get("name")
        if nm:
            try:
                body.Name = nm
            except:
                pass
        out.append(body)
    return out


def revolve_profile(points, angle_deg=360.0, origin=(0.0, 0.0, 0.0), name="Body"):
    """单个回转体（revolve_profiles 的包装）。轮廓必须整体在 u >= 0 一侧。"""
    return revolve_profiles([{
        "points": points, "angle_deg": angle_deg, "origin": origin, "name": name,
    }])[0]


def revolve_profiles(profiles):
    """一次建多个回转体（绕各自的轴旋转）。

    profiles 里每个元素是 dict：
        kind        "polyline"（默认）/ "circle"
        points      kind="polyline" 时用：[(u, v), ...] 闭合轮廓；
                    u 是**到旋转轴的距离（>= 0）**，v 是轴向坐标
        center      kind="circle" 时用：(u, v) 圆心；u 必须 > radius
        radius      kind="circle" 时用：圆半径
        angle_deg   旋转角度（度），默认 360（整圈）。底层用弧度，内部换算
        axis        "x"/"y"/"z"（回转体最终的轴向；默认 "z"）
        origin      摆正后的位置（沿轴向对齐 bbox 最小端，另两轴按中心对齐）
        name        体名

    为什么要批量：**文档里一旦有实体，再新建草图就会让 SpaceClaim 崩**（实测空引用），
    所以所有轮廓必须在任何实体之前一次画完。第 i 个轮廓沿 X 偏移 i*spacing，
    因此绕它自己那条中轴旋转，而不是绕世界 Z 轴。

    实测：矩形轮廓 (0,0)(5,0)(5,10)(0,10) 整圈 → 圆柱，3 个面，
    端面 78.54 mm² = pi*5^2、柱面 314.16 mm² = 2*pi*5*10。
    实测：圆轮廓 center=(20,0)、radius=3 整圈 → **真圆环**（1 个 torus 面，
    2368.705 mm² = 4*pi^2*R*r，包围盒 46x46x6）；只转 90° → 真圆截面弯头，
    3 个面（torus 592.176 + 两个整圆端面 28.274，包围盒 23x23x6）。

    注意角度单位：底层 `RevolveFaces.Execute(面, Line, 角度, 选项)` 用的是**弧度**
    （传 2*pi 得到整圈；传 360 也得到整圈，因为 360 rad 已超过一圈）。
    """
    import math
    ensure_document()
    existing = GetRootPart().Bodies.Count
    if existing:
        raise RuntimeError(
            "revolve_profiles: the document already has %d body/bodies. Sketch-based profiles "
            "must be created before any solid exists (SpaceClaim 2022 R1 crashes on a new "
            "sketch once a solid is present). Build the revolved bodies first, then add "
            "box/cylinder/tube bodies." % existing)
    if not profiles:
        return []

    norm = []
    for p in profiles:
        kind = str(p.get("kind", "polyline")).lower()
        if kind == "circle":
            c = p.get("center")
            if c is None:
                raise ValueError("revolve_profiles: a circle profile needs 'center' = (u, v)")
            r = float(p.get("radius", 0.0))
            cu = float(c[0])
            cv = float(c[1]) if len(c) > 1 else 0.0
            if r <= 0.0:
                raise ValueError("revolve_profiles: circle radius must be > 0")
            if cu <= r:
                raise ValueError("revolve_profiles: a circle profile must stay clear of the "
                                 "axis (center u must be greater than radius), otherwise the "
                                 "revolve axis cuts through the profile")
            norm.append({"kind": "circle", "cu": cu, "cv": cv, "r": r, "u": cu + r})
            continue
        pts = list(p.get("points") or [])
        if len(pts) < 3:
            raise ValueError("revolve_profiles: every profile needs at least 3 points")
        for (u, v) in pts:
            if u < 0:
                raise ValueError("revolve_profiles: every u (distance from the axis) must be >= 0")
        norm.append({"kind": "polyline", "points": pts,
                     "u": max(u for (u, v) in pts)})

    widest = 1.0
    for item in norm:
        if item["u"] > widest:
            widest = item["u"]
    spacing = widest * 3.0

    # 1) 先把所有轮廓画完（互不重叠）
    offsets = []
    for i in range(len(norm)):
        off = i * spacing
        offsets.append(off)
        item = norm[i]
        if item["kind"] == "circle":
            # 实测：Point2D 的第一个分量落在全局 Z 上、第二个落在全局 X 上
            SketchCircle.Create(Point2D.Create(MM(item["cv"]), MM(off + item["cu"])),
                                MM(item["r"]))
            continue
        lst = List[Point]()
        for (u, v) in item["points"]:
            lst.Add(Point.Create(MM(off + u), MM(0), MM(v)))
        first = item["points"][0]
        lst.Add(Point.Create(MM(off + first[0]), MM(0), MM(first[1])))
        SketchLine.CreatePolyLine(lst, False, False)

    ViewHelper.SetViewMode(InteractionMode.Solid, None)
    sketch_body = _sketch_region_body({})
    if sketch_body is None:
        raise RuntimeError("revolve_profiles: the profiles did not produce a region body")

    # 2) 逐个绕自己的中轴旋转
    out = []
    for i in range(len(profiles)):
        p = profiles[i]
        target = None
        best = None
        for f in list(sketch_body.Faces):
            d = abs(face_center(f)[0] - offsets[i])
            if best is None or d < best:
                best = d
                target = f
        if target is None:
            raise RuntimeError("revolve_profiles: no profile face left for profile %d" % i)
        before = {}
        for b in GetRootPart().Bodies:
            before[_body_key(b)] = 1
        axis_line = Line.Create(Point.Create(MM(offsets[i]), MM(0), MM(0)),
                                Direction.Create(0, 0, 1))
        RevolveFaces.Execute(Selection.Create(target), axis_line,
                             math.radians(float(p.get("angle_deg", 360.0))),
                             RevolveFaceOptions())
        body = _sketch_region_body(before)
        if body is None:
            raise RuntimeError("revolve_profiles: revolve produced no body for profile %d" % i)
        a = str(p.get("axis", "z")).lower()
        if a == "x":
            rotate(body, 90.0, axis="y")
        elif a == "y":
            rotate(body, -90.0, axis="x")
        elif a != "z":
            raise ValueError("revolve_profiles: axis must be 'x'/'y'/'z'")
        org = p.get("origin", (0.0, 0.0, 0.0))
        if org is not None:
            # origin=None 表示"别摆正，留在回转出来的位置"（弯头要自己按起始端面定位）
            _anchor_prism(body, a, tuple(org))
        nm = p.get("name")
        if nm:
            try:
                body.Name = nm
            except:
                pass
        out.append(body)
    return out


def _rot_point(p, angle_deg, axis):
    """把一个点按右手定则绕"过原点、方向 axis"的轴旋转 angle_deg 度（和 rotate() 同一套约定）。"""
    import math
    a = math.radians(float(angle_deg))
    c = math.cos(a)
    s = math.sin(a)
    x, y, z = p
    if axis == "x":
        return (x, y * c - z * s, y * s + z * c)
    if axis == "y":
        return (x * c + z * s, y, -x * s + z * c)
    return (x * c - y * s, x * s + y * c, z)


def elbows(bends):
    """一次建多个**真圆截面**弯头（圆环段）——弯管/弯头/回转弯。

    每个元素是 dict：
        pipe_radius  管半径 r
        bend_radius  弯曲半径 R（管中心线的回转半径），**必须 > r**
        angle_deg    弯曲角度（度），默认 90；给 360 就是一整个圆环（torus）
        origin       起始端面的圆心落在哪（默认 (0,0,0)）
        axis         弯曲轴（"x"/"y"/"z"，默认 "z"）；弯头躺在**垂直于 axis 的平面**里
        name         体名

    摆位约定（实测过，可以照着算）：**起始端面（θ=0 那个横截面）的圆心落在 origin 上**。
    管从起始端面沿垂直于 axis 的方向出发，在垂直于 axis 的平面里绕 axis 逆时针弯：

    ==========  ============  ==========
    axis        起始方向       弯曲平面
    ==========  ============  ==========
    "z"         +Y            XY
    "x"         +Y            YZ
    "y"         -Z            ZX
    ==========  ============  ==========

    实测基线（r=3、R=20）：
      * 90°  → 1 个体 3 个面：torus 592.176 mm² + 两个整圆端面 28.274 mm²
               （合计 648.725 = 4*pi^2*R*r/4 + 2*pi*r^2），包围盒 23 x 23 x 6
      * 360° → 1 个体 1 个面：torus 2368.705 mm² = 4*pi^2*R*r，包围盒 46 x 46 x 6

    和所有草图类接口一样，**必须在任何实体之前调用**（见 revolve_profiles）。
    """
    norm = []
    for b in bends:
        r = float(b.get("pipe_radius", 1.0))
        R = float(b.get("bend_radius", 3.0))
        if r <= 0.0:
            raise ValueError("elbows: pipe_radius must be > 0")
        if R <= r:
            raise ValueError("elbows: bend_radius must be greater than pipe_radius, otherwise "
                             "the bend axis cuts through the pipe wall")
        ax = str(b.get("axis", "z")).lower()
        if ax not in ("x", "y", "z"):
            raise ValueError("elbows: axis must be 'x'/'y'/'z'")
        org = b.get("origin", (0.0, 0.0, 0.0))
        norm.append({"r": r, "R": R,
                     "angle": float(b.get("angle_deg", 90.0)),
                     "axis": ax,
                     "origin": (0.0, 0.0, 0.0) if org is None else tuple(org),
                     "name": b.get("name", "Elbow")})
    if not norm:
        return []

    widest = max(it["R"] + it["r"] for it in norm)
    spacing = widest * 3.0

    profiles = []
    for it in norm:
        profiles.append({
            "kind": "circle",
            "center": (it["R"], 0.0),
            "radius": it["r"],
            "angle_deg": it["angle"],
            "axis": it["axis"],
            "origin": None,          # 不在 revolve_profiles 里摆正，下面按起始端面自己定位
            "name": it["name"],
        })
    bodies = revolve_profiles(profiles)

    for i in range(len(bodies)):
        it = norm[i]
        p = (i * spacing + it["R"], 0.0, 0.0)      # 起始端面圆心的"回转后"位置
        if it["axis"] == "x":
            p = _rot_point(p, 90.0, "y")
        elif it["axis"] == "y":
            p = _rot_point(p, -90.0, "x")
        move(bodies[i], it["origin"][0] - p[0], it["origin"][1] - p[1], it["origin"][2] - p[2])
    return bodies


def elbow(pipe_radius, bend_radius, angle_deg=90.0, origin=(0.0, 0.0, 0.0), axis="z",
          name="Elbow"):
    """单个真圆截面弯头。详见 elbows()（多个弯头请一次批量建，草图有硬限制）。"""
    return elbows([{
        "pipe_radius": pipe_radius, "bend_radius": bend_radius, "angle_deg": angle_deg,
        "origin": origin, "axis": axis, "name": name,
    }])[0]


def torus(pipe_radius, bend_radius, origin=(0.0, 0.0, 0.0), axis="z", name="Torus"):
    """整圈圆环（= 弯曲 360° 的弯头）。实测 r=3、R=20 → 1 个 torus 面 2368.705 mm²。"""
    return elbow(pipe_radius, bend_radius, angle_deg=360.0, origin=origin, axis=axis, name=name)


def cone_frustum(radius1, radius2, height, origin=(0.0, 0.0, 0.0), axis="z", name="Cone"):
    """**真正的**圆锥台/圆柱台（回转体，不是阶梯近似）。单个版本。

    radius1 在起点端、radius2 在终点端；其中一端为 0 就是圆锥。
    多个锥台请用 cone_frustums()，不要连续调本函数（草图限制）。
    """
    return cone_frustums([{
        "radius1": radius1, "radius2": radius2, "height": height,
        "origin": origin, "axis": axis, "name": name,
    }])[0]


def cone_frustums(truncated_cones):
    """一次建多个锥台/圆锥（回转体批量形式）。

    每个元素：radius1 / radius2 / height / origin / axis / name。
    实测：r1=8, r2=4, h=20 → 16x16x20，3 个面，底 201.06、顶 50.27、侧面 768.94。
    """
    profiles = []
    for t in truncated_cones:
        r1 = float(t.get("radius1", 0.0))
        r2 = float(t.get("radius2", 0.0))
        h = float(t.get("height", 1.0))
        if r1 < 0 or r2 < 0:
            raise ValueError("cone_frustums: radii must be >= 0")
        if r1 == 0 and r2 == 0:
            raise ValueError("cone_frustums: at least one radius must be > 0")
        # 圆锥（一端半径为 0）只能给 3 个点，否则末两点重合会让轮廓退化
        if r2 == 0:
            pts = [(0.0, 0.0), (r1, 0.0), (0.0, h)]
        elif r1 == 0:
            pts = [(0.0, 0.0), (0.0, h), (r2, h)]
        else:
            pts = [(0.0, 0.0), (r1, 0.0), (r2, h), (0.0, h)]
        profiles.append({
            "points": pts, "angle_deg": 360.0,
            "axis": t.get("axis", "z"),
            "origin": t.get("origin", (0.0, 0.0, 0.0)),
            "name": t.get("name", "Cone"),
        })
    return revolve_profiles(profiles)


def extrude_circle(radius, height, center2d=(0.0, 0.0), name="Body", cut=False):
    """用“草图圆 -> 拉伸”造一个实体圆（走 草图 -> Solid 模式 -> ExtrudeFaces）。

    实测要点（这几条都踩过）：
      * 草图必须用 SketchCircle.Create(Point2D, 半径) 这个重载；带显式 Plane 的
        重载在 Solid 模式下不会形成可拉伸的面（实测 bodies 仍是 0）。
      * 拉伸方向 = 默认工作平面的法向，本机实测是 **Y 轴**，不是 Z 轴。
      * ExtrudeFaces.Execute 只能用三参形式 (selection, 距离, 选项)；显式传第 5 个
        参数会让脚本宿主直接中止整个脚本。
      * 草图在切到 Solid 模式后会变成一张“面”，所以这个函数适合做单个圆；
        多条平行草图的处理不可靠（实测两个圆最后只生成一个面）。
    """
    ensure_document()
    before = {}
    for b in GetRootPart().Bodies:
        before[_body_key(b)] = 1
    SketchCircle.Create(Point2D.Create(MM(center2d[0]), MM(center2d[1])), MM(radius))
    ViewHelper.SetViewMode(InteractionMode.Solid, None)
    sketch_body = _sketch_region_body(before)
    if sketch_body is None:
        raise RuntimeError("extrude_circle(): the sketch produced no new body")
    body = _extrude_sketch_body(sketch_body, height, cut)
    if name and not cut and body is not None:
        try:
            body.Name = name
        except:
            pass
    return body


# ---------------------------------------------------------------------------
# 面的测量 / 查询（单位：mm、mm^2）
# ---------------------------------------------------------------------------

def _axis_index(axis):
    a = str(axis).lower()
    if a in ("x", "0"):
        return 0
    if a in ("y", "1"):
        return 1
    if a in ("z", "2"):
        return 2
    raise ValueError("axis must be 'x'/'y'/'z'; got: " + repr(axis))


def _shape_of(obj):
    """DesignFace / DesignEdge 是包装对象，几何实体在 .Shape 上。"""
    try:
        return obj.Shape
    except:
        return obj


# PolylineOptions 不一定在宿主预加载的名字里，按 API 版本动态取一次。
try:
    PolylineOptions
except NameError:
    PolylineOptions = None
    try:
        import clr
        import SpaceClaim
        _api = getattr(SpaceClaim, 'Api')
        _ver = globals().get('SCDM_API_VERSION', 'V22')
        PolylineOptions = getattr(getattr(_api, _ver), 'Geometry').PolylineOptions
    except:
        PolylineOptions = None


def _edge_points(edge):
    """边上的采样点。

    关键：闭合圆边的 StartPoint/EndPoint 返回的是**圆心**（退化），
    只用它会让圆柱、圆管这类曲面的面心和包围盒全部失真，
    所以优先用 GetPolyline 把边离散成多点。
    """
    pts = []
    if PolylineOptions is not None:
        try:
            sampled = edge.GetPolyline(PolylineOptions())
            if sampled is not None and sampled.Count > 0:
                pts = list(sampled)
        except:
            pass
    if not pts:
        try:
            pts = [edge.StartPoint, edge.EndPoint]
        except:
            pts = []
    # 端点/顶点也要算进去：圆锥的顶点是孤立顶点，不在任何边的采样点上，
    # 只靠采样点会把圆锥的轴向范围算成 0（实测踩过）。
    try:
        for v in (edge.StartVertex, edge.EndVertex):
            if v is not None:
                pts.append(v.Position)
    except:
        pass
    return pts


def _face_box(face):
    """面的解析包围盒，返回 (center, min, max)，单位 mm。

    用 `Face.GetBoundingBox(Matrix.CreateScale(1.0))`——实测这是唯一能覆盖
    "极值只是一个孤立顶点"的面的办法（圆锥顶点不在任何边的采样点上，
    而且圆锥面没有缝边）；旧的边采样法会把圆锥的轴向范围测成 0。
    """
    box = _shape_of(face).GetBoundingBox(Matrix.CreateScale(1.0))
    c = box.Center
    mn = box.MinCorner
    mx = box.MaxCorner
    return ((c.X * 1000.0, c.Y * 1000.0, c.Z * 1000.0),
            (mn.X * 1000.0, mn.Y * 1000.0, mn.Z * 1000.0),
            (mx.X * 1000.0, mx.Y * 1000.0, mx.Z * 1000.0))


def face_center(face):
    """面的中心 = **解析包围盒中心**，单位 mm。

    用包围盒中心而不是边采样点的平均值：切面后会多出共线顶点，平均值会被拉偏
    （实测 100x40x40 的体在底面 x=50 切开后，y=0 侧面的平均点 z 从 20 变成 16），
    而且圆锥这类"极值只是顶点"的面根本采不到。
    """
    return _face_box(face)[0]


def face_extent(face):
    """面的包围盒 ([minx,miny,minz], [maxx,maxy,maxz])，单位 mm。"""
    _c, mn, mx = _face_box(face)
    return (list(mn), list(mx))


def face_area(face):
    """面积，单位 mm^2。"""
    return _shape_of(face).Area * 1.0e6


def body_extent(body, axis="z"):
    """体在指定轴上的最小/最大坐标 (lo, hi)，单位 mm。

    取所有面解析包围盒的并集——比逐条边采样准确，也不会漏掉圆锥顶点那样的孤立极值点。
    """
    i = _axis_index(axis)
    lo = None
    hi = None
    for f in body.Faces:
        _c, mn, mx = _face_box(f)
        if lo is None or mn[i] < lo:
            lo = mn[i]
        if hi is None or mx[i] > hi:
            hi = mx[i]
    if lo is None:
        raise RuntimeError("cannot compute body extent: the body exposes no face")
    return (lo, hi)


def body_size(body):
    """体的包围盒尺寸 (dx, dy, dz)，单位 mm。"""
    lo = []
    hi = []
    for i in range(3):
        a, b = body_extent(body, i)
        lo.append(a)
        hi.append(b)
    return (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])


def faces_where(body, predicate):
    """按条件挑面：predicate(center_mm, area_mm2, face) -> True/False。

    例：faces_where(body, lambda c, a, f: a > 20)   挑面积大于 20 mm^2 的面
    """
    out = []
    for f in body.Faces:
        if predicate(face_center(f), face_area(f), f):
            out.append(f)
    return out


def faces_at(body, axis="z", value=0.0, tol=1e-3):
    """面心在指定轴坐标等于 value(mm) 的所有面（tol 单位 mm）。"""
    i = _axis_index(axis)
    return faces_where(body, lambda c, a, f: abs(c[i] - value) <= tol)


def faces_between(body, axis="z", lo=None, hi=None, tol=1e-3):
    """面心在指定轴坐标落在 [lo, hi] 区间内的面（单位 mm）。"""
    i = _axis_index(axis)
    def ok(c, a, f):
        if lo is not None and c[i] < lo - tol:
            return False
        if hi is not None and c[i] > hi + tol:
            return False
        return True
    return faces_where(body, ok)


# ---------------------------------------------------------------------------
# 边（Edge）：倒圆角 / 倒角
#
# 官方脚本命令，本机 2022 R1 实测可用：
#   ConstantRound.Execute(ISelection edges, Double radius, ICommandInfo info)
#   Chamfer.Execute(ISelection edges, Double d1[, Double d2], ICollection stops, ICommandInfo info)
# 两处的 ICommandInfo 直接传 None 都不炸（别把它塞进 ExtrudeFaces 的可选参数位，
# 那个位置传 None 会让宿主静默中止整个脚本——见 SKILL.md 的 Extrude 条目）。
#
# 四条硬约束，每一条都是实测撞出来的：
#  1. **只吃"边"的选择。** 传一张面 -> StandardError；传一个体 -> ValueError
#     （体选择不会自动展开成边，必须自己取 body.Edges）。
#  2. 失败（半径超出局部可达范围、边集里混了切向边/已经倒过角的边）时抛的是
#     **中文** StandardError（"无法对边倒圆角"）。非 ASCII 的异常信息一旦逃出
#     脚本就会让宿主静默中止，所以这里一律先 except、再抛 ASCII 的 RuntimeError。
#  3. 倒角完成后，**旧的 DesignEdge / DesignFace 包装对象全部失效**，
#     必须重新 `body.Edges` / `body.Faces` 取一次。
#  4. 判定成功看几何，不看 Success（Sweep 就是 Success=True 却什么都不做的反面教材）：
#     这里比对操作前后的"体数 / 面数 / 总面积"指纹，没变就直接报错。
# ---------------------------------------------------------------------------

_EDGE_FAIL_HINT = ("SpaceClaim refused the round/chamfer: the radius is too large for "
                   "the local geometry, or the edge set mixes tangent / already-rounded "
                   "edges. Use a smaller radius, and re-select the edges from the "
                   "CURRENT body (edge wrappers go stale after every round).")


def _edge_key(edge):
    """边的稳定标识（优先 Moniker；取不到就用几何指纹兜底）。"""
    try:
        m = edge.Moniker
        if m is not None:
            return str(m)
    except:
        pass
    c = edge_center(edge)
    return "%s|%.4f|%.4f|%.4f|%.4f" % (edge_kind(edge), c[0], c[1], c[2], edge_length(edge))


def edge_geometry(edge):
    """边的几何对象（Line / Circle / Ellipse / ...）。"""
    return _shape_of(edge).Geometry


def edge_kind(edge):
    """边的几何类型（小写）：'line' / 'circle' / 'ellipse' / 'spline' / 'unknown'。"""
    try:
        return str(type(_shape_of(edge).Geometry).__name__).lower()
    except:
        return "unknown"


def edge_length(edge):
    """边长，单位 mm（外壳的 Length 是米，这里换算过）。"""
    try:
        return float(_shape_of(edge).Length) * 1000.0
    except:
        return 0.0


def _edge_box(edge):
    box = _shape_of(edge).GetBoundingBox(Matrix.CreateScale(1.0))
    c = box.Center
    mn = box.MinCorner
    mx = box.MaxCorner
    return ((c.X * 1000.0, c.Y * 1000.0, c.Z * 1000.0),
            (mn.X * 1000.0, mn.Y * 1000.0, mn.Z * 1000.0),
            (mx.X * 1000.0, mx.Y * 1000.0, mx.Z * 1000.0))


def edge_center(edge):
    """边的包围盒中心，单位 mm（直线边就是中点，圆边就是圆心）。"""
    return _edge_box(edge)[0]


def edge_extent(edge):
    """边的解析包围盒 (min, max)，单位 mm。"""
    b = _edge_box(edge)
    return (list(b[1]), list(b[2]))


def edge_direction(edge):
    """直线边的单位方向 (dx, dy, dz)；曲边返回 None。

    实测：Geometry.Line 上有 .Direction / .Origin；曲线类型上没有 .Direction，
    所以这里先看 edge_kind，避免把圆的某个轴向错当成"边的方向"。
    """
    if edge_kind(edge) != "line":
        return None
    try:
        d = _shape_of(edge).Geometry.Direction
        v = (float(d.X), float(d.Y), float(d.Z))
    except:
        return None
    L = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
    if L <= 0.0:
        return None
    return (v[0] / L, v[1] / L, v[2] / L)


def edge_axis(edge):
    """曲边自身的轴向（圆边所在平面的法向）：XY 平面里的圆返回 (0,0,1)；取不到返回 None。"""
    try:
        g = _shape_of(edge).Geometry
    except:
        return None
    cand = None
    try:
        cand = g.Frame.DirZ
    except:
        try:
            cand = g.Axis
        except:
            try:
                cand = g.Normal
            except:
                cand = None
    if cand is None:
        return None
    try:
        v = (float(cand.X), float(cand.Y), float(cand.Z))
    except:
        return None
    L = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
    if L <= 0.0:
        return None
    return (v[0] / L, v[1] / L, v[2] / L)


def edge_is_smooth(edge):
    """这条边是不是两张面相切处的"软边"（倒角面上大量存在）。"""
    try:
        return bool(_shape_of(edge).IsSmooth)
    except:
        return False


def edge_is_concave(edge):
    """凹边（内角）返回 True，凸边（外角）返回 False。"""
    try:
        return bool(_shape_of(edge).IsConcave)
    except:
        return False


def edge_points(edge, max_points=0):
    """边上的采样点列表（mm）。

    闭合圆边不能用 StartPoint/EndPoint（它们返回的是圆心，是退化的），
    所以走 GetPolyline 离散。
    """
    pts = _edge_points(_shape_of(edge))
    out = []
    for p in pts:
        out.append((float(p.X) * 1000.0, float(p.Y) * 1000.0, float(p.Z) * 1000.0))
        if max_points and len(out) >= max_points:
            break
    return out


def _seg_distance(a, b, p):
    """点 p 到线段 ab 的距离（都按 mm 给）。"""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    dz = b[2] - a[2]
    L2 = dx * dx + dy * dy + dz * dz
    if L2 <= 0.0:
        t = 0.0
    else:
        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy + (p[2] - a[2]) * dz) / L2
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
    qx = a[0] + t * dx
    qy = a[1] + t * dy
    qz = a[2] + t * dz
    return ((p[0] - qx) ** 2 + (p[1] - qy) ** 2 + (p[2] - qz) ** 2) ** 0.5


def edge_distance_to_point(edge, x, y, z):
    """点到边的最近距离（mm）。按采样折线做线段距离，不是只看端点。"""
    pts = edge_points(edge)
    if not pts:
        c = edge_center(edge)
        return ((c[0] - x) ** 2 + (c[1] - y) ** 2 + (c[2] - z) ** 2) ** 0.5
    if len(pts) == 1:
        p = pts[0]
        return ((p[0] - x) ** 2 + (p[1] - y) ** 2 + (p[2] - z) ** 2) ** 0.5
    best = None
    for i in range(1, len(pts)):
        d = _seg_distance(pts[i - 1], pts[i], (x, y, z))
        if best is None or d < best:
            best = d
    return best


def edges_where(body, predicate):
    """按条件挑边：predicate(center_mm, direction, kind, length_mm, edge) -> True/False。

    direction 只对直线边有值（单位向量），曲边是 None；kind 见 edge_kind。
    例：edges_where(body, lambda c, d, k, L, e: k == "circle" and L > 50)
    """
    out = []
    for e in body.Edges:
        if predicate(edge_center(e), edge_direction(e), edge_kind(e), edge_length(e), e):
            out.append(e)
    return out


def edges_by_kind(body, kind):
    """指定几何类型的边：edges_by_kind(body, "line") / ("circle") / ("ellipse")。"""
    k = str(kind).lower()
    return edges_where(body, lambda c, d, kk, L, e: kk == k)


def _unit_vector(v):
    if isinstance(v, (tuple, list)):
        if len(v) != 3:
            raise ValueError("direction tuple must have 3 components")
        d = (float(v[0]), float(v[1]), float(v[2]))
    else:
        d = _dir_vector(v)
    L = (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) ** 0.5
    if L <= 0.0:
        raise ValueError("direction vector must not be zero")
    return (d[0] / L, d[1] / L, d[2] / L)


def edges_parallel(body, axis="z", tol=1e-3):
    """与给定方向平行的直线边（正反都算）。

    axis 可以是 "x"/"y"/"z" 或 (dx,dy,dz)。tol 是"1 - |cos|"的容差。
    这是"四条竖边倒圆角"最常用的入口。
    """
    a = _unit_vector(axis)
    return edges_where(body, lambda c, d, k, L, e:
                       d is not None and abs(d[0] * a[0] + d[1] * a[1] + d[2] * a[2]) >= 1.0 - tol)


def edges_perpendicular(body, axis="z", tol=1e-3):
    """与给定方向垂直的直线边（"这个面四周的边"常用）。"""
    a = _unit_vector(axis)
    return edges_where(body, lambda c, d, k, L, e:
                       d is not None and abs(d[0] * a[0] + d[1] * a[1] + d[2] * a[2]) <= tol)


def edges_along_axis(body, axis="z", tol=1e-3):
    """曲边的轴向与给定轴平行的边（"管口那一圈圆边"用这个）。"""
    a = _unit_vector(axis)
    out = []
    for e in body.Edges:
        ax = edge_axis(e)
        if ax is None:
            continue
        if abs(ax[0] * a[0] + ax[1] * a[1] + ax[2] * a[2]) >= 1.0 - tol:
            out.append(e)
    return out


def edges_at(body, axis="z", value=0.0, tol=1e-3):
    """边心在指定轴坐标等于 value(mm) 的所有边。"""
    i = _axis_index(axis)
    return edges_where(body, lambda c, d, k, L, e: abs(c[i] - value) <= tol)


def edges_between(body, axis="z", lo=None, hi=None, tol=1e-3):
    """边心在指定轴坐标落在 [lo, hi] 区间内的边（单位 mm）。"""
    i = _axis_index(axis)

    def ok(c, d, k, L, e):
        if lo is not None and c[i] < lo - tol:
            return False
        if hi is not None and c[i] > hi + tol:
            return False
        return True
    return edges_where(body, ok)


def edges_in_box(body, xmin=None, xmax=None, ymin=None, ymax=None,
                 zmin=None, zmax=None, tol=1e-3):
    """边心落在给定盒子里的边；某一维传 None 表示不限。"""
    lo = (xmin, ymin, zmin)
    hi = (xmax, ymax, zmax)

    def ok(c, d, k, L, e):
        for i in range(3):
            if lo[i] is not None and c[i] < lo[i] - tol:
                return False
            if hi[i] is not None and c[i] > hi[i] + tol:
                return False
        return True
    return edges_where(body, ok)


def edges_by_length(body, min_length=None, max_length=None, tol=1e-6):
    """按边长（mm）挑边。"""
    def ok(c, d, k, L, e):
        if min_length is not None and L < min_length - tol:
            return False
        if max_length is not None and L > max_length + tol:
            return False
        return True
    return edges_where(body, ok)


def edges_by_curvature(body, smooth=None, concave=None):
    """按"相切软边 / 凹边"挑边；两个参数都传 None 就等于不过滤。"""
    out = []
    for e in body.Edges:
        if smooth is not None and edge_is_smooth(e) != bool(smooth):
            continue
        if concave is not None and edge_is_concave(e) != bool(concave):
            continue
        out.append(e)
    return out


def edges_of_face(face):
    """一张面的所有边界边。"""
    try:
        return list(face.Edges)
    except:
        return []


def edges_of_faces(faces):
    """一组面的边界边（去重）。"把这个面的四周倒圆"用这个。"""
    if not isinstance(faces, (list, tuple)):
        faces = [faces]
    out = []
    seen = {}
    for f in faces:
        for e in edges_of_face(f):
            k = _edge_key(e)
            if k in seen:
                continue
            seen[k] = 1
            out.append(e)
    return out


def edges_at_point(body, x, y, z, tol=1e-3):
    """经过给定点的边（按采样折线做线段距离，不是只看边心）。"""
    out = []
    for e in body.Edges:
        if edge_distance_to_point(e, x, y, z) <= tol:
            out.append(e)
    return out


def nearest_edge(body, x, y, z):
    """离给定点最近的边（按到采样折线的距离）。"""
    best = None
    best_d = None
    for e in body.Edges:
        d = edge_distance_to_point(e, x, y, z)
        if best_d is None or d < best_d:
            best = e
            best_d = d
    return best


def edge_summary(body):
    """{边的几何类型: 条数, ..., "total": 总数}——倒角前后可以对一眼。"""
    out = {"total": 0}
    for e in body.Edges:
        k = edge_kind(e)
        out[k] = out.get(k, 0) + 1
        out["total"] += 1
    return out


def _rule_filtered(rule):
    """这条规则除了 rest/all 之外还有没有别的筛选条件。

    有的话，rest 就只是"前面规则没用掉的里面再按这些条件筛"，而不是"剩下全要"。
    """
    for k in ("normal", "sign", "at", "between", "in_box", "area_min", "area_max",
              "kind", "loops", "point", "nearest", "parallel", "perpendicular",
              "axis", "length_min", "length_max", "smooth", "concave"):
        if k in rule:
            return True
    return False


def match_edges(body, rule, exclude=None):
    """按一条规则挑边。rule 是 dict，键可以任意组合（组合即取交集）：

      parallel      : "x"/"y"/"z" 或 (dx,dy,dz) —— 直线边与它平行
      perpendicular : "x"/"y"/"z" 或 (dx,dy,dz) —— 直线边与它垂直
      axis          : "x"/"y"/"z" 或 (dx,dy,dz) —— 曲边自身的轴向（管口圆边圈）
      kind          : "line" / "circle" / "ellipse" / ...
      at            : (轴, 值)      —— 边心在该轴坐标等于该值
      between       : (轴, lo, hi)  —— 边心在该轴坐标落在区间内
      in_box        : (xmin,xmax,ymin,ymax,zmin,zmax)，某一维可为 None
      length_min    : 边长下限 mm
      length_max    : 边长上限 mm
      point         : (x,y,z)       —— 经过该点的边
      nearest       : (x,y,z)       —— 离该点最近的边
      smooth        : True/False    —— 是否相切软边
      concave       : True/False    —— 是否凹边
      rest          : True          —— exclude 之后剩下的所有边
      all           : True          —— 所有边
      tol           : 位置容差 mm（默认 1e-3）

    exclude 是"已经被前面的规则用掉"的边集合（{edge_key: 1}）。
    """
    tol = rule.get("tol", 1e-3)

    point_keys = None
    if "point" in rule:
        p = rule["point"]
        point_keys = {}
        for e in edges_at_point(body, p[0], p[1], p[2], tol):
            point_keys[_edge_key(e)] = 1

    nearest_key = None
    if "nearest" in rule:
        p = rule["nearest"]
        ne = nearest_edge(body, p[0], p[1], p[2])
        nearest_key = _edge_key(ne) if ne is not None else None

    par = _unit_vector(rule["parallel"]) if "parallel" in rule else None
    perp = _unit_vector(rule["perpendicular"]) if "perpendicular" in rule else None
    ax = _unit_vector(rule["axis"]) if "axis" in rule else None
    kind = str(rule["kind"]).lower() if "kind" in rule else None
    at_i = at_v = None
    if "at" in rule:
        at_i = _axis_index(rule["at"][0])
        at_v = rule["at"][1]
    bt_i = bt_lo = bt_hi = None
    if "between" in rule:
        bt_i = _axis_index(rule["between"][0])
        bt_lo = rule["between"][1]
        bt_hi = rule["between"][2]
    box_lo = box_hi = None
    if "in_box" in rule:
        b = rule["in_box"]
        box_lo = (b[0], b[2], b[4])
        box_hi = (b[1], b[3], b[5])
    len_min = rule.get("length_min")
    len_max = rule.get("length_max")
    want_smooth = rule.get("smooth")
    want_concave = rule.get("concave")
    plain_rest = bool(rule.get("rest")) and not _rule_filtered(rule)
    take_all = bool(rule.get("all")) and not _rule_filtered(rule)

    out = []
    for e in body.Edges:
        key = _edge_key(e)
        if exclude is not None and key in exclude:
            continue
        if plain_rest or take_all:
            out.append(e)
            continue
        c = edge_center(e)
        if kind is not None and edge_kind(e) != kind:
            continue
        if at_i is not None and abs(c[at_i] - at_v) > tol:
            continue
        if bt_i is not None and (c[bt_i] < bt_lo - tol or c[bt_i] > bt_hi + tol):
            continue
        if box_lo is not None:
            inside = True
            for i in range(3):
                if box_lo[i] is not None and c[i] < box_lo[i] - tol:
                    inside = False
                    break
                if box_hi[i] is not None and c[i] > box_hi[i] + tol:
                    inside = False
                    break
            if not inside:
                continue
        if par is not None or perp is not None or ax is not None:
            d = edge_direction(e)
            if par is not None:
                if d is None:
                    continue
                if abs(d[0] * par[0] + d[1] * par[1] + d[2] * par[2]) < 1.0 - 1e-3:
                    continue
            if perp is not None:
                if d is None:
                    continue
                if abs(d[0] * perp[0] + d[1] * perp[1] + d[2] * perp[2]) > 1e-3:
                    continue
            if ax is not None:
                a = edge_axis(e)
                if a is None:
                    continue
                if abs(a[0] * ax[0] + a[1] * ax[1] + a[2] * ax[2]) < 1.0 - 1e-3:
                    continue
        if len_min is not None or len_max is not None:
            L = edge_length(e)
            if len_min is not None and L < len_min - 1e-6:
                continue
            if len_max is not None and L > len_max + 1e-6:
                continue
        if want_smooth is not None and edge_is_smooth(e) != bool(want_smooth):
            continue
        if want_concave is not None and edge_is_concave(e) != bool(want_concave):
            continue
        if point_keys is not None and key not in point_keys:
            continue
        if nearest_key is not None and key != nearest_key:
            continue
        out.append(e)
    return out


def _model_signature():
    """整个文档的几何指纹（体数 / 面数 / 总面积 mm^2）。

    用 all_bodies()：文档里一旦有组件，`GetRootPart().Bodies` 会漏掉组件里的体，
    指纹就会假报"没变化"。没有组件时行为和以前完全一样。
    """
    nb = 0
    nf = 0
    area = 0.0
    for b in all_bodies():
        nb += 1
        for f in b.Faces:
            nf += 1
            try:
                area += float(_shape_of(f).Area) * 1.0e6
            except:
                pass
    return (nb, nf, round(area, 6))


def _edge_list(target):
    """把入参统一成 DesignEdge 列表：单条边 / 边的列表 / 一个体（= 它的所有边）。"""
    if target is None:
        raise ValueError("round/chamfer: no edge target given")
    tn = type(target).__name__
    if tn == "DesignEdge" or tn == "Edge":
        return [target]
    if tn == "DesignBody":
        return list(target.Edges)
    if isinstance(target, (list, tuple)):
        return list(target)
    if hasattr(target, "Edges"):
        return list(target.Edges)
    return list(target)


def _apply_edges(tag, edges, apply_fn):
    """真正执行倒角命令，并用几何指纹判定它到底动没动。"""
    edges = list(edges)
    if not edges:
        raise ValueError(tag + ": the edge selection is empty")
    before = _model_signature()
    try:
        apply_fn(edges)
    except:
        raise RuntimeError(_EDGE_FAIL_HINT)
    after = _model_signature()
    if before == after:
        raise RuntimeError(tag + ": SpaceClaim reported success but the geometry did not "
                                 "change (identical body/face count and total area)")
    return len(edges)


def round_edges(target, radius):
    """倒圆角（fillet），返回提交的边数。

    target: 一条 DesignEdge / DesignEdge 列表 / 一个体（= 该体所有边）
    radius: mm

    实测基线：20mm 立方体 12 条边 r=2 -> 面数 6 变 26
    （6 平面 + 12 圆柱面 + 8 球角面）；只倒 4 条平行于 Z 的边 -> 面数 10。

    注意：**只接受边**。传面（"把这个面倒圆"）会失败——那是
    round_face_edges(face, r) 干的活（先取面的边界边）。
    """
    return _apply_edges("round_edges", _edge_list(target),
                        lambda es: ConstantRound.Execute(
                            Selection.Create(es), MM(float(radius)), None))


def round_face_edges(faces, radius):
    """把一组面的**边界边**倒圆角——"把这个面的四周倒圆"。

    faces 可以是单张面、面列表，或 face_at_point 之类返回的面组。
    """
    return round_edges(edges_of_faces(faces), radius)


def _rules_apply(body, rules, tol, is_chamfer):
    applied = []
    counts = {}
    for i in range(len(rules)):
        rule, value = rules[i]
        r = dict(rule)
        if "tol" not in r:
            r["tol"] = tol
        exclude = {}
        for prev in applied:
            for e in match_edges(body, prev):
                exclude[_edge_key(e)] = 1
        edges = match_edges(body, r, exclude=exclude)
        counts[i] = len(edges)
        if edges:
            if is_chamfer:
                if isinstance(value, (tuple, list)):
                    chamfer_edges(edges, value[0], value[1])
                else:
                    chamfer_edges(edges, value)
            else:
                round_edges(edges, value)
            applied.append(r)
    return counts


def round_by_rules(body, rules, tol=1e-3):
    """按规则表批量倒圆角——边的版本，和 name_faces_by_rules 一个套路。

    rules 是 (规则 dict, 半径 mm) 的列表，按顺序处理；先被用掉的边会被后面的规则排除。

        round_by_rules(body, [
            ({"parallel": "z"}, 2.0),     # 四条竖边 r=2
            ({"kind": "circle"}, 0.5),    # 剩下的圆边 r=0.5
            ({"rest": True}, 1.0),        # 再剩下的 r=1
        ])

    返回 {规则序号: 边数}。有两点要知道：

    1. **每倒一次，体的边就换了一批**，所以每条规则都在"当前"体上重新枚举。
    2. 因此前面规则的排除项也是**在当前体上重新判定**的：倒完竖边后会长出
       新的切向直线边，`{"parallel": "z"}` 会连它们一起匹配上。规则表越长越要留神，
       简单场景（一条规则、或"圆边 + rest"）不受影响。
    """
    return _rules_apply(body, rules, tol, False)


def chamfer_by_rules(body, rules, tol=1e-3):
    """按规则表批量倒角。rules 是 (规则 dict, 距离) 或 (规则 dict, (d1, d2))。"""
    return _rules_apply(body, rules, tol, True)


def chamfer_edges(target, distance, distance2=None):
    """倒角（chamfer），返回提交的边数。

    target: 一条 DesignEdge / DesignEdge 列表 / 一个体（= 该体所有边）
    distance:  mm
    distance2: 给了就是"两侧不等距倒角"（d1 在第一张相邻面上、d2 在另一张上）

    实测基线：20mm 立方体 12 条边 d=2 -> 面数 6 变 26
    （6 平面 + 12 斜面 + 8 三角面）；只倒 4 条平行于 Z 的边 -> 面数 10。
    """
    edges = _edge_list(target)
    d1 = MM(float(distance))
    if distance2 is None:
        fn = lambda es: Chamfer.Execute(Selection.Create(es), d1, None, None)
    else:
        d2 = MM(float(distance2))
        fn = lambda es: Chamfer.Execute(Selection.Create(es), d1, d2, None, None)
    return _apply_edges("chamfer_edges", edges, fn)


def round_vertical_edges(body, radius, axis="z"):
    """只倒某一方向的立边——CFD 里最常见的"柱体竖边倒圆"写法。"""
    return round_edges(edges_parallel(body, axis), radius)


def round_outer_rims(body, radius, axis="z"):
    """只倒轴向平行于 axis 的圆边圈（管口的两圈边）。"""
    return round_edges(edges_along_axis(body, axis), radius)


# ---------------------------------------------------------------------------
# 抽壳（Shell）：把实体掏空成等壁厚的壳
#
# 官方脚本命令，本机 2022 R1 实测可用：
#   Shell.ShellBodies(ISelection body, Double offset, ICommandInfo info)    -- 整体掏空
#   Shell.RemoveFaces(ISelection faces, Double offset, ICommandInfo info)   -- 删掉这些面再掏空
# 两处的 ICommandInfo 传 None 都安全。
#
# **方向是关键：offset 为正时，原来的表面变成"空腔内壁"，新面往外长。**
#   实测 20mm 立方体 +2 -> 包围盒变成 24x24x24，原来 6 张 400 面法向翻转、成了空腔内壁，
#   外侧新增 6 张 576 面（= 24x24）。
# 想要 CAD 里常规的"外表面不动、壁往内长"，要传**负值**：
#   实测 20mm 立方体 -2 -> 12 个面、总面积 3936 = 6x400(外) + 6x256(16^3 空腔)，
#   包围盒仍是 20x20x20。所以下面的 shell() 默认取负号。
#
# 另外两条实测结论：
#   * offset = 0、以及"壁厚超过体最小尺寸的一半"，都抛 **中文** StandardError。
#     非 ASCII 异常一旦逃出脚本就会让宿主静默中止，所以这里一律转成 ASCII 的 RuntimeError。
#   * 对**已经命名过的面**做 RemoveFaces 会把那个命名选择打空（实测 outlet 组直接消失）。
#     顺序永远是"先抽壳、后命名"。
# ---------------------------------------------------------------------------

def shell(body, thickness, open_faces=None, outward=False):
    """抽壳：把实体掏成等壁厚的壳，返回同一个体。

    body       要掏空的实体
    thickness  壁厚，单位 mm，必须 > 0
    open_faces 要"开口"的面（单张面或面列表）；**不传就是全封闭的空腔**
    outward    False（默认）= 外表面不动、壁往**内**长（CAD 常规语义）
               True          = 原表面当内壁、壁往**外**长（SpaceClaim 命令的原始语义）

    实测基线：
      * 20mm 立方体、t=2、全封闭 -> 12 个面，总面积 3936.00
        = 6x400（外，20^3）+ 6x256（空腔，16^3），包围盒 20x20x20
      * 20mm 立方体、t=2、开口面 = 顶面 -> 11 个面，总面积 3552.00
        = 5x400（外）+ 4x288（空腔壁 16x18）+ 256（空腔底 16x16）+ 144（顶部环形口）
      * r=10 h=20 圆柱、t=2、全封闭 -> 6 个面，总面积 3091.33
        = 1256.64(外柱面) + 804.25(空腔柱面 r8 h16) + 2x314.16(外端面) + 2x201.06(空腔端面)
      * 20mm 立方体、t=2、开口 = 顶面+底面 -> 10 个面，总面积 3168.00
        = 4x400(外) + 4x320(空腔壁 16x20) + 2x144(上下两个环形口)
    """
    t = float(thickness)
    if t <= 0.0:
        raise ValueError("shell: thickness must be > 0 mm")
    offset = MM(t if outward else -t)

    faces = None
    if open_faces is not None:
        if isinstance(open_faces, (list, tuple)):
            faces = [f for f in open_faces]
        else:
            faces = [open_faces]
        if not faces:
            faces = None

    before = _model_signature()
    try:
        if faces is not None:
            Shell.RemoveFaces(Selection.Create(faces), offset, None)
        else:
            Shell.ShellBodies(Selection.Create(body), offset, None)
    except:
        raise RuntimeError(
            "shell failed: SpaceClaim refused the offset. The wall thickness is probably too "
            "large for this body (more than half of its smallest dimension), or an open face "
            "was named that cannot be removed.")
    after = _model_signature()
    if before == after:
        raise RuntimeError("shell: SpaceClaim reported success but the geometry did not change "
                           "(identical body/face count and total area)")
    return body


# ---------------------------------------------------------------------------
# 阵列 / 镜像
#
# **不用官方的 `Pattern.CreateLinear` / `CreateCircular`** —— 实测它会把体搬进一个
# component：20³ 立方体做完 4 个线性阵列后 `GetRootPart().Bodies.Count` 变成 **0**、
# `GetRootPart().Components.Count` 变成 **1**（实例成了 occurrence）。
# 那样下游的命名、`body_size`、`verify_model.py` 全部看不见体了。
# 另外数据对象里的方向/轴必须给**真实可选的几何**：
# `Selection.CreateByObjects(Line.Create(...))` 和传 `Direction` 都会直接
# `SystemError: Collection is empty`。
#
# 所以这里的阵列是"复制 + 平移/旋转"：`Copy.Execute(Selection.Create(body))`
# 会在原地生成一个副本（副本与原体相互独立），再 `move` / `rotate` 摆位。
# 好处是实例始终是根零件下的普通体，命名、校验、布尔减全都照常。
#
# 还有一个实测坑：**原地的副本如果压着别的体，会并进那个体**（不是并进种子体），
# 所以 `_copy_body` 会先把种子搬到文档包围盒之外的空白处复制、再一起搬回来。
#
# 阵列给的是**实体实例**。要在流域上开一排孔 / 管束，直接对每个位置调
# `cylinder(..., cut=True)` 更直接（cutter 不落盘，也不会跟别的东西并集）。
# ---------------------------------------------------------------------------

def _free_shift(body, margin=10.0):
    """算一个位移，把 body 搬到**整个文档包围盒之外**的空白处（沿 X 正方向）。

    为什么要这样：`Copy.Execute` 是**原地**复制。如果种子体当时正好压在别的体上，
    副本一生成就会被并进那个体（实测：叶片阵列放在管子上，结果叶片被并成了
    10x13x10、9 个面的怪东西）。所以复制前先把种子挪到空白处，复制完再挪回来。
    """
    hi_x = None
    for b in GetRootPart().Bodies:
        e = body_extent(b, "x")
        if hi_x is None or e[1] > hi_x:
            hi_x = e[1]
    if hi_x is None:
        return (0.0, 0.0, 0.0)
    lo = body_extent(body, "x")[0]
    return (hi_x + float(margin) - lo, 0.0, 0.0)


def _copy_body(body):
    """复制一个体，返回新体（一定与原体相互独立）。

    实测要点：`Copy.Execute(Selection.Create(body))` 会在**原地**生成副本；
    副本与原体本身不会并集（20³ 复制后确实是 2 个体），但如果原地压着**别的**体，
    副本会并进那个体。所以这里先把种子搬到文档包围盒之外复制，再一起搬回来。
    """
    dx, dy, dz = _free_shift(body)
    moved = (abs(dx) > 1e-9 or abs(dy) > 1e-9 or abs(dz) > 1e-9)
    if moved:
        move(body, dx, dy, dz)
    new_body = None
    try:
        snap = _snapshot_bodies()
        try:
            res = Copy.Execute(Selection.Create(body))
        except:
            raise RuntimeError("copy failed: SpaceClaim refused to copy this body")
        new_body = _created_body(res, snap)
    finally:
        if moved:
            move(body, -dx, -dy, -dz)
    if new_body is None:
        raise RuntimeError("copy failed: the copy did not appear as a new body")
    if moved:
        move(new_body, -dx, -dy, -dz)
    return new_body


def _name_instances(items, name):
    if not name:
        return items
    for k in range(len(items)):
        try:
            items[k].Name = "%s_%d" % (name, k + 1)
        except:
            pass
    return items


def array_linear(body, count, pitch, axis="x", count2=0, pitch2=None, axis2=None, name=None):
    """线性阵列（复制 + 平移），返回**所有实例**（含原体），单位 mm。

    body    种子体
    count   第一方向的实例数（含原体）；pitch 是间距
    axis    第一方向，"x"/"y"/"z"
    count2  第二方向实例数（可选，做 2D 阵列）；pitch2、axis2 配套
    name    给了就依次命名成 name_1、name_2 …（ASCII）；不给就沿用原体名

    实测：10³ 立方体 4 个实例、间距 20（沿 X）-> 4 个体、24 个面、总面积 2400
    （每个 6 面 600），整体包围盒 X 从 0 到 70。
    """
    n1 = int(count)
    if n1 < 1:
        raise ValueError("array_linear: count must be >= 1")
    p1 = float(pitch)
    a1 = _dir_vector(axis)
    items = []
    for i in range(n1):
        if i == 0:
            bb = body
        else:
            bb = _copy_body(body)
            move(bb, a1[0] * p1 * i, a1[1] * p1 * i, a1[2] * p1 * i)
        items.append(bb)
    n2 = int(count2 or 0)
    if n2 > 1:
        if pitch2 is None:
            raise ValueError("array_linear: pitch2 is required when count2 > 1")
        ax2 = axis2
        if ax2 is None:
            order = {"x": "y", "y": "z", "z": "x"}
            ax2 = order.get(str(axis).lower(), "y")
        a2 = _dir_vector(ax2)
        p2 = float(pitch2)
        base = list(items)
        for j in range(1, n2):
            for bb in base:
                cc = _copy_body(bb)
                move(cc, a2[0] * p2 * j, a2[1] * p2 * j, a2[2] * p2 * j)
                items.append(cc)
    return _name_instances(items, name)


def array_circular(body, count, axis="z", center=(0.0, 0.0, 0.0), angle_deg=360.0, name=None):
    """圆周阵列（复制 + 绕轴旋转），返回所有实例（含原体）。

    count     实例数（含原体）
    axis      旋转轴方向，"x"/"y"/"z"
    center    轴上一点，单位 mm
    angle_deg 总张角；给 360（默认）时按 360/count 均分整圈，
              否则按 angle/(count-1) 均分（首尾正好落在 0 和 angle 上）
    name      给了就依次命名成 name_1、name_2 …（ASCII）

    实测：6³ 的叶片放在半径 20 处、绕 Z 轴 6 个整圈阵列 -> 6 个体、36 个面、
    总面积 1296（每个 6 面 216）。
    """
    n = int(count)
    if n < 1:
        raise ValueError("array_circular: count must be >= 1")
    total = float(angle_deg)
    if abs(total - 360.0) < 1e-9:
        step = 360.0 / n
    elif n > 1:
        step = total / (n - 1)
    else:
        step = 0.0
    items = []
    for i in range(n):
        if i == 0:
            bb = body
        else:
            bb = _copy_body(body)
            rotate(bb, step * i, axis=axis, center=center)
        items.append(bb)
    return _name_instances(items, name)


def mirror(body, plane_face, merge=True, name=None):
    """按一张**已经存在的平面面**镜像一个体，返回 [原体] 或 [原体, 副本]。

    plane_face 必须是模型里真实存在的一张平面面（通常就是对称面）。
                **不能**临时造一个 Plane/Line 传进来——数据选择只认真实几何。
    merge      True（默认，SpaceClaim 自己的默认）：副本与原体并成一个体
               （半模型补成整模型最常用）
               False：副本保持独立，返回两个体
    name       给了就命名副本为 name（ASCII）

    实测：10³ 立方体放在 x=10..20，按它自己的 x=10 那张面镜像、merge=True
    -> 1 个体、包围盒变成 20×10×10；merge=False -> 2 个体、各 6 面。
    """
    faces = plane_face
    if not isinstance(faces, (list, tuple)):
        faces = [faces]
    faces = [f for f in faces if f is not None]
    if not faces:
        raise ValueError("mirror: a planar face of the model is required as the mirror plane")

    keys = {}
    for x in GetRootPart().Bodies:
        keys[_body_key(x)] = 1
    before = _model_signature()

    opts = MirrorOptions()
    opts.MergeObjects = bool(merge)
    try:
        Mirror.Execute(Selection.Create(body), Selection.Create(faces[0]), opts, None)
    except:
        raise RuntimeError("mirror failed: SpaceClaim refused this body / mirror plane "
                           "(the plane must be a real planar face of the model)")

    after = _model_signature()
    if before == after:
        raise RuntimeError("mirror: SpaceClaim reported success but the geometry did not change")

    out = [body]
    for x in GetRootPart().Bodies:
        if _body_key(x) not in keys:
            out.append(x)
    if name and len(out) > 1:
        try:
            out[1].Name = name
        except:
            pass
    return out


# ---------------------------------------------------------------------------
# 曲面（零厚度的面体）与加厚
#
# 官方命令，本机 2022 R1 实测可用：
#   RectangularSurface.Create(Double width, Double height, Nullable<Point> origin)
#   CircularSurface.Create(Double radius, Direction zDir, Nullable<Point> origin)
#   ThickenFaces.Execute(ISelection faces, Direction dir, Double value,
#                        ThickenFaceOptions options, ICommandInfo info)
#   ThickenFaceOptions : PullSymmetric / ExtrudeType / SelectDirection
#
# 实测要点：
#   * 曲面体是**零厚度**的：`RectangularSurface.Create(20, 10)` -> 1 个体 1 个面、
#     平面、面积 200 mm²、包围盒 20x10x0。`CircularSurface.Create(r=10)` -> 面积
#     314.159 = pi*10^2。
#   * `ThickenFaces` 把它加厚成实体：20x10 的面、+Z 2mm -> 1 个体 6 个面、
#     包围盒 20x10x2、总面积 520 = 2x200 + 2x(20x2) + 2x(10x2)。
#   * **`PullSymmetric = True` 时总厚度是 value 的两倍**：40x40 的面、value=4、
#     对称 -> 包围盒 Z 从 -4 到 +4（厚 8），而不是 4。
#   * `ThickenFaces` 作用在**实体的面**上就是"拉伸/偏移那张面"：
#     20³ 实体的顶面 +Z 5mm -> 整体长高到 25，仍然是 6 个面。
#   * `Midsurface.Convert(body, 厚度, None)` 实测返回 Success=True 但几何**毫无变化**
#     （40x40x4 的板仍是 6 个面 3840 mm²），别指望它。
# ---------------------------------------------------------------------------

def rect_surface(width, height, origin=(0.0, 0.0, 0.0), normal="z", name="Surface"):
    """一张矩形曲面（零厚度面体），返回体对象。

    默认躺在 XY 平面（法向 Z）；normal 给 "x"/"y" 时把它摆成法向朝那个轴。
    实测：20x10 -> 1 个体、1 个面、面积 200 mm²、包围盒 20x10x0。
    """
    ensure_document()
    p = Point.Create(MM(origin[0]), MM(origin[1]), MM(origin[2]))
    before = _snapshot_bodies()
    try:
        RectangularSurface.Create(MM(float(width)), MM(float(height)), p)
    except:
        raise RuntimeError("rect_surface: SpaceClaim refused to create the surface")
    body = _created_body(None, before)
    if body is None:
        raise RuntimeError("rect_surface: no surface body appeared")
    n = str(normal).lower()
    if n == "x":
        rotate(body, 90.0, axis="y")
    elif n == "y":
        rotate(body, -90.0, axis="x")
    elif n != "z":
        raise ValueError("rect_surface: normal must be 'x'/'y'/'z'")
    if name:
        try:
            body.Name = name
        except:
            pass
    return body


def circle_surface(radius, center=(0.0, 0.0, 0.0), normal="z", name="Surface"):
    """一张圆形曲面（零厚度面体）。实测 r=10 -> 1 个面、面积 314.159 mm²。"""
    ensure_document()
    d = _dir_vector(normal)
    p = Point.Create(MM(center[0]), MM(center[1]), MM(center[2]))
    before = _snapshot_bodies()
    try:
        CircularSurface.Create(MM(float(radius)),
                               Direction.Create(d[0], d[1], d[2]), p)
    except:
        raise RuntimeError("circle_surface: SpaceClaim refused to create the surface")
    body = _created_body(None, before)
    if body is None:
        raise RuntimeError("circle_surface: no surface body appeared")
    if name:
        try:
            body.Name = name
        except:
            pass
    return body


def thicken(target, value, direction="z", symmetric=False, name=None):
    """把曲面（或实体的面）加厚 / 拉伸，返回**可用的体对象**。

    target     曲面体、一张面，或面的列表
    value      厚度 / 拉伸量，单位 mm，必须 > 0
    direction  往哪个方向拉："x"/"y"/"z" 或 (dx,dy,dz)（给元组就能指定负方向）
    symmetric  True 时**两侧各拉 value**，总厚度 2*value（实测 40x40、value=4
               -> 包围盒 Z 从 -4 到 +4）

    实测：20x10 的矩形曲面 +Z 2mm -> 1 个体 6 个面、包围盒 20x10x2、总面积 520。

    **注意返回值**：给**曲面体**加厚时，SpaceClaim 会把原来那个面体**替换**掉，
    旧的体对象随即失效（拿它取 `Faces` 会抛 "The object is deleted."）。
    所以这里返回的是重新取到的新体；给**实体的面**加厚则是原地改（实测 20³ 的
    顶面 +Z 5 会让整体长到 25），此时返回原对象。
    """
    v = float(value)
    if v <= 0.0:
        raise ValueError("thicken: value must be > 0 mm")
    if isinstance(target, (list, tuple)):
        faces = list(target)
    elif _is_body(target):
        faces = list(target.Faces)
    else:
        faces = [target]
    if not faces:
        raise ValueError("thicken: no face to thicken")
    d = _unit_vector(direction)
    opts = ThickenFaceOptions()
    opts.PullSymmetric = bool(symmetric)
    old_name = None
    if _is_body(target):
        try:
            old_name = target.Name
        except:
            old_name = None
    snap = _snapshot_bodies()
    before = _model_signature()
    try:
        ThickenFaces.Execute(Selection.Create(faces),
                             Direction.Create(d[0], d[1], d[2]), MM(v), opts, None)
    except:
        raise RuntimeError("thicken failed: SpaceClaim refused to thicken this face")
    after = _model_signature()
    if before == after:
        raise RuntimeError("thicken: SpaceClaim reported success but the geometry did not change")
    new_body = _created_body(None, snap)
    out = new_body if new_body is not None else target
    # 替换出来的新体会丢掉原来的名字，这里补回去（否则会变成本地化的默认名）
    if name is None and old_name is not None and new_body is not None:
        try:
            out.Name = old_name
        except:
            pass
    if name is not None:
        try:
            out.Name = name
        except:
            pass
    return out


def _is_body(obj):
    """obj 是不是一个体（而不是面/边）。"""
    tn = type(obj).__name__
    if tn in ("DesignBody", "Body", "SurfaceBody"):
        return True
    if tn in ("DesignFace", "DesignEdge", "DesignCurve"):
        return False
    return hasattr(obj, "Faces") and hasattr(obj, "Edges")


def _body_of(face):
    """面所属的体（DesignFace.Body）。"""
    try:
        return face.Body
    except:
        try:
            return _shape_of(face).Body
        except:
            return None


# ---------------------------------------------------------------------------
# 装配：组件（Component）
#
# 官方命令，本机 2022 R1 实测可用：
#   ComponentHelper.CreateAtRoot(String name, ICommandInfo info)
#   ComponentHelper.CreateAtComponent(IComponent parent, String name, ICommandInfo info)
#   ComponentHelper.MoveBodiesToComponent(ISelection bodies, IComponent comp, Boolean copy, ICommandInfo info)
#   ComponentHelper.MoveBodiesToComponent(ISelection bodies, IPart part, Boolean copy, ICommandInfo info)
#   ComponentHelper.CreateSeparateComponents(ISelection bodies, ICommandInfo info)
#   IComponent.GetAllBodies() / GetBodies() / GetInstance() / GetOccurrence()
#
# **关键行为：体一旦进了组件，`GetRootPart().Bodies` 就再也看不到它了。**
# 实测 2 个体把一个搬进组件后，根零件的 Bodies 从 2 变 1、Components 从 0 变 1，
# 那个体只能从 `comp.GetAllBodies()` 拿到。这和 §22.1 里 Pattern 的表现是同一个坑。
#
# 搬回根零件的**唯一实测可行路径**是 `MoveBodiesToComponent(体, GetRootPart(), False, None)`
# —— 传 `IPart` 的那个重载。`ComponentHelper.FlattenAssembly(...)` 实测**是个空操作**：
# 无论选组件还是选根零件都返回 Success=True，但体纹丝不动。
#
# 另外：组件里的体一样能 measure、能挑面、能 `name_faces`（实测通过），
# 但命名之后 `NamedSelection.GetGroups()` 那次枚举让脚本硬崩过一次——
# 所以**推荐的顺序还是"先搬回根零件，再命名"**。
# ---------------------------------------------------------------------------

def component(name, parent=None):
    """建一个组件（parent=None 建在根零件下，否则建在那个组件里面），返回 **IComponent**。

    实测两件事：
      * `CreateAtRoot` 出来的组件 `.Name` 是**空的**，`SetName` 返回 True 也读不回来，
        所以名字只能自己记账（`assembly_summary()` 会显示 <unnamed>）。
      * `CreateAtComponent` 返回的是 `ComponentCommandResult`，**不是** IComponent
        （直接拿它当父级会 `TypeError: expected ISelection, got ComponentCommandResult`），
        要从 `res.CreatedComponents[0]` 取。
    """
    ensure_document()
    comp = None
    try:
        if parent is None:
            comp = ComponentHelper.CreateAtRoot(str(name), None)
        else:
            res = ComponentHelper.CreateAtComponent(parent, str(name), None)
            try:
                if res.CreatedComponents.Count > 0:
                    comp = res.CreatedComponents[0]
            except:
                comp = None
            if comp is None:
                kids = component_children(parent)
                if kids:
                    comp = kids[len(kids) - 1]
    except:
        raise RuntimeError("component: SpaceClaim refused to create the component")
    if comp is None:
        raise RuntimeError("component: the component did not appear")
    try:
        if not str(comp.Name):
            ComponentHelper.SetName(comp, str(name))
    except:
        pass
    return comp


def component_name(comp):
    """组件的显示名（`.Name` 可能是空的，依次退回 GetInstanceName / GetInstance）。"""
    try:
        nm = str(comp.Name)
        if nm:
            return nm
    except:
        pass
    try:
        nm = str(comp.GetInstanceName())
        if nm:
            return nm
    except:
        pass
    try:
        return str(comp.GetInstance().Name)
    except:
        return "<unnamed>"


def move_to_component(bodies, comp, copy=False):
    """把体搬进组件（copy=True 则保留原件）。

    实测：搬进去之后 `GetRootPart().Bodies` 就看不见它了，要用 `component_bodies()`。
    """
    items = _as_body_list(bodies)
    if not items:
        raise ValueError("move_to_component: no body given")
    try:
        ComponentHelper.MoveBodiesToComponent(Selection.Create(items), comp, bool(copy), None)
    except:
        raise RuntimeError("move_to_component: SpaceClaim refused to move these bodies")
    return comp


def move_to_root(bodies):
    """把体搬回根零件（组件 -> 根零件的唯一实测可行路径）。"""
    items = _as_body_list(bodies)
    if not items:
        raise ValueError("move_to_root: no body given")
    try:
        ComponentHelper.MoveBodiesToComponent(Selection.Create(items), GetRootPart(), False, None)
    except:
        raise RuntimeError("move_to_root: SpaceClaim refused to move these bodies back to the root")
    return items


def explode_to_components(bodies):
    """每个体单独进一个组件（实测 3 个体 -> Components=3、根零件 Bodies=0）。"""
    items = _as_body_list(bodies)
    if not items:
        raise ValueError("explode_to_components: no body given")
    try:
        ComponentHelper.CreateSeparateComponents(Selection.Create(items), None)
    except:
        raise RuntimeError("explode_to_components: SpaceClaim refused to split these bodies")
    return components()


def components(part=None):
    """根零件下（**一层**）的组件列表。要所有层级用 `all_components()`。"""
    if part is None:
        part = GetRootPart()
    out = []
    try:
        for i in range(part.Components.Count):
            out.append(part.Components[i])
    except:
        pass
    return out


def component_children(comp):
    """一个组件的**直接**子组件。"""
    out = []
    try:
        for i in range(comp.Components.Count):
            out.append(comp.Components[i])
    except:
        pass
    return out


def all_components(part=None):
    """递归列出**所有层级**的组件（先根零件下的，再往里）。"""
    if part is None:
        part = GetRootPart()
    queue = list(components(part))
    out = []
    while queue:
        c = queue.pop(0)
        out.append(c)
        queue.extend(component_children(c))
    return out


def _direct_bodies(comp):
    """只属于这个组件**自己**的体（不含子组件的）。"""
    try:
        return list(comp.GetBodies())
    except:
        try:
            return list(comp.GetAllBodies())
        except:
            return []


def component_bodies(comp, deep=True):
    """一个组件里的体；deep=True（默认）连子组件里的也算。

    这里**自己走递归**，不依赖 `GetAllBodies()` 到底含不含子组件（实测没定论）。
    按 Moniker 去重，所以嵌套再深也不会重复计数。
    """
    out = []
    seen = {}

    def walk(c):
        for b in _direct_bodies(c):
            k = _body_key(b)
            if k not in seen:
                seen[k] = 1
                out.append(b)
        for ch in component_children(c):
            walk(ch)

    if deep:
        walk(comp)
    else:
        out.extend(_direct_bodies(comp))
    return out


def all_bodies():
    """根零件下的体 + **所有层级**组件里的体（按 Moniker 去重）。

    我们的命名/校验默认只看 `GetRootPart().Bodies`；文档里一旦用了组件，
    那些体就"消失"了，所以需要这个把两边都算上。
    """
    out = []
    seen = {}

    def push(b):
        k = _body_key(b)
        if k not in seen:
            seen[k] = 1
            out.append(b)

    try:
        for i in range(GetRootPart().Bodies.Count):
            push(GetRootPart().Bodies[i])
    except:
        pass
    for c in all_components():
        for b in _direct_bodies(c):
            push(b)
    return out


def _as_body_list(bodies):
    if bodies is None:
        return []
    if isinstance(bodies, (list, tuple)):
        return list(bodies)
    if type(bodies).__name__ == "DesignBody":
        return [bodies]
    try:
        return list(bodies)
    except:
        return [bodies]


def drop_empty_components(part=None):
    """删掉空组件（**递归**，含子组件）。

    实测：搬空之后的组件如果留在文档里，`NamedSelection.GetGroups()` 会抛
    **中文**的 SystemError（"未将对象引用设置到对象的实例"）——命名选择整个读不出来，
    而且旧版 `verify_model.py` 会把这种失败吞掉、照样报 OK。所以搬完体之后请调一次。
    返回删掉的组件数（按**所有层级**计）。
    """
    if part is None:
        part = GetRootPart()
    before = len(all_components(part))
    try:
        ComponentHelper.DeleteEmptyComponents(part, None)
    except:
        try:
            ComponentHelper.DeleteEmptyComponents(None)
        except:
            return 0
    return before - len(all_components(part))


def assembly_summary():
    """当前文档的装配结构：[(名字, 体数), ...]，含**所有层级**，名字前按层数缩进。

    第一项永远是 ("(root)", 根零件里的体数)。
    """
    out = [("(root)", GetRootPart().Bodies.Count)]
    queue = [(c, 1) for c in components()]
    while queue:
        c, depth = queue.pop(0)
        nm = _ascii(component_name(c))
        out.append((("  " * (depth - 1)) + nm, len(component_bodies(c, deep=False))))
        for ch in component_children(c):
            queue.append((ch, depth + 1))
    return out


# ---------------------------------------------------------------------------
# 命名选择（Named Selection）
# ---------------------------------------------------------------------------

def name_faces(name, face_list):
    """把一组面做成命名选择并命名。

    SpaceClaim 的 NamedSelection.Create 不接受名字，只能先建后改名；
    默认名字是本地化的（中文界面下不是 ASCII），所以脚本里不要打印它。
    """
    face_list = list(face_list)
    if not face_list:
        raise ValueError("named selection '" + str(name) + "' has no faces")
    res = NamedSelection.Create(Selection.Create(face_list),
                                Selection.Empty(),
                                PartLocation.Root,
                                None)
    if not res.Success:
        raise RuntimeError("failed to create named selection: " + str(name))
    grp = res.CreatedNamedSelection
    try:
        grp.Name = name
    except:
        NamedSelection.Rename(grp.Name, name)
    return grp


def name_boundaries(body, bottom="inlet", top="outlet", sides="wall",
                    axis="z", tol=None, split_sides=False):
    """CFD 最常见的命名方式：沿 axis 方向，一端 bottom、另一端 top、其余为 sides。

    返回 {"bottom": [...], "top": [...], "sides": [...]} 三个面列表。
    传 None 可以跳过某一类；split_sides=True 会把侧面拆成 wall_1..wall_n。
    全套脚本 / 圆柱管的进出口都适用。
    """
    lo, hi = body_extent(body, axis)
    if tol is None:
        tol = max(1e-3, (hi - lo) * 1e-6)
    i = _axis_index(axis)

    buckets = {"bottom": [], "top": [], "sides": []}
    for f in body.Faces:
        v = face_center(f)[i]
        if abs(v - lo) <= tol:
            buckets["bottom"].append(f)
        elif abs(v - hi) <= tol:
            buckets["top"].append(f)
        else:
            buckets["sides"].append(f)

    if bottom and buckets["bottom"]:
        name_faces(bottom, buckets["bottom"])
    if top and buckets["top"]:
        name_faces(top, buckets["top"])
    if sides and buckets["sides"]:
        if split_sides:
            for k in range(len(buckets["sides"])):
                name_faces("%s_%d" % (sides, k + 1), [buckets["sides"][k]])
        else:
            name_faces(sides, buckets["sides"])
    return buckets


# ---------------------------------------------------------------------------
# 通用选面：把"自然语言描述"翻译成面组
#
# 命名那层本来就是开放的（name_faces 接受任意 ASCII 名字），真正需要的是
# "按什么挑面"这一层。下面这些函数配合 match_faces / name_faces_by_rules，
# 覆盖 CFD 里绝大多数边界条件的描述方式。
# ---------------------------------------------------------------------------

def _face_key(face):
    """面的稳定标识（用 Moniker 而不是对象 id：重复遍历 body.Faces 可能给出不同的包装对象）。"""
    try:
        return str(face.Moniker)
    except:
        return str(id(face))


def face_normal(face):
    """平面面的单位法向 (nx, ny, nz)；非平面面返回 None。

    实测：Geometry.Plane 上没有 .Normal，法向在 Plane.Frame.DirZ 上；
    面的朝向还要看 IsReversed（同一个平面可能被面反向引用）。
    """
    shape = _shape_of(face)
    try:
        g = shape.Geometry
        if str(type(g).__name__) != "Plane":
            return None
        d = g.Frame.DirZ
        n = (d.X, d.Y, d.Z)
    except:
        return None
    try:
        if shape.IsReversed:
            n = (-n[0], -n[1], -n[2])
    except:
        pass
    L = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) ** 0.5
    if L <= 0.0:
        return None
    return (n[0] / L, n[1] / L, n[2] / L)


def face_kind(face):
    """面的几何类型（小写）：'plane' / 'cylinder' / 'cone' / 'sphere' / 'torus' / 'unknown'。"""
    try:
        return str(type(_shape_of(face).Geometry).__name__).lower()
    except:
        return "unknown"


def _dir_vector(axis):
    i = _axis_index(axis)
    return (1.0 if i == 0 else 0.0, 1.0 if i == 1 else 0.0, 1.0 if i == 2 else 0.0)


def faces_by_normal(body, axis="z", sign=1, tol=0.99):
    """法向朝向某个方向的面。

    axis 可以是 "x"/"y"/"z"，也可以是任意单位方向 (nx,ny,nz)——后者用来匹配
    **斜几何**（例如绕 Z 轴转 45 度后，管口法向是 (0.7071, 0.7071, 0)）。
    sign=+1 朝该方向，-1 朝反方向。

    只有平面面有法向；圆柱侧面等一律不入选（要圆柱面用 faces_by_kind(body, "cylinder")）。
    """
    d = axis if isinstance(axis, (tuple, list)) else _dir_vector(axis)
    L = (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) ** 0.5
    if L <= 0.0:
        raise ValueError("faces_by_normal: direction must be non-zero")
    d = (d[0] / L, d[1] / L, d[2] / L)
    out = []
    for f in body.Faces:
        n = face_normal(f)
        if n is None:
            continue
        dot = n[0] * d[0] + n[1] * d[1] + n[2] * d[2]
        if (sign >= 0 and dot >= tol) or (sign < 0 and dot <= -tol):
            out.append(f)
    return out


def faces_by_kind(body, kind):
    """按几何类型挑面：'plane'（平面）/ 'cylinder'（圆柱面）/ 'cone' / 'sphere' / 'torus'。

    对应"管子内壁"（cylinder）、"圆端面"（plane）、"锥面段"这类说法。
    """
    k = str(kind).lower()
    return [f for f in body.Faces if face_kind(f) == k]


def faces_by_area(body, min_area=None, max_area=None, tol=1e-6):
    """按面积挑面，单位 mm^2。对应"最大的那个面""面积小于 1 的小面"。"""
    out = []
    for f in body.Faces:
        a = face_area(f)
        if min_area is not None and a < min_area - tol:
            continue
        if max_area is not None and a > max_area + tol:
            continue
        out.append(f)
    return out


def face_at_point(body, x, y, z):
    """包含给定点的面（点恰好落在公共边上时可能返回多个）。"""
    p = Point.Create(MM(x), MM(y), MM(z))
    out = []
    for f in body.Faces:
        try:
            if _shape_of(f).ContainsPoint(p):
                out.append(f)
        except:
            pass
    return out


def nearest_face(body, x, y, z):
    """离给定点最近的面（按面心距离）。点难精确落在面上时用这个。"""
    best = None
    best_d = None
    for f in body.Faces:
        c = face_center(f)
        d = (c[0] - x) ** 2 + (c[1] - y) ** 2 + (c[2] - z) ** 2
        if best_d is None or d < best_d:
            best_d = d
            best = f
    return best


def faces_in_box(body, xmin=None, xmax=None, ymin=None, ymax=None,
                 zmin=None, zmax=None, tol=1e-3):
    """面心落在给定长方体范围内的面（每一维都可以传 None 表示不限）。

    对应"左上角那一片""x 在 0~50 且 z 在 100 以上的面"。
    """
    lo = (xmin, ymin, zmin)
    hi = (xmax, ymax, zmax)
    out = []
    for f in body.Faces:
        c = face_center(f)
        ok = True
        for i in range(3):
            if lo[i] is not None and c[i] < lo[i] - tol:
                ok = False
                break
            if hi[i] is not None and c[i] > hi[i] + tol:
                ok = False
                break
        if ok:
            out.append(f)
    return out


def match_faces(body, rule, exclude=None):
    """按一条规则挑面。rule 是 dict，支持的键可以任意组合（组合即取交集）：

      normal    : "x"/"y"/"z" 或 (nx,ny,nz) —— 法向朝向
      sign      : +1 / -1（配合 normal，默认 +1）
      at        : (轴, 值)          —— 面心在该轴坐标等于该值
      between   : (轴, lo, hi)      —— 面心在该轴坐标落在区间内
      in_box    : (xmin,xmax,ymin,ymax,zmin,zmax)，某一维可为 None
      area_min  : 面积下限 mm^2
      area_max  : 面积上限 mm^2
      kind      : "plane" / "cylinder" / ...
      loops     : 边界环数量（1 = 简单面；2 = 中间有洞/被"盖章"的面）
      point     : (x,y,z)           —— 包含该点的面
      nearest   : (x,y,z)           —— 离该点最近的面
      rest      : True              —— exclude 之后剩下的所有面（兜底 wall 用）
      all       : True              —— 所有面
      tol       : 位置容差 mm（默认 1e-3）

    exclude 是"已经被前面的规则用掉"的面集合（{face_key: 1}）。
    单次遍历 body.Faces 完成判定，避免重复枚举时拿到不同的包装对象。
    """
    tol = rule.get("tol", 1e-3)

    point_keys = None
    if "point" in rule:
        p = rule["point"]
        point_keys = {}
        for f in face_at_point(body, p[0], p[1], p[2]):
            point_keys[_face_key(f)] = 1

    nearest_key = None
    if "nearest" in rule:
        p = rule["nearest"]
        nf = nearest_face(body, p[0], p[1], p[2])
        nearest_key = _face_key(nf) if nf is not None else None

    d = None
    if "normal" in rule:
        nd = rule["normal"]
        d = nd if isinstance(nd, (tuple, list)) else _dir_vector(nd)
        L = (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) ** 0.5
        if L > 0:
            d = (d[0] / L, d[1] / L, d[2] / L)
    sign = rule.get("sign", 1)
    kind = str(rule["kind"]).lower() if "kind" in rule else None
    at_i = at_v = None
    if "at" in rule:
        at_i = _axis_index(rule["at"][0])
        at_v = rule["at"][1]
    bt_i = bt_lo = bt_hi = None
    if "between" in rule:
        bt_i = _axis_index(rule["between"][0])
        bt_lo = rule["between"][1]
        bt_hi = rule["between"][2]
    box_lo = box_hi = None
    if "in_box" in rule:
        b = rule["in_box"]
        box_lo = (b[0], b[2], b[4])
        box_hi = (b[1], b[3], b[5])
    a_min = rule.get("area_min")
    a_max = rule.get("area_max")
    want_loops = rule.get("loops")
    if want_loops is not None:
        want_loops = int(want_loops)
    plain_rest = bool(rule.get("rest")) and not _rule_filtered(rule)
    take_all = bool(rule.get("all")) and not _rule_filtered(rule)

    out = []
    for f in body.Faces:
        key = _face_key(f)
        if exclude is not None and key in exclude:
            continue
        if plain_rest or take_all:
            out.append(f)
            continue
        c = face_center(f)
        if kind is not None and face_kind(f) != kind:
            continue
        if want_loops is not None:
            try:
                if len(list(_shape_of(f).Loops)) != want_loops:
                    continue
            except:
                continue
        if d is not None:
            n = face_normal(f)
            if n is None:
                continue
            dot = n[0] * d[0] + n[1] * d[1] + n[2] * d[2]
            if (sign >= 0 and dot < 0.99) or (sign < 0 and dot > -0.99):
                continue
        if at_i is not None and abs(c[at_i] - at_v) > tol:
            continue
        if bt_i is not None and (c[bt_i] < bt_lo - tol or c[bt_i] > bt_hi + tol):
            continue
        if box_lo is not None:
            inside = True
            for i in range(3):
                if box_lo[i] is not None and c[i] < box_lo[i] - tol:
                    inside = False
                    break
                if box_hi[i] is not None and c[i] > box_hi[i] + tol:
                    inside = False
                    break
            if not inside:
                continue
        if a_min is not None or a_max is not None:
            a = face_area(f)
            if a_min is not None and a < a_min - 1e-6:
                continue
            if a_max is not None and a > a_max + 1e-6:
                continue
        if point_keys is not None and key not in point_keys:
            continue
        if nearest_key is not None and key != nearest_key:
            continue
        out.append(f)
    return out


def name_faces_by_rules(body, rules, tol=1e-3):
    """按规则表批量命名边界——"把自然语言描述翻成命名选择"的主入口。

    rules 是 (名字, 规则 dict) 的列表，按顺序处理：先匹配的面会被后面的规则排除，
    所以 {"rest": True} 放在最后就是"剩下的都算 wall"。

        name_faces_by_rules(body, [
            ("inlet",       {"normal": "x", "sign": -1}),
            ("outlet",      {"normal": "x", "sign": +1}),
            ("symmetry",    {"at": ("y", 0.0)}),
            ("heated_wall", {"normal": "z", "sign": -1,
                             "between": ("x", 30.0, 70.0)}),
            ("wall",        {"rest": True}),
        ])

    返回 {名字: 面数}；面数为 0 的规则不会创建命名选择（避免空分区）。
    """
    used = {}
    counts = {}
    for name, rule in rules:
        r = dict(rule)
        if "tol" not in r:
            r["tol"] = tol
        faces = match_faces(body, r, exclude=used)
        counts[name] = len(faces)
        if faces:
            name_faces(name, faces)
            for f in faces:
                used[_face_key(f)] = 1
    return counts


# ---------------------------------------------------------------------------
# 面分割 / 体分割：让"一张大面分几段分别命名"成为可能
# ---------------------------------------------------------------------------

def split_face_by_body(face, cutter_body, cutter_face=None):
    """用**另一个体**的表面当刀，把目标面切开（在面上"盖章"出交线围成的区域）。

    实测要点：刀具体必须传**面选择**，不能传体选择——
    传整个体时 `SplitFace.ByCutter` 返回 `Success=False` 且什么都不做；
    传刀具的侧面（如圆柱的柱面）就成功：40x40 的板底被 r=5 的圆柱切出
    一张 78.54 mm² 的圆补丁 + 一张 1521.46 mm²、带内环(loops=2)的面。

    不指定 cutter_face 时，会依次拿 cutter_body 的每张面去试，返回第一张成功的。
    返回起作用的那张刀具面。
    """
    if cutter_face is not None:
        candidates = [cutter_face]
    else:
        candidates = list(cutter_body.Faces)
    for cf in candidates:
        if cf is None:
            continue
        try:
            res = SplitFace.ByCutter(Selection.Create(face),
                                     Selection.Create(cf),
                                     SplitFaceOptions())
        except:
            continue
        try:
            if res is not None and res.Success:
                return cf
        except:
            continue
    raise RuntimeError("split_face_by_body: no face of that body splits the target face")


def split_face_by_points(face, p1, p2):
    """用面上的两点连成一条直线，把这张面切开。

    实测：ByTwoPoints 的三参形式可用。例：100x40 的底面用 (50,0,0)-(50,40,0)
    切开后变成两张 2000 mm^2 的面，面心分别在 (25,20,0) 与 (75,20,0)。

    两点都要落在这张面上。**切完原面对象可能失效，要重新取面。**
    """
    return SplitFace.ByTwoPoints(Selection.Create(face),
                                 Point.Create(MM(p1[0]), MM(p1[1]), MM(p1[2])),
                                 Point.Create(MM(p2[0]), MM(p2[1]), MM(p2[2])))


def split_face_by_line(face, axis="x", value=0.0, tol=1e-6):
    """把一张面沿"axis = value"这条线切开（自动在该面内算出切分线的两个端点）。

    只对**轴对齐的平面面**可靠。典型用法（一个底面上分两段热流）：

        bottom = faces_by_normal(body, "z", -1)[0]
        split_face_by_line(bottom, axis="x", value=50.0)
        # 底面现在是两张 2000 mm^2 的面，面心 (25,20,0) / (75,20,0)，
        # 之后用 {"in_box": (None, 50, ...)} 就能只选到其中一段
    """
    a_i = _axis_index(axis)
    lo, hi = face_extent(face)
    if value < lo[a_i] - tol or value > hi[a_i] + tol:
        raise ValueError("split_face_by_line: %s=%.3f is outside the face range (%.3f ~ %.3f)"
                         % (axis, value, lo[a_i], hi[a_i]))
    others = [i for i in range(3) if i != a_i]
    others.sort(key=lambda i: hi[i] - lo[i], reverse=True)
    j = others[0]
    p1 = [0.0, 0.0, 0.0]
    p2 = [0.0, 0.0, 0.0]
    for k in range(3):
        if k == j:
            p1[k] = lo[k]
            p2[k] = hi[k]
        elif k == a_i:
            p1[k] = value
            p2[k] = value
        else:
            mid = (lo[k] + hi[k]) / 2.0
            p1[k] = mid
            p2[k] = mid
    return split_face_by_points(face, p1, p2)


def split_body_by_plane(body, axis="x", value=0.0):
    """用一个坐标平面把实体切成两个体。

    实测：100x40x40 的体在 x=50 处切开 → 2 个体，各 6 个面。
    """
    d = _dir_vector(axis)
    pl = Plane.Create(Frame.Create(
        Point.Create(MM(value * d[0]), MM(value * d[1]), MM(value * d[2])),
        Direction.Create(d[0], d[1], d[2])))
    return SplitBody.ByCutter(Selection.Create(body), pl, None)


# ---------------------------------------------------------------------------
# 成对边界条件：交界面 / 内部挡板 / 周期面
#
# 这几类边界条件的难点不在"起名字"，而在**几何前提**：
#   * 交界面（共轭传热）：两个体必须在同一位置各有一张面，且两张面重合
#   * 内部挡板 / 多孔跳变 / 风扇面：面必须在**体内部**，而实心体内部本来没有面，
#     所以要先把体切开
#   * 周期边界：两侧面的形状/面积必须对应得上
# 下面这些函数把"找面 + 配对 + 命名"一次做完，并返回数量供脚本自检。
# ---------------------------------------------------------------------------

def faces_match(face_a, face_b, tol=1e-3):
    """两张面是否**几何对应**：面积相同、包围盒三个方向的尺寸都相同。

    用来确认周期边界的两侧面确实配得上（位置可以不同，形状必须一致）。
    """
    aa = face_area(face_a)
    ab = face_area(face_b)
    if abs(aa - ab) > tol * max(1.0, aa):
        return False
    la, ha = face_extent(face_a)
    lb, hb = face_extent(face_b)
    for k in range(3):
        if abs((ha[k] - la[k]) - (hb[k] - lb[k])) > tol:
            return False
    return True


def find_coincident_pairs(body_a, body_b, tol=1e-3):
    """找出两个体之间所有**重合**的面（面心与面积都吻合），返回 [(face_a, face_b), ...]。

    这就是交界面 / 内部挡板的基础：两个体在同位置各有一张面。
    """
    pairs = []
    for fa in body_a.Faces:
        ca = face_center(fa)
        aa = face_area(fa)
        for fb in body_b.Faces:
            cb = face_center(fb)
            if abs(ca[0] - cb[0]) > tol or abs(ca[1] - cb[1]) > tol or abs(ca[2] - cb[2]) > tol:
                continue
            ab = face_area(fb)
            if abs(aa - ab) > tol * max(1.0, aa):
                continue
            pairs.append((fa, fb))
    return pairs


def _face_center_key(c, tol):
    """把面心按容差取整，作为哈希键（避免 O(N*M) 的两两比较）。"""
    return (int(round(c[0] / tol)), int(round(c[1] / tol)), int(round(c[2] / tol)))


def _all_faces(target):
    """把一个体 / 一串体 展开成面列表。"""
    out = []
    for b in _as_body_list(target):
        try:
            out.extend(list(b.Faces))
        except:
            pass
    return out


def _face_contains(big, small, tol=1e-3):
    """small 是不是**贴在 big 上、并且被 big 包住**（用来处理被切断的分段交界面）。

    典型场景：管束里插了折流板，壳程流体的管孔壁被切成好几段，而管壁的外表面
    还是完整的一根 100mm 圆柱面 —— 整面面积对不上，但每一段都确实贴在它上面。
    """
    if face_kind(big) != face_kind(small):
        return False
    # 大面必须是一张**没有内环**的面。带内环的面（板端面上被通道穿出的那些孔）
    # 包围盒照样能罩住小面，但小面其实落在孔里、并不贴着材料 ——
    # 实测：PCHE 里流体域的半圆端面就被误配到了固体端面上（多出 4 对假交界面、
    # 面积多算 6.28mm²）。带孔的面直接不做包含判定，这类假阳性一刀切掉。
    try:
        if len(list(_shape_of(big).Loops)) != 1:
            return False
    except:
        return False
    lb, hb = face_extent(big)
    ls, hs = face_extent(small)
    for k in range(3):
        if ls[k] < lb[k] - tol or hs[k] > hb[k] + tol:
            return False
    kind = face_kind(big)
    cb = face_center(big)
    cs = face_center(small)
    if kind == "plane":
        nb = face_normal(big)
        ns = face_normal(small)
        if nb is None or ns is None:
            return False
        if abs(nb[0] * ns[0] + nb[1] * ns[1] + nb[2] * ns[2]) < 1.0 - 1e-6:
            return False
        off = (nb[0] * (cs[0] - cb[0]) + nb[1] * (cs[1] - cb[1]) + nb[2] * (cs[2] - cb[2]))
        return abs(off) <= tol
    if kind == "cylinder":
        # 不依赖 Geometry 的成员（反射取不到 Radius/Frame 时整条判定会静默失败），
        # 改用**包围盒截面比对**：取大面最长的那个方向当轴向，剩下两个方向的尺寸
        # 必须和小面一致（同轴同半径才会一致；小面套在大半径圆柱里就一致不了）。
        ex = [hb[k] - lb[k] for k in range(3)]
        ax = 0
        for k in (1, 2):
            if ex[k] > ex[ax]:
                ax = k
        for k in range(3):
            if k == ax:
                continue
            if abs((hs[k] - ls[k]) - ex[k]) > max(tol, ex[k] * 1e-3):
                return False
        return True
    return False


def find_coincident_pairs_multi(bodies_a, bodies_b, tol=1e-3, allow_split=False):
    """跨**多个体**找出成对的交界面（面心与面积都吻合），返回 [(face_a, face_b), ...]。

    和单体的 `find_coincident_pairs` 相比：两侧都可以是一串体 —— 管束里
    "壳程流体上的 12 个管孔壁" 对 "12 个管壁体的外表面" 就是这种。
    用面心取整做哈希索引，不做 O(N*M) 的两两比较；同一边的每张面只会被配一次。

    `allow_split=True` 时再做**第二遍**：处理"一侧一张面、另一侧被切成几段"的情况
    （`_face_contains`）。典型场景是管束里插了折流板 —— 壳程的管孔壁被切成 3 段，
    而管壁外表面仍是完整的 100mm 圆柱面，整面面积对不上，只有做包含判定才配得上。
    第二遍是 O(未配上的面 × 另一侧的面)，模型大的时候会慢一些。
    """
    fa_list = _all_faces(bodies_a)
    fb_list = _all_faces(bodies_b)
    index = {}
    for fb in fb_list:
        index.setdefault(_face_center_key(face_center(fb), tol), []).append(fb)
    pairs = []
    used_a = {}
    used_b = {}
    for fa in fa_list:
        aa = face_area(fa)
        for fb in index.get(_face_center_key(face_center(fa), tol), []):
            kb = _face_key(fb)
            if kb in used_b:
                continue
            ab = face_area(fb)
            if abs(aa - ab) > tol * max(1.0, aa):
                continue
            used_a[_face_key(fa)] = 1
            used_b[kb] = 1
            pairs.append((fa, fb))
            break

    if allow_split:
        # 分段接触：小面贴在大面上。**大面可以被多张小面共用**（一根管壁外表面
        # 会被折流板切成好几段的壳程孔壁同时贴着），所以这里只对 A 侧去重。
        for fa in fa_list:
            ka = _face_key(fa)
            if ka in used_a:
                continue
            for fb in fb_list:
                if _face_contains(fb, fa, tol):
                    used_a[ka] = 1
                    pairs.append((fa, fb))
                    break
    return pairs


def interface_report(bodies_a, bodies_b, tol=1e-3, tol_loose=1.0, find_suspects=False,
                     allow_split=False):
    """交界面**配平自检**，返回 dict：

      pairs      配上的面对数
      split_pairs allow_split=True 时，其中"小面贴大面"（分段交界面）的条数
      area_a     配上的面在 A 侧的面积合计（mm²）
      area_b     配上的面在 B 侧的面积合计
      coverage   min(area_a, area_b) / max(...) —— 两侧覆盖比
      balanced   两侧面积是否相等（严格判据；分段交界面天然 <1，见下）
      suspects   [(face_a, face_b, area_a, area_b), ...]，**默认不查**（find_suspects=True 才填）
      faces_a / faces_b  两侧各自的面数（供参考，不是所有面都该配上）

    为什么要它：管束里几十张面配对，眼睛是数不清的；`pairs` 对不对、`area_a` 与
    `area_b` 是否相等，这两条就能把"少配了一根管""一侧多出一段"全部抓出来。
    实测：12 根管的 CHT 模型两侧各 37699.11 mm²、`balanced=True`；故意把管壁做长
    10mm 时两侧立刻变成 3455.75 vs 3141.59 一根、`balanced=False`。

    **分段交界面要 `allow_split=True`**：管束里插了折流板之后，壳程那侧的管孔壁被
    切成几段（每根管少 2mm×折流板数），而管壁外表面还是完整的 100mm 圆柱面 ——
    严格面积判据下 `balanced` 永远是 False（实测 coverage ≈ 0.96，缺的 4% 正是折流板
    贴住的那两小段）。这时候看 `coverage`，别只看 `balanced`。

    `suspects` 为什么默认关：它的判据是"面心很接近但面积差 >1%"，而**同心的圆盘和圆环
    天然会落进来**——实测在一个完全正确的模型里它报了 36 条假阳性
    （管壁端面环 28.27 mm² vs 管程端面圆盘 50.27 mm²，圆心正好重合）。
    只有在你怀疑"一侧一张面、另一侧被切成两张"时才打开它，而且**要一条条看**。
    """
    pairs = find_coincident_pairs_multi(bodies_a, bodies_b, tol)
    area_a = 0.0
    area_b = 0.0
    for (fa, fb) in pairs:
        area_a += face_area(fa)
        area_b += face_area(fb)
    hi = max(area_a, area_b)
    coverage = 0.0 if hi <= 0.0 else min(area_a, area_b) / hi

    # 分段接触单独统计，**不混进 area_a/area_b/balanced** —— 那条判据的语义是
    # "整面对整面、两侧面积相等"，混进来会让它没法用。
    split_pairs = 0
    split_area_a = 0.0
    split_area_b = 0.0
    if allow_split:
        exact = {}
        for (fa, fb) in pairs:
            exact[(_face_key(fa), _face_key(fb))] = 1
        allp = find_coincident_pairs_multi(bodies_a, bodies_b, tol, allow_split=True)
        seen_a = {}
        seen_b = {}
        for (fa, fb) in allp:
            if (_face_key(fa), _face_key(fb)) in exact:
                continue
            split_pairs += 1
            ka = _face_key(fa)
            if ka not in seen_a:
                seen_a[ka] = 1
                split_area_a += face_area(fa)
            kb = _face_key(fb)
            if kb not in seen_b:
                seen_b[kb] = 1
                split_area_b += face_area(fb)

    suspects = []
    if find_suspects:
        fa_list = _all_faces(bodies_a)
        fb_list = _all_faces(bodies_b)
        index = {}
        for fb in fb_list:
            index.setdefault(_face_center_key(face_center(fb), tol_loose), []).append(fb)
        for fa in fa_list:
            ca = face_center(fa)
            aa = face_area(fa)
            kx, ky, kz = _face_center_key(ca, tol_loose)
            best = None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for fb in index.get((kx + dx, ky + dy, kz + dz), []):
                            cb = face_center(fb)
                            d = max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1]), abs(ca[2] - cb[2]))
                            if d <= tol_loose and (best is None or d < best[0]):
                                best = (d, fb)
            if best is None:
                continue
            ab = face_area(best[1])
            if abs(aa - ab) > 0.01 * max(1.0, aa):
                suspects.append((fa, best[1], aa, ab))

    return {
        "pairs": len(pairs),
        "split_pairs": split_pairs,
        "split_area_a": split_area_a,
        "split_area_b": split_area_b,
        "area_a": area_a,
        "area_b": area_b,
        "coverage": coverage,
        "balanced": len(pairs) > 0 and abs(area_a - area_b) <= tol * max(1.0, area_a),
        "suspects": suspects,
        "faces_a": len(_all_faces(bodies_a)),
        "faces_b": len(_all_faces(bodies_b)),
    }


def _face_body_map(bodies):
    """{面 Moniker: 体} —— 把面归属到体。

    不要用 `face.Body`：DesignFace 上的这个属性取到的是**原始 Modeler Body**，
    它的 Moniker 和 DesignBody 的对不上（实测逐体统计因此全是 0）。
    自己按面建索引最稳。
    """
    m = {}
    for b in _as_body_list(bodies):
        try:
            for f in b.Faces:
                m[_face_key(f)] = b
        except:
            pass
    return m


def interface_pairing_by_body(bodies_a, bodies_b, tol=1e-3):
    """逐体统计配对情况，返回 [(体名, 面数, 面积 mm²), ...]（按 bodies_a 的传入顺序）。

    用来回答"这 12 根管子是不是每根都配上了"——只看到一个 `pairs=11` 是查不出
    是哪一根没配的，这个表能直接点名。
    """
    pairs = find_coincident_pairs_multi(bodies_a, bodies_b, tol)
    fmap = _face_body_map(list(_as_body_list(bodies_a)) + list(_as_body_list(bodies_b)))
    got = {}
    for (fa, fb) in pairs:
        for f in (fa, fb):
            b = fmap.get(_face_key(f))
            if b is None:
                continue
            k = _body_key(b)
            rec = got.get(k)
            if rec is None:
                got[k] = [0, 0.0]
                rec = got[k]
            rec[0] += 1
            rec[1] += face_area(f)
    out = []
    for b in _as_body_list(bodies_a):
        rec = got.get(_body_key(b))
        out.append((_ascii(b.Name), 0 if rec is None else rec[0],
                    0.0 if rec is None else rec[1]))
    return out


def interface_gaps(bodies_a, bodies_b, tol=1e-3):
    """**一张交界面面都没配上**的体 —— 返回 {"a": [体, ...], "b": [体, ...]}。

    这是最该盯的一条：管束里某根管子位置放错、或者某个固体域根本没贴上流体域，
    `pairs` 只会少一个数（12 变成 11），而这里会把那根管子**点名**出来。
    """
    pairs = find_coincident_pairs_multi(bodies_a, bodies_b, tol)
    fmap = _face_body_map(list(_as_body_list(bodies_a)) + list(_as_body_list(bodies_b)))
    hit = {}
    for (fa, fb) in pairs:
        for f in (fa, fb):
            b = fmap.get(_face_key(f))
            if b is not None:
                hit[_body_key(b)] = 1
    gaps = {"a": [], "b": []}
    for key, group in (("a", _as_body_list(bodies_a)), ("b", _as_body_list(bodies_b))):
        for b in group:
            if _body_key(b) not in hit:
                gaps[key].append(b)
    return gaps


def interface_graph(bodies, tol=1e-3):
    """体与体之间的**共享面邻接表**：{体键: [(邻体, 面数, 面积 mm²), ...]}。

    用来回答"这个体到底跟谁贴着"。管束里一根管子该贴 2 个（壳程流体 + 管程流体），
    折流板该贴 3 个（壳程流体 + 它穿过的每根管壁）。返回的是 dict，键是 Moniker，
    值的第一项是体对象本身不方便序列化，所以提供 `interface_neighbours()` 这个名字列表版。
    """
    items = _as_body_list(bodies)
    fmap = _face_body_map(items)
    pairs = find_coincident_pairs_multi(items, items, tol)
    acc = {}
    for (fa, fb) in pairs:
        ba = fmap.get(_face_key(fa))
        bb = fmap.get(_face_key(fb))
        if ba is None or bb is None:
            continue
        ka = _body_key(ba)
        kb = _body_key(bb)
        if ka == kb:
            continue
        a = acc.setdefault(ka, {})
        rec = a.get(kb)
        if rec is None:
            a[kb] = [0, 0.0]
            rec = a[kb]
        rec[0] += 1
        rec[1] += face_area(fa)
    return acc


def interface_neighbours(bodies, tol=1e-3):
    """和 `interface_graph` 同源，但返回 {(体名, 序号): [(邻体名, 面数, 面积), ...]}。

    体名可能重复（12 根都叫 TubeWall），所以键里带一个序号。
    """
    items = _as_body_list(bodies)
    graph = interface_graph(items, tol)
    order = {}
    names = []
    for i in range(len(items)):
        b = items[i]
        order[_body_key(b)] = i
        nm = _ascii(b.Name)
        if names.count(nm) > 0:
            nm = "%s#%d" % (nm, i)
        names.append(nm)
    out = {}
    for i in range(len(items)):
        b = items[i]
        nb = graph.get(_body_key(b), {})
        row = []
        for kb in nb.keys():
            j = order.get(kb)
            if j is None:
                continue
            row.append((names[j], nb[kb][0], nb[kb][1]))
        out[names[i]] = row
    return out


def cht_check(layers, tol=1e-3, allow_split=True, min_coverage=0.9):
    """多体共轭传热的**自动分层检查**。

    layers 是有序的 [(层名, [体...]), ...]。顺序只影响报告顺序，不影响结果。
    自动做四件事，**不需要你指定哪两层相接**：

      1. 每一对层之间算交界面：`pairs` / `split_pairs` / 两侧面积 / `coverage` / `balanced`
      2. 把**一张交界面都没有**的层对列出来（"这两层根本没接触"）
      3. 逐体统计**邻居层**：只贴到 1 层的体在外边界上；**一层都贴不到的体直接点名**
      4. 汇总每层的体数 / 面数 / 总面积

    参数 `allow_split=True`（默认）会启用分段交界面的包含式匹配 —— 带折流板的模型
    必须用它，否则壳程那侧被切成几段的管孔壁一个都配不上。`min_coverage` 是判定
    "这两层算不算真接触"的覆盖比下限（默认 0.9）：分段交界面天然不到 1
    （实测带折流板模型 coverage ≈ 0.96，缺的 4% 正是折流板贴住的那两小段）。

    返回 dict::

        {
          "pairs": {(层a, 层b): report},                 # 每个层对的 interface_report
          "touching": [(层a, 层b, 面数, coverage), ...],  # 相接的层对
          "not_touching": [(层a, 层b), ...],             # 没接触的层对
          "isolated_bodies": [(层名, 体名), ...],         # 一张交界面都没配上的体
          "layer_stats": {层名: {"bodies":…, "faces":…, "area":…}},
          "low_coverage": [(层a, 层b, coverage), ...],   # 接触了但覆盖不足
          "ok": True/False,                              # 无孤立体 且 无覆盖不足
        }
    """
    norm = []
    for pair in layers:
        name = str(pair[0])
        norm.append((name, _as_body_list(pair[1])))
    names = [n for (n, _b) in norm]

    pairs_report = {}
    touching = []
    not_touching = []
    low_coverage = []
    for i in range(len(norm)):
        for j in range(i + 1, len(norm)):
            na, ba = norm[i]
            nb, bb = norm[j]
            rep = interface_report(ba, bb, tol, allow_split=allow_split)
            pairs_report[(na, nb)] = rep
            if rep["pairs"] > 0 or rep["split_pairs"] > 0:
                cnt = rep["pairs"] + rep["split_pairs"]
                arc = rep["area_a"] + rep["split_area_a"]
                touching.append((na, nb, cnt, arc))
                # 整面对整面但不配平 -> 记一笔；分段接触不看 area 判据（两侧本来就不等）
                if rep["pairs"] > 0 and rep["split_pairs"] == 0 and not rep["balanced"]:
                    low_coverage.append((na, nb, rep["coverage"]))
            else:
                not_touching.append((na, nb))

    isolated = []
    for (name, bodies) in norm:
        if not bodies:
            continue
        others = []
        for (n2, b2) in norm:
            if n2 != name:
                others.extend(b2)
        if not others:
            continue
        fmap = _face_body_map(list(bodies) + list(others))
        hit = {}
        for (fa, fb) in find_coincident_pairs_multi(bodies, others, tol,
                                                    allow_split=allow_split):
            for f in (fa, fb):
                b = fmap.get(_face_key(f))
                if b is not None:
                    hit[_body_key(b)] = 1
        for b in bodies:
            if _body_key(b) not in hit:
                isolated.append((name, _ascii(b.Name)))

    layer_stats = {}
    for (name, bodies) in norm:
        nf = 0
        area = 0.0
        for b in bodies:
            try:
                for f in b.Faces:
                    nf += 1
                    area += face_area(f)
            except:
                pass
        layer_stats[name] = {"bodies": len(bodies), "faces": nf, "area": area}

    return {
        "pairs": pairs_report,
        "touching": touching,
        "not_touching": not_touching,
        "isolated_bodies": isolated,
        "layer_stats": layer_stats,
        "low_coverage": low_coverage,
        "ok": (len(isolated) == 0 and len(low_coverage) == 0),
    }


def half_round_channel(radius, length, origin, axis="x", flat="+y", name="Channel"):
    """**D 形（半圆）通道体** —— 平的一侧朝 flat 指定的方向，弧朝另一侧。

    origin 是**平的那一面**的中心；通道从该面向 flat 的反方向鼓出 radius。
    实测用法（PCHE 的刻槽通道）：平的一侧朝上，就是半圆槽 + 上方盖板的形式。

    **为什么要绕一圈**：`cut=True` 是**全局**的，没法只切某一个体 —— 直接在目标位置
    把整圆柱砍一半，会把周围固体一起砍掉。而 `move()` 是刚体变换、**不会并集**。
    所以这里先把整圆柱造在**文档包围盒之外的空白处**，在那儿切掉一半（那时文档里
    只有它），再搬回目标位置。这个套路在 `_copy_body` 里也用过。

    限制：`axis` 不能与 `flat` 的方向相同（比如 axis="y" 配 flat="+y"）。
    """
    ensure_document()
    a = str(axis).lower()
    if a not in ("x", "y", "z"):
        raise ValueError("half_round_channel: axis must be 'x'/'y'/'z'")
    f = str(flat).lower()
    if f not in ("+y", "-y", "+z", "-z"):
        raise ValueError("half_round_channel: flat must be '+y'/'-y'/'+z'/'-z'")
    fdir = 1.0 if f[0] == "+" else -1.0
    facis = f[1]
    if facis == a:
        raise ValueError("half_round_channel: axis and flat must be different directions")

    x0, y0, z0 = origin
    # 1) 挑一块空白：沿 +X 推到文档包围盒之外
    hi = None
    for b in all_bodies():
        e = body_extent(b, "x")
        if hi is None or e[1] > hi:
            hi = e[1]
    shift_x = 0.0 if hi is None else (hi + 20.0 - x0)
    ox = [x0 + shift_x, y0, z0]

    c = cylinder(radius, length, origin=(ox[0], ox[1], ox[2]), axis=a,
                 name=name, separate=True)

    # 2) 在空白处切掉 flat 那一半：盒子只罩住"要切走"的那半边
    ia = _axis_index(a)
    ifa = _axis_index(facis)
    it = 3 - ia - ifa                      # 与两者都垂直的那一维
    lo = [0.0, 0.0, 0.0]
    hi3 = [0.0, 0.0, 0.0]
    lo[ia] = ox[ia] - 10.0
    hi3[ia] = ox[ia] + float(length) + 10.0
    if fdir > 0:
        lo[ifa] = ox[ifa]
        hi3[ifa] = ox[ifa] + 2.0 * radius + 1.0
    else:
        lo[ifa] = ox[ifa] - 2.0 * radius - 1.0
        hi3[ifa] = ox[ifa]
    lo[it] = ox[it] - radius - 1.0
    hi3[it] = ox[it] + radius + 1.0
    box(hi3[0] - lo[0], hi3[1] - lo[1], hi3[2] - lo[2],
        origin=(lo[0], lo[1], lo[2]), cut=True)

    # 3) 搬回目标位置（刚体变换，不会并集）
    if abs(shift_x) > 1e-9:
        move(c, -shift_x, 0.0, 0.0)
    return c


def name_interfaces_multi(bodies_a, bodies_b, prefix="interface", grouped=True,
                          tol=1e-3, allow_split=False):
    """跨**多个体**命名交界面，返回配对数。

    grouped=True（默认）：两侧各做成**一个**命名选择 —— `<prefix>_a` / `<prefix>_b`。
        管束那种几十张面配对的场景，Fluent 里要的就是"一对 zone"，而不是几十对。
        B 侧会**按面去重**（分段接触时一张大面会被好几张小面共用）。
    grouped=False：逐对命名 `<prefix>_a1` / `<prefix>_b1` …（需要逐管单独控制时用）

    `allow_split=True` 时把"小面贴在大面上"的分段接触也算进来 —— 带折流板的模型
    必须开，否则壳程那边被折流板切开的管孔壁一张都不会被命名。

    典型用法（壳程流体 ↔ 管壁固体）：

        n = name_interfaces_multi(shell_side, tube_walls, "shell_tube", allow_split=True)
        r = interface_report(shell_side, tube_walls, allow_split=True)
        assert r["pairs"] + r["split_pairs"] > 0, r
    """
    pairs = find_coincident_pairs_multi(bodies_a, bodies_b, tol, allow_split=allow_split)
    if not pairs:
        return 0
    if grouped:
        a_faces = []
        b_faces = []
        seen_b = {}
        for (fa, fb) in pairs:
            a_faces.append(fa)
            kb = _face_key(fb)
            if kb not in seen_b:
                seen_b[kb] = 1
                b_faces.append(fb)
        name_faces("%s_a" % prefix, a_faces)
        name_faces("%s_b" % prefix, b_faces)
    else:
        for idx in range(len(pairs)):
            fa, fb = pairs[idx]
            tag = "_%d" % (idx + 1)
            name_faces("%s_a%s" % (prefix, tag), [fa])
            name_faces("%s_b%s" % (prefix, tag), [fb])
    return len(pairs)


def name_face_pair(name_a, name_b, face_a, face_b):
    """给一对面分别命名（周期 / 交界面 / 内部挡板都要成对命名）。"""
    name_faces(name_a, [face_a])
    name_faces(name_b, [face_b])
    return (name_a, name_b)


def name_interfaces(body_a, body_b, prefix="interface", tol=1e-3):
    """把两个体之间所有重合面自动配对命名：<prefix>_a / <prefix>_b（多对时带 _1 _2）。

    典型场景：流体域与固体域的共轭传热交界面。返回配对数。
    """
    pairs = find_coincident_pairs(body_a, body_b, tol)
    for idx in range(len(pairs)):
        fa, fb = pairs[idx]
        tag = "" if len(pairs) == 1 else "_%d" % (idx + 1)
        name_faces("%s_a%s" % (prefix, tag), [fa])
        name_faces("%s_b%s" % (prefix, tag), [fb])
    return len(pairs)


def name_internal_baffle(body, axis="x", value=0.0, name="baffle", tol=1e-3):
    """把一个体沿 axis=value 切开，并把切出来的两张内部重合面成对命名。

    对应内部挡板 / 多孔跳变 / 风扇面这类"体内部的面"——实心体内部本来没有面，
    必须先切分。返回被命名的两张面 (face_a, face_b)。

    扫描时限定在切分前那个体的包围盒内，避免误抓同一坐标上别的体的面。
    """
    a_i = _axis_index(axis)
    lo, hi = body_extent(body, axis)
    if value < lo - tol or value > hi + tol:
        raise ValueError("name_internal_baffle: %s=%.3f is outside the body range (%.3f ~ %.3f)"
                         % (axis, value, lo, hi))
    box_lo = list(body_extent(body, 0)) + []
    ext0 = body_extent(body, "x")
    ext1 = body_extent(body, "y")
    ext2 = body_extent(body, "z")
    lo3 = (ext0[0], ext1[0], ext2[0])
    hi3 = (ext0[1], ext1[1], ext2[1])

    split_body_by_plane(body, axis=axis, value=value)

    found = []
    for b in GetRootPart().Bodies:
        for f in b.Faces:
            c = face_center(f)
            if abs(c[a_i] - value) > tol:
                continue
            inside = True
            for k in range(3):
                if c[k] < lo3[k] - tol or c[k] > hi3[k] + tol:
                    inside = False
                    break
            if inside:
                found.append(f)
    if len(found) != 2:
        raise RuntimeError("name_internal_baffle: expected 2 coincident faces, found %d" % len(found))
    return name_face_pair(name + "_a", name + "_b", found[0], found[1])


# ---------------------------------------------------------------------------
# 保存与输出
# ---------------------------------------------------------------------------

def save_model(path):
    """另存为 .scdocx（已存在则先删掉，避免覆盖提示）。"""
    try:
        from System.IO import File
        if File.Exists(path):
            File.Delete(path)
    except:
        pass
    DocumentSave.Execute(path)
    return path


def group_summary(part=None):
    """当前文档所有命名选择的 [(名字, 成员数), ...]。"""
    if part is None:
        part = GetRootPart()
    out = []
    for g in NamedSelection.GetGroups():
        out.append((str(g.Name), int(g.Members.Count)))
    return out


def _ascii(text):
    """把名字转成纯 ASCII 字符串。

    默认名是本地化的（中文界面下是中文），直接参与 `"%s" % name` 会在格式化阶段
    就抛 UnicodeEncodeError —— 那一步发生在 _safe_print 的保护之外，会把整个脚本干掉。
    """
    try:
        raw = text if isinstance(text, str) else str(text)
        return raw.encode("ascii", "replace")
    except:
        return "<name>"


def _safe_print(text):
    try:
        print(text)
    except:
        try:
            print(text.encode("ascii", "replace"))
        except:
            pass


def finish(path, body=None):
    """收尾：保存 -> 打成功哨兵 -> 打印自检摘要。

    成功哨兵 <<<SCDM_OK>>> 是 Invoke-Scdm.ps1 判定成功的依据，
    所以它必须在任何可能失败的操作之前打印。
    """
    save_model(path)
    print("<<<SCDM_OK>>>")
    print("saved: " + str(path))
    try:
        if body is not None:
            dx, dy, dz = body_size(body)
            _safe_print("[size] %.3f x %.3f x %.3f mm, %d face(s), %d edge(s)"
                        % (dx, dy, dz, len(list(body.Faces)), len(list(body.Edges))))
        for nm, cnt in group_summary():
            _safe_print("[named selection] %s -> %d face(s)" % (_ascii(nm), cnt))
    except:
        print("[warn] summary failed, artifact is still saved")
    return path
