# Copyright (C) 2026 Your Name
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the consideration of
# merchantability or fitness for a particular purpose. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

bl_info = {
    "name": "Keychain Builder for Blender 5.0",
    "author": "@kabser",
    "version": (1, 0, 0),
    "blender": (5, 0, 1),
    "location": "View3D > Sidebar > Keychain",
    "description": "Build keychain by joining filled expanded pads, adding side ear, cutting ear hole, assigning materials and exporting STL",
    "category": "3D View",
}

import bpy
import bmesh
import os
import math
from mathutils import Vector
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import (
    StringProperty,
    PointerProperty,
    FloatProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
)
from bpy_extras.io_utils import ImportHelper
from bpy.app.translations import contexts as i18n_contexts


MM = 0.001


translations_dict = {
    "ru_RU": {
        (i18n_contexts.default, "Keychain"): "Брелок",

        (i18n_contexts.default, "Text"): "Текст",
        (i18n_contexts.default, "Text to generate on the keychain"): "Текст для генерации брелока",

        (i18n_contexts.default, "Font Path"): "Путь к шрифту",
        (i18n_contexts.default, "Path to TTF or OTF font file"): "Путь к файлу шрифта TTF или OTF",

        (i18n_contexts.default, "Letter Spacing"): "Межбуквенный интервал",
        (i18n_contexts.default, "Character spacing factor for the generated text"): "Коэффициент межбуквенного интервала для генерируемого текста",

        (i18n_contexts.default, "Width (mm)"): "Ширина (мм)",
        (i18n_contexts.default, "Target total width of the generated keychain"): "Целевая общая ширина готового брелока",

        (i18n_contexts.default, "Base Merge Distance (mm)"): "Base Merge Distance (мм)",
        (i18n_contexts.default, "Merge distance for the base geometry before creating the backing shape"): "Порог склейки близких вершин для геометрии основания перед созданием подложки",

        (i18n_contexts.default, "Top Merge Distance (mm)"): "Top Merge Distance (мм)",
        (i18n_contexts.default, "Merge distance for the top text geometry"): "Порог склейки близких вершин для верхнего текста",

        (i18n_contexts.default, "Base Margin (mm)"): "Запас основания (мм)",
        (i18n_contexts.default, "Extra margin around letters for the base backing shape"): "Дополнительный запас вокруг букв для основания",

        (i18n_contexts.default, "Base Thickness (mm)"): "Толщина основания (мм)",
        (i18n_contexts.default, "Thickness of the lower base part"): "Толщина нижней части основания",

        (i18n_contexts.default, "Text Height (mm)"): "Высота текста (мм)",
        (i18n_contexts.default, "Height of the raised top text"): "Высота выступающего верхнего текста",

        (i18n_contexts.default, "Sharp Angle Limit (deg)"): "Порог острого угла (°)",
        (i18n_contexts.default, "Angles sharper than this may be softened on the base outline"): "Углы острее этого значения могут быть смягчены на контуре основания",

        (i18n_contexts.default, "Corner Inset (mm)"): "Скругление угла (мм)",
        (i18n_contexts.default, "Inset amount used to soften sharp corners"): "Величина отступа для смягчения острых углов",

        (i18n_contexts.default, "Corner Segments"): "Сегменты скругления",
        (i18n_contexts.default, "Number of segments used for corner smoothing"): "Количество сегментов для скругления углов",

        (i18n_contexts.default, "Add Side Ear"): "Добавить ушко",
        (i18n_contexts.default, "Add a side ear for the key ring hole"): "Добавить ушко сбоку для отверстия под кольцо",

        (i18n_contexts.default, "Ear Side"): "Сторона ушка",
        (i18n_contexts.default, "Choose which side to place the ear on"): "Выберите, с какой стороны размещать ушко",

        (i18n_contexts.default, "Left"): "Слева",
        (i18n_contexts.default, "Place the ear on the left side"): "Разместить ушко с левой стороны",

        (i18n_contexts.default, "Right"): "Справа",
        (i18n_contexts.default, "Place the ear on the right side"): "Разместить ушко с правой стороны",

        (i18n_contexts.default, "Ear Height (mm)"): "Высота ушка (мм)",
        (i18n_contexts.default, "Height of the side ear"): "Высота бокового ушка",

        (i18n_contexts.default, "Ear Length (mm)"): "Длина ушка (мм)",
        (i18n_contexts.default, "Length of the side ear"): "Длина бокового ушка",

        (i18n_contexts.default, "Ear Y Offset (mm)"): "Смещение ушка по Y (мм)",
        (i18n_contexts.default, "Vertical offset of the ear"): "Смещение ушка по вертикали",

        (i18n_contexts.default, "Ear Gap (mm)"): "Зазор от подложки (мм)",
        (i18n_contexts.default, "Gap between the ear and the base before auto-weld"): "Зазор между ушком и основанием до автосоединения",

        (i18n_contexts.default, "Ear Bevel (mm)"): "Скругление ушка (мм)",
        (i18n_contexts.default, "Bevel size on the outer side of the ear"): "Размер скругления на внешнем крае ушка",

        (i18n_contexts.default, "Ear Bevel Segments"): "Сегменты скругления ушка",
        (i18n_contexts.default, "Number of bevel segments on the ear"): "Количество сегментов скругления ушка",

        (i18n_contexts.default, "Intersection Search Step (mm)"): "Шаг поиска пересечения (мм)",
        (i18n_contexts.default, "Step used while pushing the ear into the base"): "Шаг, используемый при заходе ушка в основание",

        (i18n_contexts.default, "Max Push Into Base (mm)"): "Макс. заход в подложку (мм)",
        (i18n_contexts.default, "Maximum distance the ear may be pushed into the base"): "Максимальная глубина захода ушка в основание",

        (i18n_contexts.default, "Create Ear Hole"): "Сделать отверстие в ушке",
        (i18n_contexts.default, "Create a round hole inside the ear"): "Создать круглое отверстие внутри ушка",

        (i18n_contexts.default, "Hole Diameter (mm)"): "Диаметр отверстия (мм)",
        (i18n_contexts.default, "Diameter of the round hole in the ear"): "Диаметр круглого отверстия в ушке",

        (i18n_contexts.default, "Hole Offset From Outer Edge (mm)"): "Отступ отверстия от внешнего края (мм)",
        (i18n_contexts.default, "Distance from the outer edge of the ear to the nearest edge of the hole"): "Расстояние от внешнего края ушка до ближайшего края отверстия",

        (i18n_contexts.default, "Hole Y Offset (mm)"): "Смещение отверстия по Y (мм)",
        (i18n_contexts.default, "Vertical offset of the hole center"): "Смещение центра отверстия по вертикали",

        (i18n_contexts.default, "Hole Segments"): "Сегменты отверстия",
        (i18n_contexts.default, "Number of segments used for the hole cutter cylinder"): "Количество сегментов цилиндра, вырезающего отверстие",

        (i18n_contexts.default, "Overhang Angle (deg)"): "Overhang Angle (°)",
        (i18n_contexts.default, "Faces steeper than this overhang angle are detected before base extrusion"): "Грани круче этого угла нависания определяются перед экструзией основания",

        (i18n_contexts.default, "Delete Overhang Faces Before Extrude"): "Удалять overhang faces перед Extrude",
        (i18n_contexts.default, "Delete detected overhang faces before extruding the base"): "Удалять найденные нависающие грани перед экструзией основания",

        (i18n_contexts.default, "Hide Helpers"): "Скрыть вспомогательные объекты",
        (i18n_contexts.default, "Hide intermediate helper objects after build"): "Скрывать промежуточные вспомогательные объекты после построения",

        (i18n_contexts.default, "Choose Font"): "Выбрать шрифт",
        (i18n_contexts.default, "Build Joined Filled Pads"): "Построить Joined Filled Pads",
        (i18n_contexts.default, "Save STL"): "Сохранить STL",
        (i18n_contexts.default, "STL File"): "Файл STL",

        (i18n_contexts.default, "Base"): "Основа",
        (i18n_contexts.default, "Base Advanced"): "Основа — доп. настройки",
        (i18n_contexts.default, "Ear"): "Ушко",
        (i18n_contexts.default, "Hole"): "Отверстие",
        (i18n_contexts.default, "Checks"): "Проверки",
        (i18n_contexts.default, "Export"): "Экспорт",

        (i18n_contexts.default, "Reset All Settings"): "Сбросить все настройки",
        (i18n_contexts.default, "Reset all addon settings to factory defaults"): "Сбросить все настройки аддона к заводским значениям",
    }
}


