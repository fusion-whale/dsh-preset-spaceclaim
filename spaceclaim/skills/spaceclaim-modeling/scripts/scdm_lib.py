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


def _created_body(res):
    """从命令结果里取新建/被修改的体；不同命令的成员名不一样。

    兜底：如果结果对象取不到体（例如新体与已有体发生了合并/相加），
    就取根零件里最后一个体——对“新建”语义来说它就是刚生成（或被改）的那个。
    """
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
    try:
        bodies = list(GetRootPart().Bodies)
        if bodies:
            return bodies[len(bodies) - 1]
    except:
        pass
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
    res = BlockBody.Create(p1, p2) if et is None else BlockBody.Create(p1, p2, et)
    body = _created_body(res)
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
    res = CylinderBody.Create(c, start, end) if et is None else CylinderBody.Create(c, start, end, et)
    # 注意：CylinderBodyResult 只有 CreatedBodies，没有 CreatedBody
    #（BlockBodyResult / SphereResult 才两个都有），取错会得到
    # "Script failed: 'CylinderBodyResult' object has no attribute 'CreatedBody'"
    body = _created_body(res)
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
         name="Pipe", overshoot=1.0):
    """空心圆管：外圆柱 + 内圆柱布尔减。

    overshoot 是内圆柱两端各多伸出的长度(mm)，保证把管壁切穿干净。
    返回外圆柱那个体（布尔减之后它就是管体本身）。
    """
    if inner_radius >= outer_radius:
        raise ValueError("tube(): inner_radius must be smaller than outer_radius")
    a = axis.lower()
    outer = cylinder(outer_radius, height, origin=origin, axis=a, name=name)
    x0, y0, z0 = origin
    if a == "x":
        cut_origin = (x0 - overshoot, y0, z0)
    elif a == "y":
        cut_origin = (x0, y0 - overshoot, z0)
    else:
        cut_origin = (x0, y0, z0 - overshoot)
    cylinder(inner_radius, height + 2.0 * overshoot, origin=cut_origin, axis=a, cut=True)
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
    for i in range(segs):
        rr = radius1 + (radius2 - radius1) * (i / float(segs))
        p1 = base_pt(i * step)
        p2 = base_pt((i + 1) * step)
        p3 = rim_pt((i + 1) * step, rr)
        if i == 0:
            body = _created_body(CylinderBody.Create(p1, p2, p3))
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
    """正多边形棱柱（单个）。内部走 polygon_prisms，只是包了一层。

    注意：**必须在文档还没有任何实体时调用**（见 polygon_prisms 的说明）。
    """
    return polygon_prisms([{
        "sides": sides, "radius": radius, "height": height,
        "origin": origin, "axis": axis, "name": name,
        "rotation_deg": rotation_deg,
    }])[0]


