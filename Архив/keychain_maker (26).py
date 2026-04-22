bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (25, 0, 0),
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
# Ушко
# ---------------------------------------------------------------------------

def build_lug_3d(context, final_obj, props):
    """
    Строит ушко как отдельный 3D объект и присоединяет к брелоку.

    Вызывается ПОСЛЕ transform_apply — координаты финального объекта:
      низ подложки  = Z=0
      верх подложки = Z=base_h
      верх букв     = Z=base_h+letter_h

    Ушко:
      - высота совпадает с подложкой: Z=0 .. Z=base_h
      - правый край заходит в подложку на `overlap` мм
      - фаска только на левых (внешних) вертикальных рёбрах
      - отверстие вырезается Boolean
    """
    base_h   = props.base_height
    lug_x    = props.lug_size_x
    lug_y    = props.lug_size_y
    chamfer  = props.lug_chamfer
    segs     = props.lug_chamfer_segments
    offset_y = props.lug_offset_y
    hole_r   = props.lug_hole_diameter / 2.0
    overlap  = 1.0   # мм захода в подложку

    # Берём левый край подложки и центр по Y из мировых координат
    mw = final_obj.matrix_world
    world_verts = [mw @ v.co for v in final_obj.data.vertices]
    xs = [v.x for v in world_verts]
    ys = [v.y for v in world_verts]

    base_min_x = min(xs)
    base_cy    = (min(ys) + max(ys)) / 2.0

    # Ушко от Z=0 до Z=base_h (высота = подложка)
    z_bot = 0.0
    z_top = base_h

    # X: правый край заходит в подложку на overlap мм
    x1 = base_min_x + overlap
    x0 = x1 - lug_x            # левый (внешний) край

    yc = base_cy + offset_y
    y0 = yc - lug_y / 2.0
    y1 = yc + lug_y / 2.0

    # Строим параллелепипед
    mesh    = bpy.data.meshes.new("_KM_LugMesh")
    lug_obj = bpy.data.objects.new("_KM_Lug", mesh)
    context.collection.objects.link(lug_obj)

    bm = bmesh.new()
    bot = [
        bm.verts.new((x0, y0, z_bot)),
        bm.verts.new((x1, y0, z_bot)),
        bm.verts.new((x1, y1, z_bot)),
        bm.verts.new((x0, y1, z_bot)),
    ]
    top = [
        bm.verts.new((x0, y0, z_top)),
        bm.verts.new((x1, y0, z_top)),
        bm.verts.new((x1, y1, z_top)),
        bm.verts.new((x0, y1, z_top)),
    ]
    # Грани с правильными нормалями
    bm.faces.new([bot[3], bot[2], bot[1], bot[0]])  # низ
    bm.faces.new([top[0], top[1], top[2], top[3]])  # верх
    bm.faces.new([bot[0], bot[1], top[1], top[0]])  # фронт (Y-)
    bm.faces.new([bot[1], bot[2], top[2], top[1]])  # правый (X+, заходит в подложку)
    bm.faces.new([bot[2], bot[3], top[3], top[2]])  # зад (Y+)
    bm.faces.new([bot[3], bot[0], top[0], top[3]])  # левый (X-, внешний)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()

    # Фаска на двух левых вертикальных рёбрах (X=x0)
    # Правые рёбра (X=x1) не скругляем — они уходят в подложку
    if chamfer > 0.0:
        set_active(context, lug_obj)
        bpy.ops.object.editmode_toggle()
        bm2 = bmesh.from_edit_mesh(lug_obj.data)
        bm2.edges.ensure_lookup_table()

        tol = 0.001
        for e in bm2.edges:
            va, vb = e.verts
            # Левое вертикальное ребро: оба конца на x0, одинаковый Y
            e.select = (
                abs(va.co.x - x0) < tol and
                abs(vb.co.x - x0) < tol and
                abs(va.co.y - vb.co.y) < tol
            )

        bmesh.update_edit_mesh(lug_obj.data)
        bpy.ops.mesh.bevel(
            offset=chamfer,
            offset_type='OFFSET',
            segments=max(1, segs),
            affect='EDGES'
        )
        bpy.ops.object.editmode_toggle()

    # Отверстие
    # Центр по X: от внешнего левого края + hole_r + 2 мм
    hole_cx = x0 + hole_r + 2.0
    hole_cy = yc
    hole_cz = (z_bot + z_top) / 2.0

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48,
        radius=hole_r,
        depth=(z_top - z_bot) + 1.0,
        location=(hole_cx, hole_cy, hole_cz),
    )
    hole_cyl = context.active_object
    hole_cyl.name = "_KM_LugHoleCyl"

    set_active(context, lug_obj)
    mod = lug_obj.modifiers.new("LugHole", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object    = hole_cyl
    mod.solver    = "EXACT"
    bpy.ops.object.modifier_apply(modifier="LugHole")
    delete_obj(hole_cyl)

    return lug_obj


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
            self.report({"ERROR"}, "Подложка пустая. Попробуйте увеличить отступ.")
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

        # ── 5. Буквы: контуры + Solidify вверх ─────────────────────────────
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

        # ── 6. Объединяем подложку и буквы → поднимаем ─────────────────────
        deselect_all()
        base_obj.select_set(True)
        letters_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        final_obj = context.active_object

        # Нижняя грань на Z=0
        final_obj.location.z = base_h
        bpy.ops.object.transform_apply(location=True)

        # ── 7. Ушко строим ПОСЛЕ transform_apply ───────────────────────────
        if props.lug_enable:
            lug_obj = build_lug_3d(context, final_obj, props)

            deselect_all()
            final_obj.select_set(True)
            lug_obj.select_set(True)
            context.view_layer.objects.active = final_obj
            bpy.ops.object.join()
            final_obj = context.active_object

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
