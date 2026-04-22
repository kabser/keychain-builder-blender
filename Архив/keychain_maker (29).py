bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (28, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Keychain",
    "description": "Генерирует брелок с ушком для кольца",
    "category": "Add Mesh",
}

import bpy
import bmesh
import math
import os
from mathutils import Vector
from bpy.props import StringProperty, FloatProperty, BoolProperty, IntProperty
from bpy.types import Panel, Operator, PropertyGroup


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def delete_obj(obj):
    if obj and obj.name in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

def delete_by_prefix(prefix):
    for o in [o for o in bpy.data.objects if o.name.startswith(prefix)]:
        bpy.data.objects.remove(o, do_unlink=True)

def deselect_all():
    bpy.ops.object.select_all(action="DESELECT")

def set_active(context, obj):
    deselect_all()
    obj.select_set(True)
    context.view_layer.objects.active = obj

def flip_faces_up(bm):
    to_flip = [f for f in bm.faces if f.normal.z < 0]
    if to_flip:
        bmesh.ops.reverse_faces(bm, faces=to_flip)

def points_along_edges(mesh_obj, step):
    pts = []
    m  = mesh_obj.data
    mw = mesh_obj.matrix_world
    for edge in m.edges:
        v0 = mw @ m.vertices[edge.vertices[0]].co
        v1 = mw @ m.vertices[edge.vertices[1]].co
        n  = max(1, math.ceil((v1 - v0).length / step))
        for i in range(n + 1):
            p = v0.lerp(v1, i / n)
            pts.append((p.x, p.y))
    return pts


# ---------------------------------------------------------------------------
# Подложка (v20)
# ---------------------------------------------------------------------------

def build_flat_base(context, pts, offset):
    mb_resolution = max(offset * 0.08, 0.0001)
    elem_radius   = offset * 1.1
    grid_size     = offset * 0.35

    mb_data = bpy.data.metaballs.new("_KM_MB")
    mb_data.resolution        = mb_resolution
    mb_data.render_resolution = mb_resolution
    mb_data.threshold         = 0.6
    mb_obj = bpy.data.objects.new("_KM_MetaObj", mb_data)
    context.collection.objects.link(mb_obj)

    seen = set()
    for vx, vy in pts:
        key = (round(vx / grid_size), round(vy / grid_size))
        if key in seen:
            continue
        seen.add(key)
        el = mb_data.elements.new(type="BALL")
        el.co = Vector((vx, vy, 0.0))
        el.radius = elem_radius
        el.stiffness = 1.0

    context.view_layer.update()
    set_active(context, mb_obj)
    bpy.ops.object.convert(target="MESH")
    base_raw = context.active_object
    base_raw.name = "_KM_BaseRaw"

    set_active(context, base_raw)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(base_raw.data)

    lower_faces = [f for f in bm.faces if all(v.co.z <= 0.0 for v in f.verts)]
    bmesh.ops.delete(bm, geom=lower_faces, context="FACES")
    lower_edges = [e for e in bm.edges if all(v.co.z < 0.0 for v in e.verts)]
    if lower_edges:
        bmesh.ops.delete(bm, geom=lower_edges, context="EDGES")
    lower_verts = [v for v in bm.verts if v.co.z < 0.0]
    if lower_verts:
        bmesh.ops.delete(bm, geom=lower_verts, context="VERTS")

    for v in bm.verts:
        v.co.z = 0.0
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)

    inner_edges = [e for e in bm.edges if not e.is_boundary]
    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
    valid_inner = [e for e in inner_edges if e.is_valid]
    if valid_inner:
        bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
    isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
    if isolated:
        bmesh.ops.delete(bm, geom=isolated, context="VERTS")

    all_edges = [e for e in bm.edges if e.is_valid]
    if all_edges:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_edges)

    flip_faces_up(bm)
    bmesh.update_edit_mesh(base_raw.data)
    bpy.ops.object.editmode_toggle()
    return base_raw


# ---------------------------------------------------------------------------
# Буквы (v20)
# ---------------------------------------------------------------------------

def prepare_letters_mesh(bm):
    inner = [e for e in bm.edges if not e.is_boundary]
    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
    valid_inner = [e for e in inner if e.is_valid]
    if valid_inner:
        bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
    isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
    if isolated:
        bmesh.ops.delete(bm, geom=isolated, context="VERTS")
    all_e = [e for e in bm.edges if e.is_valid]
    if all_e:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_e)
    flip_faces_up(bm)


