bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (4, 0, 0),
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


def points_along_edges(mesh_obj, step):
    """
    Точки равномерно вдоль каждого ребра меша.
    Возвращает список (x, y).
    """
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


def build_flat_base_from_metaball(context, pts, offset, mb_resolution):
    """
    Строит плоский (Z=0) замкнутый меш-контур по точкам pts,
    используя метаболы. Возвращает объект с плоским мешем или None.
    """
    # --- метаболы ---
    mb_data = bpy.data.metaballs.new("_KM_MB")
    mb_data.resolution        = mb_resolution
    mb_data.render_resolution = mb_resolution
    mb_data.threshold         = 0.6

    mb_obj = bpy.data.objects.new("_KM_MetaObj", mb_data)
    context.collection.objects.link(mb_obj)

    elem_radius = offset * 1.1
    grid_size   = offset * 0.35          # шаг дедупликации
    seen        = set()
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

    # --- конвертируем в меш ---
    set_active(context, mb_obj)
    bpy.ops.object.convert(target="MESH")
    base_raw = context.active_object
    base_raw.name = "_KM_BaseRaw"

    # --- сплющиваем в Z=0 ---
    base_raw.scale.z = 0.0
    bpy.ops.object.transform_apply(scale=True)

    # --- чистим меш через bmesh ---
    set_active(context, base_raw)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(base_raw.data)

    # 1. Удаляем все грани (оставляем только рёбра и вершины)
    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")

    # 2. Удаляем внутренние рёбра — оставляем только граничные
    #    (граничное ребро принадлежит ровно 0 граням после удаления граней)
    interior_edges = [e for e in bm.edges if not e.is_boundary]
    bmesh.ops.delete(bm, geom=interior_edges, context="EDGES")

    # 3. Удаляем изолированные вершины
    isolated_verts = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=isolated_verts, context="VERTS")

    # 4. Merge by distance
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.05)

    # 5. Заполняем контур(ы) — edge_face_add заполняет каждый замкнутый loop
    #    Нам нужен именно grid_fill или holes_fill для правильной триангуляции
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    if boundary_edges:
        bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)

    # 6. Правим нормали
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    bmesh.update_edit_mesh(base_raw.data)
    bpy.ops.object.editmode_toggle()

    return base_raw


