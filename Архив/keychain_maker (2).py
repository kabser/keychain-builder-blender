bl_info = {
    "name": "Keychain Maker",
    "author": "Custom",
    "version": (3, 0, 0),
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
    Возвращает список (x, y) точек, равномерно расставленных
    вдоль каждого ребра меша (в мировых координатах).
    step — максимальное расстояние между точками.
    """
    pts = []
    m = mesh_obj.data
    mw = mesh_obj.matrix_world

    for edge in m.edges:
        v0 = mw @ m.vertices[edge.vertices[0]].co
        v1 = mw @ m.vertices[edge.vertices[1]].co
        length = (v1 - v0).length
        # сколько отрезков разбиваем
        n = max(1, math.ceil(length / step))
        for i in range(n + 1):
            t = i / n
            p = v0.lerp(v1, t)
            pts.append((p.x, p.y))

    return pts


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
        offset    = props.base_offset    # мм — отступ подложки
        base_h    = props.base_height    # мм — толщина подложки
        letter_h  = props.letter_height  # мм — высота букв над подложкой

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

        # Dissolve + Merge — убираем лишние точки
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(5))
        bpy.ops.mesh.remove_doubles(threshold=0.2)
        bpy.ops.object.editmode_toggle()

        # ── 3. Точки вдоль рёбер ───────────────────────────────────────────
        # Шаг расстановки точек = offset * 0.7
        # Это гарантирует, что соседние метаболы перекрываются
        # и не оставляют дырок даже на длинных прямых рёбрах
        sample_step = offset * 0.7

        pts = points_along_edges(letters_obj, sample_step)

        if len(pts) < 2:
            self.report({"ERROR"}, "Не удалось получить рёбра текста.")
            delete_obj(letters_obj)
            return {"CANCELLED"}

        # ── 4. Метаболы ────────────────────────────────────────────────────
        mb_data = bpy.data.metaballs.new("_KM_MB")
        # resolution адаптируется под размер шара
        mb_data.resolution        = max(0.15, offset * 0.06)
        mb_data.render_resolution = mb_data.resolution
        mb_data.threshold         = 0.6

        mb_obj = bpy.data.objects.new("_KM_MetaObj", mb_data)
        context.collection.objects.link(mb_obj)

        # Радиус шара: offset + небольшой запас для перекрытия
        elem_radius = offset * 1.1

        # Дедупликация точек с сеткой (избегаем дублей на расстоянии < step/2)
        grid_size = sample_step * 0.5
        seen = set()
        for vx, vy in pts:
            key = (round(vx / grid_size), round(vy / grid_size))
            if key in seen:
                continue
            seen.add(key)
            el = mb_data.elements.new(type="BALL")
            el.co        = Vector((vx, vy, 0.0))
            el.radius    = elem_radius
            el.stiffness = 1.0

        # ── 5. Конвертируем метабол → меш ──────────────────────────────────
        set_active(context, mb_obj)
        context.view_layer.update()
        bpy.ops.object.convert(target="MESH")
        base_raw = context.active_object
        base_raw.name = "_KM_BaseRaw"

        # ── 6. Сплющиваем → плоский контур ────────────────────────────────
        set_active(context, base_raw)

        base_raw.scale.z = 0.0
        bpy.ops.object.transform_apply(scale=True)

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.05)
        # Удаляем «внутренние» грани, которые могут остаться после сплющивания.
        # dissolve_degenerate убирает грани нулевой площади
        bpy.ops.mesh.dissolve_degenerate(threshold=0.01)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.editmode_toggle()

        # ── 7. Экструдируем на толщину подложки ────────────────────────────
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, base_h)}
        )
        bpy.ops.object.editmode_toggle()

        # Опускаем: верхняя грань на Z = 0
        base_raw.location.z = -base_h
        bpy.ops.object.transform_apply(location=True)
        base_obj = base_raw

        # ── 8. Буквы: экструдируем вверх ───────────────────────────────────
        # letters_obj уже лежит на Z=0 (совпадает с верхом подложки)
        set_active(context, letters_obj)
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, letter_h)}
        )
        bpy.ops.object.editmode_toggle()

        # ── 9. Объединяем подложку и буквы ─────────────────────────────────
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
