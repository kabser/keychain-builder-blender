bl_info = {
    "name": "Keychain Maker",
    "author": "@kabser",
    "version": (1, 1, 1),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Keychain",
    "description": "Keychain generator with ear",
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
# Переводы / Translations
# ---------------------------------------------------------------------------

translations_dict = {
    "ru_RU": {
        # Операторы
        ("*", "Create Keychain"):                    "Создать брелок",
        ("*", "Generate a 3D-printable keychain from the current settings"): "Создать брелок для 3D-печати на основе текущих настроек",
        ("*", "Reset Settings"):                     "Сбросить настройки",
        ("*", "Reset all parameters to default values"): "Вернуть все параметры к значениям по умолчанию",

        # Сообщения
        ("*", "Enter text!"):                        "Введите текст!",
        ("*", "Text has no vertices."):              "Текст не содержит вершин.",
        ("*", "Could not get text edges."):          "Не удалось получить рёбра текста.",
        ("*", "Base is empty."):                     "Подложка пустая.",
        ("*", "Settings reset"):                     "Настройки сброшены",

        # Заголовки панелей
        ("*", "Text"):                               "Надпись",
        ("*", "Base"):                               "Подложка",
        ("*", "Ear"):                                "Ушко",

        # Свойства — имена
        ("*", "Font (.ttf)"):                        "Шрифт (.ttf)",
        ("*", "Char Spacing"):                       "Расстояние между символами",
        ("*", "Base Offset (mm)"):                   "Отступ подложки (мм)",
        ("*", "Base Height (mm)"):                   "Толщина подложки (мм)",
        ("*", "Letter Height (mm)"):                 "Высота букв (мм)",
        ("*", "Add Ear"):                            "Добавить ушко",
        ("*", "Ear Side"):                           "Сторона ушка",
        ("*", "Left"):                               "Слева",
        ("*", "Right"):                              "Справа",
        ("*", "Ear Length X (mm)"):                  "Длина ушка X (мм)",
        ("*", "Ear Width Y (mm)"):                   "Ширина ушка Y (мм)",
        ("*", "Chamfer (mm)"):                       "Фаска рёбер (мм)",
        ("*", "Chamfer Segments"):                   "Сегменты фаски",
        ("*", "Y Offset (mm)"):                      "Смещение по Y (мм)",
        ("*", "Hole Diameter (mm)"):                 "Диаметр отверстия (мм)",
        ("*", "Hole Edge Margin (mm)"):             "Отступ от края ушка (мм)",
        ("*", "Oval Hole"):                         "Овальное отверстие",

        # Свойства — подсказки
        ("*", "Text to engrave on the keychain"):    "Надпись на брелоке",
        ("*", "Path to TTF/OTF font file"):          "Путь к файлу шрифта TTF/OTF",
        ("*", "Character spacing (1.0 = default, less = tighter)"): "Межсимвольный интервал (1.0 = стандартный, меньше = теснее)",
        ("*", "How much the base extends beyond the letters"): "Насколько подложка выступает за буквы",
        ("*", "Thickness of the base plate"):        "Толщина основания брелока",
        ("*", "How much letters protrude above the base"): "На сколько буквы выступают над подложкой",
        ("*", "Add a key ring ear to the keychain"): "Добавить ушко для кольца",
        ("*", "Which side to place the ear on"):     "С какой стороны разместить ушко",
        ("*", "Ear on the left side"):               "Ушко с левой стороны",
        ("*", "Ear on the right side"):              "Ушко с правой стороны",
        ("*", "Ear length along X axis"):            "Длина ушка по оси X",
        ("*", "Ear width along Y axis"):             "Ширина ушка по оси Y",
        ("*", "Chamfer size on outer vertical edges of the ear"): "Размер фаски на внешних вертикальных рёбрах ушка",
        ("*", "Number of chamfer segments (1 = flat, 4+ = rounded)"): "Количество сегментов фаски (1 = прямая, 4+ = скругление)",
        ("*", "Ear offset along Y relative to base centre"): "Смещение ушка по Y относительно центра подложки",
        ("*", "Diameter of the key ring hole"):      "Диаметр отверстия для кольца",
        ("*", "Distance from the nearest hole edge to the outer ear edge"): "Расстояние от ближайшего края отверстия до внешнего края ушка",
        ("*", "Expand hole along Y so its edges are exactly Hole Edge Margin away from the ear edges"): "Расширить отверстие по Y так, чтобы расстояние от его краёв до краёв ушка равнялось значению «Отступ от края ушка»",
    }
}


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
# Подложка
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
# Буквы
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
# Ушко: сварка методом из PDF
# ---------------------------------------------------------------------------

def weld_ear_pdf_method(context, base_obj, ear_obj, inner_x, y0, y1, side="LEFT"):
    # Join
    deselect_all()
    base_obj.select_set(True)
    ear_obj.select_set(True)
    context.view_layer.objects.active = base_obj
    bpy.ops.object.join()
    joined = context.active_object

    ts = context.scene.tool_settings
    old_automerge = ts.use_mesh_automerge
    old_split     = getattr(ts, 'use_mesh_automerge_and_split', False)
    old_threshold = ts.double_threshold
    old_snap      = ts.use_snap

    ts.use_mesh_automerge = True
    if hasattr(ts, 'use_mesh_automerge_and_split'):
        ts.use_mesh_automerge_and_split = True
    ts.double_threshold = 0.0001
    ts.use_snap = False

    try:
        bpy.ops.object.editmode_toggle()
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

        ear_bot = right_verts[0]
        ear_top = right_verts[-1]

        extrude_dir  = 1.0 if side == "LEFT" else -1.0
        extrude_dist = 5.0 * extrude_dir

        for ear_v in [ear_bot, ear_top]:
            if not ear_v.is_valid:
                continue
            for v in bm.verts:
                v.select = False
            bm.select_flush(False)
            ear_v.select = True
            bmesh.update_edit_mesh(joined.data)

            bpy.ops.mesh.extrude_vertices_move(
                TRANSFORM_OT_translate={
                    "value": (extrude_dist, 0.0, 0.0),
                    "constraint_axis": (True, False, False)
                }
            )

            bm = bmesh.from_edit_mesh(joined.data)
            bm.verts.ensure_lookup_table()

            to_delete = [v for v in bm.verts if v.select and v.is_valid]
            if to_delete:
                bmesh.ops.delete(bm, geom=to_delete, context="VERTS")
                bm = bmesh.from_edit_mesh(joined.data)
                bm.verts.ensure_lookup_table()

        bm.verts.ensure_lookup_table()
        for v in bm.verts:
            v.select = False

        tol_x = 0.15
        tol_y = 0.15

        ear_right = [v for v in bm.verts
                     if abs(v.co.x - inner_x) < tol_x
                     and (y0 - tol_y) < v.co.y < (y1 + tol_y)]

        if side == "LEFT":
            base_region = [v for v in bm.verts
                           if v.co.x > inner_x + 0.01
                           and (y0 - tol_y) < v.co.y < (y1 + tol_y)]
        else:
            base_region = [v for v in bm.verts
                           if v.co.x < inner_x - 0.01
                           and (y0 - tol_y) < v.co.y < (y1 + tol_y)]

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
        bpy.ops.mesh.fill()

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


# ---------------------------------------------------------------------------
# Ушко: создание 2D плоскости
# ---------------------------------------------------------------------------

def create_ear_2d(context, left_x, right_x, y0, y1, chamfer, segs):
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
    mesh    = bpy.data.meshes.new("_KM_Ear")
    ear_obj = bpy.data.objects.new("_KM_Ear", mesh)
    context.collection.objects.link(ear_obj)

    c = chamfer
    bm = bmesh.new()

    if c > 0.0 and segs >= 1:
        pts2d = []
        pts2d.append((inner_x, y0))
        pts2d.append((inner_x, y1))
        for i in range(segs + 1):
            a = math.pi * 0.5 - math.pi * 0.5 * (i / segs)
            pts2d.append((outer_x - c + math.cos(a) * c,
                          y1 - c + math.sin(a) * c))
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


# ---------------------------------------------------------------------------
# Отверстие в ушке
# ---------------------------------------------------------------------------

def cut_ear_hole(context, obj, outer_x, yc, base_h, hole_d, side="LEFT", margin=2.0, oval=False, lug_y=6.0):
    hole_r = hole_d / 2.0
    if side == "LEFT":
        cx = outer_x + hole_r + margin
    else:
        cx = outer_x - hole_r - margin
    cy  = yc
    cz  = base_h / 2.0

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=hole_r,
        depth=base_h + 1.0,
        location=(cx, cy, cz),
    )
    cyl = context.active_object
    cyl.name = "_KM_EarHoleCyl"

    if oval:
        oval_ry = lug_y / 2.0 - margin
        if oval_ry > hole_r:
            cyl.scale.y = oval_ry / hole_r
            bpy.ops.object.transform_apply(scale=True)

    set_active(context, obj)
    mod = obj.modifiers.new("EarHole", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object    = cyl
    mod.solver    = "EXACT"
    bpy.ops.object.modifier_apply(modifier="EarHole")
    delete_obj(cyl)


# ---------------------------------------------------------------------------
# Оператор генерации
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Generate(Operator):
    bl_idname      = "keychain.generate"
    bl_label       = "Create Keychain"
    bl_description = "Generate a 3D-printable keychain from the current settings"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self, context):
        props     = context.scene.keychain_props
        text      = props.text
        font_path = props.font_path
        offset    = props.base_offset
        base_h    = props.base_height
        letter_h  = props.letter_height

        if not text:
            self.report({"WARNING"}, "Enter text!")
            return {"CANCELLED"}

        text_or_font_changed = (text != props.last_text or font_path != props.last_font)
        if not text_or_font_changed and props.last_name:
            old = bpy.data.objects.get(props.last_name)
            if old:
                bpy.data.objects.remove(old, do_unlink=True)

        delete_by_prefix("_KM_")

        # ── 1. Текст → меш ─────────────────────────────────────────────────
        bpy.ops.object.text_add(location=(0, 0, 0))
        txt_obj = context.active_object
        txt_obj.data.body = text
        txt_obj.data.size = 10.0
        txt_obj.data.space_character = props.char_spacing
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
            self.report({"ERROR"}, "Text has no vertices.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 2. Точки вдоль рёбер ───────────────────────────────────────────
        pts = points_along_edges(letters_obj, offset * 0.7)
        if len(pts) < 2:
            self.report({"ERROR"}, "Could not get text edges.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 3. Плоская подложка ────────────────────────────────────────────
        base_flat = build_flat_base(context, pts, offset)
        if not base_flat.data.vertices or not base_flat.data.polygons:
            self.report({"ERROR"}, "Base is empty.")
            delete_obj(base_flat)
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Ушко ────────────────────────────────────────────────────────
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

            gap = 0.5
            yc  = base_cy + oy
            y0  = yc - lug_y / 2.0
            y1  = yc + lug_y / 2.0

            if side == 'LEFT':
                inner_x = base_min_x - gap
                outer_x = inner_x - lug_x
                ear_obj = create_ear_2d(context, outer_x, inner_x, y0, y1, chamfer, segs)
            else:
                inner_x = base_max_x + gap
                outer_x = inner_x + lug_x
                ear_obj = create_ear_2d_right(context, inner_x, outer_x, y0, y1, chamfer, segs)

            base_flat = weld_ear_pdf_method(
                context, base_flat, ear_obj,
                inner_x, y0, y1, side=side
            )

            ear_info = {"outer_x": outer_x, "yc": yc, "side": side, "lug_y": lug_y}

        # ── 5. Экструзия подложки вниз ─────────────────────────────────────
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

        # ── 7. Join + поднимаем ────────────────────────────────────────────
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
                         ear_info.get("side", "LEFT"),
                         props.lug_hole_margin,
                         props.lug_hole_oval,
                         ear_info.get("lug_y", 6.0))

        # ── 9. Shade Auto Smooth ───────────────────────────────────────────
        set_active(context, final_obj)
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(30.0))
        except Exception:
            bpy.ops.object.shade_smooth()

        safe = "".join(
            c for c in text if c.isascii() and (c.isalnum() or c in " _-")
        )[:20].strip() or "keychain"
        final_obj.name = f"Keychain_{safe}"

        props.last_name = final_obj.name
        props.last_text = text
        props.last_font = font_path

        self.report({"INFO"}, f"Keychain '{text}' created!")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Свойства
