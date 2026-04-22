bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (31, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Keychain",
    "description": "Генерирует брелок с ушком",
    "category": "Add Mesh",
}

import bpy
import bmesh
import math
import os
from mathutils import Vector
from bpy.props import StringProperty, FloatProperty, BoolProperty, IntProperty, EnumProperty
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

    lo_f = [f for f in bm.faces if all(v.co.z <= 0.0 for v in f.verts)]
    bmesh.ops.delete(bm, geom=lo_f, context="FACES")
    lo_e = [e for e in bm.edges if all(v.co.z < 0.0 for v in e.verts)]
    if lo_e:
        bmesh.ops.delete(bm, geom=lo_e, context="EDGES")
    lo_v = [v for v in bm.verts if v.co.z < 0.0]
    if lo_v:
        bmesh.ops.delete(bm, geom=lo_v, context="VERTS")

    for v in bm.verts:
        v.co.z = 0.0
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)

    inner = [e for e in bm.edges if not e.is_boundary]
    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
    vi = [e for e in inner if e.is_valid]
    if vi:
        bmesh.ops.delete(bm, geom=vi, context="EDGES")
    iso = [v for v in bm.verts if v.is_valid and not v.link_edges]
    if iso:
        bmesh.ops.delete(bm, geom=iso, context="VERTS")

    all_e = [e for e in bm.edges if e.is_valid]
    if all_e:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_e)

    bmesh.ops.dissolve_limit(bm,
        angle_limit=math.radians(2.0),
        verts=bm.verts[:],
        edges=bm.edges[:])

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
    vi = [e for e in inner if e.is_valid]
    if vi:
        bmesh.ops.delete(bm, geom=vi, context="EDGES")
    iso = [v for v in bm.verts if v.is_valid and not v.link_edges]
    if iso:
        bmesh.ops.delete(bm, geom=iso, context="VERTS")
    all_e = [e for e in bm.edges if e.is_valid]
    if all_e:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_e)
    flip_faces_up(bm)


# ---------------------------------------------------------------------------
# Ушко: точное воспроизведение ручного процесса из PDF
# ---------------------------------------------------------------------------

