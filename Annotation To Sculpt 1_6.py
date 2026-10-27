bl_info = {
    "name": "Annotation to Sculpt Stroke",
    "author": "Grok + Paweł HARNAŹ Trzciński",
    "version": (1, 6),
    "blender": (4, 0, 0),
    "location": "Sculpt Mode → Sidebar (N) → Tool",
    "description": "Draw Along Annotation + Resample + Fake Pressure / Taper",
    "category": "Sculpting",
}

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
import mathutils
import math

# ====================== PROPERTIES ======================
class AnnotationToSculptProps(bpy.types.PropertyGroup):
    spacing: bpy.props.IntProperty(
        name="Spacing",
        description="Co ile punktów brać po resamplu (1 = najgęściej)",
        default=1,
        min=1,
        max=30,
    )
    resample_points: bpy.props.IntProperty(
        name="Resample Points",
        description="Ile punktów docelowo (0 = bez resamplu)",
        default=0,
        min=0,
        max=1000,
        soft_max=300,
    )
    resample_enabled: bpy.props.BoolProperty(
        name="Enable Resample",
        default=False,
    )

    # --- Fake Pressure ---
    use_fake_pressure: bpy.props.BoolProperty(
        name="Use Fake Pressure",
        description="Generuj sztuczny nacisk (Annotations nie zapisują prawdziwego pressure)",
        default=True,
    )
    fake_mode: bpy.props.EnumProperty(
        name="Fake Mode",
        items=[
            ('MIDDLE', "Thickest in Middle", "Najgrubsze na środku, cieńsze na końcach"),
            ('ENDS', "Thickest at Ends", "Najgrubsze na końcach, cieńsze na środku"),
            ('LINEAR', "Linear Taper", "Od cienkiego do grubego (lub odwrotnie)"),
            ('CONSTANT', "Constant", "Stała grubość"),
        ],
        default='MIDDLE',
    )
    min_pressure: bpy.props.FloatProperty(
        name="Min Pressure",
        description="Najniższy nacisk (końce przy trybie Middle)",
        default=0.25,
        min=0.05,
        max=1.0,
        soft_min=0.1,
        soft_max=0.6,
    )
    max_pressure: bpy.props.FloatProperty(
        name="Max Pressure",
        description="Najwyższy nacisk (środek przy trybie Middle)",
        default=1.0,
        min=0.1,
        max=1.0,
    )
    pressure_power: bpy.props.FloatProperty(
        name="Curve Power",
        description="Kształt krzywej (1.0 = liniowa, >1 ostrzejszy szczyt, <1 bardziej płaski)",
        default=1.4,
        min=0.3,
        max=4.0,
        soft_min=0.6,
        soft_max=2.5,
    )

    use_pressure_size: bpy.props.BoolProperty(
        name="Affect Size",
        description="Fake pressure wpływa na rozmiar pędzla",
        default=True,
    )
    use_pressure_strength: bpy.props.BoolProperty(
        name="Affect Strength",
        description="Fake pressure wpływa na siłę pędzla",
        default=True,
    )

# ====================== RESAMPLE ======================
def resample_stroke(points, target_count):
    if len(points) < 2 or target_count < 2:
        return points

    lengths = [0.0]
    total_length = 0.0
    for i in range(1, len(points)):
        segment_len = (points[i].co - points[i-1].co).length
        total_length += segment_len
        lengths.append(total_length)

    if total_length < 0.0001:
        return points

    new_points = []
    step = total_length / (target_count - 1)

    for i in range(target_count):
        target_dist = i * step
        for j in range(1, len(lengths)):
            if lengths[j] >= target_dist:
                t = (target_dist - lengths[j-1]) / (lengths[j] - lengths[j-1])
                co = points[j-1].co.lerp(points[j].co, t)

                class SimplePoint:
                    pass
                new_pt = SimplePoint()
                new_pt.co = co
                new_points.append(new_pt)
                break

    return new_points

# ====================== FAKE PRESSURE ======================
def compute_fake_pressure(index, total, props):
    """Zwraca pressure 0..1 na podstawie pozycji w stroke'u"""
    if total <= 1:
        return props.max_pressure

    # t od 0 do 1 wzdłuż stroke'a
    t = index / (total - 1)

    mode = props.fake_mode
    min_p = props.min_pressure
    max_p = props.max_pressure
    power = props.pressure_power

    if mode == 'CONSTANT':
        return max_p

    elif mode == 'MIDDLE':
        # Najgrubsze na środku → używamy odwróconej paraboli / power
        # 0 na końcach, 1 na środku
        center = 1.0 - abs(2.0 * t - 1.0)          # 0 → 1 → 0
        center = center ** power
        return min_p + (max_p - min_p) * center

    elif mode == 'ENDS':
        # Najgrubsze na końcach
        edge = abs(2.0 * t - 1.0)                   # 1 → 0 → 1
        edge = edge ** power
        return min_p + (max_p - min_p) * edge

    elif mode == 'LINEAR':
        # Od min do max
        return min_p + (max_p - min_p) * (t ** power)

    return max_p

