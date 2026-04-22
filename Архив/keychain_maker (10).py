bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (11, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Keychain",
    "description": "Генерирует брелок: подложка плавно огибает буквы",
    "category": "Add Mesh",
}

import bpy
import bmesh
import math
import os
from mathutils import Vector
from bpy.props import StringProperty, FloatProperty
from bpy.types import Panel, Operator, PropertyGroup


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def delete_obj(obj):
    if obj and obj.name in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

def deselect_all():
    bpy.ops.object.select_all(action="DESELECT")

def set_active(context, obj):
    deselect_all()
    obj.select_set(True)
    context.view_layer.objects.active = obj

def L(msg):
    print(f"[KM] {msg}")


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


def get_contour_edges(bm):
    """
    Возвращает граничные рёбра плоского меша.
    Определяем по минимальному числу смежных граней.
    """
    if not bm.edges:
        return [], []
    fc = [len(e.link_faces) for e in bm.edges]
    min_fc = min(fc)
    contour = [e for e in bm.edges if len(e.link_faces) <= min_fc + 1]
    inner   = [e for e in bm.edges if len(e.link_faces) >  min_fc + 1]
    return contour, inner


def remove_small_islands(bm, min_edge_count=4):
    """
    Удаляет небольшие изолированные острова (артефакты метаболов).
    Остров — связный компонент рёбер с числом рёбер < min_edge_count.
    """
    visited = set()
    islands = []

    for start_edge in bm.edges:
        if start_edge in visited:
            continue
        # BFS по рёбрам через общие вершины
        island = set()
        queue = [start_edge]
        while queue:
            e = queue.pop()
            if e in visited:
                continue
            visited.add(e)
            island.add(e)
            for v in e.verts:
                for ne in v.link_edges:
                    if ne not in visited:
                        queue.append(ne)
        islands.append(island)

    removed = 0
    for island in islands:
        if len(island) < min_edge_count:
            verts_to_del = set()
            for e in island:
                for v in e.verts:
                    verts_to_del.add(v)
            bmesh.ops.delete(bm, geom=list(island), context="EDGES")
            isolated = [v for v in verts_to_del if v.is_valid and not v.link_edges]
            if isolated:
                bmesh.ops.delete(bm, geom=isolated, context="VERTS")
            removed += 1

    L(f"  remove_small_islands: островов={len(islands)}, удалено малых={removed}")


def fill_contours_with_holes(bm):
    """
    Заполняет замкнутые контуры с учётом вложенности (дырки букв).
    
    Алгоритм:
    1. Находим все замкнутые петли рёбер (edge loops)
    2. Для каждой петли определяем: внешняя она или дырка (по ориентации / площади)
    3. Заполняем triangle_fill
    
    Упрощённый вариант: заполняем все петли через triangle_fill —
    он сам разбирается с вложенностью если грани правильно ориентированы.
    """
    all_edges = list(bm.edges)
    if not all_edges:
        return

    result = bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_edges)
    new_faces = [g for g in result.get("geom", []) if isinstance(g, bmesh.types.BMFace)]
    L(f"  triangle_fill: граней={len(new_faces)}")

    # Удаляем грани которые оказались «заглушками» дырок:
    # дырка буквы — это маленькая грань ВНУТРИ внешней грани.
    # Определяем по площади: очень маленькие грани внутри других — удаляем.
    # Используем другой признак: если нормаль грани смотрит вниз (Z < 0) —
    # это «крышка» дырки, которую triangle_fill создал неправильно.
    # После recalc_face_normals все нормали будут согласованы,
    # поэтому просто пересчитываем и оставляем как есть.
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def build_flat_base(context, pts, offset):
    """Строит плоский заполненный меш (Z=0) через метаболы."""
    mb_resolution = max(offset * 0.15, 0.0001)
    elem_radius   = offset * 1.1
    grid_size     = offset * 0.35
    merge_dist    = elem_radius * 0.05

    L(f"build_flat_base: offset={offset:.3f}, res={mb_resolution:.4f}, r={elem_radius:.3f}")

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
        el           = mb_data.elements.new(type="BALL")
        el.co        = Vector((vx, vy, 0.0))
        el.radius    = elem_radius
        el.stiffness = 1.0

    context.view_layer.update()

    set_active(context, mb_obj)
    bpy.ops.object.convert(target="MESH")
    base_raw = context.active_object
    base_raw.name = "_KM_BaseRaw"

    set_active(context, base_raw)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(base_raw.data)

    # Сплющиваем Z→0
    for v in bm.verts:
        v.co.z = 0.0

    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge_dist)
    L(f"  после merge: verts={len(bm.verts)}, edges={len(bm.edges)}, faces={len(bm.faces)}")

    # Получаем контурные рёбра до удаления граней
    contour_edges, inner_edges = get_contour_edges(bm)
    L(f"  контурных рёбер: {len(contour_edges)}, внутренних: {len(inner_edges)}")

    # Удаляем все грани
    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
    # Удаляем внутренние рёбра
    valid_inner = [e for e in inner_edges if e.is_valid]
    if valid_inner:
        bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
    # Удаляем изолированные вершины
    isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
    if isolated:
        bmesh.ops.delete(bm, geom=isolated, context="VERTS")

    L(f"  после удаления внутренних: verts={len(bm.verts)}, edges={len(bm.edges)}")

    # Удаляем мелкие острова-артефакты
    remove_small_islands(bm, min_edge_count=5)

    L(f"  контур после чистки: verts={len(bm.verts)}, edges={len(bm.edges)}")

    # Заполняем контур
    fill_contours_with_holes(bm)

    L(f"  итог: verts={len(bm.verts)}, edges={len(bm.edges)}, faces={len(bm.faces)}")

    bmesh.update_edit_mesh(base_raw.data)
    bpy.ops.object.editmode_toggle()

    return base_raw