def polygon_prisms(profiles):
    """一次建多个正多边形棱柱——非圆形截面的管道（六边形、八边形……）。

    profiles 里每个元素是 dict：
        sides        边数（>=3）
        radius       外接圆半径 mm（草图第二点定义的是顶点）
        height       长度 mm
        axis         "x"/"y"/"z"（棱柱轴向）
        origin       底面中心（与 cylinder() 约定一致）
        name         体名
        rotation_deg 绕自身轴额外旋转的角度（可选）

    为什么必须是批量接口（这几条都是实测得出的）：
      * **文档里一旦有实体，再新建草图就会让 SpaceClaim 抛空引用**（脚本直接中止）。
        所以所有草图必须在任何实体存在之前一次画完。
      * 多个**互不重叠**的草图在 Solid 模式下会各自成为一张面（一个表面体带 N 张面）；
        重叠的草图会合并成一张，所以这里自动给每个草图拉开间距。
      * 每拉伸一张面，草图体上剩下的面仍然可用，因此可以逐个拉伸。

    实测：六边形 r=5 h=20 沿 Z + 八边形 r=6 h=15 沿 X → 2 个体，
    分别是 8 面 (10.000 x 8.660 x 20.000) 与 10 面 (15.000 x 12.000 x 11.086)。
    """
    ensure_document()
    existing = GetRootPart().Bodies.Count
    if existing:
        raise RuntimeError(
            "polygon_prisms: the document already has %d body/bodies. Sketch-based profiles "
            "must be created before any solid exists (SpaceClaim 2022 R1 crashes on a new "
            "sketch once a solid is present). Build the polygon ducts first, then add "
            "box/cylinder/tube bodies." % existing)
    if not profiles:
        return []

    spacing = 10.0
    for p in profiles:
        need = float(p.get("radius", 1.0)) * 4.0
        if need > spacing:
            spacing = need
    centers = []
    for i in range(len(profiles)):
        p = profiles[i]
        r = float(p.get("radius", 1.0))
        n = int(p.get("sides", 6))
        if n < 3:
            raise ValueError("polygon_prisms: sides must be at least 3")
        cx = i * spacing
        SketchPolygon.Create(Point.Create(MM(cx), MM(0), MM(0)),
                             Point.Create(MM(cx + r), MM(0), MM(0)),
                             False, n)
        centers.append(cx)

    ViewHelper.SetViewMode(InteractionMode.Solid, None)
    sketch_body = _sketch_region_body({})
    if sketch_body is None:
        raise RuntimeError("polygon_prisms: the sketches did not produce a region body")

    out = []
    for i in range(len(profiles)):
        p = profiles[i]
        target = None
        for f in list(sketch_body.Faces):
            if abs(face_center(f)[0] - centers[i]) <= 1e-3:
                target = f
                break
        if target is None:
            raise RuntimeError("polygon_prisms: sketch face %d not found" % i)
        body = _extrude_face(target, float(p.get("height", 10.0)))
        if body is None:
            raise RuntimeError("polygon_prisms: extrude produced no body for profile %d" % i)
        a = str(p.get("axis", "z")).lower()
        if a == "z":
            rotate(body, 90.0, axis="x")
        elif a == "x":
            rotate(body, -90.0, axis="z")
        elif a != "y":
            raise ValueError("polygon_prisms: axis must be 'x'/'y'/'z'")
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
    if PolylineOptions is not None:
        try:
            pts = edge.GetPolyline(PolylineOptions())
            if pts is not None and pts.Count > 0:
                return list(pts)
        except:
            pass
    try:
        return [edge.StartPoint, edge.EndPoint]
    except:
        return []


def face_extent(face):
    """面的包围盒 ([minx,miny,minz], [maxx,maxy,maxz])，单位 mm。"""
    lo = [None, None, None]
    hi = [None, None, None]
    for e in _shape_of(face).Edges:
        for p in _edge_points(e):
            vals = (p.X, p.Y, p.Z)
            for i in range(3):
                v = vals[i]
                if lo[i] is None or v < lo[i]:
                    lo[i] = v
                if hi[i] is None or v > hi[i]:
                    hi[i] = v
    if lo[0] is None:
        raise RuntimeError("cannot compute face extent: the face exposes no usable edge")
    return ([lo[0] * 1000.0, lo[1] * 1000.0, lo[2] * 1000.0],
            [hi[0] * 1000.0, hi[1] * 1000.0, hi[2] * 1000.0])


def face_center(face):
    """面的中心 = **包围盒中心**，单位 mm。

    为什么不用边界采样点的平均值：面被切分之后会多出共线顶点，平均值会被拉偏。
    实测：100x40x40 的体在底面 x=50 处切开后，y=0 那张侧面的"平均点"z 从 20 变成 16，
    而包围盒中心仍然是 20。规则表按面心定位，所以这一点必须稳。

    注意：脚本里的面是 DesignFace 包装对象，真实几何要通过 face.Shape 取。
    直接用 face.Edges 会报 'DesignEdge' object has no attribute 'StartPoint'。
    """
    lo, hi = face_extent(face)
    return ((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, (lo[2] + hi[2]) / 2.0)


def face_area(face):
    """面积，单位 mm^2。"""
    return _shape_of(face).Area * 1.0e6


def body_extent(body, axis="z"):
    """体在指定轴上的最小/最大坐标 (lo, hi)，单位 mm。"""
    i = _axis_index(axis)
    vals = []
    for f in body.Faces:
        for e in _shape_of(f).Edges:
            for p in _edge_points(e):
                vals.append((p.X, p.Y, p.Z)[i])
    if not vals:
        raise RuntimeError("cannot compute body extent: no edge points found")
    return (min(vals) * 1000.0, max(vals) * 1000.0)


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
    plain_rest = bool(rule.get("rest"))
    take_all = bool(rule.get("all"))

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
            _safe_print("[size] %.3f x %.3f x %.3f mm, %d face(s)"
                        % (dx, dy, dz, len(list(body.Faces))))
        for nm, cnt in group_summary():
            _safe_print("[named selection] %s -> %d face(s)" % (nm, cnt))
    except:
        print("[warn] summary failed, artifact is still saved")
    return path