def mm(v):
    return v * MM


def ensure_object_mode():
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def deselect_all():
    for obj in bpy.context.selected_objects:
        obj.select_set(False)


def set_active(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def cleanup_name(name):
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in name.strip())
    return safe or "text"


def get_or_create_collection(name):
    scene = bpy.context.scene
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        scene.collection.children.link(coll)
    return coll


def move_object_to_collection(obj, collection):
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    if collection.objects.get(obj.name) is None:
        collection.objects.link(obj)


def remove_object_and_data(obj):
    if obj is None:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data and hasattr(data, "users") and data.users == 0:
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)


def clear_generated_objects(collection, base_name):
    prefixes = [
        f"KCB5J10_Text_{base_name}",
        f"KCB5J10_TextCurve_{base_name}",
        f"KCB5J10_SourceMesh_{base_name}",
        f"KCB5J10_BaseSource_{base_name}",
        f"TopText_{base_name}",
        f"LetterPart_{base_name}",
        f"PadLetter_{base_name}",
        f"BasePad2D_{base_name}",
        f"BasePad3D_{base_name}",
        f"FinalKeychain_{base_name}",
        f"EarPlane_{base_name}",
        f"EarHoleCutter_{base_name}",
    ]
    for obj in list(collection.objects):
        if any(obj.name.startswith(prefix) for prefix in prefixes):
            remove_object_and_data(obj)


def create_text_curve(body, font_path="", base_name="Text", letter_spacing=1.0):
    data = bpy.data.curves.new(name=f"KCB5J10_TextCurve_{base_name}", type='FONT')
    data.body = body
    data.align_x = 'CENTER'
    data.align_y = 'CENTER'
    data.size = 1.0
    data.space_character = letter_spacing
    data.fill_mode = 'BOTH'
    data.resolution_u = 32
    data.extrude = 0.0
    data.bevel_depth = 0.0
    data.bevel_resolution = 0

    font_abs = bpy.path.abspath(font_path) if font_path else ""
    if font_abs and os.path.exists(font_abs):
        data.font = bpy.data.fonts.load(font_abs, check_existing=True)

    obj = bpy.data.objects.new(f"KCB5J10_Text_{base_name}", data)
    bpy.context.collection.objects.link(obj)
    return obj


def duplicate_object(obj, new_name):
    dup = obj.copy()
    if obj.data:
        dup.data = obj.data.copy()
    dup.name = new_name
    bpy.context.collection.objects.link(dup)
    return dup


def convert_to_mesh(obj):
    deselect_all()
    set_active(obj)
    bpy.ops.object.convert(target='MESH')
    return bpy.context.view_layer.objects.active


def apply_scale(obj):
    deselect_all()
    set_active(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def mesh_bbox_xy(obj):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not verts:
        return 0.0, 0.0, 0.0, 0.0
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    return min(xs), min(ys), max(xs), max(ys)


def object_width_xy(obj):
    x0, _, x1, _ = mesh_bbox_xy(obj)
    return x1 - x0


def set_object_width_mm_and_apply(obj, target_width_mm):
    target_width_m = mm(target_width_mm)
    width = object_width_xy(obj)
    if width <= 1e-9:
        raise ValueError("Ширина объекта равна нулю, масштабировать невозможно")

    factor = target_width_m / width
    obj.scale = (obj.scale.x * factor, obj.scale.y * factor, obj.scale.z * factor)
    bpy.context.view_layer.update()
    apply_scale(obj)
    bpy.context.view_layer.update()
    return object_width_xy(obj) / MM


def clean_mesh_for_base(obj, merge_distance_mm=0.2):
    ensure_object_mode()
    deselect_all()
    set_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.dissolve_limited()
    bpy.ops.mesh.remove_doubles(threshold=mm(merge_distance_mm))
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def clean_mesh_for_top(obj, merge_distance_mm=0.0):
    ensure_object_mode()
    deselect_all()
    set_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    if merge_distance_mm > 0.0:
        bpy.ops.mesh.remove_doubles(threshold=mm(merge_distance_mm))
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def separate_loose_parts(obj):
    ensure_object_mode()
    deselect_all()
    set_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')

    parts = list(bpy.context.selected_objects)
    parts.sort(key=lambda o: mesh_bbox_xy(o)[0])
    return parts


def join_objects(objects, name):
    valid = [o for o in objects if o is not None]
    if not valid:
        return None

    ensure_object_mode()
    deselect_all()
    for obj in valid:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = valid[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    return joined


def extrude_mesh_z(obj, delta_z):
    ensure_object_mode()
    deselect_all()
    set_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0.0, 0.0, delta_z)}
    )
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def polygon_signed_area(points):
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def ensure_ccw(points):
    pts2d = [(p.x, p.y) for p in points]
    if polygon_signed_area(pts2d) < 0:
        return list(reversed(points))
    return points