# ---------------------------------------------------------------------------

class KeychainProperties(PropertyGroup):
    text: StringProperty(
        name="Text",
        description="Text to engrave on the keychain",
        default="Sergey")
    font_path: StringProperty(
        name="Font (.ttf)",
        description="Path to TTF/OTF font file",
        subtype="FILE_PATH", default="")
    char_spacing: FloatProperty(
        name="Char Spacing",
        description="Character spacing (1.0 = default, less = tighter)",
        default=1.0, min=0.1, max=3.0,
        precision=2, step=5)
    base_offset: FloatProperty(
        name="Base Offset (mm)",
        description="How much the base extends beyond the letters",
        default=2.0, min=0.5, max=30.0,
        precision=1, step=10)
    base_height: FloatProperty(
        name="Base Height (mm)",
        description="Thickness of the base plate",
        default=3.0, min=0.5, max=20.0,
        precision=1, step=10)
    letter_height: FloatProperty(
        name="Letter Height (mm)",
        description="How much letters protrude above the base",
        default=2.0, min=0.2, max=10.0,
        precision=1, step=10)
    lug_enable: BoolProperty(
        name="Add Ear",
        description="Add a key ring ear to the keychain",
        default=True)
    lug_side: EnumProperty(
        name="Ear Side",
        description="Which side to place the ear on",
        items=[
            ('LEFT',  "Left",  "Ear on the left side"),
            ('RIGHT', "Right", "Ear on the right side"),
        ],
        default='LEFT')
    lug_size_x: FloatProperty(
        name="Ear Length X (mm)",
        description="Ear length along X axis",
        default=6.0, min=3.0, max=30.0,
        precision=1, step=10)
    lug_size_y: FloatProperty(
        name="Ear Width Y (mm)",
        description="Ear width along Y axis",
        default=6.0, min=3.0, max=30.0,
        precision=1, step=10)
    lug_chamfer: FloatProperty(
        name="Chamfer (mm)",
        description="Chamfer size on outer vertical edges of the ear",
        default=1.5, min=0.0, max=5.0,
        precision=1, step=5)
    lug_chamfer_segments: IntProperty(
        name="Chamfer Segments",
        description="Number of chamfer segments (1 = flat, 4+ = rounded)",
        default=4, min=1, max=16)
    lug_offset_y: FloatProperty(
        name="Y Offset (mm)",
        description="Ear offset along Y relative to base centre",
        default=0.0, min=-50.0, max=50.0,
        precision=1, step=10)
    lug_hole_diameter: FloatProperty(
        name="Hole Diameter (mm)",
        description="Diameter of the key ring hole",
        default=2.0, min=0.5, max=10.0,
        precision=1, step=5)
    lug_hole_margin: FloatProperty(
        name="Hole Edge Margin (mm)",
        description="Distance from the nearest hole edge to the outer ear edge",
        default=2.0, min=0.5, max=10.0,
        precision=1, step=5)
    lug_hole_oval: BoolProperty(
        name="Oval Hole",
        description="Expand hole along Y so its edges are exactly Hole Edge Margin away from the ear edges",
        default=False)
    # Internal tracking — not shown in UI
    last_name: StringProperty(default="", options={"HIDDEN"})
    last_text: StringProperty(default="", options={"HIDDEN"})
    last_font: StringProperty(default="", options={"HIDDEN"})


