bl_info = {
    "name": "Keychain Maker (Отладка ушка)",
    "author": "Custom",
    "version": (28, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Keychain",
    "description": "Пошаговая отладка приварки ушка",
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

def get_obj(name):
    return bpy.data.objects.get(name)

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
    base_raw.name = "_KM_S1_Base"

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
# ШАГ 1 — Подложка
# ---------------------------------------------------------------------------
class KEYCHAIN_OT_LugStep1(Operator):
    bl_idname  = "keychain.lug_step1"
    bl_label   = "Шаг 1: Плоская подложка"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.keychain_props
        delete_by_prefix("_KM_")

        bpy.ops.object.text_add(location=(0, 0, 0))
        txt = context.active_object
        txt.data.body = props.text
        txt.data.size = 10.0
        if props.font_path and os.path.isfile(props.font_path):
            txt.data.font = bpy.data.fonts.load(props.font_path)
        set_active(context, txt)
        bpy.ops.object.convert(target="MESH")
        letters = context.active_object
        letters.name = "_KM_Letters"

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
        bpy.ops.mesh.remove_doubles(threshold=0.001)
        bpy.ops.object.editmode_toggle()

        pts = points_along_edges(letters, props.base_offset * 0.7)
        base = build_flat_base(context, pts, props.base_offset)

        vx = [v.co.x for v in base.data.vertices]
        vy = [v.co.y for v in base.data.vertices]
        self.report({"INFO"},
            f"Подложка: verts={len(base.data.vertices)}, "
            f"X={min(vx):.2f}..{max(vx):.2f}, "
            f"Y={min(vy):.2f}..{max(vy):.2f}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 2 — Создаём ушко как отдельный объект рядом с подложкой
# ---------------------------------------------------------------------------
class KEYCHAIN_OT_LugStep2(Operator):
    bl_idname  = "keychain.lug_step2"
    bl_label   = "Шаг 2: Создать ушко (отдельный объект)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props    = context.scene.keychain_props
        base_obj = get_obj("_KM_S1_Base")
        if not base_obj:
            self.report({"ERROR"}, "Сначала Шаг 1"); return {"CANCELLED"}

        lug_x    = props.lug_size_x
        lug_y    = props.lug_size_y
        chamfer  = min(props.lug_chamfer, lug_x * 0.45, lug_y * 0.45)
        segs     = props.lug_chamfer_segments
        offset_y = props.lug_offset_y

        vx = [v.co.x for v in base_obj.data.vertices]
        vy = [v.co.y for v in base_obj.data.vertices]
        base_min_x = min(vx)
        base_cy    = (min(vy) + max(vy)) / 2.0

        gap     = 0.5
        right_x = base_min_x - gap
        left_x  = right_x - lug_x
        yc      = base_cy + offset_y
        y0      = yc - lug_y / 2.0
        y1      = yc + lug_y / 2.0

        # Сохраняем параметры в custom properties для следующих шагов
        base_obj["lug_right_x"] = right_x
        base_obj["lug_left_x"]  = left_x
        base_obj["lug_y0"]      = y0
        base_obj["lug_y1"]      = y1
        base_obj["lug_yc"]      = yc

        # Строим ушко
        mesh = bpy.data.meshes.new("_KM_S2_Ear")
        ear_obj = bpy.data.objects.new("_KM_S2_Ear", mesh)
        context.collection.objects.link(ear_obj)

        c = chamfer
        if c > 0.0 and segs >= 1:
            pts_2d = []
            # Правые вершины (без фаски)
            pts_2d.append((right_x, y0))
            pts_2d.append((right_x, y1))
            # Левый верхний — дуга
            for i in range(segs + 1):
                angle = math.pi * 0.5 + math.pi * 0.5 * (i / segs)
                pts_2d.append((left_x + c + math.cos(angle) * c,
                               y1 - c + math.sin(angle) * c))
            # Левый нижний — дуга
            for i in range(segs + 1):
                angle = math.pi + math.pi * 0.5 * (i / segs)
                pts_2d.append((left_x + c + math.cos(angle) * c,
                               y0 + c + math.sin(angle) * c))

            bm = bmesh.new()
            verts = [bm.verts.new((x, y, 0.0)) for x, y in pts_2d]
            bm.faces.new(verts)
        else:
            bm = bmesh.new()
            v0 = bm.verts.new((right_x, y0, 0.0))
            v1 = bm.verts.new((right_x, y1, 0.0))
            v2 = bm.verts.new((left_x,  y1, 0.0))
            v3 = bm.verts.new((left_x,  y0, 0.0))
            bm.faces.new([v0, v1, v2, v3])

        flip_faces_up(bm)
        bm.to_mesh(mesh)
        bm.free()

        self.report({"INFO"},
            f"Ушко: right_x={right_x:.2f}, left_x={left_x:.2f}, "
            f"Y={y0:.2f}..{y1:.2f}, gap={gap}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 3 — Join и показываем состояние до сварки
# ---------------------------------------------------------------------------
class KEYCHAIN_OT_LugStep3(Operator):
    bl_idname  = "keychain.lug_step3"
    bl_label   = "Шаг 3: Join (смотрим граничные рёбра)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        base_obj = get_obj("_KM_S1_Base")
        ear_obj  = get_obj("_KM_S2_Ear")
        if not base_obj or not ear_obj:
            self.report({"ERROR"}, "Сначала Шаги 1 и 2"); return {"CANCELLED"}

        # Копируем custom props
        right_x = base_obj.get("lug_right_x", 0)
        left_x  = base_obj.get("lug_left_x",  0)
        y0      = base_obj.get("lug_y0", 0)
        y1      = base_obj.get("lug_y1", 0)
        yc      = base_obj.get("lug_yc", 0)

        deselect_all()
        base_obj.select_set(True)
        ear_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        joined = context.active_object
        joined.name = "_KM_S3_Joined"
        joined["lug_right_x"] = right_x
        joined["lug_left_x"]  = left_x
        joined["lug_y0"]      = y0
        joined["lug_y1"]      = y1
        joined["lug_yc"]      = yc

        # Считаем граничные рёбра и правые вершины ушка
        bm = bmesh.new()
        bm.from_mesh(joined.data)
        boundary = [e for e in bm.edges if e.is_boundary]
        tol = 0.1
        right_verts = [v for v in bm.verts
                       if abs(v.co.x - right_x) < tol
                       and (y0 - tol) < v.co.y < (y1 + tol)]
        bm.free()

        self.report({"INFO"},
            f"Joined: verts={len(joined.data.vertices)}, "
            f"boundary_edges={len(boundary)}, "
            f"right_verts_ear={len(right_verts)} (X≈{right_x:.2f})")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 4 — Находим пересечение и разбиваем ребро подложки
# ---------------------------------------------------------------------------
class KEYCHAIN_OT_LugStep4(Operator):
    bl_idname  = "keychain.lug_step4"
    bl_label   = "Шаг 4: Найти пересечение и разбить ребро"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        joined = get_obj("_KM_S3_Joined")
        if not joined:
            self.report({"ERROR"}, "Сначала Шаг 3"); return {"CANCELLED"}

        right_x = joined.get("lug_right_x", 0)
        y0      = joined.get("lug_y0", 0)
        y1      = joined.get("lug_y1", 0)
        yc      = joined.get("lug_yc", 0)

        set_active(context, joined)
        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(joined.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        tol = 0.15
        right_verts = sorted(
            [v for v in bm.verts
             if abs(v.co.x - right_x) < tol
             and (y0 - tol) < v.co.y < (y1 + tol)],
            key=lambda v: v.co.y
        )

        print(f"[KM LUG] right_verts count={len(right_verts)}")
        for v in right_verts:
            print(f"  v=({v.co.x:.3f}, {v.co.y:.3f})")

        results = []
        for ear_v in right_verts:
            ey = ear_v.co.y
            ex = ear_v.co.x

            # Луч по +X от вершины ушка
            ray_p1 = Vector((ex, ey))
            ray_p2 = Vector((ex + 500.0, ey))

            best = None
            best_dist = float('inf')

            for edge in bm.edges:
                if not edge.is_valid:
                    continue
                va, vb = edge.verts
                # Пропускаем рёбра ушка (обе вершины у right_x или левее)
                if max(va.co.x, vb.co.x) <= ex + 0.01:
                    continue

                p3 = Vector((va.co.x, va.co.y))
                p4 = Vector((vb.co.x, vb.co.y))

                # Пересечение отрезков
                d1 = ray_p2 - ray_p1
                d2 = p4 - p3
                cross = d1.x * d2.y - d1.y * d2.x
                if abs(cross) < 1e-9:
                    continue
                diff = p3 - ray_p1
                t_ray  = (diff.x * d2.y - diff.y * d2.x) / cross
                t_edge = (diff.x * d1.y - diff.y * d1.x) / cross

                if t_ray < 0.001 or not (0.0 <= t_edge <= 1.0):
                    continue

                pt   = ray_p1 + d1 * t_ray
                dist = (pt - ray_p1).length
                if dist < best_dist:
                    best_dist  = dist
                    best       = (edge, t_edge, pt)

            if best is None:
                print(f"  WARN: нет пересечения для v=({ex:.2f},{ey:.2f})")
                results.append(None)
                continue

            edge, t_edge, pt = best
            print(f"  → ребро ({edge.verts[0].co.x:.2f},{edge.verts[0].co.y:.2f})-"
                  f"({edge.verts[1].co.x:.2f},{edge.verts[1].co.y:.2f}), "
                  f"t={t_edge:.3f}, pt=({pt.x:.2f},{pt.y:.2f})")

            # Разбиваем ребро подложки
            va0 = edge.verts[0].co.copy()
            va1 = edge.verts[1].co.copy()
            res = bmesh.ops.subdivide_edges(bm, edges=[edge], cuts=1,
                                             use_grid_fill=False)
            new_verts = [g for g in res.get("geom_inner", [])
                         if isinstance(g, bmesh.types.BMVert)]
            if new_verts:
                nv = new_verts[0]
                nv.co.x = pt.x
                nv.co.y = pt.y
                nv.co.z = 0.0
                print(f"  new_vert @ ({nv.co.x:.3f},{nv.co.y:.3f})")

                # Соединяем вершину ушка с новой вершиной
                bm.verts.ensure_lookup_table()
                if ear_v.is_valid and nv.is_valid:
                    try:
                        new_edge = bm.edges.new([ear_v, nv])
                        print(f"  edge created: {new_edge.is_valid}")
                    except Exception as ex2:
                        print(f"  edge error: {ex2}")

            results.append(best)

        bmesh.update_edit_mesh(joined.data)
        bpy.ops.object.editmode_toggle()

        joined.name = "_KM_S4_Intersected"
        joined["lug_right_x"] = right_x
        joined["lug_y0"] = y0
        joined["lug_y1"] = y1
        joined["lug_yc"] = yc

        hits = sum(1 for r in results if r is not None)
        self.report({"INFO"}, f"Пересечений найдено: {hits}/{len(right_verts)} — смотрите консоль")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 5 — Fill и финальная очистка
# ---------------------------------------------------------------------------
class KEYCHAIN_OT_LugStep5(Operator):
    bl_idname  = "keychain.lug_step5"
    bl_label   = "Шаг 5: Fill и очистка"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        joined = get_obj("_KM_S4_Intersected")
        if not joined:
            self.report({"ERROR"}, "Сначала Шаг 4"); return {"CANCELLED"}

        set_active(context, joined)
        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(joined.data)

        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
        bm.edges.ensure_lookup_table()
        open_edges = [e for e in bm.edges if e.is_boundary]
        print(f"[KM LUG] open_edges before fill: {len(open_edges)}")
        if open_edges:
            bmesh.ops.triangle_fill(bm, use_beauty=True, edges=open_edges)

        flip_faces_up(bm)
        bmesh.update_edit_mesh(joined.data)
        bpy.ops.object.editmode_toggle()

        joined.name = "_KM_S5_Final2D"
        self.report({"INFO"},
            f"Готово: verts={len(joined.data.vertices)}, "
            f"faces={len(joined.data.polygons)}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Сброс
# ---------------------------------------------------------------------------
class KEYCHAIN_OT_LugReset(Operator):
    bl_idname  = "keychain.lug_reset"
    bl_label   = "Сбросить"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        delete_by_prefix("_KM_")
        self.report({"INFO"}, "Сброшено")
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
        box.prop(props, "lug_size_x")
        box.prop(props, "lug_size_y")
        row = box.row(align=True)
        row.prop(props, "lug_chamfer")
        row.prop(props, "lug_chamfer_segments")
        box.prop(props, "lug_offset_y")
        box.prop(props, "lug_hole_diameter")

        box = layout.box()
        box.label(text="Пошаговая отладка ушка", icon="SEQUENCE")
        col = box.column(align=True)
        col.operator("keychain.lug_step1", icon="MESH_PLANE")
        col.operator("keychain.lug_step2", icon="LINKED")
        col.operator("keychain.lug_step3", icon="AUTOMERGE_ON")
        col.operator("keychain.lug_step4", icon="DRIVER_DISTANCE")
        col.operator("keychain.lug_step5", icon="MESH_GRID")
        layout.operator("keychain.lug_reset", icon="TRASH")


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------

classes = (
    KeychainProperties,
    KEYCHAIN_OT_LugStep1,
    KEYCHAIN_OT_LugStep2,
    KEYCHAIN_OT_LugStep3,
    KEYCHAIN_OT_LugStep4,
    KEYCHAIN_OT_LugStep5,
    KEYCHAIN_OT_LugReset,
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