def extract_boundary_loops(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if not boundary_edges:
        bm.free()
        return []

    vert_to_edges = {}
    for e in boundary_edges:
        for v in e.verts:
            vert_to_edges.setdefault(v.index, []).append(e)

    unused = set(id(e) for e in boundary_edges)
    edge_by_id = {id(e): e for e in boundary_edges}
    loops = []

    while unused:
        start_edge_id = next(iter(unused))
        start_edge = edge_by_id[start_edge_id]
        v0 = start_edge.verts[0]
        v1 = start_edge.verts[1]

        loop = [v0.co.copy(), v1.co.copy()]
        unused.remove(start_edge_id)

        prev_v = v0
        current_v = v1

        guard = 0
        while guard < 100000:
            guard += 1
            connected = vert_to_edges.get(current_v.index, [])
            next_edge = None

            for e in connected:
                if id(e) not in unused:
                    continue
                other = e.other_vert(current_v)
                if other.index == prev_v.index:
                    continue
                next_edge = e
                break

            if next_edge is None:
                for e in connected:
                    if id(e) in unused:
                        next_edge = e
                        break

            if next_edge is None:
                break

            unused.remove(id(next_edge))
            next_v = next_edge.other_vert(current_v)

            if next_v.index == v0.index:
                break

            loop.append(next_v.co.copy())
            prev_v = current_v
            current_v = next_v

        if len(loop) >= 3:
            loop = ensure_ccw(loop)
            pts2d = [(p.x, p.y) for p in loop]
            loops.append({
                "points": loop,
                "area": abs(polygon_signed_area(pts2d)),
            })

    bm.free()
    return loops


def line_intersection_2d(p1, d1, p2, d2):
    cross = d1.x * d2.y - d1.y * d2.x
    if abs(cross) < 1e-10:
        return None
    diff = p2 - p1
    t = (diff.x * d2.y - diff.y * d2.x) / cross
    return p1 + d1 * t


def soften_sharp_corners(points, angle_limit_deg=55.0, inset_mm=0.25, segments=3):
    pts = ensure_ccw(points)
    n = len(pts)
    if n < 3:
        return pts[:]

    inset = mm(inset_mm)
    result = []

    for i in range(n):
        p_prev = Vector((pts[(i - 1) % n].x, pts[(i - 1) % n].y))
        p_curr = Vector((pts[i].x, pts[i].y))
        p_next = Vector((pts[(i + 1) % n].x, pts[(i + 1) % n].y))

        v_in = p_prev - p_curr
        v_out = p_next - p_curr

        len_in = v_in.length
        len_out = v_out.length

        if len_in < 1e-10 or len_out < 1e-10:
            result.append(Vector((p_curr.x, p_curr.y, 0.0)))
            continue

        d_in = v_in.normalized()
        d_out = v_out.normalized()

        dot_val = max(-1.0, min(1.0, d_in.dot(d_out)))
        angle_deg = math.degrees(math.acos(dot_val))
        local_inset = min(inset, len_in * 0.35, len_out * 0.35)

        if angle_deg >= angle_limit_deg or local_inset <= 1e-9:
            result.append(Vector((p_curr.x, p_curr.y, 0.0)))
            continue

        p1 = p_curr + d_in * local_inset
        p2 = p_curr + d_out * local_inset

        a1 = math.atan2((p1 - p_curr).y, (p1 - p_curr).x)
        a2 = math.atan2((p2 - p_curr).y, (p2 - p_curr).x)

        delta = a2 - a1
        while delta <= -math.pi:
            delta += math.tau
        while delta > math.pi:
            delta -= math.tau
        if delta < 0:
            delta += math.tau

        if delta > math.pi:
            result.append(Vector((p_curr.x, p_curr.y, 0.0)))
            continue

        result.append(Vector((p1.x, p1.y, 0.0)))
        for s in range(1, max(segments, 1)):
            t = s / float(segments)
            ang = a1 + delta * t
            p_arc = Vector((
                p_curr.x + math.cos(ang) * local_inset,
                p_curr.y + math.sin(ang) * local_inset,
                0.0
            ))
            result.append(p_arc)
        result.append(Vector((p2.x, p2.y, 0.0)))

    return ensure_ccw(result)


def expand_loop(points, offset):
    pts = ensure_ccw(points)
    n = len(pts)
    if n < 3:
        return pts[:]

    expanded = []

    for i in range(n):
        p_prev = Vector((pts[(i - 1) % n].x, pts[(i - 1) % n].y))
        p_curr = Vector((pts[i].x, pts[i].y))
        p_next = Vector((pts[(i + 1) % n].x, pts[(i + 1) % n].y))

        e1 = p_curr - p_prev
        e2 = p_next - p_curr

        if e1.length < 1e-10 or e2.length < 1e-10:
            expanded.append(Vector((p_curr.x, p_curr.y, 0.0)))
            continue

        d1 = e1.normalized()
        d2 = e2.normalized()

        n1 = Vector((d1.y, -d1.x))
        n2 = Vector((d2.y, -d2.x))

        p1 = p_prev + n1 * offset
        p3 = p_curr + n2 * offset

        inter = line_intersection_2d(p1, d1, p3, d2)

        if inter is None:
            avg_n = (n1 + n2)
            if avg_n.length < 1e-10:
                new_p = p_curr + n1 * offset
            else:
                new_p = p_curr + avg_n.normalized() * offset
        else:
            max_dist = max(offset * 6.0, mm(0.5))
            if (inter - p_curr).length > max_dist:
                avg_n = (n1 + n2)
                if avg_n.length < 1e-10:
                    new_p = p_curr + n1 * offset
                else:
                    new_p = p_curr + avg_n.normalized() * offset
            else:
                new_p = inter

        expanded.append(Vector((new_p.x, new_p.y, 0.0)))

    return ensure_ccw(expanded)


def create_filled_mesh_from_loop(points3d, name):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    verts = [bm.verts.new((p.x, p.y, 0.0)) for p in points3d]
    bm.verts.ensure_lookup_table()

    try:
        bm.faces.new(verts)
    except ValueError:
        pass

    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()

    return obj


def build_pad_from_letter(letter_obj, new_name, margin_mm, angle_limit_deg, corner_inset_mm, corner_segments):
    loops = extract_boundary_loops(letter_obj)
    if not loops:
        return None

    outer = max(loops, key=lambda item: item["area"])
    softened = soften_sharp_corners(
        outer["points"],
        angle_limit_deg=angle_limit_deg,
        inset_mm=corner_inset_mm,
        segments=corner_segments
    )
    expanded = expand_loop(softened, mm(margin_mm))
    pad = create_filled_mesh_from_loop(expanded, new_name)
    pad.matrix_world = letter_obj.matrix_world.copy()
    return pad


def cleanup_joined_base(obj, merge_distance_mm=0.05):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=mm(merge_distance_mm))
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=mm(0.01))
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def setup_automerge_settings():
    ts = bpy.context.scene.tool_settings
    old = {
        "use_mesh_automerge": ts.use_mesh_automerge,
        "use_snap": ts.use_snap,
        "snap_elements": set(ts.snap_elements),
    }
    ts.use_mesh_automerge = True
    ts.use_snap = False
    return old


def restore_automerge_settings(old):
    ts = bpy.context.scene.tool_settings
    ts.use_mesh_automerge = old["use_mesh_automerge"]
    ts.use_snap = old["use_snap"]
    ts.snap_elements = old["snap_elements"]


def create_ear_plane_mesh(name, x_left, x_right, y_bottom, y_top):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    v_lb = bm.verts.new((x_left, y_bottom, 0.0))
    v_rb = bm.verts.new((x_right, y_bottom, 0.0))
    v_rt = bm.verts.new((x_right, y_top, 0.0))
    v_lt = bm.verts.new((x_left, y_top, 0.0))
    bm.verts.ensure_lookup_table()

    try:
        bm.faces.new([v_lb, v_rb, v_rt, v_lt])
    except ValueError:
        pass

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    return obj


