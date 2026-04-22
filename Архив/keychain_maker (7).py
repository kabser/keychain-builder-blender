bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (8, 0, 0),
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
    """
    Строит плоский заполненный меш (Z=0) через метаболы.
    offset — в единицах сцены (scene units).
    """
    # Автоматически вычисляем resolution метабола.
    # Правило: resolution должен быть примерно offset/4,
    # чтобы меш был достаточно детальным.
    mb_resolution = max(offset * 0.15, 0.0001)
    elem_radius   = offset * 1.1
    grid_size     = offset * 0.35
    # merge_dist после сплющивания — должен быть значительно меньше
    # расстояния между соседними точками контура, но достаточным
    # чтобы слить дубли. Берём elem_radius * 0.05
    merge_dist = elem_radius * 0.05

    L(f"build_flat_base: offset={offset:.4f}, resolution={mb_resolution:.4f}, "
      f"elem_radius={elem_radius:.4f}, merge_dist={merge_dist:.4f}, pts={len(pts)}")

    # --- метаболы ---
    mb_data = bpy.data.metaballs.new("_KM_MB")
    mb_data.resolution        = mb_resolution
    mb_data.render_resolution = mb_resolution
    mb_data.threshold         = 0.6

    mb_obj = bpy.data.objects.new("_KM_MetaObj", mb_data)
    context.collection.objects.link(mb_obj)

    seen = set()
    count = 0
    for vx, vy in pts:
        key = (round(vx / grid_size), round(vy / grid_size))
        if key in seen:
            continue
        seen.add(key)
        el           = mb_data.elements.new(type="BALL")
        el.co        = Vector((vx, vy, 0.0))
        el.radius    = elem_radius
        el.stiffness = 1.0
        count += 1

    L(f"  метабол-элементов: {count}")
    context.view_layer.update()

    # --- конвертируем метабол в меш ---
    set_active(context, mb_obj)
    bpy.ops.object.convert(target="MESH")
    base_raw = context.active_object
    base_raw.name = "_KM_BaseRaw"

    L(f"  после конвертации: verts={len(base_raw.data.vertices)}, faces={len(base_raw.data.polygons)}")
    if base_raw.data.vertices:
        zvals = [v.co.z for v in base_raw.data.vertices]
        L(f"  Z диапазон: {min(zvals):.4f} .. {max(zvals):.4f}")

    # --- bmesh: сплющиваем и строим плоский контур ---
    set_active(context, base_raw)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(base_raw.data)

    # Принудительно Z=0
    for v in bm.verts:
        v.co.z = 0.0

    L(f"  до merge: verts={len(bm.verts)}, edges={len(bm.edges)}, faces={len(bm.faces)}")

    # merge by distance
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge_dist)
    L(f"  после merge(dist={merge_dist:.5f}): verts={len(bm.verts)}, edges={len(bm.edges)}, faces={len(bm.faces)}")

    # dissolve degenerate
    bmesh.ops.dissolve_degenerate(bm, dist=merge_dist * 0.5, edges=bm.edges[:])
    L(f"  после dissolve_degen: verts={len(bm.verts)}, edges={len(bm.edges)}, faces={len(bm.faces)}")

    # Удаляем грани
    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
    L(f"  после удаления граней: edges={len(bm.edges)}")

    # Удаляем внутренние рёбра
    inner = [e for e in bm.edges if not e.is_boundary]
    L(f"  внутренних рёбер (не boundary): {len(inner)}")
    bmesh.ops.delete(bm, geom=inner, context="EDGES")

    # Удаляем изолированные вершины
    isolated = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=isolated, context="VERTS")
    L(f"  после чистки: verts={len(bm.verts)}, edges={len(bm.edges)}")

    # triangle_fill
    all_edges = list(bm.edges)
    L(f"  рёбер для triangle_fill: {len(all_edges)}")
    if all_edges:
        result = bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_edges)
        L(f"  triangle_fill создал граней: {len(result.get('geom', []))}")

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    L(f"  итог: verts={len(bm.verts)}, edges={len(bm.edges)}, faces={len(bm.faces)}")

    bmesh.update_edit_mesh(base_raw.data)
    bpy.ops.object.editmode_toggle()

    return base_raw


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

        # unit_scale: при мм-сцене = 0.001
        # Пользователь вводит числа в мм, но они хранятся как scene units.
        # При unit_scale=0.001: 1 scene unit = 1 мм, всё ок.
        us = context.scene.unit_settings.scale_length
        L(f"=== Keychain Generate: text='{text}', offset={offset}, base_h={base_h}, letter_h={letter_h}")
        L(f"    unit_scale={us}, Length={context.scene.unit_settings.length_unit}")

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

        verts = letters_obj.data.vertices
        if not verts:
            self.report({"ERROR"}, "Текст не содержит вершин.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        xs = [v.co.x for v in verts]
        ys = [v.co.y for v in verts]
        L(f"  Текст: verts={len(verts)}, X={min(xs):.3f}..{max(xs):.3f}, Y={min(ys):.3f}..{max(ys):.3f}")

        # ── 2. Точки вдоль рёбер ───────────────────────────────────────────
        sample_step = offset * 0.7
        pts = points_along_edges(letters_obj, sample_step)
        L(f"  Точек вдоль рёбер: {len(pts)}, step={sample_step:.4f}")

        if len(pts) < 2:
            self.report({"ERROR"}, "Не удалось получить рёбра текста.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 3. Плоский контур подложки ─────────────────────────────────────
        base_flat = build_flat_base(context, pts, offset)

        vb = base_flat.data.vertices
        fb = base_flat.data.polygons
        L(f"  Результат подложки: verts={len(vb)}, faces={len(fb)}")

        if len(vb) == 0 or len(fb) == 0:
            self.report({"ERROR"}, "Подложка пустая — смотрите консоль (Window→Toggle System Console)")
            delete_obj(base_flat)
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Solidify подложки вниз ──────────────────────────────────────
        set_active(context, base_flat)
        mod_base = base_flat.modifiers.new("SolidifyBase", "SOLIDIFY")
        mod_base.thickness       = -base_h
        mod_base.offset          = 1.0
        mod_base.use_even_offset = False
        mod_base.use_rim         = True
        bpy.ops.object.modifier_apply(modifier="SolidifyBase")
        base_flat.name = "_KM_Base"
        base_obj = base_flat

        # ── 5. Буквы: чистим топологию + Solidify вверх ────────────────────
        set_active(context, letters_obj)
        bpy.ops.object.editmode_toggle()
        bm5 = bmesh.from_edit_mesh(letters_obj.data)

        bmesh.ops.delete(bm5, geom=bm5.faces[:], context="FACES_ONLY")
        inner5 = [e for e in bm5.edges if not e.is_boundary]
        bmesh.ops.delete(bm5, geom=inner5, context="EDGES")
        iso5 = [v for v in bm5.verts if not v.link_edges]
        bmesh.ops.delete(bm5, geom=iso5, context="VERTS")

        all_edges5 = list(bm5.edges)
        if all_edges5:
            bmesh.ops.triangle_fill(bm5, use_beauty=True, edges=all_edges5)
        bmesh.ops.recalc_face_normals(bm5, faces=bm5.faces[:])
        bmesh.update_edit_mesh(letters_obj.data)
        bpy.ops.object.editmode_toggle()

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