# ---------------------------------------------------------------------------
# Оператор генерации брелока
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Generate(Operator):
    bl_idname  = "keychain.generate"
    bl_label   = "Создать брелок"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.keychain_props

        text      = props.text
        font_path = props.font_path
        offset    = props.base_offset
        base_h    = props.base_height
        letter_h  = props.letter_height

        if not text:
            self.report({"WARNING"}, "Введите текст!")
            return {"CANCELLED"}

        # ── 1. Текстовый объект ─────────────────────────────────────────────
        bpy.ops.object.text_add(location=(0, 0, 0))
        txt_obj = context.active_object
        txt_obj.name = "_KM_TextSrc"
        txt_obj.data.body = text
        txt_obj.data.size = 10.0

        if font_path and os.path.isfile(font_path):
            font = bpy.data.fonts.load(font_path)
            txt_obj.data.font = font

        # ── 2. Конвертируем текст → меш ────────────────────────────────────
        set_active(context, txt_obj)
        bpy.ops.object.convert(target="MESH")
        letters_obj = context.active_object
        letters_obj.name = "_KM_Letters"

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
        bpy.ops.mesh.remove_doubles(threshold=0.2)
        bpy.ops.object.editmode_toggle()

        # ── 3. Точки вдоль рёбер букв ──────────────────────────────────────
        sample_step   = offset * 0.7
        mb_resolution = max(0.15, offset * 0.06)
        pts = points_along_edges(letters_obj, sample_step)

        if len(pts) < 2:
            self.report({"ERROR"}, "Не удалось получить рёбра текста.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Строим плоский контур подложки ──────────────────────────────
        base_flat = build_flat_base_from_metaball(
            context, pts, offset, mb_resolution
        )
        if base_flat is None:
            self.report({"ERROR"}, "Не удалось построить подложку.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 5. Экструдируем подложку вниз на base_h ────────────────────────
        set_active(context, base_flat)
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, -base_h)}
        )
        # Закрываем нижнюю крышку
        bpy.ops.mesh.select_all(action="DESELECT")
        # выбираем только нижние вершины (z < -base_h/2)
        bpy.ops.object.editmode_toggle()

        bpy.ops.object.editmode_toggle()
        bm2 = bmesh.from_edit_mesh(base_flat.data)
        bot_verts = [v for v in bm2.verts if v.co.z < -(base_h * 0.5)]
        bot_edges = [e for e in bm2.edges
                     if all(v in bot_verts for v in e.verts) and e.is_boundary]
        if bot_edges:
            bmesh.ops.holes_fill(bm2, edges=bot_edges, sides=0)
            bmesh.ops.recalc_face_normals(bm2, faces=bm2.faces[:])
        bmesh.update_edit_mesh(base_flat.data)
        bpy.ops.object.editmode_toggle()

        base_obj = base_flat
        base_obj.name = "_KM_Base"

        # ── 6. Буквы: Solidify → правильная экструзия с дырками ───────────
        set_active(context, letters_obj)

        # Удаляем внутренние (не граничные) рёбра меша букв —
        # это убирает «перегородки» внутри замкнутых контуров (e, g, о…)
        bpy.ops.object.editmode_toggle()
        bm3 = bmesh.from_edit_mesh(letters_obj.data)

        # Удаляем все грани
        bmesh.ops.delete(bm3, geom=bm3.faces[:], context="FACES_ONLY")
        # Удаляем внутренние рёбра
        inner = [e for e in bm3.edges if not e.is_boundary]
        bmesh.ops.delete(bm3, geom=inner, context="EDGES")
        isolated = [v for v in bm3.verts if not v.link_edges]
        bmesh.ops.delete(bm3, geom=isolated, context="VERTS")
        # Заполняем каждый контур (внешний + дырки внутри букв)
        bound = [e for e in bm3.edges if e.is_boundary]
        if bound:
            bmesh.ops.holes_fill(bm3, edges=bound, sides=0)
        bmesh.ops.recalc_face_normals(bm3, faces=bm3.faces[:])
        bmesh.update_edit_mesh(letters_obj.data)
        bpy.ops.object.editmode_toggle()

        # Solidify вверх на letter_h
        mod = letters_obj.modifiers.new("Solidify", "SOLIDIFY")
        mod.thickness         = letter_h
        mod.offset            = 1.0       # экструзия вверх (от Z=0)
        mod.use_even_offset   = True
        mod.use_rim           = True
        bpy.ops.object.modifier_apply(modifier="Solidify")

        # ── 7. Объединяем ──────────────────────────────────────────────────
        deselect_all()
        base_obj.select_set(True)
        letters_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        final_obj = context.active_object

        safe_name = "".join(
            c for c in text if c.isalnum() or c in " _-"
        )[:20].strip()
        final_obj.name = f"Keychain_{safe_name}"

        self.report({"INFO"}, f'Брелок «{text}» создан!')
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Свойства
# ---------------------------------------------------------------------------

class KeychainProperties(PropertyGroup):
    text: StringProperty(
        name="Текст",
        description="Надпись на брелоке",
        default="IVAN",
    )
    font_path: StringProperty(
        name="Шрифт (.ttf)",
        description="Путь к файлу шрифта (.ttf / .otf)",
        subtype="FILE_PATH",
        default="",
    )
    base_offset: FloatProperty(
        name="Отступ подложки (мм)",
        description="Насколько подложка выступает за буквы",
        default=3.0, min=0.5, max=30.0,
        unit="LENGTH",
    )
    base_height: FloatProperty(
        name="Толщина подложки (мм)",
        description="Высота основания",
        default=3.0, min=0.5, max=20.0,
        unit="LENGTH",
    )
    letter_height: FloatProperty(
        name="Высота букв (мм)",
        description="На сколько буквы выступают над подложкой",
        default=2.0, min=0.2, max=10.0,
        unit="LENGTH",
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
        layout.operator(
            "keychain.generate",
            icon="MESH_DATA",
            text="Создать брелок",
        )


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------

classes = (
    KeychainProperties,
    KEYCHAIN_OT_Generate,
    KEYCHAIN_PT_Panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.keychain_props = bpy.props.PointerProperty(
        type=KeychainProperties
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.keychain_props


if __name__ == "__main__":
    register()