def get_plane_side_edge_points(x_left, x_right, y_bottom, y_top, side):
    if side == 'LEFT':
        edge_bottom = Vector((x_right, y_bottom, 0.0))
        edge_top = Vector((x_right, y_top, 0.0))
    else:
        edge_bottom = Vector((x_left, y_bottom, 0.0))
        edge_top = Vector((x_left, y_top, 0.0))
    return edge_bottom, edge_top


def bevel_left_plane_corners(plane_obj, bevel_mm, segments):
    if bevel_mm <= 0.0:
        return

    ensure_object_mode()
    deselect_all()
    set_active(plane_obj)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')

    bm = bmesh.from_edit_mesh(plane_obj.data)
    bm.verts.ensure_lookup_table()

    x_values = [v.co.x for v in bm.verts]
    if not x_values:
        bpy.ops.object.mode_set(mode='OBJECT')
        return

    min_x = min(x_values)
    tol = mm(0.02)

    for v in bm.verts:
        v.select = abs(v.co.x - min_x) <= tol

    bmesh.update_edit_mesh(plane_obj.data)

    bpy.ops.mesh.bevel(
        offset=mm(bevel_mm),
        offset_type='OFFSET',
        segments=max(1, segments),
        affect='VERTICES'
    )

    bpy.ops.object.mode_set(mode='OBJECT')


def bevel_right_plane_corners(plane_obj, bevel_mm, segments):
    if bevel_mm <= 0.0:
        return

    ensure_object_mode()
    deselect_all()
    set_active(plane_obj)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')

    bm = bmesh.from_edit_mesh(plane_obj.data)
    bm.verts.ensure_lookup_table()

    x_values = [v.co.x for v in bm.verts]
    if not x_values:
        bpy.ops.object.mode_set(mode='OBJECT')
        return

    max_x = max(x_values)
    tol = mm(0.02)

    for v in bm.verts:
        v.select = abs(v.co.x - max_x) <= tol

    bmesh.update_edit_mesh(plane_obj.data)

    bpy.ops.mesh.bevel(
        offset=mm(bevel_mm),
        offset_type='OFFSET',
        segments=max(1, segments),
        affect='VERTICES'
    )

    bpy.ops.object.mode_set(mode='OBJECT')