# ====================== OPERATOR ======================
class SCULPT_OT_annotation_to_stroke(bpy.types.Operator):
    bl_idname = "sculpt.annotation_to_stroke"
    bl_label = "Draw Along Annotation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.annotation_to_sculpt_props
        brush = context.tool_settings.sculpt.brush
        if not brush:
            self.report({'WARNING'}, "Nie znaleziono pędzla!")
            return {'CANCELLED'}

        gp = getattr(context.scene, 'annotation', None)
        if not gp or not gp.layers:
            self.report({'WARNING'}, "Nie znaleziono annotacji!")
            return {'CANCELLED'}

        # === VIEW_3D ===
        area = region = rv3d = window = screen = None
        for win in context.window_manager.windows:
            for a in win.screen.areas:
                if a.type == 'VIEW_3D':
                    for r in a.regions:
                        if r.type == 'WINDOW':
                            area = a
                            region = r
                            window = win
                            screen = win.screen
                            for s in a.spaces:
                                if s.type == 'VIEW_3D':
                                    rv3d = s.region_3d
                                    break
                            break
                if area:
                    break
            if area:
                break

        if not area or not region or not rv3d:
            self.report({'WARNING'}, "Nie znaleziono widoku 3D!")
            return {'CANCELLED'}

        # === BUDOWANIE STROKE ===
        stroke = []
        step = props.spacing
        base_size = float(brush.size)

        for layer in gp.layers:
            for frame in layer.frames:
                for gp_stroke in frame.strokes:
                    points = list(gp_stroke.points)

                    if props.resample_enabled and props.resample_points > 2:
                        points = resample_stroke(points, props.resample_points)

                    total = len(points)
                    if total == 0:
                        continue

                    for i in range(0, total, step):
                        point = points[i]

                        # --- Pressure ---
                        if props.use_fake_pressure:
                            pressure = compute_fake_pressure(i, total, props)
                        else:
                            pressure = 1.0

                        # Size
                        if props.use_pressure_size:
                            size = base_size * pressure
                        else:
                            size = base_size

                        # Strength pressure
                        stroke_pressure = pressure if props.use_pressure_strength else 1.0

                        mouse_pos = location_3d_to_region_2d(region, rv3d, point.co)
                        if mouse_pos is None:
                            mouse_pos = (region.width / 2, region.height / 2)

                        elem = {
                            "name": f"pt_{i}",
                            "mouse": mouse_pos,
                            "mouse_event": mouse_pos,
                            "location": point.co[:],
                            "pressure": stroke_pressure,
                            "size": size,
                            "time": i * 0.008,
                            "is_start": (i == 0),
                            "x_tilt": 0.0,
                            "y_tilt": 0.0,
                        }
                        stroke.append(elem)

        if not stroke:
            self.report({'WARNING'}, "Brak punktów")
            return {'CANCELLED'}

        # === OVERRIDE + WYKONANIE ===
        override = {
            'window': window,
            'screen': screen,
            'area': area,
            'region': region,
            'region_data': rv3d,
            'scene': context.scene,
            'view_layer': context.view_layer,
            'active_object': context.active_object,
            'object': context.object,
        }

        try:
            with context.temp_override(**override):
                if context.mode != 'SCULPT':
                    bpy.ops.object.mode_set(mode='SCULPT')
                bpy.ops.sculpt.brush_stroke(stroke=stroke, mode='NORMAL')

            self.report({'INFO'}, f"✅ Narysowano {len(stroke)} punktów")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Błąd: {str(e)}")
            return {'CANCELLED'}

# ====================== PANEL ======================
class VIEW3D_PT_annotation_to_sculpt(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    bl_label = "Annotation to Sculpt"

    @classmethod
    def poll(cls, context):
        return context.mode == 'SCULPT'

    def draw(self, context):
        layout = self.layout
        props = context.scene.annotation_to_sculpt_props

        # Resample
        box = layout.box()
        box.label(text="Resample", icon='IPO_EASE_IN_OUT')
        box.prop(props, "resample_enabled")
        if props.resample_enabled:
            box.prop(props, "resample_points")

        # Fake Pressure
        box = layout.box()
        box.label(text="Fake Pressure / Taper", icon='STYLUS_PRESSURE')
        box.prop(props, "use_fake_pressure")
        
        if props.use_fake_pressure:
            box.prop(props, "fake_mode")
            col = box.column(align=True)
            col.prop(props, "min_pressure")
            col.prop(props, "max_pressure")
            col.prop(props, "pressure_power")
            
            row = box.row(align=True)
            row.prop(props, "use_pressure_size", toggle=True)
            row.prop(props, "use_pressure_strength", toggle=True)

        layout.separator()
        layout.prop(props, "spacing")
        layout.operator("sculpt.annotation_to_stroke", icon='BRUSH_DATA', text="Draw Along Annotation")

# ====================== REGISTER ======================
def register():
    bpy.utils.register_class(AnnotationToSculptProps)
    bpy.utils.register_class(SCULPT_OT_annotation_to_stroke)
    bpy.utils.register_class(VIEW3D_PT_annotation_to_sculpt)
    bpy.types.Scene.annotation_to_sculpt_props = bpy.props.PointerProperty(type=AnnotationToSculptProps)

def unregister():
    bpy.utils.unregister_class(AnnotationToSculptProps)
    bpy.utils.unregister_class(SCULPT_OT_annotation_to_stroke)
    bpy.utils.unregister_class(VIEW3D_PT_annotation_to_sculpt)
    del bpy.types.Scene.annotation_to_sculpt_props

if __name__ == "__main__":
    register()