# ---------------------------------------------------------------------------
# Ушко: математическое пересечение рёбер в bmesh
# ---------------------------------------------------------------------------

def seg_intersect_2d(p1, p2, p3, p4, tol=1e-9):
    """
    Пересечение двух отрезков p1-p2 и p3-p4 в 2D (X,Y).
    Возвращает (точка_пересечения, t) или None.
    t — параметр на отрезке p1-p2 (0..1).
    """
    d1 = p2 - p1
    d2 = p4 - p3
    cross = d1.x * d2.y - d1.y * d2.x
    if abs(cross) < tol:
        return None  # параллельны
    diff = p3 - p1
    t = (diff.x * d2.y - diff.y * d2.x) / cross
    u = (diff.x * d1.y - diff.y * d1.x) / cross
    if -tol <= t <= 1 + tol and -tol <= u <= 1 + tol:
        pt = p1 + d1 * t
        return pt, t
    return None


def split_edge_at_point(bm, edge, t):
    """
    Разбивает ребро edge в точке с параметром t (0..1).
    Возвращает новую вершину.
    """
    result = bmesh.ops.subdivide_edges(
        bm,
        edges=[edge],
        cuts=1,
        use_grid_fill=False,
    )
    # subdivide_edges возвращает geom_inner — новые вершины
    new_verts = [g for g in result.get("geom_inner", [])
                 if isinstance(g, bmesh.types.BMVert)]
    if not new_verts:
        return None
    new_v = new_verts[0]
    # Интерполируем позицию точно по t
    v0 = edge.verts[0].co.copy()
    v1 = edge.verts[1].co.copy()
    # После subdivide новая вершина уже примерно в середине,
    # но нам нужна точная позиция пересечения
    # Пересчитаем вручную:
    # edge после subdivide разбит на два — нам нужно найти новую вершину
    # и поставить её на нужное место
    new_v.co = v0.lerp(v1, t)
    return new_v


def weld_ear_bmesh(bm, ear_right_verts, y_bot, y_top):
    """
    Сваривает ушко с подложкой напрямую через bmesh.

    Алгоритм:
    1. Для каждой правой вершины ушка (верхней и нижней):
       a. Бросаем луч по +X от вершины
       b. Находим ребро контура подложки которое пересекает этот луч
       c. Разбиваем ребро подложки в точке пересечения → новая вершина
       d. Соединяем правую вершину ушка с новой вершиной ребром
    2. Удаляем изолированные «висячие» вершины ушка если они появились
    3. triangle_fill закрывает образовавшийся контур
    """
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    tol_y = 0.1

    for ear_v in ear_right_verts:
        if not ear_v.is_valid:
            continue

        ex = ear_v.co.x
        ey = ear_v.co.y

        # Луч: от (ex, ey) по +X на большое расстояние
        ray_start = Vector((ex, ey))
        ray_end   = Vector((ex + 1000.0, ey))

        best_t_edge = None   # параметр t на ребре подложки
        best_edge   = None
        best_pt     = None
        best_dist   = float('inf')

        # Ищем ребро контура подложки которое пересекает луч
        for edge in list(bm.edges):
            if not edge.is_valid:
                continue
            # Берём только граничные рёбра подложки (не рёбра ушка)
            # Рёбра ушка: обе вершины имеют x <= ex + 0.5
            va, vb = edge.verts
            if max(va.co.x, vb.co.x) < ex - 0.1:
                continue  # ребро левее вершины ушка — пропускаем
            if min(va.co.x, vb.co.x) > ex + 1000.0:
                continue

            p3 = Vector((va.co.x, va.co.y))
            p4 = Vector((vb.co.x, vb.co.y))

            result = seg_intersect_2d(ray_start, ray_end, p3, p4)
            if result is None:
                continue

            pt, t_ray = result
            # t_ray — расстояние вдоль луча (нормировано на длину луча=1000)
            dist = (pt - ray_start).length

            # Должно быть правее вершины ушка
            if dist < 0.01:
                continue

            # Ребро должно реально пересекать луч (не быть частью ушка)
            # Проверяем: хотя бы одна вершина ребра должна быть правее ex
            if max(va.co.x, vb.co.x) < ex + 0.01:
                continue

            _, t_edge = result if len(result) == 2 else (result, None)
            # Пересчитаем t для самого ребра
            res2 = seg_intersect_2d(p3, p4, ray_start, ray_end)
            if res2 is None:
                continue
            _, t_on_edge = res2

            if dist < best_dist:
                best_dist     = dist
                best_edge     = edge
                best_pt       = pt
                best_t_edge   = t_on_edge

        if best_edge is None:
            continue  # не нашли ребро — пропускаем

        # Разбиваем ребро подложки в точке пересечения
        new_v = split_edge_at_point(bm, best_edge, best_t_edge)
        if new_v is None:
            continue

        # Устанавливаем точную позицию
        new_v.co.x = best_pt.x
        new_v.co.y = best_pt.y
        new_v.co.z = 0.0

        # Соединяем вершину ушка с новой вершиной на контуре подложки
        if ear_v.is_valid and new_v.is_valid:
            try:
                bm.edges.new([ear_v, new_v])
            except ValueError:
                pass  # ребро уже существует

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()