def weld_ear_pdf_method(context, base_obj, ear_obj, inner_x, y0, y1, side="LEFT"):
    """
    Реализует ручной процесс из PDF:

    1. Ctrl+J — объединяем ушко и подложку
    2. Включаем Auto Merge + Split Edges & Faces (threshold=0.001)
    3. Берём правую верхнюю точку ушка, делаем Extrude по +X
       пока не пересечём ребро основания → Auto Merge создаёт точку на ребре
    4. Удаляем экструдированную точку (ту что вышла за контур)
    5. Повторяем для правой нижней точки
    6. Выделяем: новые точки на основании + все точки основания между ними
       + точки правой стороны ушка
    7. Alt+F (Fill) → заполнение
    8. Экструзия вниз
    """
    # Шаг 1: Join
    deselect_all()
    base_obj.select_set(True)
    ear_obj.select_set(True)
    context.view_layer.objects.active = base_obj
    bpy.ops.object.join()
    joined = context.active_object

    # Шаг 2: Включаем Auto Merge + Split Edges & Faces
    ts = context.scene.tool_settings
    old_automerge       = ts.use_mesh_automerge
    old_split           = getattr(ts, 'use_mesh_automerge_and_split', False)
    old_threshold       = ts.double_threshold
    old_snap            = ts.use_snap

    ts.use_mesh_automerge = True
    if hasattr(ts, 'use_mesh_automerge_and_split'):
        ts.use_mesh_automerge_and_split = True
    ts.double_threshold = 0.0001  # 0.1 мм
    ts.use_snap = False

    try:
        bpy.ops.object.editmode_toggle()

        # Находим правые вершины ушка (верхнюю и нижнюю) через bmesh
        bm = bmesh.from_edit_mesh(joined.data)
        bm.verts.ensure_lookup_table()

        tol = 0.15
        right_verts = sorted(
            [v for v in bm.verts
             if abs(v.co.x - inner_x) < tol
             and (y0 - tol) < v.co.y < (y1 + tol)],
            key=lambda v: v.co.y
        )

        if len(right_verts) < 2:
            bmesh.update_edit_mesh(joined.data)
            bpy.ops.object.editmode_toggle()
            return joined

        ear_bot = right_verts[0]   # нижняя правая
        ear_top = right_verts[-1]  # верхняя правая

        # Шаги 3-5: для каждой правой вершины экструдируем по +X
        # Extrude на расстояние достаточное чтобы пересечь контур основания
        # Направление экструзии: к основанию
        # LEFT: ушко слева, основание правее → +X
        # RIGHT: ушко справа, основание левее → -X
        extrude_dir = 1.0 if side == "LEFT" else -1.0
        extrude_dist = 5.0 * extrude_dir

        new_base_verts = []

        for ear_v in [ear_bot, ear_top]:
            if not ear_v.is_valid:
                continue

            # Деселектируем всё
            for v in bm.verts:
                v.select = False
            bm.select_flush(False)

            # Выбираем только эту вершину
            ear_v.select = True
            bmesh.update_edit_mesh(joined.data)

            # Запоминаем количество вершин до экструзии
            n_verts_before = len(joined.data.vertices)

            # Extrude vertex + Move по +X
            # Split Edges & Faces автоматически создаст точку на ребре основания
            bpy.ops.mesh.extrude_vertices_move(
                TRANSFORM_OT_translate={
                    "value": (extrude_dist, 0.0, 0.0),
                    "constraint_axis": (True, False, False)
                }
            )
            # Для правого ушка экструдируем влево (-X)

            # Обновляем bmesh
            bm = bmesh.from_edit_mesh(joined.data)
            bm.verts.ensure_lookup_table()

            # Новые вершины появились благодаря Split Edges & Faces
            n_verts_after = len(joined.data.vertices)

            # Удаляем экструдированную вершину (выбранная = та что сдвинулась)
            # Она находится правее исходной позиции
            to_delete = [v for v in bm.verts if v.select and v.is_valid]
            if to_delete:
                bmesh.ops.delete(bm, geom=to_delete, context="VERTS")
                bm = bmesh.from_edit_mesh(joined.data)
                bm.verts.ensure_lookup_table()

        # Шаг 6: выделяем нужные вершины для Fill
        # - точки правой стороны ушка (X ≈ right_x)
        # - новые точки на основании (появились в результате Split)
        # - все точки основания между этими двумя новыми точками по Y

        bm.verts.ensure_lookup_table()

        # Сначала деселектируем всё
        for v in bm.verts:
            v.select = False

        tol_x = 0.15
        tol_y = 0.15

        # Вершины внутренней стороны ушка (примыкающие к основанию)
        ear_right = [v for v in bm.verts
                     if abs(v.co.x - inner_x) < tol_x
                     and (y0 - tol_y) < v.co.y < (y1 + tol_y)]

        # Вершины основания в зоне стыка
        # LEFT: основание правее inner_x; RIGHT: основание левее inner_x
        if side == "LEFT":
            base_region = [v for v in bm.verts
                           if v.co.x > inner_x + 0.01
                           and (y0 - tol_y) < v.co.y < (y1 + tol_y)]
        else:
            base_region = [v for v in bm.verts
                           if v.co.x < inner_x - 0.01
                           and (y0 - tol_y) < v.co.y < (y1 + tol_y)]

        # Все вершины основания между y0 и y1 по Y
        # (это контур основания в зоне стыка)
        region_y_min = min((v.co.y for v in ear_right), default=y0) - tol_y
        region_y_max = max((v.co.y for v in ear_right), default=y1) + tol_y

        fill_verts = set()
        for v in ear_right:
            fill_verts.add(v)
        for v in base_region:
            if region_y_min <= v.co.y <= region_y_max:
                fill_verts.add(v)

        for v in fill_verts:
            if v.is_valid:
                v.select = True

        bm.select_flush(True)
        bmesh.update_edit_mesh(joined.data)

        # Шаг 7: Fill (Alt+F = Face → Fill)
        bpy.ops.mesh.fill()

        # Финальная очистка
        bm = bmesh.from_edit_mesh(joined.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
        bmesh.ops.dissolve_limit(bm,
            angle_limit=math.radians(2.0),
            verts=bm.verts[:],
            edges=bm.edges[:])
        flip_faces_up(bm)
        bmesh.update_edit_mesh(joined.data)
        bpy.ops.object.editmode_toggle()

    finally:
        ts.use_mesh_automerge = old_automerge
        if hasattr(ts, 'use_mesh_automerge_and_split'):
            ts.use_mesh_automerge_and_split = old_split
        ts.double_threshold = old_threshold
        ts.use_snap = old_snap

    return joined


def create_ear_2d(context, left_x, right_x, y0, y1, chamfer, segs):
    """Создаёт плоский меш ушка."""
    mesh    = bpy.data.meshes.new("_KM_Ear")
    ear_obj = bpy.data.objects.new("_KM_Ear", mesh)
    context.collection.objects.link(ear_obj)

    c = chamfer
    bm = bmesh.new()

    if c > 0.0 and segs >= 1:
        pts2d = []
        pts2d.append((right_x, y0))
        pts2d.append((right_x, y1))
        for i in range(segs + 1):
            a = math.pi * 0.5 + math.pi * 0.5 * (i / segs)
            pts2d.append((left_x + c + math.cos(a) * c,
                          y1 - c + math.sin(a) * c))
        for i in range(segs + 1):
            a = math.pi + math.pi * 0.5 * (i / segs)
            pts2d.append((left_x + c + math.cos(a) * c,
                          y0 + c + math.sin(a) * c))
        verts = [bm.verts.new((x, y, 0.0)) for x, y in pts2d]
    else:
        verts = [
            bm.verts.new((right_x, y0, 0.0)),
            bm.verts.new((right_x, y1, 0.0)),
            bm.verts.new((left_x,  y1, 0.0)),
            bm.verts.new((left_x,  y0, 0.0)),
        ]

    bm.faces.new(verts)
    flip_faces_up(bm)
    bm.to_mesh(mesh)
    bm.free()
    return ear_obj


def create_ear_2d_right(context, inner_x, outer_x, y0, y1, chamfer, segs):
    """
    Создаёт плоский меш ушка для ПРАВОЙ стороны (зеркально к левому).
    inner_x — левый край ушка (примыкает к основанию)
    outer_x — правый край (внешний, со скруглением)
    Скругление на правых (внешних) углах.
    """
    mesh    = bpy.data.meshes.new("_KM_Ear")
    ear_obj = bpy.data.objects.new("_KM_Ear", mesh)
    context.collection.objects.link(ear_obj)

    c = chamfer
    bm = bmesh.new()

    if c > 0.0 and segs >= 1:
        pts2d = []
        pts2d.append((inner_x, y0))  # нижний внутренний (примыкает к основанию)
        pts2d.append((inner_x, y1))  # верхний внутренний
        # Правый верхний угол — дуга скругления
        for i in range(segs + 1):
            a = math.pi * 0.5 - math.pi * 0.5 * (i / segs)
            pts2d.append((outer_x - c + math.cos(a) * c,
                          y1 - c + math.sin(a) * c))
        # Правый нижний угол — дуга скругления
        for i in range(segs + 1):
            a = -math.pi * 0.5 * (i / segs)
            pts2d.append((outer_x - c + math.cos(a) * c,
                          y0 + c + math.sin(a) * c))
        verts = [bm.verts.new((x, y, 0.0)) for x, y in pts2d]
    else:
        verts = [
            bm.verts.new((inner_x, y0, 0.0)),
            bm.verts.new((inner_x, y1, 0.0)),
            bm.verts.new((outer_x,  y1, 0.0)),
            bm.verts.new((outer_x,  y0, 0.0)),
        ]

    bm.faces.new(verts)
    flip_faces_up(bm)
    bm.to_mesh(mesh)
    bm.free()
    return ear_obj


def cut_ear_hole(context, obj, outer_x, yc, base_h, hole_d, side="LEFT"):
    """Вырезает отверстие в ушке."""
    hole_r = hole_d / 2.0
    # LEFT: outer_x — левый край, отверстие смещено вправо от него
    # RIGHT: outer_x — правый край, отверстие смещено влево от него
    if side == "LEFT":
        cx = outer_x + hole_r + 2.0
    else:
        cx = outer_x - hole_r - 2.0
    cy = yc
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

        # ── 3. Плоская подложка ────────────────────────────────────────────
        base_flat = build_flat_base(context, pts, offset)
        if not base_flat.data.vertices or not base_flat.data.polygons:
            self.report({"ERROR"}, "Подложка пустая.")
            delete_obj(base_flat)
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Ушко: создаём и вшиваем в подложку ──────────────────────────
        ear_info = None
        if props.lug_enable:
            xs = [v.co.x for v in base_flat.data.vertices]
            ys = [v.co.y for v in base_flat.data.vertices]
            base_min_x = min(xs)
            base_max_x = max(xs)
            base_cy    = (min(ys) + max(ys)) / 2.0

            lug_x   = props.lug_size_x
            lug_y   = props.lug_size_y
            chamfer = min(props.lug_chamfer, lug_x * 0.45, lug_y * 0.45)
            segs    = props.lug_chamfer_segments
            oy      = props.lug_offset_y
            side    = props.lug_side

            gap = 0.5   # зазор для Auto Merge + Split
            yc  = base_cy + oy
            y0  = yc - lug_y / 2.0
            y1  = yc + lug_y / 2.0

            if side == 'LEFT':
                # Ушко слева: inner_x — правый край ушка (у основания)
                inner_x = base_min_x - gap
                outer_x = inner_x - lug_x
                # Для левого ушка: правые вершины — примыкающие к основанию
                # Для right вершин ушка outer — левый край (со скруглением)
                ear_obj = create_ear_2d(context, outer_x, inner_x, y0, y1, chamfer, segs)
            else:
                # Ушко справа: inner_x — левый край ушка (у основания)
                inner_x = base_max_x + gap
                outer_x = inner_x + lug_x
                # Зеркально: скругление на правых (внешних) углах
                ear_obj = create_ear_2d_right(context, inner_x, outer_x, y0, y1, chamfer, segs)

            base_flat = weld_ear_pdf_method(
                context, base_flat, ear_obj,
                inner_x, y0, y1, side=side
            )

            ear_info = {"outer_x": outer_x, "yc": yc, "side": side}

        # ── 5. Экструдируем подложку + ушко вниз ──────────────────────────
        set_active(context, base_flat)
        bpy.ops.object.editmode_toggle()
        bm_b = bmesh.from_edit_mesh(base_flat.data)
        ret = bmesh.ops.extrude_face_region(bm_b, geom=list(bm_b.faces))
        new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm_b, verts=new_verts, vec=Vector((0, 0, -base_h)))
        bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces[:])
        bmesh.update_edit_mesh(base_flat.data)
        bpy.ops.object.editmode_toggle()
        base_flat.name = "_KM_Base"
        base_obj = base_flat

        # ── 6. Буквы: контуры + Solidify вверх ─────────────────────────────
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

        # ── 7. Join подложки и букв → поднимаем ────────────────────────────
        deselect_all()
        base_obj.select_set(True)
        letters_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        final_obj = context.active_object

        final_obj.location.z = base_h
        bpy.ops.object.transform_apply(location=True)

        # ── 8. Отверстие в ушке ────────────────────────────────────────────
        if props.lug_enable and ear_info:
            cut_ear_hole(context, final_obj,
                         ear_info["outer_x"], ear_info["yc"],
                         base_h, props.lug_hole_diameter,
                         ear_info.get("side", "LEFT"))

        # ── Shade Auto Smooth ──────────────────────────────────────────────
        set_active(context, final_obj)
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(30.0))
        except Exception:
            bpy.ops.object.shade_smooth()

        safe = "".join(
            c for c in text if c.isascii() and (c.isalnum() or c in " _-")
        )[:20].strip() or "keychain"
        final_obj.name = f"Keychain_{safe}"

        self.report({"INFO"}, f"Брелок «{text}» создан!")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Свойства
