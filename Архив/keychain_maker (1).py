bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (2, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Keychain",
    "description": "Генерирует брелок: подложка плавно огибает буквы + отверстие для кольца",
    "category": "Add Mesh",
}

import bpy
import bmesh
import math
import os
from mathutils import Vector
from bpy.props import (
    StringProperty,
    FloatProperty,
    BoolProperty,
)
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


# ---------------------------------------------------------------------------
# Оператор генерации брелока
# ---------------------------------------------------------------------------

class KEYCHAIN_OT_Generate(Operator):
    bl_idname  = "keychain.generate"
    bl_label   = "Создать брелок"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.keychain_props

        text        = props.text
        font_path   = props.font_path
        offset      = props.base_offset       # мм
        base_h      = props.base_height       # мм
        letter_h    = props.letter_height     # мм
        hole_d      = props.hole_radius       # мм (поле называется hole_radius, но хранит диаметр)
        hole_r      = hole_d / 2.0
        do_export   = props.auto_export
        export_path = props.export_path

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

        # ── 2. Конвертируем текст в меш ────────────────────────────────────
        set_active(context, txt_obj)
        bpy.ops.object.convert(target="MESH")
        letters_obj = context.active_object
        letters_obj.name = "_KM_Letters"

        # Limited Dissolve + Merge by Distance
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
        bpy.ops.mesh.remove_doubles(threshold=0.2)
        bpy.ops.object.editmode_toggle()

        # ── 3. Читаем вершины букв ─────────────────────────────────────────
        depsgraph = context.evaluated_depsgraph_get()
        ev = letters_obj.evaluated_get(depsgraph)
        em = ev.to_mesh()
        verts_2d = [(v.co.x, v.co.y) for v in em.vertices]
        ev.to_mesh_clear()

        if len(verts_2d) < 3:
            self.report({"ERROR"}, "Не удалось получить вершины текста.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        min_x = min(p[0] for p in verts_2d)
        max_x = max(p[0] for p in verts_2d)
        min_y = min(p[1] for p in verts_2d)
        max_y = max(p[1] for p in verts_2d)

        # ── 4. Метабол-подложка (плавный контур вокруг букв) ───────────────
        #
        # Принцип: на каждую вершину буквы ставим мета-шар радиуса = offset.
        # После конвертации получаем меш, который плавно «обтекает» все буквы.
        # Прореживаем вершины, чтобы не создавать тысячи элементов.

        mb_data = bpy.data.metaballs.new("_KM_MB")
        # resolution: чем меньше — тем точнее, но медленнее
        mb_data.resolution        = max(0.2, offset * 0.08)
        mb_data.render_resolution = mb_data.resolution
        mb_data.threshold         = 0.6

        mb_obj = bpy.data.objects.new("_KM_MetaObj", mb_data)
        context.collection.objects.link(mb_obj)

        elem_radius = offset * 1.15   # немного больше offset для перекрытия

        # Прореживаем: берём не более ~400 точек
        step = max(1, len(verts_2d) // 400)
        for vx, vy in verts_2d[::step]:
            el = mb_data.elements.new(type="BALL")
            el.co        = Vector((vx, vy, 0.0))
            el.radius    = elem_radius
            el.stiffness = 1.0

        # ── 5. Конвертируем метабол в меш ─────────────────────────────────
        set_active(context, mb_obj)
        # Сначала обновляем depsgraph, чтобы метабол «запёкся»
        context.view_layer.update()
        bpy.ops.object.convert(target="MESH")
        base_raw = context.active_object
        base_raw.name = "_KM_BaseRaw"

        # ── 6. Сплющиваем по Z в плоский контур ───────────────────────────
        set_active(context, base_raw)
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.object.editmode_toggle()

        base_raw.scale.z = 0.0
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        # Удаляем дубли вершин после сплющивания
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.05)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.editmode_toggle()

        # ── 7. Экструдируем плоский диск вверх на base_h ──────────────────
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, base_h)}
        )
        bpy.ops.object.editmode_toggle()

        # Опускаем объект так, чтобы верхняя грань была на Z = 0
        base_raw.location.z = -base_h
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        base_obj = base_raw

        # ── 8. Вырезаем отверстие для кольца ──────────────────────────────
        hole_margin = 2.0
        hole_cx = min_x - offset - hole_r - hole_margin
        hole_cy = (min_y + max_y) / 2.0

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=48,
            radius=hole_r,
            depth=base_h + 0.4,
            location=(hole_cx, hole_cy, -base_h / 2.0),
        )
        hole_cyl = context.active_object
        hole_cyl.name = "_KM_HoleCyl"

        set_active(context, base_obj)
        mod = base_obj.modifiers.new("CutHole", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object    = hole_cyl
        mod.solver    = "EXACT"
        bpy.ops.object.modifier_apply(modifier="CutHole")
        delete_obj(hole_cyl)

        # ── 9. Буквы: поднимаем на base_h, экструдируем вверх ─────────────
        letters_obj.location.z = 0.0   # верхняя грань подложки на Z=0

        set_active(context, letters_obj)
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, letter_h)}
        )
        bpy.ops.object.editmode_toggle()

        # ── 10. Объединяем подложку и буквы ───────────────────────────────
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

        # ── 11. Авто-экспорт STL ──────────────────────────────────────────
        if do_export:
            path = export_path
            if not path:
                path = os.path.join(
                    os.path.expanduser("~"), final_obj.name + ".stl"
                )
            if not path.lower().endswith(".stl"):
                path += ".stl"

            deselect_all()
            final_obj.select_set(True)
            bpy.ops.wm.stl_export(
                filepath=path,
                export_selected_objects=True,
            )
            self.report({"INFO"}, f"STL сохранён: {path}")

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
    hole_radius: FloatProperty(
        name="Диаметр отверстия (мм)",
        description="Диаметр отверстия для кольца",
        default=6.0, min=1.0, max=20.0,
        unit="LENGTH",
    )
    auto_export: BoolProperty(
        name="Авто-экспорт в STL",
        description="Сохранить STL сразу после генерации",
        default=False,
    )
    export_path: StringProperty(
        name="Путь сохранения",
        description="Путь к файлу STL (если пусто — домашняя папка)",
        subtype="FILE_PATH",
        default="",
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
        box.prop(props, "hole_radius")

        box = layout.box()
        box.label(text="Экспорт", icon="EXPORT")
        box.prop(props, "auto_export")
        if props.auto_export:
            box.prop(props, "export_path")

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