def weld_side_ear_plane_into_base(base_pad_2d, plane_obj, edge_bottom, edge_top, props, side):
    old_settings = setup_automerge_settings()
    try:
        joined = join_objects([base_pad_2d, plane_obj], base_pad_2d.name)
        ensure_object_mode()
        deselect_all()
        set_active(joined)

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='VERT')

        bm = bmesh.from_edit_mesh(joined.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        tol = mm(0.02)

        def find_vert_by_co(target):
            matches = []
            for v in bm.verts:
                if (v.co - target).length <= tol:
                    matches.append(v)
            if not matches:
                return None
            matches.sort(key=lambda v: (v.co - target).length)
            return matches[0]

        def capture_state(v1, v2):
            return {
                "vert_count": len(bm.verts),
                "edge_count": len(bm.edges),
                "face_count": len(bm.faces),
                "v1_edges": len(v1.link_edges) if v1 and v1.is_valid else -1,
                "v2_edges": len(v2.link_edges) if v2 and v2.is_valid else -1,
                "v1_faces": len(v1.link_faces) if v1 and v1.is_valid else -1,
                "v2_faces": len(v2.link_faces) if v2 and v2.is_valid else -1,
            }

        def state_changed(base_state, current_state):
            if current_state["vert_count"] > base_state["vert_count"]:
                return True
            if current_state["edge_count"] > base_state["edge_count"]:
                return True
            if current_state["face_count"] > base_state["face_count"]:
                return True
            if current_state["v1_edges"] > base_state["v1_edges"]:
                return True
            if current_state["v2_edges"] > base_state["v2_edges"]:
                return True
            if current_state["v1_faces"] > base_state["v1_faces"]:
                return True
            if current_state["v2_faces"] > base_state["v2_faces"]:
                return True
            return False

        def refresh_bm():
            nonlocal bm
            bm = bmesh.from_edit_mesh(joined.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

        current_push_mm = 0.0
        direction = 1.0 if side == 'LEFT' else -1.0

        def move_pair(delta_x):
            nonlocal bm, current_push_mm
            v1 = find_vert_by_co(Vector((edge_bottom.x + direction * mm(current_push_mm), edge_bottom.y, edge_bottom.z)))
            v2 = find_vert_by_co(Vector((edge_top.x + direction * mm(current_push_mm), edge_top.y, edge_top.z)))
            if v1 is None or v2 is None:
                return False

            v1.co.x += delta_x
            v2.co.x += delta_x
            bm.normal_update()
            bmesh.update_edit_mesh(joined.data, loop_triangles=False, destructive=False)
            refresh_bm()
            return True

        v_a = find_vert_by_co(edge_bottom)
        v_b = find_vert_by_co(edge_top)

        if v_a is None or v_b is None:
            bpy.ops.object.mode_set(mode='OBJECT')
            raise ValueError("Не удалось найти две точки внутреннего края ушка после объединения")

        base_state = capture_state(v_a, v_b)

        coarse_step_mm = props.ear_plane_auto_step_mm
        coarse_step_m = mm(coarse_step_mm) * direction
        max_push_mm = props.ear_plane_auto_max_push_mm

        fine_step_mm = max(0.01, coarse_step_mm * 0.2)
        fine_step_m = mm(fine_step_mm) * direction

        coarse_steps = max(1, int(round(max_push_mm / coarse_step_mm)))
        fine_steps = max(1, int(math.ceil(coarse_step_mm / fine_step_mm)) + 2)

        hit_detected = False

        for _ in range(coarse_steps):
            ok = move_pair(coarse_step_m)
            if not ok:
                break

            current_push_mm += coarse_step_mm

            v_a = find_vert_by_co(Vector((edge_bottom.x + direction * mm(current_push_mm), edge_bottom.y, edge_bottom.z)))
            v_b = find_vert_by_co(Vector((edge_top.x + direction * mm(current_push_mm), edge_top.y, edge_top.z)))
            if v_a is None or v_b is None:
                break

            current_state = capture_state(v_a, v_b)
            if state_changed(base_state, current_state):
                hit_detected = True
                break

        if hit_detected:
            ok = move_pair(-coarse_step_m)
            if ok:
                current_push_mm -= coarse_step_mm
                if current_push_mm < 0.0:
                    current_push_mm = 0.0

                for _ in range(fine_steps):
                    ok = move_pair(fine_step_m)
                    if not ok:
                        break

                    current_push_mm += fine_step_mm

                    v_a = find_vert_by_co(Vector((edge_bottom.x + direction * mm(current_push_mm), edge_bottom.y, edge_bottom.z)))
                    v_b = find_vert_by_co(Vector((edge_top.x + direction * mm(current_push_mm), edge_top.y, edge_top.z)))
                    if v_a is None or v_b is None:
                        break

                    current_state = capture_state(v_a, v_b)
                    if state_changed(base_state, current_state):
                        break

        bpy.ops.object.mode_set(mode='OBJECT')
        cleanup_joined_base(joined, merge_distance_mm=0.01)
        return joined
    finally:
        restore_automerge_settings(old_settings)


def add_side_ear_plane_before_extrude(base_pad_2d, props, coll, base_name):
    x_min, y_min, x_max, y_max = mesh_bbox_xy(base_pad_2d)

    plane_length = mm(props.ear_plane_length_mm)
    plane_height = mm(props.ear_plane_height_mm)
    plane_gap = mm(props.ear_plane_gap_mm)

    side = props.ear_side

    if side == 'LEFT':
        x_right = x_min - plane_gap
        x_left = x_right - plane_length
    else:
        x_left = x_max + plane_gap
        x_right = x_left + plane_length

    y_center = (y_min + y_max) * 0.5 + mm(props.ear_plane_y_offset_mm)
    y_bottom = y_center - plane_height * 0.5
    y_top = y_center + plane_height * 0.5

    plane_obj = create_ear_plane_mesh(
        f"EarPlane_{base_name}",
        x_left,
        x_right,
        y_bottom,
        y_top
    )
    move_object_to_collection(plane_obj, coll)

    edge_bottom, edge_top = get_plane_side_edge_points(
        x_left, x_right, y_bottom, y_top, side
    )

    if side == 'LEFT':
        bevel_left_plane_corners(
            plane_obj,
            props.ear_plane_bevel_mm,
            props.ear_plane_bevel_segments
        )
    else:
        bevel_right_plane_corners(
            plane_obj,
            props.ear_plane_bevel_mm,
            props.ear_plane_bevel_segments
        )

    joined = weld_side_ear_plane_into_base(
        base_pad_2d,
        plane_obj,
        edge_bottom,
        edge_top,
        props,
        side
    )
    move_object_to_collection(joined, coll)

    ear_info = {
        "side": side,
        "x_left": x_left,
        "x_right": x_right,
        "y_bottom": y_bottom,
        "y_top": y_top,
        "y_center": y_center,
        "height": plane_height,
        "length": plane_length,
    }

    return joined, ear_info


def create_ear_hole_cutter(base_name, center, radius_m, depth_m, segments):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=max(12, segments),
        radius=radius_m,
        depth=depth_m,
        enter_editmode=False,
        align='WORLD',
        location=center,
        rotation=(0.0, 0.0, 0.0)
    )
    cutter = bpy.context.active_object
    cutter.name = f"EarHoleCutter_{base_name}"
    return cutter


def apply_boolean_difference(target_obj, cutter_obj, modifier_name="EarHoleBoolean"):
    ensure_object_mode()

    deselect_all()
    set_active(target_obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    deselect_all()
    set_active(cutter_obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    deselect_all()
    set_active(target_obj)

    mod = target_obj.modifiers.new(name=modifier_name, type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.operand_type = 'OBJECT'
    mod.object = cutter_obj
    mod.solver = 'EXACT'

    if hasattr(mod, "use_hole_tolerant"):
        mod.use_hole_tolerant = True

    bpy.ops.object.modifier_apply(modifier=mod.name)


def cut_hole_in_side_ear(base_pad_3d, props, coll, base_name, ear_info):
    if not props.add_side_ear or not props.ear_hole_enable:
        return base_pad_3d

    if not ear_info:
        return base_pad_3d

    hole_radius = mm(props.ear_hole_diameter_mm * 0.5)

    side = ear_info["side"]
    ear_x_left = ear_info["x_left"]
    ear_x_right = ear_info["x_right"]
    ear_y_center = ear_info["y_center"]
    half_height = ear_info["height"] * 0.5

    if side == 'LEFT':
        hole_center_x = ear_x_left + mm(props.ear_hole_offset_x_mm) + hole_radius
    else:
        hole_center_x = ear_x_right - mm(props.ear_hole_offset_x_mm) - hole_radius

    hole_center_y = ear_y_center + mm(props.ear_hole_offset_y_mm)

    safe_margin = hole_radius + mm(0.2)

    min_x_allowed = ear_x_left + safe_margin
    max_x_allowed = ear_x_right - safe_margin

    if min_x_allowed > max_x_allowed:
        raise ValueError("Отверстие слишком большое для ушка по ширине")

    if hole_center_x < min_x_allowed:
        hole_center_x = min_x_allowed
    if hole_center_x > max_x_allowed:
        hole_center_x = max_x_allowed

    min_y_allowed = ear_y_center - half_height + safe_margin
    max_y_allowed = ear_y_center + half_height - safe_margin

    if min_y_allowed > max_y_allowed:
        raise ValueError("Отверстие слишком большое для ушка по высоте")

    if hole_center_y < min_y_allowed:
        hole_center_y = min_y_allowed
    if hole_center_y > max_y_allowed:
        hole_center_y = max_y_allowed

    depth_m = mm(max(props.base_thickness_mm, props.text_height_mm) + 20.0)

    cutter = create_ear_hole_cutter(
        base_name,
        (hole_center_x, hole_center_y, -mm(props.base_thickness_mm) * 0.5),
        hole_radius,
        depth_m,
        props.ear_hole_segments
    )
    move_object_to_collection(cutter, coll)

    apply_boolean_difference(base_pad_3d, cutter, modifier_name="EarHoleBoolean")

    if props.hide_helpers:
        cutter.hide_set(True)
        cutter.hide_render = True

    return base_pad_3d


def get_or_create_principled_material(name, base_color_rgba):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)

    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    output = nodes.get("Material Output")
    if output is None:
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (300, 0)

    principled = None
    if output.inputs["Surface"].is_linked:
        from_node = output.inputs["Surface"].links[0].from_node
        if from_node and from_node.bl_idname == "ShaderNodeBsdfPrincipled":
            principled = from_node

    if principled is None:
        principled = nodes.get("Principled BSDF")

    if principled is None or principled.bl_idname != "ShaderNodeBsdfPrincipled":
        principled = nodes.new("ShaderNodeBsdfPrincipled")
        principled.location = (0, 0)

    if not output.inputs["Surface"].is_linked:
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    else:
        from_node = output.inputs["Surface"].links[0].from_node
        if from_node != principled:
            while output.inputs["Surface"].links:
                nt.links.remove(output.inputs["Surface"].links[0])
            links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    if "Base Color" in principled.inputs:
        principled.inputs["Base Color"].default_value = base_color_rgba

    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.45

    mat.diffuse_color = base_color_rgba
    return mat


def assign_object_single_material(obj, material):
    if obj is None or obj.type != 'MESH':
        return

    obj.data.materials.clear()
    obj.data.materials.append(material)

    for poly in obj.data.polygons:
        poly.material_index = 0

    obj.active_material = material


def shade_smooth_object(obj):
    if obj is None or obj.type != 'MESH':
        return

    ensure_object_mode()
    deselect_all()
    set_active(obj)
    bpy.ops.object.shade_smooth()


def apply_auto_smooth(obj, angle_deg=30.0):
    if obj is None or obj.type != 'MESH':
        return

    ensure_object_mode()
    deselect_all()
    set_active(obj)

    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
    except Exception:
        bpy.ops.object.shade_smooth()
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
        if hasattr(obj.data, "auto_smooth_angle"):
            obj.data.auto_smooth_angle = math.radians(angle_deg)


def get_overhang_face_indices(obj, angle_deg=45.0):
    if obj is None or obj.type != 'MESH':
        return []

    ensure_object_mode()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh_eval = obj_eval.to_mesh()

    bm = bmesh.new()
    bm.from_mesh(mesh_eval)
    bm.faces.ensure_lookup_table()
    bm.normal_update()

    world_normal_matrix = obj.matrix_world.to_3x3()
    z_down = Vector((0.0, 0.0, -1.0))
    angle_limit = (math.pi / 2.0) - math.radians(angle_deg)

    overhang_faces = []
    for f in bm.faces:
        n = (world_normal_matrix @ f.normal).normalized()
        try:
            angle_to_down = z_down.angle(n, 4.0)
        except Exception:
            continue

        if angle_to_down < angle_limit:
            overhang_faces.append(f.index)

    bm.free()
    obj_eval.to_mesh_clear()
    return overhang_faces


def select_faces_by_indices(obj, face_indices):
    ensure_object_mode()
    deselect_all()
    set_active(obj)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    index_set = set(face_indices)
    for poly in obj.data.polygons:
        poly.select = poly.index in index_set

    bpy.ops.object.mode_set(mode='EDIT')


def delete_faces_by_indices(obj, face_indices):
    if obj is None or obj.type != 'MESH' or not face_indices:
        return 0

    ensure_object_mode()
    mesh = obj.data

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    index_set = set(face_indices)
    faces_to_delete = [f for f in bm.faces if f.index in index_set]
    count = len(faces_to_delete)

    if faces_to_delete:
        bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return count


def check_overhang_on_base(obj, angle_deg=45.0, select_faces=True):
    face_indices = get_overhang_face_indices(obj, angle_deg=angle_deg)
    if face_indices and select_faces:
        select_faces_by_indices(obj, face_indices)
    return len(face_indices), face_indices


def build_joined_filled_pads(context):
    ensure_object_mode()
    props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings

    text_value = props.text.strip()
    if not text_value:
        raise ValueError("Введите текст")

    base_name = cleanup_name(text_value)
    coll_name = f"KCB5J10_{base_name}"
    coll = get_or_create_collection(coll_name)
    clear_generated_objects(coll, base_name)

    text_obj = create_text_curve(
        text_value,
        props.font_path,
        base_name=base_name,
        letter_spacing=props.letter_spacing
    )
    move_object_to_collection(text_obj, coll)

    source_mesh = duplicate_object(text_obj, f"KCB5J10_SourceMesh_{base_name}")
    move_object_to_collection(source_mesh, coll)
    convert_to_mesh(source_mesh)

    final_width_mm = set_object_width_mm_and_apply(source_mesh, props.target_width_mm)

    top_text = duplicate_object(source_mesh, f"TopText_{base_name}")
    move_object_to_collection(top_text, coll)
    clean_mesh_for_top(top_text, merge_distance_mm=props.top_merge_distance_mm)

    base_source = duplicate_object(source_mesh, f"KCB5J10_BaseSource_{base_name}")
    move_object_to_collection(base_source, coll)
    clean_mesh_for_base(base_source, merge_distance_mm=props.base_merge_distance_mm)

    letters_source = duplicate_object(base_source, f"LetterPart_{base_name}")
    move_object_to_collection(letters_source, coll)

    parts = separate_loose_parts(letters_source)
    if not parts:
        raise ValueError("Не удалось разделить текст на буквы")

    for i, part in enumerate(parts, start=1):
        part.name = f"LetterPart_{base_name}_{i:02d}"
        move_object_to_collection(part, coll)

    pads = []
    for i, part in enumerate(parts, start=1):
        pad = build_pad_from_letter(
            part,
            f"PadLetter_{base_name}_{i:02d}",
            props.base_margin_mm,
            props.sharp_angle_deg,
            props.corner_inset_mm,
            props.corner_segments
        )
        if pad is not None:
            move_object_to_collection(pad, coll)
            pads.append(pad)

    if not pads:
        raise ValueError("Не удалось создать основания букв")

    base_pad_2d = join_objects(pads, f"BasePad2D_{base_name}")
    move_object_to_collection(base_pad_2d, coll)

    cleanup_joined_base(base_pad_2d, merge_distance_mm=0.05)

    ear_info = None
    if props.add_side_ear:
        base_pad_2d, ear_info = add_side_ear_plane_before_extrude(base_pad_2d, props, coll, base_name)

    base_pad_3d = duplicate_object(base_pad_2d, f"BasePad3D_{base_name}")
    move_object_to_collection(base_pad_3d, coll)

    overhang_count, overhang_faces = check_overhang_on_base(
        base_pad_3d,
        angle_deg=props.overhang_angle_deg,
        select_faces=True
    )

    if overhang_count > 0:
        if props.delete_overhang_faces_before_extrude:
            deleted_count = delete_faces_by_indices(base_pad_3d, overhang_faces)
            if deleted_count <= 0:
                raise ValueError(
                    f"Найдены нависающие грани ({overhang_count}), но удалить их не удалось на объекте {base_pad_3d.name}"
                )
            ensure_object_mode()
        else:
            raise ValueError(
                f"Найдены нависающие грани перед Extrude основания: {overhang_count}. "
                f"Они выделены на объекте {base_pad_3d.name}"
            )

    extrude_mesh_z(base_pad_3d, -mm(props.base_thickness_mm))

    if props.add_side_ear and props.ear_hole_enable:
        base_pad_3d = cut_hole_in_side_ear(base_pad_3d, props, coll, base_name, ear_info)

    extrude_mesh_z(top_text, mm(props.text_height_mm))

    base_mat = get_or_create_principled_material(
        "KCB5J10_Base_Red",
        (0.80, 0.08, 0.08, 1.0)
    )
    text_mat = get_or_create_principled_material(
        "KCB5J10_Text_White",
        (0.95, 0.95, 0.95, 1.0)
    )

    assign_object_single_material(base_pad_3d, base_mat)
    assign_object_single_material(top_text, text_mat)

    final_obj = join_objects([base_pad_3d, top_text], f"FinalKeychain_{base_name}")
    move_object_to_collection(final_obj, coll)

    shade_smooth_object(final_obj)
    apply_auto_smooth(final_obj, angle_deg=30.0)

    if props.hide_helpers:
        for obj in [text_obj, source_mesh, base_source, letters_source, base_pad_2d]:
            if obj:
                obj.hide_set(True)
                obj.hide_render = True
        for part in parts:
            part.hide_set(True)
            part.hide_render = True

    bpy.context.view_layer.update()
    return coll, final_obj, final_width_mm


class KCB5J10_PG_settings(PropertyGroup):
    text: StringProperty(
        name="Text",
        description="Text to generate on the keychain",
        default="Сергей"
    )
    font_path: StringProperty(
        name="Font Path",
        description="Path to TTF or OTF font file",
        default="",
        subtype='FILE_PATH'
    )
    letter_spacing: FloatProperty(
        name="Letter Spacing",
        description="Character spacing factor for the generated text",
        default=1.0, min=0.0, max=10.0
    )

    target_width_mm: FloatProperty(
        name="Width (mm)",
        description="Target total width of the generated keychain",
        default=50.0, min=5.0, max=300.0
    )
    base_merge_distance_mm: FloatProperty(
        name="Base Merge Distance (mm)",
        description="Merge distance for the base geometry before creating the backing shape",
        default=0.03, min=0.0, max=5.0
    )
    top_merge_distance_mm: FloatProperty(
        name="Top Merge Distance (mm)",
        description="Merge distance for the top text geometry",
        default=0.0, min=0.0, max=5.0
    )
    base_margin_mm: FloatProperty(
        name="Base Margin (mm)",
        description="Extra margin around letters for the base backing shape",
        default=1.80, min=0.0, max=10.0
    )

    base_thickness_mm: FloatProperty(
        name="Base Thickness (mm)",
        description="Thickness of the lower base part",
        default=3.0, min=0.2, max=20.0
    )
    text_height_mm: FloatProperty(
        name="Text Height (mm)",
        description="Height of the raised top text",
        default=2.0, min=0.2, max=20.0
    )
    sharp_angle_deg: FloatProperty(
        name="Sharp Angle Limit (deg)",
        description="Angles sharper than this may be softened on the base outline",
        default=55.0, min=10.0, max=120.0
    )
    corner_inset_mm: FloatProperty(
        name="Corner Inset (mm)",
        description="Inset amount used to soften sharp corners",
        default=0.25, min=0.0, max=5.0
    )
    corner_segments: IntProperty(
        name="Corner Segments",
        description="Number of segments used for corner smoothing",
        default=3, min=1, max=12
    )

    add_side_ear: BoolProperty(
        name="Add Side Ear",
        description="Add a side ear for the key ring hole",
        default=True
    )
    ear_side: EnumProperty(
        name="Ear Side",
        description="Choose which side to place the ear on",
        items=[
            ('LEFT', "Left", "Place the ear on the left side"),
            ('RIGHT', "Right", "Place the ear on the right side"),
        ],
        default='LEFT'
    )
    ear_plane_height_mm: FloatProperty(
        name="Ear Height (mm)",
        description="Height of the side ear",
        default=10.00, min=0.5, max=50.0
    )
    ear_plane_length_mm: FloatProperty(
        name="Ear Length (mm)",
        description="Length of the side ear",
        default=8.0, min=0.5, max=50.0
    )
    ear_plane_y_offset_mm: FloatProperty(
        name="Ear Y Offset (mm)",
        description="Vertical offset of the ear",
        default=0.0, min=-100.0, max=100.0
    )
    ear_plane_gap_mm: FloatProperty(
        name="Ear Gap (mm)",
        description="Gap between the ear and the base before auto-weld",
        default=0.0, min=0.0, max=20.0
    )
    ear_plane_bevel_mm: FloatProperty(
        name="Ear Bevel (mm)",
        description="Bevel size on the outer side of the ear",
        default=3.00, min=0.0, max=20.0
    )
    ear_plane_bevel_segments: IntProperty(
        name="Ear Bevel Segments",
        description="Number of bevel segments on the ear",
        default=6, min=1, max=32
    )
    ear_plane_auto_step_mm: FloatProperty(
        name="Intersection Search Step (mm)",
        description="Step used while pushing the ear into the base",
        default=0.1, min=0.01, max=2.0
    )
    ear_plane_auto_max_push_mm: FloatProperty(
        name="Max Push Into Base (mm)",
        description="Maximum distance the ear may be pushed into the base",
        default=2.00, min=0.1, max=20.0
    )

    ear_hole_enable: BoolProperty(
        name="Create Ear Hole",
        description="Create a round hole inside the ear",
        default=True
    )
    ear_hole_diameter_mm: FloatProperty(
        name="Hole Diameter (mm)",
        description="Diameter of the round hole in the ear",
        default=3.0, min=0.2, max=20.0
    )
    ear_hole_offset_x_mm: FloatProperty(
        name="Hole Offset From Outer Edge (mm)",
        description="Distance from the outer edge of the ear to the nearest edge of the hole",
        default=2.0, min=0.0, max=50.0
    )
    ear_hole_offset_y_mm: FloatProperty(
        name="Hole Y Offset (mm)",
        description="Vertical offset of the hole center",
        default=0.0, min=-50.0, max=50.0
    )
    ear_hole_segments: IntProperty(
        name="Hole Segments",
        description="Number of segments used for the hole cutter cylinder",
        default=48, min=12, max=128
    )

    overhang_angle_deg: FloatProperty(
        name="Overhang Angle (deg)",
        description="Faces steeper than this overhang angle are detected before base extrusion",
        default=45.0, min=0.0, max=89.9
    )
    delete_overhang_faces_before_extrude: BoolProperty(
        name="Delete Overhang Faces Before Extrude",
        description="Delete detected overhang faces before extruding the base",
        default=True
    )

    hide_helpers: BoolProperty(
        name="Hide Helpers",
        description="Hide intermediate helper objects after build",
        default=True
    )


class KCB5J10_OT_pick_font(Operator, ImportHelper):
    bl_idname = "kcb5j10.pick_font"
    bl_label = "Choose Font"

    filter_glob: StringProperty(default="*.ttf;*.otf", options={'HIDDEN'})

    def execute(self, context):
        context.scene.keychain_builder_mvp10_joined_filled_pads_settings.font_path = self.filepath
        return {'FINISHED'}


class KCB5J10_OT_build(Operator):
    bl_idname = "kcb5j10.build"
    bl_label = "Build Joined Filled Pads"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            _, final_obj, final_width_mm = build_joined_filled_pads(context)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        self.report({'INFO'}, f"Готово: {final_obj.name}, ширина {final_width_mm:.2f} мм")
        return {'FINISHED'}


class KCB5J10_OT_export_stl(Operator):
    bl_idname = "kcb5j10.export_stl"
    bl_label = "Save STL"

    filepath: StringProperty(
        name="STL File",
        default="",
        subtype='FILE_PATH'
    )

    filename_ext = ".stl"
    filter_glob: StringProperty(default="*.stl", options={'HIDDEN'})

    def invoke(self, context, event):
        props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings
        text_value = props.text.strip()
        base_name = cleanup_name(text_value) if text_value else "keychain"

        active = context.view_layer.objects.active
        if active and active.type == 'MESH':
            filename = active.name
        else:
            filename = f"FinalKeychain_{base_name}"

        if not filename.lower().endswith(".stl"):
            filename += ".stl"

        self.filepath = bpy.path.abspath(f"//{filename}")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        active = context.view_layer.objects.active
        if active is None or active.type != 'MESH':
            self.report({'ERROR'}, "Нет активного mesh-объекта для экспорта STL")
            return {'CANCELLED'}

        ensure_object_mode()
        deselect_all()
        set_active(active)

        filepath = bpy.path.ensure_ext(self.filepath, ".stl")
        ok = False
        last_error = ""

        if hasattr(bpy.ops.wm, "stl_export"):
            try:
                result = bpy.ops.wm.stl_export(
                    filepath=filepath,
                    export_selected_objects=True
                )
                if 'FINISHED' in result:
                    ok = True
            except Exception as e:
                last_error = str(e)

        if not ok and hasattr(bpy.ops.export_mesh, "stl"):
            try:
                result = bpy.ops.export_mesh.stl(
                    filepath=filepath,
                    use_selection=True,
                    ascii=False
                )
                if 'FINISHED' in result:
                    ok = True
            except Exception as e:
                last_error = str(e)

        if not ok:
            msg = "Не удалось сохранить STL"
            if last_error:
                msg += f": {last_error}"
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        self.report({'INFO'}, f"STL сохранён: {filepath}")
        return {'FINISHED'}

class KCB5J10_OT_reset_settings(Operator):
    bl_idname = "kcb5j10.reset_settings"
    bl_label = "Reset All Settings"
    bl_description = "Reset all addon settings to factory defaults"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings
        
        # Сохраняем текущие значения текста и шрифта
        saved_text = props.text
        saved_font_path = props.font_path

        # Сбрасываем все настройки
        props.text = saved_text  # оставляем сохраненное значение
        props.font_path = saved_font_path  # оставляем сохраненный путь
        props.letter_spacing = 1.0

        props.target_width_mm = 50.0
        props.base_merge_distance_mm = 0.03
        props.top_merge_distance_mm = 0.0
        props.base_margin_mm = 1.80

        props.base_thickness_mm = 3.0
        props.text_height_mm = 2.0
        props.sharp_angle_deg = 55.0
        props.corner_inset_mm = 0.25
        props.corner_segments = 3

        props.add_side_ear = True
        props.ear_side = 'LEFT'
        props.ear_plane_height_mm = 10.0
        props.ear_plane_length_mm = 8.0
        props.ear_plane_y_offset_mm = 0.0
        props.ear_plane_gap_mm = 0.0
        props.ear_plane_bevel_mm = 3.0
        props.ear_plane_bevel_segments = 6
        props.ear_plane_auto_step_mm = 0.1
        props.ear_plane_auto_max_push_mm = 2.0

        props.ear_hole_enable = True
        props.ear_hole_diameter_mm = 3.0
        props.ear_hole_offset_x_mm = 2.0
        props.ear_hole_offset_y_mm = 0.0
        props.ear_hole_segments = 48

        props.overhang_angle_deg = 45.0
        props.delete_overhang_faces_before_extrude = True
        props.hide_helpers = True

        self.report({'INFO'}, "Настройки сброшены к заводским")
        return {'FINISHED'}

class KCB5J10_PT_panel(Panel):
    bl_label = "Keychain"
    bl_idname = "KCB5J10_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Keychain"

    def draw(self, context):
        pass


class KCB5J10_PT_text(Panel):
    bl_label = "Text"
    bl_idname = "KCB5J10_PT_text"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Keychain"
    bl_parent_id = "KCB5J10_PT_panel"

    def draw(self, context):
        layout = self.layout
        props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings

        col = layout.column(align=True)
        col.prop(props, "text")
        col.prop(props, "font_path")
        col.operator("kcb5j10.pick_font", icon='FILE_FOLDER')


class KCB5J10_PT_base(Panel):
    bl_label = "Base"
    bl_idname = "KCB5J10_PT_base"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Keychain"
    bl_parent_id = "KCB5J10_PT_panel"

    def draw(self, context):
        layout = self.layout
        props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings

        col = layout.column(align=True)
        col.prop(props, "target_width_mm")
        col.prop(props, "letter_spacing")
        col.prop(props, "base_merge_distance_mm")
        col.prop(props, "top_merge_distance_mm")
        col.prop(props, "base_margin_mm")


class KCB5J10_PT_base_advanced(Panel):
    bl_label = "Base Advanced"
    bl_idname = "KCB5J10_PT_base_advanced"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Keychain"
    bl_parent_id = "KCB5J10_PT_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings

        col = layout.column(align=True)
        col.prop(props, "base_thickness_mm")
        col.prop(props, "text_height_mm")
        col.prop(props, "sharp_angle_deg")
        col.prop(props, "corner_inset_mm")
        col.prop(props, "corner_segments")


class KCB5J10_PT_ear(Panel):
    bl_label = "Ear"
    bl_idname = "KCB5J10_PT_ear"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Keychain"
    bl_parent_id = "KCB5J10_PT_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings

        col = layout.column(align=True)
        col.prop(props, "add_side_ear")
        col.prop(props, "ear_side")
        col.prop(props, "ear_plane_height_mm")
        col.prop(props, "ear_plane_length_mm")
        col.prop(props, "ear_plane_y_offset_mm")
        col.prop(props, "ear_plane_gap_mm")
        col.prop(props, "ear_plane_bevel_mm")
        col.prop(props, "ear_plane_bevel_segments")
        col.prop(props, "ear_plane_auto_step_mm")
        col.prop(props, "ear_plane_auto_max_push_mm")


class KCB5J10_PT_hole(Panel):
    bl_label = "Hole"
    bl_idname = "KCB5J10_PT_hole"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Keychain"
    bl_parent_id = "KCB5J10_PT_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings

        col = layout.column(align=True)
        col.prop(props, "ear_hole_enable")
        col.prop(props, "ear_hole_diameter_mm")
        col.prop(props, "ear_hole_offset_x_mm")
        col.prop(props, "ear_hole_offset_y_mm")
        col.prop(props, "ear_hole_segments")


class KCB5J10_PT_checks(Panel):
    bl_label = "Checks"
    bl_idname = "KCB5J10_PT_checks"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Keychain"
    bl_parent_id = "KCB5J10_PT_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.keychain_builder_mvp10_joined_filled_pads_settings

        col = layout.column(align=True)
        col.prop(props, "overhang_angle_deg")
        col.prop(props, "delete_overhang_faces_before_extrude")
        col.prop(props, "hide_helpers")


class KCB5J10_PT_export(Panel):
    bl_label = "Export"
    bl_idname = "KCB5J10_PT_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Keychain"
    bl_parent_id = "KCB5J10_PT_panel"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.scale_y = 1.2
        row.operator("kcb5j10.build", text="Build Joined Filled Pads", icon='MESH_GRID')

        row = layout.row()
        row.scale_y = 1.1
        row.operator("kcb5j10.export_stl", text="Save STL", icon='EXPORT')

        layout.separator()

        row = layout.row()
        row.scale_y = 1.0
        row.operator("kcb5j10.reset_settings", text="Reset All Settings", icon='LOOP_BACK')


classes = (
    KCB5J10_PG_settings,
    KCB5J10_OT_pick_font,
    KCB5J10_OT_build,
    KCB5J10_OT_export_stl,
    KCB5J10_OT_reset_settings,
    KCB5J10_PT_panel,
    KCB5J10_PT_text,
    KCB5J10_PT_base,
    KCB5J10_PT_base_advanced,
    KCB5J10_PT_ear,
    KCB5J10_PT_hole,
    KCB5J10_PT_checks,
    KCB5J10_PT_export,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.keychain_builder_mvp10_joined_filled_pads_settings = PointerProperty(type=KCB5J10_PG_settings)
    bpy.app.translations.register(__name__, translations_dict)


def unregister():
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass

    if hasattr(bpy.types.Scene, "keychain_builder_mvp10_joined_filled_pads_settings"):
        del bpy.types.Scene.keychain_builder_mvp10_joined_filled_pads_settings

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()