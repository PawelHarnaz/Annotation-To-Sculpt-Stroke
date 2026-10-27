# Annotation to Sculpt Stroke

Blender addon that converts **Annotation** strokes into real **Sculpt** brush strokes.

Useful when you want to quickly sketch a path with the Annotation tool (or tablet) and then turn it into an actual sculpt stroke with controllable size and strength.

---

### Features

- Convert Annotation strokes → Sculpt brush strokes
- **Resample** strokes to even spacing (arc-length based)
- **Fake Pressure / Taper** system (because Annotations in Blender 5.x do not expose per-point pressure)
  - Thickest in the Middle
  - Thickest at Ends
  - Linear Taper
  - Constant
- Control over Min/Max pressure and curve shape
- Affect brush **Size** and/or **Strength**
- Spacing control
- Works in Blender 4.0+ and 5.x (tested on 5.2)

---

### Installation

1. Download the `.py` file
2. In Blender go to **Edit → Preferences → Add-ons → Install...**
3. Select the file and enable the addon
4. In **Sculpt Mode** open the Sidebar (`N`) → **Tool** tab

---

### How to use

1. Switch to **Sculpt Mode**
2. Draw one or more strokes with the **Annotation** tool
3. Adjust settings in the **Annotation to Sculpt** panel:
   - Enable **Fake Pressure** and choose the mode (recommended: *Thickest in Middle*)
   - Set Min / Max Pressure and Curve Power
   - Optionally enable Resample
4. Click **Draw Along Annotation**

---

### Fake Pressure Modes

| Mode                  | Description                              |
|-----------------------|------------------------------------------|
| Thickest in Middle    | Thickest in the center, thinner at ends  |
| Thickest at Ends      | Opposite of above                        |
| Linear Taper          | From thin to thick (or reverse)          |
| Constant              | Uniform pressure                         |

**Curve Power** controls the shape:
- `1.0` = linear
- `> 1.0` = sharper peak
- `< 1.0` = flatter / more rounded

---

### Notes

- Blender’s Annotation system (5.x) does **not** store per-point pressure in a way accessible via Python. That’s why the Fake Pressure system was added.
- For real tablet pressure support, use a full **Grease Pencil** object instead of Annotations.
- The addon uses `bpy.ops.sculpt.brush_stroke` under the hood.

---

### Author

Grok + Paweł HARNAŹ Trzciński

---

### License

MIT