# ---------------------------------------------------------------------------

class KeychainProperties(PropertyGroup):
    text: StringProperty(name="Текст", default="IVAN")
    font_path: StringProperty(name="Шрифт (.ttf)", subtype="FILE_PATH", default="")
    base_offset: FloatProperty(
        name="Отступ подложки (мм)", default=3.0, min=0.5, max=30.0,
        precision=1, step=10)
    base_height: FloatProperty(
        name="Толщина подложки (мм)", default=3.0, min=0.5, max=20.0,
        precision=1, step=10)
    letter_height: FloatProperty(
        name="Высота букв (мм)", default=2.0, min=0.2, max=10.0,
        precision=1, step=10)
    lug_enable: BoolProperty(name="Добавить ушко", default=True)
    lug_side: EnumProperty(
        name="Сторона ушка",
        items=[
            ('LEFT',  "Слева",  "Ушко с левой стороны"),
            ('RIGHT', "Справа", "Ушко с правой стороны"),
        ],
        default='LEFT')
    lug_size_x: FloatProperty(
        name="Длина ушка X (мм)", default=8.0, min=3.0, max=30.0,
        precision=1, step=10)
    lug_size_y: FloatProperty(
        name="Ширина ушка Y (мм)", default=8.0, min=3.0, max=30.0,
        precision=1, step=10)
    lug_chamfer: FloatProperty(
        name="Фаска рёбер (мм)", default=1.5, min=0.0, max=5.0,
        precision=1, step=5)
    lug_chamfer_segments: IntProperty(
        name="Сегменты фаски", default=4, min=1, max=16)
    lug_offset_y: FloatProperty(
        name="Смещение по Y (мм)", default=0.0, min=-50.0, max=50.0,
        precision=1, step=10)
    lug_hole_diameter: FloatProperty(
        name="Диаметр отверстия (мм)", default=2.0, min=0.5, max=10.0,
        precision=1, step=5)


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
            box.prop(props, "lug_side")
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