def extrude_flat_mesh_down(context, obj, depth):
    """
    Экструдирует плоский меш вниз на depth.
    Делаем дубликат верхних вершин, опускаем вниз, создаём боковые грани и нижнюю крышку.
    Использует простую экструзию в editmode — контур повторяется точно.
    """
    set_active(context, obj)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(obj.data)

    # Запоминаем верхние вершины и грани
    top_verts = list(bm.verts)
    top_faces = list(bm.faces)

    # Экструдируем все грани вниз
    ret = bmesh.ops.extrude_face_region(bm, geom=top_faces)
    extruded_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]

    # Перемещаем новые вершины вниз
    bmesh.ops.translate(bm, verts=extruded_verts, vec=Vector((0, 0, -depth)))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.editmode_toggle()


def prepare_letters(context, letters_obj):
    """
    Подготавливает меш букв: оставляет только контуры, заполняет с дырками.
    """
    set_active(context, letters_obj)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(letters_obj.data)

    L(f"prepare_letters: verts={len(bm.verts)}, edges={len(bm.edges)}, faces={len(bm.faces)}")

    # Для букв меш изначально плоский (после конвертации текста),
    # поэтому is_boundary работает сразу
    boundary = [e for e in bm.edges if e.is_boundary]
    non_boundary = [e for e in bm.edges if not e.is_boundary]
    L(f"  boundary edges={len(boundary)}, non-boundary={len(non_boundary)}")

    if boundary:
        # Удаляем грани и внутренние рёбра — оставляем только контуры
        bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
        inner = [e for e in bm.edges if e.is_valid and not e.is_boundary]
        if inner:
            bmesh.ops.delete(bm, geom=inner, context="EDGES")
        isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
        if isolated:
            bmesh.ops.delete(bm, geom=isolated, context="VERTS")
        L(f"  после чистки: verts={len(bm.verts)}, edges={len(bm.edges)}")
    else:
        # Если is_boundary не работает — используем метод по числу граней
        L("  is_boundary не работает, используем метод по числу граней")
        fc = [len(e.link_faces) for e in bm.edges]
        if fc:
            min_fc = min(fc)
            inner = [e for e in bm.edges if len(e.link_faces) > min_fc + 1]
            bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
            valid_inner = [e for e in inner if e.is_valid]
            if valid_inner:
                bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
            isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
            if isolated:
                bmesh.ops.delete(bm, geom=isolated, context="VERTS")

    # Заполняем — triangle_fill должен корректно обработать дырки
    all_edges = list(bm.edges)
    if all_edges:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_edges)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.update_edit_mesh(letters_obj.data)
    bpy.ops.object.editmode_toggle()


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

        L(f"=== Generate: '{text}', offset={offset}, base_h={base_h}, letter_h={letter_h}")

        if not text:
            self.report({"WARNING"}, "Введите текст!")
            return {"CANCELLED"}

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
        sample_step = offset * 0.7
        pts = points_along_edges(letters_obj, sample_step)
        L(f"  точек: {len(pts)}, step={sample_step:.3f}")

        if len(pts) < 2:
            self.report({"ERROR"}, "Не удалось получить рёбра текста.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 3. Плоский контур подложки ─────────────────────────────────────
        base_flat = build_flat_base(context, pts, offset)

        if not base_flat.data.vertices or not base_flat.data.polygons:
            self.report({"ERROR"}, "Подложка пустая — смотрите консоль.")
            delete_obj(base_flat)
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Экструдируем подложку вниз (контур повторяется точно) ───────
        extrude_flat_mesh_down(context, base_flat, base_h)
        base_flat.name = "_KM_Base"
        base_obj = base_flat

        # ── 5. Буквы: подготавливаем контуры с дырками + Solidify вверх ────
        prepare_letters(context, letters_obj)

        mod_let = letters_obj.modifiers.new("SolidifyLetters", "SOLIDIFY")
        mod_let.thickness       = letter_h
        mod_let.offset          = 1.0
        mod_let.use_even_offset = True
        mod_let.use_rim         = True
        bpy.ops.object.modifier_apply(modifier="SolidifyLetters")

        # ── 6. Объединяем ──────────────────────────────────────────────────
        deselect_all()
        base_obj.select_set(True)
        letters_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        final_obj = context.active_object

        safe = "".join(c for c in text if c.isalnum() or c in " _-")[:20].strip()
        final_obj.name = f"Keychain_{safe}"

        L(f"=== Готово: {final_obj.name}")
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
        box.label(text="Размеры", icon="DRIVER_DISTANCE")
        box.prop(props, "base_offset")
        box.prop(props, "base_height")
        box.prop(props, "letter_height")

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
