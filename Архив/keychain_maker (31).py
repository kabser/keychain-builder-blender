bl_info = {
    "name": "Keychain Lug Debug",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Keychain",
    "category": "Add Mesh",
}

import bpy
import bmesh
import math
import os
from mathutils import Vector
from bpy.props import StringProperty, FloatProperty, IntProperty
from bpy.types import Panel, Operator, PropertyGroup


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


# ---------------------------------------------------------------------------
# ШАГ 1 — Плоская подложка
# ---------------------------------------------------------------------------
class KLD_OT_Step1(Operator):
    bl_idname  = "kld.step1"
    bl_label   = "Шаг 1: Подложка"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.kld_props
        delete_by_prefix("_KLD_")

        # Текст
        bpy.ops.object.text_add(location=(0, 0, 0))
        txt = context.active_object
        txt.data.body = props.text
        txt.data.size = 10.0
        if props.font_path and os.path.isfile(props.font_path):
            txt.data.font = bpy.data.fonts.load(props.font_path)
        bpy.ops.object.convert(target="MESH")
        letters = context.active_object
        letters.name = "_KLD_Letters"

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
        bpy.ops.mesh.remove_doubles(threshold=0.001)
        bpy.ops.object.editmode_toggle()

        # Метаболы
        offset = props.base_offset
        mb_res = max(offset * 0.08, 0.0001)
        elem_r = offset * 1.1
        grid   = offset * 0.35

        pts = points_along_edges(letters, offset * 0.7)

        mb_data = bpy.data.metaballs.new("_KLD_MB")
        mb_data.resolution = mb_res
        mb_data.render_resolution = mb_res
        mb_data.threshold = 0.6
        mb_obj = bpy.data.objects.new("_KLD_MetaObj", mb_data)
        context.collection.objects.link(mb_obj)

        seen = set()
        for vx, vy in pts:
            key = (round(vx / grid), round(vy / grid))
            if key in seen: continue
            seen.add(key)
            el = mb_data.elements.new(type="BALL")
            el.co = Vector((vx, vy, 0.0))
            el.radius = elem_r
            el.stiffness = 1.0

        context.view_layer.update()
        set_active(context, mb_obj)
        bpy.ops.object.convert(target="MESH")
        base = context.active_object
        base.name = "_KLD_Base"

        # Чистка
        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(base.data)

        lo_f = [f for f in bm.faces if all(v.co.z <= 0.0 for v in f.verts)]
        bmesh.ops.delete(bm, geom=lo_f, context="FACES")
        lo_e = [e for e in bm.edges if all(v.co.z < 0.0 for v in e.verts)]
        if lo_e: bmesh.ops.delete(bm, geom=lo_e, context="EDGES")
        lo_v = [v for v in bm.verts if v.co.z < 0.0]
        if lo_v: bmesh.ops.delete(bm, geom=lo_v, context="VERTS")

        for v in bm.verts: v.co.z = 0.0
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)

        inner = [e for e in bm.edges if not e.is_boundary]
        bmesh.ops.delete(bm, geom=bm.faces[:], context="FACES_ONLY")
        valid_i = [e for e in inner if e.is_valid]
        if valid_i: bmesh.ops.delete(bm, geom=valid_i, context="EDGES")
        iso = [v for v in bm.verts if v.is_valid and not v.link_edges]
        if iso: bmesh.ops.delete(bm, geom=iso, context="VERTS")

        all_e = [e for e in bm.edges if e.is_valid]
        if all_e: bmesh.ops.triangle_fill(bm, use_beauty=True, edges=all_e)
        flip_faces_up(bm)
        bmesh.update_edit_mesh(base.data)
        bpy.ops.object.editmode_toggle()

        xs = [v.co.x for v in base.data.vertices]
        ys = [v.co.y for v in base.data.vertices]
        self.report({"INFO"},
            f"Подложка: V={len(base.data.vertices)} "
            f"X=[{min(xs):.1f},{max(xs):.1f}] Y=[{min(ys):.1f},{max(ys):.1f}]")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 2 — Ушко отдельным объектом
