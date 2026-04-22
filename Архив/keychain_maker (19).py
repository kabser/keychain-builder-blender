bl_info = {
    "name": "Keychain Maker (Пошаговый режим)",
    "author": "Custom",
    "version": (16, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Keychain",
    "description": "Генерирует брелок пошагово для отладки контура",
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
    to_del = [o for o in bpy.data.objects if o.name.startswith(prefix)]
    for o in to_del:
        bpy.data.objects.remove(o, do_unlink=True)

def deselect_all():
    bpy.ops.object.select_all(action="DESELECT")

def set_active(context, obj):
    deselect_all()
    obj.select_set(True)
    context.view_layer.objects.active = obj

def get_obj(name):
    return bpy.data.objects.get(name)

def copy_obj(src, new_name, context):
    new_mesh = src.data.copy()
    new_obj  = bpy.data.objects.new(new_name, new_mesh)
    context.collection.objects.link(new_obj)
    return new_obj

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
# ШАГ 1 — Текст → меш букв
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Step1(Operator):
    bl_idname  = "keychain.step1"
    bl_label   = "Шаг 1: Текст → меш"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.keychain_props
        delete_by_prefix("_KM_")

        bpy.ops.object.text_add(location=(0, 0, 0))
        txt_obj = context.active_object
        txt_obj.data.body = props.text
        txt_obj.data.size = 10.0
        if props.font_path and os.path.isfile(props.font_path):
            txt_obj.data.font = bpy.data.fonts.load(props.font_path)

        set_active(context, txt_obj)
        bpy.ops.object.convert(target="MESH")
        obj = context.active_object
        obj.name = "_KM_S1_Letters"

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
        bpy.ops.mesh.remove_doubles(threshold=0.001)
        bpy.ops.object.editmode_toggle()

        self.report({"INFO"},
            f"Шаг 1: verts={len(obj.data.vertices)}, "
            f"edges={len(obj.data.edges)}, faces={len(obj.data.polygons)}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 2 — Создаём метаболы
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Step2(Operator):
    bl_idname  = "keychain.step2"
    bl_label   = "Шаг 2: Метаболы"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props       = context.scene.keychain_props
        letters_obj = get_obj("_KM_S1_Letters")
        if not letters_obj:
            self.report({"ERROR"}, "Сначала Шаг 1"); return {"CANCELLED"}

        offset      = props.base_offset
        elem_radius = offset * 1.1
        grid_size   = offset * 0.35
        sample_step = offset * 0.7
        mb_res      = max(offset * 0.08, 0.0001)
        pts         = points_along_edges(letters_obj, sample_step)

        mb_data = bpy.data.metaballs.new("_KM_S2_MB")
        mb_data.resolution        = mb_res
        mb_data.render_resolution = mb_res
        mb_data.threshold         = 0.6
        mb_obj = bpy.data.objects.new("_KM_S2_MetaObj", mb_data)
        context.collection.objects.link(mb_obj)

        seen = set(); count = 0
        for vx, vy in pts:
            key = (round(vx / grid_size), round(vy / grid_size))
            if key in seen: continue
            seen.add(key)
            el = mb_data.elements.new(type="BALL")
            el.co = Vector((vx, vy, 0.0))
            el.radius = elem_radius
            el.stiffness = 1.0
            count += 1

        context.view_layer.update()
        self.report({"INFO"}, f"Шаг 2: {count} элементов, radius={elem_radius:.2f}, res={mb_res:.4f}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 3 — Конвертация метабола в меш
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Step3(Operator):
    bl_idname  = "keychain.step3"
    bl_label   = "Шаг 3: Метабол → меш (шар)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        mb_obj = get_obj("_KM_S2_MetaObj")
        if not mb_obj:
            self.report({"ERROR"}, "Сначала Шаг 2"); return {"CANCELLED"}

        set_active(context, mb_obj)
        bpy.ops.object.convert(target="MESH")
        obj = context.active_object
        obj.name = "_KM_S3_Ball"

        self.report({"INFO"},
            f"Шаг 3: verts={len(obj.data.vertices)}, faces={len(obj.data.polygons)}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 4 — Срезаем нижнюю полусферу ТОЧНО по Z=0
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Step4(Operator):
    bl_idname  = "keychain.step4"
    bl_label   = "Шаг 4: Срезать низ по Z=0"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        src = get_obj("_KM_S3_Ball")
        if not src:
            self.report({"ERROR"}, "Сначала Шаг 3"); return {"CANCELLED"}

        new_obj = copy_obj(src, "_KM_S4_TopHalf", context)
        set_active(context, new_obj)

        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(new_obj.data)

        # Срезаем точно по Z=0:
        # Удаляем грани у которых ВСЕ вершины имеют Z <= 0
        # Это чище чем порог от elem_radius
        lower = [f for f in bm.faces
                 if all(v.co.z <= 0.0 for v in f.verts)]
        bmesh.ops.delete(bm, geom=lower, context="FACES")

        # Удаляем рёбра которые остались ниже Z=0 (висячие)
        lower_edges = [e for e in bm.edges
                       if all(v.co.z < 0.0 for v in e.verts)]
        if lower_edges:
            bmesh.ops.delete(bm, geom=lower_edges, context="EDGES")

        # Удаляем вершины ниже Z=0
        lower_verts = [v for v in bm.verts if v.co.z < 0.0]
        if lower_verts:
            bmesh.ops.delete(bm, geom=lower_verts, context="VERTS")

        bmesh.update_edit_mesh(new_obj.data)
        bpy.ops.object.editmode_toggle()

        src.hide_set(True)
        self.report({"INFO"},
            f"Шаг 4: удалено {len(lower)} граней, "
            f"осталось verts={len(new_obj.data.vertices)}, faces={len(new_obj.data.polygons)}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 5 — Проецируем на Z=0 + минимальный merge
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Step5(Operator):
    bl_idname  = "keychain.step5"
    bl_label   = "Шаг 5: Проекция Z=0 + Merge"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        src = get_obj("_KM_S4_TopHalf")
        if not src:
            self.report({"ERROR"}, "Сначала Шаг 4"); return {"CANCELLED"}

        new_obj = copy_obj(src, "_KM_S5_Flat", context)
        set_active(context, new_obj)

        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(new_obj.data)

        # Ставим Z=0 всем вершинам
        for v in bm.verts:
            v.co.z = 0.0

        # Минимальный merge — только настоящие дубли (очень маленький порог)
        # Не используем большой порог чтобы не схлопывать соседние вершины
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)

        bmesh.update_edit_mesh(new_obj.data)
        bpy.ops.object.editmode_toggle()

        src.hide_set(True)
        self.report({"INFO"},
            f"Шаг 5: verts={len(new_obj.data.vertices)}, "
            f"edges={len(new_obj.data.edges)}, faces={len(new_obj.data.polygons)}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 6 — Извлекаем граничный контур
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Step6(Operator):
    bl_idname  = "keychain.step6"
    bl_label   = "Шаг 6: Извлечь контур (boundary)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        src = get_obj("_KM_S5_Flat")
        if not src:
            self.report({"ERROR"}, "Сначала Шаг 5"); return {"CANCELLED"}

        new_obj = copy_obj(src, "_KM_S6_Contour", context)
        set_active(context, new_obj)

        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(new_obj.data)

        boundary_edges = [e for e in bm.edges if e.is_boundary]
        inner_edges    = [e for e in bm.edges if not e.is_boundary]

        bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
        valid_inner = [e for e in inner_edges if e.is_valid]
        if valid_inner:
            bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
        isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
        if isolated:
            bmesh.ops.delete(bm, geom=isolated, context="VERTS")

        open_verts = [v for v in bm.verts
                      if v.is_valid and len(list(v.link_edges)) != 2]

        bmesh.update_edit_mesh(new_obj.data)
        bpy.ops.object.editmode_toggle()

        src.hide_set(True)
        status = "замкнут ✓" if not open_verts else f"РАЗРЫВ! вершин={len(open_verts)}"
        self.report({"INFO"},
            f"Шаг 6: boundary={len(boundary_edges)}, "
            f"verts={len(new_obj.data.vertices)}, контур {status}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 7 — Заполняем контур
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Step7(Operator):
    bl_idname  = "keychain.step7"
    bl_label   = "Шаг 7: Заполнить контур"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        src = get_obj("_KM_S6_Contour")
        if not src:
            self.report({"ERROR"}, "Сначала Шаг 6"); return {"CANCELLED"}

        new_obj = copy_obj(src, "_KM_S7_Filled", context)
        set_active(context, new_obj)

        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(new_obj.data)

        all_edges = list(bm.edges)
        new_faces = []
        if all_edges:
            result    = bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_edges)
            new_faces = [g for g in result.get("geom", []) if isinstance(g, bmesh.types.BMFace)]
        flip_faces_up(bm)

        bmesh.update_edit_mesh(new_obj.data)
        bpy.ops.object.editmode_toggle()

        src.hide_set(True)
        self.report({"INFO"},
            f"Шаг 7: граней={len(new_faces)}, "
            f"verts={len(new_obj.data.vertices)}, faces={len(new_obj.data.polygons)}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Сброс
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Reset(Operator):
    bl_idname  = "keychain.reset_steps"
    bl_label   = "Сбросить все шаги"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        delete_by_prefix("_KM_")
        self.report({"INFO"}, "Сброшено")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Финальная сборка
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Generate(Operator):
    bl_idname  = "keychain.generate"
    bl_label   = "Создать брелок (финал)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props     = context.scene.keychain_props
        text      = props.text
        font_path = props.font_path
        offset    = props.base_offset
        base_h    = props.base_height
        letter_h  = props.letter_height

        if not text:
            self.report({"WARNING"}, "Введите текст!"); return {"CANCELLED"}

        delete_by_prefix("_KM_")

        # Текст → меш
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
            self.report({"ERROR"}, "Текст пустой"); return {"CANCELLED"}

        # Метаболы
        elem_radius = offset * 1.1
        grid_size   = offset * 0.35
        mb_res      = max(offset * 0.08, 0.0001)
        pts         = points_along_edges(letters_obj, offset * 0.7)

        mb_data = bpy.data.metaballs.new("_KM_MB")
        mb_data.resolution = mb_res
        mb_data.render_resolution = mb_res
        mb_data.threshold = 0.6
        mb_obj = bpy.data.objects.new("_KM_MetaObj", mb_data)
        context.collection.objects.link(mb_obj)
        seen = set()
        for vx, vy in pts:
            key = (round(vx / grid_size), round(vy / grid_size))
            if key in seen: continue
            seen.add(key)
            el = mb_data.elements.new(type="BALL")
            el.co = Vector((vx, vy, 0.0)); el.radius = elem_radius; el.stiffness = 1.0
        context.view_layer.update()

        set_active(context, mb_obj)
        bpy.ops.object.convert(target="MESH")
        base_raw = context.active_object
        base_raw.name = "_KM_BaseRaw"

        set_active(context, base_raw)
        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(base_raw.data)

        # Срезаем точно по Z=0
        lower = [f for f in bm.faces if all(v.co.z <= 0.0 for v in f.verts)]
        bmesh.ops.delete(bm, geom=lower, context="FACES")
        lower_edges = [e for e in bm.edges if all(v.co.z < 0.0 for v in e.verts)]
        if lower_edges: bmesh.ops.delete(bm, geom=lower_edges, context="EDGES")
        lower_verts = [v for v in bm.verts if v.co.z < 0.0]
        if lower_verts: bmesh.ops.delete(bm, geom=lower_verts, context="VERTS")

        # Проецируем на Z=0 с минимальным merge
        for v in bm.verts:
            v.co.z = 0.0
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)

        # Граничный контур
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        inner_edges    = [e for e in bm.edges if not e.is_boundary]
        bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
        valid_inner = [e for e in inner_edges if e.is_valid]
        if valid_inner: bmesh.ops.delete(bm, geom=valid_inner, context="EDGES")
        isolated = [v for v in bm.verts if v.is_valid and not v.link_edges]
        if isolated: bmesh.ops.delete(bm, geom=isolated, context="VERTS")

        all_edges = list(bm.edges)
        if all_edges:
            bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_edges)
        flip_faces_up(bm)
        bmesh.update_edit_mesh(base_raw.data)
        bpy.ops.object.editmode_toggle()
        base_flat = base_raw

        if not base_flat.data.vertices or not base_flat.data.polygons:
            self.report({"ERROR"}, "Подложка пустая")
            delete_obj(base_flat); delete_obj(letters_obj); return {"CANCELLED"}

        # Экструзия подложки вниз
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

        # Буквы
        set_active(context, letters_obj)
        bpy.ops.object.editmode_toggle()
        bm5 = bmesh.from_edit_mesh(letters_obj.data)
        inner5 = [e for e in bm5.edges if not e.is_boundary]
        bmesh.ops.delete(bm5, geom=bm5.faces[:], context="FACES_ONLY")
        if inner5: bmesh.ops.delete(bm5, geom=[e for e in inner5 if e.is_valid], context="EDGES")
        iso5 = [v for v in bm5.verts if v.is_valid and not v.link_edges]
        if iso5: bmesh.ops.delete(bm5, geom=iso5, context="VERTS")
        all_e5 = list(bm5.edges)
        if all_e5: bmesh.ops.triangle_fill(bm5, use_beauty=True, edges=all_e5)
        flip_faces_up(bm5)
        bmesh.update_edit_mesh(letters_obj.data)
        bpy.ops.object.editmode_toggle()

        mod = letters_obj.modifiers.new("Solidify", "SOLIDIFY")
        mod.thickness = letter_h; mod.offset = 1.0
        mod.use_even_offset = True; mod.use_rim = True
        bpy.ops.object.modifier_apply(modifier="Solidify")

        deselect_all()
        base_flat.select_set(True); letters_obj.select_set(True)
        context.view_layer.objects.active = base_flat
        bpy.ops.object.join()
        final_obj = context.active_object
        final_obj.location.z = base_h
        bpy.ops.object.transform_apply(location=True)

        safe = "".join(c for c in text if c.isascii() and (c.isalnum() or c in " _-"))[:20].strip() or "keychain"
        final_obj.name = f"Keychain_{safe}"

        self.report({"INFO"}, f'Брелок «{text}» создан!')
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Свойства
# ---------------------------------------------------------------------------

class KeychainProperties(PropertyGroup):
    text: StringProperty(name="Текст", default="IVAN")
    font_path: StringProperty(name="Шрифт (.ttf)", subtype="FILE_PATH", default="")
    base_offset: FloatProperty(name="Отступ подложки (мм)", default=3.0, min=0.5, max=30.0, precision=1, step=10)
    base_height: FloatProperty(name="Толщина подложки (мм)", default=3.0, min=0.5, max=20.0, precision=1, step=10)
    letter_height: FloatProperty(name="Высота букв (мм)", default=2.0, min=0.2, max=10.0, precision=1, step=10)


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

        box = layout.box()
        box.label(text="Пошаговый режим (основание)", icon="SEQUENCE")
        col = box.column(align=True)
        col.operator("keychain.step1", icon="FONT_DATA")
        col.operator("keychain.step2", icon="META_BALL")
        col.operator("keychain.step3", icon="MESH_UVSPHERE")
        col.operator("keychain.step4", icon="REMOVE")
        col.operator("keychain.step5", icon="AXIS_TOP")
        col.operator("keychain.step6", icon="CURVE_PATH")
        col.operator("keychain.step7", icon="MESH_GRID")
        box.operator("keychain.reset_steps", icon="TRASH")

        layout.separator()
        layout.operator("keychain.generate", icon="MESH_DATA", text="Создать брелок (финал)")


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------

classes = (
    KeychainProperties,
    KEYCHAIN_OT_Step1, KEYCHAIN_OT_Step2, KEYCHAIN_OT_Step3,
    KEYCHAIN_OT_Step4, KEYCHAIN_OT_Step5, KEYCHAIN_OT_Step6,
    KEYCHAIN_OT_Step7, KEYCHAIN_OT_Reset, KEYCHAIN_OT_Generate,
    KEYCHAIN_PT_Panel,
)

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