# ---------------------------------------------------------------------------
# Оператор сброса настроек
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Reset(Operator):
    bl_idname      = "keychain.reset_settings"
    bl_label       = "Reset Settings"
    bl_description = "Reset all parameters to default values"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.keychain_props
        p.text                 = "Sergey"
        p.font_path            = ""
        p.char_spacing         = 1.0
        p.base_offset          = 2.0
        p.base_height          = 3.0
        p.letter_height        = 2.0
        p.lug_enable           = True
        p.lug_side             = "LEFT"
        p.lug_size_x           = 6.0
        p.lug_size_y           = 6.0
        p.lug_chamfer          = 1.5
        p.lug_chamfer_segments = 4
        p.lug_offset_y         = 0.0
        p.lug_hole_diameter    = 2.0
        p.lug_hole_margin      = 2.0
        p.lug_hole_oval        = False
        self.report({"INFO"}, "Settings reset")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# N-Panel
# ---------------------------------------------------------------------------

class KEYCHAIN_PT_Panel(Panel):
    bl_label       = "Keychain Maker"
    bl_idname      = "KEYCHAIN_PT_Panel"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Keychain 1.1"

    def draw(self, context):
        layout = self.layout
        props  = context.scene.keychain_props

        box = layout.box()
        box.label(text="Text", icon="FONT_DATA")
        box.prop(props, "text")
        box.prop(props, "font_path")
        box.prop(props, "char_spacing")

        box = layout.box()
        box.label(text="Base", icon="MESH_PLANE")
        box.prop(props, "base_offset")
        box.prop(props, "base_height")
        box.prop(props, "letter_height")

        box = layout.box()
        box.label(text="Ear", icon="LINKED")
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
            box.prop(props, "lug_hole_margin")
            box.prop(props, "lug_hole_oval")

        layout.separator()
        layout.operator("keychain.generate", icon="MESH_DATA")
        layout.separator()
        layout.operator("keychain.reset_settings", icon="LOOP_BACK")


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------

classes = (KeychainProperties, KEYCHAIN_OT_Generate, KEYCHAIN_OT_Reset, KEYCHAIN_PT_Panel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.keychain_props = bpy.props.PointerProperty(type=KeychainProperties)
    bpy.app.translations.register(__name__, translations_dict)

def unregister():
    bpy.app.translations.unregister(__name__)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.keychain_props

if __name__ == "__main__":
    register()
