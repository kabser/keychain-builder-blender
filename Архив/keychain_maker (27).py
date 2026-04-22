bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (26, 0, 0),
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
# Ушко: 2D плоскость + автосварка с подложкой
# ---------------------------------------------------------------------------

def create_ear_plane_2d(context, x_left, x_right, y_bot, y_top):
    """Создаёт плоский прямоугольник ушка (Z=0)."""
    mesh = bpy.data.meshes.new("_KM_EarPlane")
    obj  = bpy.data.objects.new("_KM_EarPlane", mesh)
    context.collection.objects.link(obj)

    bm = bmesh.new()
    v0 = bm.verts.new((x_left,  y_bot, 0.0))
    v1 = bm.verts.new((x_right, y_bot, 0.0))
    v2 = bm.verts.new((x_right, y_top, 0.0))
    v3 = bm.verts.new((x_left,  y_top, 0.0))
    bm.faces.new([v0, v1, v2, v3])
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    return obj


def bevel_left_verts(context, obj, x_left, chamfer, segments):
    """Фаска на двух левых вершинах плоского прямоугольника."""
    if chamfer <= 0.0:
        return
    set_active(context, obj)
    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(obj.data)
    tol = 0.001
    for v in bm.verts:
        v.select = abs(v.co.x - x_left) < tol
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.bevel(
        offset=chamfer,
        offset_type='OFFSET',
        segments=max(1, segments),
        affect='VERTICES'
    )
    bpy.ops.object.editmode_toggle()


def count_boundary_edges(bm):
    """Количество граничных рёбер в bmesh."""
    return sum(1 for e in bm.edges if e.is_boundary)


def weld_ear_push(context, base_obj, ear_obj,
                  right_x, y_bot, y_top,
                  step=0.05, max_push=5.0):
    """
    Объединяет ушко с плоской подложкой и двигает правые два ребра ушка
    вглубь подложки маленькими шагами.

    Критерий остановки: количество граничных рёбер уменьшилось
    (правые рёбра ушка вошли в подложку и «исчезли»).

    Возвращает объединённый объект.
    """
    # Объединяем
    deselect_all()
    base_obj.select_set(True)
    ear_obj.select_set(True)
    context.view_layer.objects.active = base_obj
    bpy.ops.object.join()
    joined = context.active_object

    bpy.ops.object.editmode_toggle()
    bm = bmesh.from_edit_mesh(joined.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Начальное количество граничных рёбер
    initial_boundary = count_boundary_edges(bm)
    tol = step * 1.5  # допуск для поиска вершин

    pushed = 0.0
    current_x = right_x

    while pushed < max_push:
        # Находим правые вершины ушка по текущей X-позиции
        right_verts = [
            v for v in bm.verts
            if v.is_valid
            and abs(v.co.x - current_x) < tol
            and (y_bot - tol) < v.co.y < (y_top + tol)
        ]

        if not right_verts:
            break

        # Двигаем вправо (+X, в сторону подложки)
        for v in right_verts:
            v.co.x += step

        current_x += step
        pushed    += step

        bm.normal_update()
        bmesh.update_edit_mesh(joined.data, loop_triangles=False, destructive=False)
        bm = bmesh.from_edit_mesh(joined.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        new_boundary = count_boundary_edges(bm)

        # Правые рёбра ушка вошли в подложку — граничных рёбер стало меньше
        if new_boundary < initial_boundary:
            break

    # Финальная очистка: удаляем возможные дубли на шве
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=step * 2)

    # Заполняем все открытые петли которые могли образоваться
    open_edges = [e for e in bm.edges if e.is_boundary]
    if open_edges:
        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=open_edges)

    flip_faces_up(bm)
    bmesh.update_edit_mesh(joined.data)
    bpy.ops.object.editmode_toggle()
    return joined


def add_ear_to_base_2d(context, base_obj, props):
    """
    Добавляет ушко к плоской подложке (до экструзии).
    Возвращает (объединённый объект, ear_info).
    """
    lug_x    = props.lug_size_x
    lug_y    = props.lug_size_y
    chamfer  = min(props.lug_chamfer, lug_x * 0.45, lug_y * 0.45)
    segs     = props.lug_chamfer_segments
    offset_y = props.lug_offset_y

    # Читаем габариты плоской подложки
    xs = [v.co.x for v in base_obj.data.vertices]
    ys = [v.co.y for v in base_obj.data.vertices]
    base_min_x = min(xs)
    base_cy    = (min(ys) + max(ys)) / 2.0

    # Начальная позиция ушка: правый край с небольшим зазором от подложки
    gap     = 0.5        # начальный зазор (мм)
    right_x = base_min_x - gap   # правый край ушка
    left_x  = right_x - lug_x    # левый (внешний) край

    yc  = base_cy + offset_y
    y0  = yc - lug_y / 2.0
    y1  = yc + lug_y / 2.0

    # Создаём плоский прямоугольник ушка
    ear_obj = create_ear_plane_2d(context, left_x, right_x, y0, y1)

    # Фаска на левых (внешних) вершинах
    bevel_left_verts(context, ear_obj, left_x, chamfer, segs)

    # Автосварка: двигаем правые рёбра в подложку
    joined = weld_ear_push(
        context, base_obj, ear_obj,
        right_x, y0, y1,
        step=props.lug_weld_step,
        max_push=props.lug_weld_max,
    )

    ear_info = {
        "outer_x":  left_x,
        "y_center": yc,
    }
    return joined, ear_info


# ---------------------------------------------------------------------------
# Отверстие в ушке
# ---------------------------------------------------------------------------

def cut_ear_hole(context, obj, ear_info, props):
    """
    Вырезает отверстие через Boolean.
    Вызывается после transform_apply — координаты финальные.
    """
    hole_r = props.lug_hole_diameter / 2.0
    base_h = props.base_height

    # Центр отверстия: от внешнего края + hole_r + 2 мм
    cx = ear_info["outer_x"] + hole_r + 2.0
    cy = ear_info["y_center"]
    cz = base_h / 2.0   # середина по высоте подложки

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

        # ── 4. Ушко: к плоской подложке ДО экструзии ──────────────────────
        ear_info = None
        if props.lug_enable:
            base_flat, ear_info = add_ear_to_base_2d(context, base_flat, props)

        # ── 5. Экструдируем подложку (+ ушко) вниз ────────────────────────
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

        # ── 7. Объединяем подложку и буквы ─────────────────────────────────
        deselect_all()
        base_obj.select_set(True)
        letters_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        final_obj = context.active_object

        # Нижняя грань на Z=0
        final_obj.location.z = base_h
        bpy.ops.object.transform_apply(location=True)

        # ── 8. Отверстие в ушке (после transform_apply) ────────────────────
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
    lug_weld_step: FloatProperty(
        name="Шаг вдавливания (мм)",
        description="Шаг движения ушка внутрь подложки",
        default=0.05, min=0.01, max=0.5, precision=2, step=1,
    )
    lug_weld_max: FloatProperty(
        name="Макс. вдавливание (мм)",
        description="Максимальная глубина вхождения ушка в подложку",
        default=5.0, min=0.5, max=15.0, precision=1, step=5,
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
            box.separator()
            box.label(text="Вдавливание в подложку:", icon="SETTINGS")
            box.prop(props, "lug_weld_step")
            box.prop(props, "lug_weld_max")

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
