# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Blender add-on (plugin) written in Python for generating customized, 3D-printable keychains with personalized text. It targets **Blender 4.0+** and is entirely self-contained — no external dependencies beyond Blender's built-in Python API.

## Installation & Running

There is no build system or test runner. The addon is a single `.py` file installed directly in Blender:

1. **Edit → Preferences → Add-ons → Install** → select `Keychain_Builder_for_Blender.py`
2. Enable the addon
3. Access via **N-panel → Keychain 1.1** tab in the 3D Viewport

## File Layout

| File | Purpose |
|------|---------|
| `Keychain_Builder_for_Blender.py` | **Stable release** (v1.1.0, 785 lines) — the distributable addon |
| `keychain_maker.py` | **Development version** (v1.1.1, 797 lines) — active work goes here |
| `keychain_maker (44).py` | Experimental variant (853 lines) |
| `Архив/` | 45 historical versions (do not modify) |

When making changes, edit `keychain_maker.py`. When ready to release, sync changes into `Keychain_Builder_for_Blender.py`.

## Code Architecture

The addon is structured as a single file with these sections:

### Blender API Imports
```python
import bpy, bmesh, math, os
from mathutils import Vector
from bpy.props import *
from bpy.types import Panel, Operator, PropertyGroup
```

### Section Layout (by line range in the stable file)

| Lines | Section | Description |
|-------|---------|-------------|
| 20–80 | Translations | Bilingual EN/RU strings via Blender's translation system |
| 85–120 | Utilities | `delete_obj()`, `deselect_all()`, `set_active()`, `flip_faces_up()`, `points_along_edges()` |
| 124–194 | Base Generation | `build_flat_base()` — metaball-based smooth base algorithm |
| 198–214 | Letter Mesh | `prepare_letters_mesh()` — text outline → geometry |
| 217–342 | Ear Welding | `weld_ear_pdf_method()` — seamless ear-to-base join via automerge |
| 349–419 | Ear Creation | `create_ear_2d()`, `create_ear_2d_right()` — keyring lug geometry |
| 425–449 | Hole Cutting | `cut_ear_hole()` — boolean cylinder subtraction |
| 456–611 | Main Operator | `KEYCHAIN_OT_Generate` — orchestrates all 9 generation steps |
| 618–688 | Properties | `KeychainProperties` — all 17 user-configurable parameters |
| 694–717 | Reset Operator | `KEYCHAIN_OT_Reset` |
| 724–763 | UI Panel | `KEYCHAIN_PT_Panel` — N-panel layout with collapsible boxes |
| 770–783 | Registration | `register()` / `unregister()` |

### Generation Pipeline (9 steps inside `KEYCHAIN_OT_Generate.execute()`)

1. Convert text to mesh (supports custom TTF/OTF fonts via `bpy.ops.object.convert`)
2. Sample points along letter edges with `points_along_edges()`
3. Build smooth base using metaballs → convert → mesh cleanup
4. (Conditional) Create and weld ear geometry
5. Extrude base downward
6. Apply solidify modifier to letters
7. Join base + letters into one object
8. (Conditional) Cut keyring hole via boolean operation
9. Apply auto-smooth shading

### Object Naming Convention

Temporary/intermediate objects use the `_KM_*` prefix and are cleaned up during generation. Final output object has a user-specified name.

## Key Patterns

- **Context management**: Always call `deselect_all()` and `set_active(obj)` before mesh operations; modes are switched explicitly with `bpy.ops.object.mode_set()`.
- **bmesh workflow**: Enter edit mode → get bmesh → modify → free bmesh → exit edit mode. Never leave edit mode open.
- **Error reporting**: Use `self.report({'ERROR'}, ...)` and `return {'CANCELLED'}` for failures inside operators.
- **Translation**: All UI strings go through `bpy.app.translations.pgettext()` or the translation dict at the top of the file. Add both EN and RU entries when adding new UI text.
- **Properties**: All parameters live in `KeychainProperties` (a `PropertyGroup`). Access via `context.scene.keychain_props`. Reset defaults are hardcoded in `KEYCHAIN_OT_Reset`.

## Bilingual UI

The addon supports English and Russian (`ru_RU`). The translation dictionary (lines 24–77 of stable file) maps English keys to Russian strings. When adding new UI labels, tooltips, or error messages, add entries to this dictionary.
