bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (20, 0, 0),
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
    """Все нормали плоского меша должны смотреть вверх (+Z)."""
    to_flip = [f for f in bm.faces if f.normal.z < 0]
    if to_flip:
        bmesh.ops.reverse_faces(bm, faces=to_flip)

def points_along_edges(mesh_obj, step):
    """Точки равномерно вдоль каждого ребра меша."""
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
# Построение плоского контура подложки
# ---------------------------------------------------------------------------

def build_flat_base(context, pts, offset):
    """
    Строит плоский заполненный меш (Z=0) через метаболы.

    Алгоритм (отлажен пошагово):
    1. Создаём метаболы вдоль рёбер букв → получаем 3D-шар
    2. Конвертируем в меш
    3. Срезаем нижнюю полусферу ТОЧНО по Z=0 (all verts <= 0)
    4. Проецируем оставшиеся вершины на Z=0
    5. Минимальный merge (dist=0.001) — только настоящие дубли
    6. Граничные рёбра = контур экватора
    7. Удаляем грани и внутренние рёбра
    8. triangle_fill заполняет контур
    """
    mb_resolution = max(offset * 0.08, 0.0001)
    elem_radius   = offset * 1.1
    grid_size     = offset * 0.35

    # --- метаболы ---
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

    # --- конвертируем метабол в меш ---
    set_active(context, mb_obj)
    bpy.ops.object.convert(target="MESH")
    base_raw = context.active_object
    base_raw.name = "_KM_BaseRaw"

    # --- обрабатываем в bmesh ---
    set_active(context, base_raw)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(base_raw.data)

    # Шаг 1: срезаем нижнюю полусферу точно по Z=0
    lower_faces = [f for f in bm.faces if all(v.co.z <= 0.0 for v in f.verts)]
    bmesh.ops.delete(bm, geom=lower_faces, context="FACES")
    lower_edges = [e for e in bm.edges if all(v.co.z < 0.0 for v in e.verts)]
    if lower_edges:
        bmesh.ops.delete(bm, geom=lower_edges, context="EDGES")
    lower_verts = [v for v in bm.verts if v.co.z < 0.0]
    if lower_verts:
        bmesh.ops.delete(bm, geom=lower_verts, context="VERTS")

    # Шаг 2: проецируем на Z=0
    for v in bm.verts:
        v.co.z = 0.0

    # Шаг 3: минимальный merge — только настоящие дубли
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)

    # Шаг 4: граничные рёбра = контур
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    inner_edges    = [e for e in bm.edges if not e.is_boundary]

    # Шаг 5: удаляем грани и внутренние рёбра
    bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
    valid_inner = [e for e in inner_edges if e.is_valid]
    if valid_inner:
        bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
    isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
    if isolated:
        bmesh.ops.delete(bm, geom=isolated, context="VERTS")

    # Шаг 6: заполняем контур
    all_edges = [e for e in bm.edges if e.is_valid]
    if all_edges:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_edges)

    flip_faces_up(bm)

    bmesh.update_edit_mesh(base_raw.data)
    bpy.ops.object.editmode_toggle()
    return base_raw


# ---------------------------------------------------------------------------
# Подготовка меша букв
# ---------------------------------------------------------------------------

def prepare_letters_mesh(bm):
    """
    Из заполненного меша букв оставляет только контуры (внешние + дырки),
    заполняет через triangle_fill, нормали вверх.
    """
    boundary = [e for e in bm.edges if e.is_boundary]
    inner    = [e for e in bm.edges if not e.is_boundary]

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

        # ── 2. Точки вдоль рёбер для метаболов ────────────────────────────
        pts = points_along_edges(letters_obj, offset * 0.7)
        if len(pts) < 2:
            self.report({"ERROR"}, "Не удалось получить рёбра текста.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 3. Плоский контур подложки ─────────────────────────────────────
        base_flat = build_flat_base(context, pts, offset)

        if not base_flat.data.vertices or not base_flat.data.polygons:
            self.report({"ERROR"}, "Подложка пустая. Попробуйте увеличить отступ.")
            delete_obj(base_flat)
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Экструдируем подложку вниз ──────────────────────────────────
        # Верхняя грань = Z=0, нижняя = Z=-base_h
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

        # ── 5. Буквы: контуры + Solidify вверх ─────────────────────────────
        # Буквы начинаются от Z=0 (верх подложки) и идут до Z=+letter_h
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

        # ── 6. Объединяем ──────────────────────────────────────────────────
        deselect_all()
        base_obj.select_set(True)
        letters_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        final_obj = context.active_object

        # Поднимаем: нижняя грань на Z=0
        final_obj.location.z = base_h
        bpy.ops.object.transform_apply(location=True)

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
        precision=1, step=10,
    )
    base_height: FloatProperty(
        name="Толщина подложки (мм)",
        description="Высота основания",
        default=3.0, min=0.5, max=20.0,
        precision=1, step=10,
    )
    letter_height: FloatProperty(
        name="Высота букв (мм)",
        description="На сколько буквы выступают над подложкой",
        default=2.0, min=0.2, max=10.0,
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
