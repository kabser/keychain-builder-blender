bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (14, 0, 0),
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


def build_flat_base(context, pts, offset):
    """Строит плоский заполненный меш (Z=0) через метаболы."""
    mb_resolution = max(offset * 0.15, 0.0001)
    elem_radius   = offset * 1.1
    grid_size     = offset * 0.35
    merge_dist    = elem_radius * 0.05

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

    # Удаляем нижнюю полусферу
    z_threshold = elem_radius * 0.05
    lower_faces = [f for f in bm.faces
                   if sum(v.co.z for v in f.verts) / len(f.verts) < z_threshold]
    bmesh.ops.delete(bm, geom=lower_faces, context="FACES")

    # Проецируем на Z=0
    for v in bm.verts:
        v.co.z = 0.0
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge_dist)

    # Граничные рёбра = контур
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    inner_edges    = [e for e in bm.edges if not e.is_boundary]
    L(f"  подложка: граничных={len(boundary_edges)}, внутренних={len(inner_edges)}")

    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
    valid_inner = [e for e in inner_edges if e.is_valid]
    if valid_inner:
        bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
    isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
    if isolated:
        bmesh.ops.delete(bm, geom=isolated, context="VERTS")

    all_edges = list(bm.edges)
    if all_edges:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_edges)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    L(f"  подложка итог: verts={len(bm.verts)}, faces={len(bm.faces)}")

    bmesh.update_edit_mesh(base_raw.data)
    bpy.ops.object.editmode_toggle()
    return base_raw


def prepare_letters_mesh(context, letters_obj):
    """
    Подготавливает меш букв с правильными дырками.

    Текст конвертируется с fill_mode по умолчанию (BOTH) — это даёт
    корректный меш для любого шрифта и языка. Затем мы:
    1. Находим граничные рёбра (внешние + внутренние контуры букв)
       — они есть потому что текстовый меш НЕ закрытый (только верх)
    2. Удаляем грани и внутренние рёбра
    3. triangle_fill заполняет все петли, сохраняя дырки
    """
    set_active(context, letters_obj)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(letters_obj.data)

    L(f"letters: verts={len(bm.verts)}, edges={len(bm.edges)}, faces={len(bm.faces)}")

    # Граничные рёбра текстового меша — это контуры букв (внешние и дырки)
    # Текст конвертируется как плоский меш (только верхняя грань),
    # поэтому у граничных рёбер ровно 1 смежная грань
    boundary = [e for e in bm.edges if e.is_boundary]
    inner    = [e for e in bm.edges if not e.is_boundary]
    L(f"  boundary={len(boundary)}, inner={len(inner)}")

    # Удаляем грани и внутренние рёбра — оставляем только контуры
    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
    valid_inner = [e for e in inner if e.is_valid]
    if valid_inner:
        bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
    isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
    if isolated:
        bmesh.ops.delete(bm, geom=isolated, context="VERTS")

    L(f"  после чистки: verts={len(bm.verts)}, edges={len(bm.edges)}")

    # Заполняем все петли (triangle_fill корректно обрабатывает дырки)
    all_e = list(bm.edges)
    if all_e:
        result = bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_e)
        new_faces = [g for g in result.get("geom", []) if isinstance(g, bmesh.types.BMFace)]
        L(f"  triangle_fill: граней={len(new_faces)}")

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
        # fill_mode НЕ меняем — оставляем BOTH (по умолчанию)
        # Это гарантирует корректную конвертацию для любого языка

        if font_path and os.path.isfile(font_path):
            txt_obj.data.font = bpy.data.fonts.load(font_path)

        set_active(context, txt_obj)
        bpy.ops.object.convert(target="MESH")
        letters_obj = context.active_object
        letters_obj.name = "_KM_Letters"

        # Dissolve + Merge
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
        bpy.ops.mesh.remove_doubles(threshold=0.001)
        bpy.ops.object.editmode_toggle()

        if not letters_obj.data.vertices:
            self.report({"ERROR"}, "Текст не содержит вершин.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        L(f"  буквы: verts={len(letters_obj.data.vertices)}, edges={len(letters_obj.data.edges)}, faces={len(letters_obj.data.polygons)}")

        # ── 2. Точки вдоль рёбер для метаболов ────────────────────────────
        sample_step = offset * 0.7
        pts = points_along_edges(letters_obj, sample_step)
        L(f"  точек: {len(pts)}")

        # ── 3. Плоский контур подложки ─────────────────────────────────────
        base_flat = build_flat_base(context, pts, offset)

        if not base_flat.data.vertices or not base_flat.data.polygons:
            self.report({"ERROR"}, "Подложка пустая.")
            delete_obj(base_flat)
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Экструдируем подложку вниз ──────────────────────────────────
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

        # ── 5. Буквы: чистим контуры + Solidify вверх ──────────────────────
        prepare_letters_mesh(context, letters_obj)

        mod_let = letters_obj.modifiers.new("Solidify", "SOLIDIFY")
        mod_let.thickness       = letter_h
        mod_let.offset          = 1.0
        mod_let.use_even_offset = True
        mod_let.use_rim         = True
        bpy.ops.object.modifier_apply(modifier="Solidify")

        # ── 6. Объединяем ──────────────────────────────────────────────────
        deselect_all()
        base_obj.select_set(True)
        letters_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        final_obj = context.active_object

        safe = "".join(c for c in text if c.isalnum() or c in " _-")[:20].strip()
        if not safe:
            safe = "keychain"
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