def build_ear_plane_in_bm(bm, x_left, x_right, y_bot, y_top, chamfer, segs):
    """
    Добавляет плоскость ушка прямо в существующий bmesh подложки.
    Возвращает список правых вершин ушка (те что примыкают к подложке).

    Фаска делается вручную через срезание углов.
    """
    c = min(chamfer, (x_right - x_left) * 0.45, (y_top - y_bot) * 0.45)

    if c > 0.0 and segs >= 1:
        # Строим очертание с фаской на левых углах
        # Левый нижний угол: (x_left, y_bot) → срезаем
        # Левый верхний угол: (x_left, y_top) → срезаем

        pts_2d = []

        # Правые вершины (без фаски)
        pts_2d.append((x_right, y_bot))
        pts_2d.append((x_right, y_top))

        # Левый верхний угол — фаска (дуга из segs сегментов)
        for i in range(segs + 1):
            angle = math.pi * 0.5 + math.pi * 0.5 * (i / segs)
            pts_2d.append((x_left + c + math.cos(angle) * c,
                           y_top  - c + math.sin(angle) * c))

        # Левый нижний угол — фаска
        for i in range(segs + 1):
            angle = math.pi + math.pi * 0.5 * (i / segs)
            pts_2d.append((x_left + c + math.cos(angle) * c,
                           y_bot  + c + math.sin(angle) * c))

        verts = [bm.verts.new((x, y, 0.0)) for x, y in pts_2d]
        bm.faces.new(verts)

        right_verts = [v for v in verts
                       if abs(v.co.x - x_right) < 0.001]
    else:
        # Простой прямоугольник
        v0 = bm.verts.new((x_right, y_bot, 0.0))
        v1 = bm.verts.new((x_right, y_top, 0.0))
        v2 = bm.verts.new((x_left,  y_top, 0.0))
        v3 = bm.verts.new((x_left,  y_bot, 0.0))
        bm.faces.new([v0, v1, v2, v3])
        right_verts = [v0, v1]

    return right_verts


def add_ear_to_base_2d(context, base_obj, props):
    """
    Добавляет ушко к плоской подложке через прямую работу с bmesh.
    Не делает join отдельных объектов — всё строится в одном bmesh.
    """
    lug_x    = props.lug_size_x
    lug_y    = props.lug_size_y
    chamfer  = props.lug_chamfer
    segs     = props.lug_chamfer_segments
    offset_y = props.lug_offset_y

    xs = [v.co.x for v in base_obj.data.vertices]
    ys = [v.co.y for v in base_obj.data.vertices]
    base_min_x = min(xs)
    base_cy    = (min(ys) + max(ys)) / 2.0

    # Ушко левее подложки с зазором
    gap     = 0.5
    right_x = base_min_x - gap
    left_x  = right_x - lug_x

    yc = base_cy + offset_y
    y0 = yc - lug_y / 2.0
    y1 = yc + lug_y / 2.0

    # Работаем напрямую в bmesh объекта подложки
    set_active(context, base_obj)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(base_obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Добавляем ушко в тот же bmesh
    right_verts = build_ear_plane_in_bm(bm, left_x, right_x, y0, y1, chamfer, segs)

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Находим граничный контур ушка
    # Сортируем правые вершины по Y
    right_verts.sort(key=lambda v: v.co.y)

    # Соединяем ушко с подложкой через математическое пересечение
    weld_ear_bmesh(bm, right_verts, y0, y1)

    # Финальная очистка
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)

    # Заполняем все открытые петли
    bm.edges.ensure_lookup_table()
    open_edges = [e for e in bm.edges if e.is_boundary]
    if open_edges:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=open_edges)

    flip_faces_up(bm)
    bmesh.update_edit_mesh(base_obj.data)
    bpy.ops.object.editmode_toggle()

    ear_info = {
        "outer_x":  left_x,
        "y_center": yc,
    }
    return base_obj, ear_info