# ---------------------------------------------------------------------------
class KLD_OT_Step2(Operator):
    bl_idname  = "kld.step2"
    bl_label   = "Шаг 2: Ушко"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props    = context.scene.kld_props
        base_obj = get_obj("_KLD_Base")
        if not base_obj:
            self.report({"ERROR"}, "Сначала Шаг 1"); return {"CANCELLED"}

        lug_x = props.lug_x
        lug_y = props.lug_y
        c     = min(props.chamfer, lug_x * 0.45, lug_y * 0.45)
        segs  = props.chamfer_segs
        oy    = props.offset_y

        xs = [v.co.x for v in base_obj.data.vertices]
        ys = [v.co.y for v in base_obj.data.vertices]
        base_min_x = min(xs)
        base_cy    = (min(ys) + max(ys)) / 2.0

        gap     = 0.5
        right_x = base_min_x - gap
        left_x  = right_x - lug_x
        yc      = base_cy + oy
        y0      = yc - lug_y / 2.0
        y1      = yc + lug_y / 2.0

        # Сохраняем в custom props базы
        base_obj["lug_right_x"] = right_x
        base_obj["lug_left_x"]  = left_x
        base_obj["lug_y0"]      = y0
        base_obj["lug_y1"]      = y1
        base_obj["lug_yc"]      = yc
        base_obj["lug_gap"]     = gap

        # Строим ушко
        mesh    = bpy.data.meshes.new("_KLD_Ear")
        ear_obj = bpy.data.objects.new("_KLD_Ear", mesh)
        context.collection.objects.link(ear_obj)

        bm = bmesh.new()
        if c > 0.0 and segs >= 1:
            pts2d = []
            pts2d.append((right_x, y0))
            pts2d.append((right_x, y1))
            for i in range(segs + 1):
                a = math.pi * 0.5 + math.pi * 0.5 * (i / segs)
                pts2d.append((left_x + c + math.cos(a) * c,
                              y1 - c + math.sin(a) * c))
            for i in range(segs + 1):
                a = math.pi + math.pi * 0.5 * (i / segs)
                pts2d.append((left_x + c + math.cos(a) * c,
                              y0 + c + math.sin(a) * c))
            verts = [bm.verts.new((x, y, 0.0)) for x, y in pts2d]
        else:
            verts = [
                bm.verts.new((right_x, y0, 0.0)),
                bm.verts.new((right_x, y1, 0.0)),
                bm.verts.new((left_x,  y1, 0.0)),
                bm.verts.new((left_x,  y0, 0.0)),
            ]
        bm.faces.new(verts)
        flip_faces_up(bm)
        bm.to_mesh(mesh)
        bm.free()

        self.report({"INFO"},
            f"Ушко: right_x={right_x:.2f}, left_x={left_x:.2f} "
            f"Y=[{y0:.2f},{y1:.2f}] gap={gap}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 3 — Только Join, смотрим что получилось
# ---------------------------------------------------------------------------
class KLD_OT_Step3(Operator):
    bl_idname  = "kld.step3"
    bl_label   = "Шаг 3: Join"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        base_obj = get_obj("_KLD_Base")
        ear_obj  = get_obj("_KLD_Ear")
        if not base_obj or not ear_obj:
            self.report({"ERROR"}, "Сначала Шаги 1 и 2"); return {"CANCELLED"}

        right_x = base_obj.get("lug_right_x", 0.0)
        left_x  = base_obj.get("lug_left_x",  0.0)
        y0      = base_obj.get("lug_y0", 0.0)
        y1      = base_obj.get("lug_y1", 0.0)
        yc      = base_obj.get("lug_yc", 0.0)

        deselect_all()
        base_obj.select_set(True)
        ear_obj.select_set(True)
        context.view_layer.objects.active = base_obj
        bpy.ops.object.join()
        joined = context.active_object
        joined.name = "_KLD_Joined"

        # Сохраняем параметры
        joined["lug_right_x"] = right_x
        joined["lug_left_x"]  = left_x
        joined["lug_y0"]      = y0
        joined["lug_y1"]      = y1
        joined["lug_yc"]      = yc

        # Анализ через отдельный bmesh (не editmode — безопаснее)
        bm = bmesh.new()
        bm.from_mesh(joined.data)

        boundary = [e for e in bm.edges if e.is_boundary]
        tol = 0.2
        right_verts = [v for v in bm.verts
                       if abs(v.co.x - right_x) < tol
                       and (y0 - tol) < v.co.y < (y1 + tol)]

        # Выводим в консоль
        print("\n[KLD Step3] === АНАЛИЗ ПОСЛЕ JOIN ===")
        print(f"  Всего вершин:       {len(bm.verts)}")
        print(f"  Всего рёбер:        {len(bm.edges)}")
        print(f"  Граничных рёбер:    {len(boundary)}")
        print(f"  right_x искомый:    {right_x:.3f}")
        print(f"  Найдено right_verts:{len(right_verts)}")
        for v in sorted(right_verts, key=lambda v: v.co.y):
            print(f"    ({v.co.x:.3f}, {v.co.y:.3f})")
        print(f"  Диапазон X всех вершин: [{min(v.co.x for v in bm.verts):.2f} .. {max(v.co.x for v in bm.verts):.2f}]")
        print(f"  Диапазон Y всех вершин: [{min(v.co.y for v in bm.verts):.2f} .. {max(v.co.y for v in bm.verts):.2f}]")

        bm.free()

        self.report({"INFO"},
            f"Join OK: V={len(joined.data.vertices)}, "
            f"boundary={len(boundary)}, right_verts={len(right_verts)} "
            f"— подробности в консоли")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 4 — Только поиск пересечений (БЕЗ subdivide), выводим в консоль
# ---------------------------------------------------------------------------
class KLD_OT_Step4(Operator):
    bl_idname  = "kld.step4"
    bl_label   = "Шаг 4: Найти пересечения (только лог)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        joined = get_obj("_KLD_Joined")
        if not joined:
            self.report({"ERROR"}, "Сначала Шаг 3"); return {"CANCELLED"}

        right_x = joined.get("lug_right_x", 0.0)
        y0      = joined.get("lug_y0", 0.0)
        y1      = joined.get("lug_y1", 0.0)

        bm = bmesh.new()
        bm.from_mesh(joined.data)

        tol = 0.2
        right_verts = sorted(
            [v for v in bm.verts
             if abs(v.co.x - right_x) < tol
             and (y0 - tol) < v.co.y < (y1 + tol)],
            key=lambda v: v.co.y
        )

        print("\n[KLD Step4] === ПОИСК ПЕРЕСЕЧЕНИЙ ===")
        print(f"  right_verts: {len(right_verts)}")

        found = 0
        for ear_v in right_verts:
            ex, ey = ear_v.co.x, ear_v.co.y
            print(f"\n  Луч от ({ex:.3f}, {ey:.3f}) → +X")

            best_dist  = float('inf')
            best_pt    = None
            best_e_idx = None

            for i, edge in enumerate(bm.edges):
                va, vb = edge.verts
                # Пропускаем рёбра ушка
                if max(va.co.x, vb.co.x) <= ex + 0.05:
                    continue
                # Ребро должно пересекать горизонталь Y=ey
                if not (min(va.co.y, vb.co.y) - 0.001 <= ey <= max(va.co.y, vb.co.y) + 0.001):
                    continue

                # Линейная интерполяция X по Y
                dy = vb.co.y - va.co.y
                if abs(dy) < 1e-9:
                    continue
                t = (ey - va.co.y) / dy
                if not (-0.001 <= t <= 1.001):
                    continue
                ix = va.co.x + t * (vb.co.x - va.co.x)
                if ix <= ex + 0.05:
                    continue

                dist = ix - ex
                if dist < best_dist:
                    best_dist  = dist
                    best_pt    = (ix, ey)
                    best_e_idx = i

            if best_pt:
                found += 1
                e = bm.edges[best_e_idx]
                print(f"    → пересечение @ ({best_pt[0]:.3f},{best_pt[1]:.3f}), "
                      f"dist={best_dist:.3f}")
                print(f"      ребро #{best_e_idx}: "
                      f"({e.verts[0].co.x:.3f},{e.verts[0].co.y:.3f})-"
                      f"({e.verts[1].co.x:.3f},{e.verts[1].co.y:.3f})")
            else:
                print(f"    → НЕ НАЙДЕНО")

        bm.free()

        self.report({"INFO"},
            f"Найдено пересечений: {found}/{len(right_verts)} — смотрите консоль")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# ШАГ 5 — Применяем пересечения: subdivide + соединяем рёбра
# ---------------------------------------------------------------------------
class KLD_OT_Step5(Operator):
    bl_idname  = "kld.step5"
    bl_label   = "Шаг 5: Применить пересечения"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        joined = get_obj("_KLD_Joined")
        if not joined:
            self.report({"ERROR"}, "Сначала Шаг 3"); return {"CANCELLED"}

        right_x = joined.get("lug_right_x", 0.0)
        y0      = joined.get("lug_y0", 0.0)
        y1      = joined.get("lug_y1", 0.0)

        set_active(context, joined)
        bpy.ops.object.editmode_toggle()
        bm = bmesh.from_edit_mesh(joined.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        tol = 0.2
        right_verts = sorted(
            [v for v in bm.verts
             if v.is_valid
             and abs(v.co.x - right_x) < tol
             and (y0 - tol) < v.co.y < (y1 + tol)],
            key=lambda v: v.co.y
        )

        created = 0
        for ear_v in right_verts:
            if not ear_v.is_valid:
                continue
            ex, ey = ear_v.co.x, ear_v.co.y

            best_dist  = float('inf')
            best_edge  = None
            best_t     = None
            best_ix    = None

            # Перебираем рёбра — простой перебор без bmesh.ops
            for edge in list(bm.edges):
                if not edge.is_valid:
                    continue
                va, vb = edge.verts
                if max(va.co.x, vb.co.x) <= ex + 0.05:
                    continue
                dy = vb.co.y - va.co.y
                if abs(dy) < 1e-9:
                    continue
                t = (ey - va.co.y) / dy
                if not (-0.001 <= t <= 1.001):
                    continue
                t = max(0.001, min(0.999, t))  # не на самом конце
                ix = va.co.x + t * (vb.co.x - va.co.x)
                if ix <= ex + 0.05:
                    continue
                dist = ix - ex
                if dist < best_dist:
                    best_dist = dist
                    best_edge = edge
                    best_t    = t
                    best_ix   = ix

            if best_edge is None or not best_edge.is_valid:
                continue

            # Добавляем вершину на ребро вручную (без subdivide_edges)
            va = best_edge.verts[0]
            vb = best_edge.verts[1]
            new_co = Vector((best_ix, ey, 0.0))

            # Создаём новую вершину
            new_v = bm.verts.new(new_co)

            # Удаляем старое ребро
            bm.edges.remove(best_edge)

            # Создаём два новых ребра вместо одного
            try:
                bm.edges.new([va, new_v])
            except Exception:
                pass
            try:
                bm.edges.new([new_v, vb])
            except Exception:
                pass

            # Соединяем вершину ушка с новой вершиной
            try:
                bm.edges.new([ear_v, new_v])
                created += 1
            except Exception:
                pass

            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

        # Заполняем открытые петли
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
        open_edges = [e for e in bm.edges if e.is_boundary]
        if open_edges:
            bmesh.ops.triangle_fill(bm, use_beauty=True, edges=open_edges)

        flip_faces_up(bm)
        bmesh.update_edit_mesh(joined.data)
        bpy.ops.object.editmode_toggle()

        joined.name = "_KLD_Final2D"
        self.report({"INFO"},
            f"Создано соединений: {created}. "
            f"V={len(joined.data.vertices)}, F={len(joined.data.polygons)}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Сброс
# ---------------------------------------------------------------------------
class KLD_OT_Reset(Operator):
    bl_idname  = "kld.reset"
    bl_label   = "Сбросить"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        delete_by_prefix("_KLD_")
        self.report({"INFO"}, "Сброшено")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Свойства
# ---------------------------------------------------------------------------
class KLD_Props(PropertyGroup):
    text: StringProperty(name="Текст", default="IVAN")
    font_path: StringProperty(name="Шрифт", subtype="FILE_PATH", default="")
    base_offset: FloatProperty(name="Отступ подложки (мм)", default=3.0,
                                min=0.5, max=30.0, precision=1, step=10)
    base_height: FloatProperty(name="Толщина подложки (мм)", default=3.0,
                                min=0.5, max=20.0, precision=1, step=10)
    lug_x: FloatProperty(name="Длина ушка X (мм)", default=8.0,
                          min=3.0, max=30.0, precision=1, step=10)
    lug_y: FloatProperty(name="Ширина ушка Y (мм)", default=8.0,
                          min=3.0, max=30.0, precision=1, step=10)
    chamfer: FloatProperty(name="Фаска (мм)", default=1.5,
                            min=0.0, max=5.0, precision=1, step=5)
    chamfer_segs: IntProperty(name="Сегменты фаски", default=4, min=1, max=16)
    offset_y: FloatProperty(name="Смещение Y (мм)", default=0.0,
                             min=-50.0, max=50.0, precision=1, step=10)


# ---------------------------------------------------------------------------
# N-Panel
# ---------------------------------------------------------------------------
class KLD_PT_Panel(Panel):
    bl_label       = "Lug Debug"
    bl_idname      = "KLD_PT_Panel"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Keychain"

    def draw(self, context):
        layout = self.layout
        props  = context.scene.kld_props

        box = layout.box()
        box.label(text="Параметры", icon="SETTINGS")
        box.prop(props, "text")
        box.prop(props, "font_path")
        box.prop(props, "base_offset")
        box.prop(props, "base_height")
        box.separator()
        box.prop(props, "lug_x")
        box.prop(props, "lug_y")
        row = box.row(align=True)
        row.prop(props, "chamfer")
        row.prop(props, "chamfer_segs")
        box.prop(props, "offset_y")

        box = layout.box()
        box.label(text="Пошаговая отладка", icon="SEQUENCE")
        col = box.column(align=True)
        col.operator("kld.step1", icon="MESH_PLANE")
        col.operator("kld.step2", icon="LINKED")
        col.operator("kld.step3", icon="AUTOMERGE_ON")
        col.operator("kld.step4", icon="VIEWZOOM")
        col.operator("kld.step5", icon="MESH_GRID")
        layout.operator("kld.reset", icon="TRASH")


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------
classes = (
    KLD_Props,
    KLD_OT_Step1, KLD_OT_Step2, KLD_OT_Step3,
    KLD_OT_Step4, KLD_OT_Step5, KLD_OT_Reset,
    KLD_PT_Panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kld_props = bpy.props.PointerProperty(type=KLD_Props)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.kld_props

if __name__ == "__main__":
    register()