# ---------------------------------------------------------------------------
# Отверстие в ушке
# ---------------------------------------------------------------------------

def cut_ear_hole(context, obj, ear_info, props):
    hole_r = props.lug_hole_diameter / 2.0
    base_h = props.base_height

    cx = ear_info["outer_x"] + hole_r + 2.0
    cy = ear_info["y_center"]
    cz = base_h / 2.0

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48,
        radius=hole_r,
        depth=base_h + 1.0,
        location=(cx, cy, cz),
    )
    cyl = context.active_object
    cyl.name = "_KM_EarHoleCyl"

    set_active(context, obj)
    mod = obj.modifiers.new("EarHole", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object    = cyl
    mod.solver    = "EXACT"
    bpy.ops.object.modifier_apply(modifier="EarHole")
    delete_obj(cyl)


# ---------------------------------------------------------------------------
# Оператор
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Generate(Operator):
    bl_idname  = "keychain.generate"
    bl_label   = "Создать брелок"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props     = context.scene.keychain_props
        text      = props.text
        font_path = props.font_path
        offset    = props.base_offset
        base_h    = props.base_height
        letter_h  = props.letter_height

        if not text:
            self.report({"WARNING"}, "Введите текст!")
            return {"CANCELLED"}

        delete_by_prefix("_KM_")

        # ── 1. Текст → меш ─────────────────────────────────────────────────
        bpy.ops.object.text_add(location=(0, 0, 0))
        txt_obj = context.active_object
        txt_obj.data.body = text
        txt_obj.data.size = 10.0
        if font_path and os.path.isfile(font_path):
            txt_obj.data.font = bpy.data.fonts.load(font_path)

        set_active(context, txt_obj)
        bpy.ops.object.convert(target="MESH")
        letters_obj = context.active_object
        letters_obj.name = "_KM_Letters"

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
        bpy.ops.mesh.remove_doubles(threshold=0.001)
        bpy.ops.object.editmode_toggle()

        if not letters_obj.data.vertices:
            self.report({"ERROR"}, "Текст не содержит вершин.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 2. Точки вдоль рёбер ───────────────────────────────────────────
        pts = points_along_edges(letters_obj, offset * 0.7)
        if len(pts) < 2:
            self.report({"ERROR"}, "Не удалось получить рёбра текста.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 3. Плоский контур подложки ─────────────────────────────────────
        base_flat = build_flat_base(context, pts, offset)
        if not base_flat.data.vertices or not base_flat.data.polygons:
            self.report({"ERROR"}, "Подложка пустая.")
            delete_obj(base_flat)
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Ушко вшито прямо в bmesh подложки ──────────────────────────
        ear_info = None
        if props.lug_enable:
            base_flat, ear_info = add_ear_to_base_2d(context, base_flat, props)

        # ── 5. Экструдируем вниз ───────────────────────────────────────────
        set_active(context, base_flat)
        bpy.ops.object.editmode_toggle()
        bm_base = bmesh.from_edit_mesh(base_flat.data)
        ret = bmesh.ops.extrude_face_region(bm_base, geom=list(bm_base.faces))
        new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm_base, verts=new_verts, vec=Vector((0, 0, -base_h)))
        bmesh.ops.recalc_face_normals(bm_base, faces=bm_base.faces[:])
        bmesh.update_edit_mesh(base_flat.data)
        bpy.ops.object.editmode_toggle()
        base_flat.name = "_KM_Base"
        base_obj = base_flat

        # ── 6. Буквы + Solidify ────────────────────────────────────────────
        set_active(context, letters_obj)
        bpy.ops.object.editmode_toggle()
        bm5 = bmesh.from_edit_mesh(letters_obj.data)
        prepare_letters_mesh(bm5)
        bmesh.update_edit_mesh(letters_obj.data)
        bpy.ops.object.editmode_toggle()

        mod = letters_obj.modifiers.new("Solidify", "SOLIDIFY")
        mod.thickness       = letter_h
        mod.offset          = 1.0
        mod.use_even_offset = True
        mod.use_rim         = True
        bpy.ops.object.modifier_apply(modifier="Solidify")

        # ── 7. Join ────────────────────────────────────────────────────────
        deselect_all()
        base_obj.select_set(True)
        letters_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        final_obj = context.active_object

        final_obj.location.z = base_h
        bpy.ops.object.transform_apply(location=True)

        # ── 8. Отверстие ───────────────────────────────────────────────────
        if props.lug_enable and ear_info:
            cut_ear_hole(context, final_obj, ear_info, props)

        safe = "".join(
            c for c in text if c.isascii() and (c.isalnum() or c in " _-")
        )[:20].strip() or "keychain"
        final_obj.name = f"Keychain_{safe}"

        self.report({"INFO"}, f'Брелок «{text}» создан!')
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Свойства
# ---------------------------------------------------------------------------

class KeychainProperties(PropertyGroup):
    text: StringProperty(name="Текст", default="IVAN")
    font_path: StringProperty(name="Шрифт (.ttf)", subtype="FILE_PATH", default="")
    base_offset: FloatProperty(
        name="Отступ подложки (мм)", default=3.0, min=0.5, max=30.0,
        precision=1, step=10,
    )
    base_height: FloatProperty(
        name="Толщина подложки (мм)", default=3.0, min=0.5, max=20.0,
        precision=1, step=10,
    )
    letter_height: FloatProperty(
        name="Высота букв (мм)", default=2.0, min=0.2, max=10.0,
        precision=1, step=10,
    )
    lug_enable: BoolProperty(name="Добавить ушко", default=True)
    lug_size_x: FloatProperty(
        name="Длина ушка X (мм)", default=8.0, min=3.0, max=30.0,
        precision=1, step=10,
    )
    lug_size_y: FloatProperty(
        name="Ширина ушка Y (мм)", default=8.0, min=3.0, max=30.0,
        precision=1, step=10,
    )
    lug_chamfer: FloatProperty(
        name="Фаска рёбер (мм)", default=1.5, min=0.0, max=5.0,
        precision=1, step=5,
    )
    lug_chamfer_segments: IntProperty(
        name="Сегменты фаски", default=4, min=1, max=16,
    )
    lug_offset_y: FloatProperty(
        name="Смещение по Y (мм)", default=0.0, min=-50.0, max=50.0,
        precision=1, step=10,
    )
    lug_hole_diameter: FloatProperty(
        name="Диаметр отверстия (мм)", default=2.0, min=0.5, max=10.0,
        precision=1, step=5,
    )


# ---------------------------------------------------------------------------
# N-Panel
# ---------------------------------------------------------------------------

class KEYCHAIN_PT_Panel(Panel):
    bl_label       = "Keychain Maker"
    bl_idname      = "KEYCHAIN_PT_Panel"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Keychain"

    def draw(self, context):
        layout = self.layout
        props  = context.scene.keychain_props

        box = layout.box()
        box.label(text="Надпись", icon="FONT_DATA")
        box.prop(props, "text")
        box.prop(props, "font_path")

        box = layout.box()
        box.label(text="Подложка", icon="MESH_PLANE")
        box.prop(props, "base_offset")
        box.prop(props, "base_height")
        box.prop(props, "letter_height")

        box = layout.box()
        box.label(text="Ушко", icon="LINKED")
        box.prop(props, "lug_enable")
        if props.lug_enable:
            box.prop(props, "lug_size_x")
            box.prop(props, "lug_size_y")
            row = box.row(align=True)
            row.prop(props, "lug_chamfer")
            row.prop(props, "lug_chamfer_segments")
            box.prop(props, "lug_offset_y")
            box.prop(props, "lug_hole_diameter")

        layout.separator()
        layout.operator("keychain.generate", icon="MESH_DATA", text="Создать брелок")


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------

classes = (KeychainProperties, KEYCHAIN_OT_Generate, KEYCHAIN_PT_Panel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.keychain_props = bpy.props.PointerProperty(type=KeychainProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.keychain_props

if __name__ == "__main__":
    register()
