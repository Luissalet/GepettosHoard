---
name: SculptHoard
description: A local graphite-and-chalk material workbench for inspecting textures and editing relative heights.
colors:
  action: "#c8512e"
  action-hover: "#af4324"
  focus: "#d76c46"
  background: "#f5f5f1"
  surface: "#fbfbf8"
  library: "#f1f2ec"
  text: "#303733"
  muted: "#65705e"
  line: "#dedfd8"
  canvas: "#272c2b"
  canvas-controls: "#2e3530"
  canvas-active: "#444c46"
  canvas-text: "#f0f3e9"
  secondary: "#fbfcf8"
  secondary-text: "#363e34"
  secondary-hover: "#edf0e7"
  region-selected: "#edf1e4"
  approved: "#e1ead4"
  approved-text: "#48622f"
  region-lavender: "#a799e1"
  region-mint: "#add4a3"
  region-rose: "#eaa9b7"
  region-ochre: "#e6c374"
  region-cyan: "#82bfcd"
  region-peach: "#e49a70"
  region-stone: "#bcb5a6"
  region-periwinkle: "#8da4d7"
typography:
  headline:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "22px"
    fontWeight: 650
    letterSpacing: "-0.03em"
  title:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "13px"
    fontWeight: 750
  body:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "13px"
    fontWeight: 450
    lineHeight: 1.65
  label:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "11px"
    fontWeight: 700
  small:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "11px"
    lineHeight: 1.75
  micro:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "10px"
    lineHeight: 1.6
rounded:
  thumbnail: "3px"
  field: "5px"
  region: "6px"
  control: "7px"
  toast: "8px"
  canvas: "10px"
spacing:
  tight: "4px"
  compact: "8px"
  control-x: "14px"
  panel: "20px"
  section-y: "22px"
  header-x: "24px"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "#fff"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
  button-primary-hover:
    backgroundColor: "{colors.action-hover}"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.secondary-text}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  button-approved:
    backgroundColor: "{colors.approved}"
    textColor: "{colors.approved-text}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
  field:
    backgroundColor: "#fff"
    textColor: "#394137"
    rounded: "{rounded.field}"
    padding: "8px"
  canvas-tab-active:
    backgroundColor: "{colors.canvas-active}"
    textColor: "{colors.canvas-text}"
    rounded: "{rounded.field}"
    padding: "8px 10px"
  region-row-selected:
    backgroundColor: "{colors.region-selected}"
    textColor: "#3f4b35"
    rounded: "{rounded.region}"
    padding: "8px"
  canvas:
    backgroundColor: "{colors.canvas}"
    rounded: "{rounded.canvas}"
---

# Design System: SculptHoard

## Overview

**Creative North Star: "The Digital Material Workbench"**

The figure and its textures occupy a graphite working area, surrounded by chalk panels with a slight olive cast. Compact Manrope typography, precise dividers and restrained orange actions make this an editor for close inspection and quick correction. The visual direction comes from the delegated, code-led build recorded in `docs/surface.md`.

Pastel numbers identify regions across the texture and inspector. Selection changes the viewed material and brings its height controls into view, connecting the visual result to a concrete adjustment. The system keeps processing, proposals and reviewed states visibly distinct without implying measured AI accuracy.

**Key Characteristics:**

- Graphite working canvas framed by chalk tool panels.
- Compact Manrope typography and tabular numeric metadata.
- Orange actions, quiet olive neutrals and numbered pastel region identities.
- Connected selection across preview, region list and height editor.
- Flat panel structure with restrained shadow around the working surface.

## Colors

Orange marks actions; warm, slightly olive neutrals carry the editor chrome. Pastels encode region identity rather than decorative emphasis. The frontmatter owns reusable color values.

### Primary

- **Kiln Orange** (`action`): processing actions, slider accent and caret.
- **Deep Kiln Orange** (`action-hover`): primary button hover.
- **Warm Focus** (`focus`): keyboard focus outline.

### Secondary

- **Region Lavender, Mint, Rose, Ochre, Cyan, Peach, Stone and Periwinkle**: the eight ordered region-ID colors in `src/types.ts`. Their sequence repeats by region ID; printed numbers remain necessary because color is not unique beyond eight regions.
- **Reviewed Sage** (`approved`, `approved-text`): saved-review button state, paired with a check icon and explicit text.

### Neutral

- **Chalk Background, Chalk Surface and Library Chalk**: progressively differentiated application, panel and library surfaces.
- **Graphite Canvas and Graphite Controls**: the preview and its lower control bar.
- **Ink, Muted Olive and Fine Line**: primary text, secondary explanations and structural dividers.
- **Selected Sage**: region-row selection, accompanied by a border and preview highlighting.

**The Identity and Height Rule.** Region colors identify numbered regions. “Colores de relieve” uses a separate fixed 256-entry height palette generated in `backend/processing.py`; its RGB values are labels for heights, not luminance measurements. Grayscale height values range from 0 to 255 with an initial neutral value of 128. Preserve this distinction in new legends and controls.

The fixed height palette steps HSV hue from 0 to 0.72 at saturation 0.36 and value 0.9, with collision handling to keep RGB labels unique. It is generated data, not an eight-color UI scale.

## Typography

**Display and body font:** Manrope Variable, with sans-serif fallback. No separate display or monospace family is implemented.

**Character:** compact, clear and lightly technical. Medium-weight prose and small metadata allow the texture and model to retain visual priority.

### Hierarchy

- **Headline:** asset title; slightly tightened tracking. It reduces to 19px below 950px and becomes 20px in the phone layout.
- **Title:** inspector section headings; stronger weight separates groups without oversized headings.
- **Body:** root type role; paragraph line-height is generous within compact panels.
- **Label:** primary buttons and strong control labels. Most controls use 10–11px.
- **Small and micro:** help text, interpretation reasons and metadata. Additional 8–9px annotations are used for viewport captions, status and small numeric labels.
- **Brand:** “relief” uses 800 weight and “studio” 450 at 21px, with tight tracking; 18px on phones.
- **Numbers:** dimensions, heights, timing and strength use tabular numerals.

**The Quiet Hierarchy Rule.** Establish hierarchy through weight, spacing and panel grouping before increasing text size.

## Layout

The desktop app fills the dynamic viewport, with a 630px minimum height. A 68px top bar and 31px footer frame a three-column workspace: 224px library, flexible central workspace with a 340px minimum, and 305px inspector. The center has 26px top and 25px side padding; its preview expands into available height. The library and inspector content scroll independently. The inspector footer remains outside its scrolling content.

The central composition is an asset heading, preview toolbar and stage, lower view controls, then a four-step workflow strip. The implemented lower strip is workflow status, not a thumbnail filmstrip. Textures appear in the left library.

- At 1600px and wider: library and inspector expand to 246px and 335px; central minimum becomes 500px, with 30px top and 34px side padding. The header becomes 74px.
- At 1150px and below: columns compact to 190px / flexible minimum 280px / 270px; the local connection label hides.
- At 950px and below: the library hides behind a header toggle and opens as a fixed 250px drawer. The remaining workspace uses a flexible minimum 300px center and 280px inspector.
- At 680px and below: the page flows vertically, with a sticky 62px header, 470px preview, workflow strip and full-width inspector. The breadcrumb and export text hide while icons remain. Region rows form two columns inside a bounded list; inspector content joins page scrolling. The footer's secondary metadata hides.

Preserve the large preview and an immediately reachable correction panel when adapting this editor to another screen.

## Elevation & Depth

Depth comes mainly from contrasting surface tones, fine borders and the rendered model. Shadows are restrained and structural; panels are not floating cards. The UV surface uses a dark checkerboard. The 3D stage uses a subtle perspective grid and neutral material lighting.

### Shadow Vocabulary

- **Canvas ambient:** `0 8px 24px #28352610`, separating the preview from chalk.
- **UV texture:** `0 3px 18px #0003`, distinguishing the texture plane from its checkerboard.
- **Library drawer:** `8px 0 25px #1e2e2020`, used only when the library overlays the workspace.
- **Status toast:** `0 6px 30px #22321e25`, lifting temporary confirmation above the page.

## Shapes

Controls have gently curved corners, with smaller fields and swatches nested inside larger preview corners. Structural panels remain rectangular and are separated by one-pixel dividers. Import uses a dashed border; selected rows use solid borders. Status dots and workflow numbers are circular. Texture thumbnails retain their aspect with contained imagery.

## Components

### Buttons

Compact, direct and icon-supported. Primary actions use orange with white text; secondary actions use a pale fill, dark text and a fine border. Standard buttons have a 36px minimum height. The empty-stage import action deliberately uses a warm chalk fill on graphite. Icon buttons are 30px squares; outlined recalculation is 35px wide by 37px high.

Hover changes background and text with a 160ms transition. Keyboard focus uses a 2px warm outline offset by 3px. Disabled buttons have 0.45 opacity and a not-allowed cursor. The saved-review variant combines sage fill, check icon and changed copy.

### Inputs / Fields

White inputs and selects use fine borders, small corners and 8px padding. Inspector fields are generally 33px high and use 10px text. Sliders use orange and a visible numeric value. The selected-region height control spans 0–255 and includes “Hundido”, “Neutro 128” and “Elevado”. Name edits persist on blur; height changes persist after pointer release or supported adjustment keys.

### Navigation

Graphite preview tabs switch between Modelo 3D, Textura UV and Relieve; the active tab gains a lighter graphite fill and pale text. Inspector tabs use an orange underline, stronger active text and an optional count badge. Asset rows show a contained thumbnail, filename, dimensions and preparation/review indicator. The selected asset gets a white surface and solid border.

### Region List and Editor

Each row pairs a numbered pastel swatch with the name, interpretation status and numeric height. Selected rows gain sage fill and a border. Selecting a region in the list, UV image or 3D model brings “Editar superficie” into view immediately.

In 3D, selected texture pixels receive a warm highlight and other pixels darken; other mapped materials also dim. In UV, selected pixels receive a translucent white overlay and other labeled pixels a dark overlay. Preserve the region number and row state alongside color. Selection identifies the segmentation mask; it does not certify the interpretation attached to it.

### Material Preview

One framed stage contains the scene and compact controls. Original texture, numbered regions, relief colors and grayscale heights are explicit view modes. The UV stage offers a triangulation overlay and crosshair selection. The relief mode shows an approximate displaced plate with a separate visual-strength control. Keep the approximation caption visible; the plate is not a calibrated physical result.

### Status and Proposal States

Busy work appears in the footer, while vision jobs also show an inspector progress block. Spinners rotate over 1.4 seconds; reduced-motion preference removes animations and transitions. Proposal badges distinguish Propuesta, Aplicada and Desactualizada; stale relations and their apply button are disabled. Error banners use a warm pale surface, alert icon and dismiss action. Toasts show check-mark confirmation for five seconds. Warning and confidence copy retain their qualifications.

## Do's and Don'ts

### Do:

- **Do** keep the figure and textures visually dominant inside the graphite canvas.
- **Do** pair pastel region colors with visible numbers and selection state.
- **Do** keep selected-region height controls immediately reachable.
- **Do** use the existing Manrope hierarchy and tabular numeric metadata.
- **Do** retain explicit proposal, stale, processing and reviewed states.
- **Do** preserve keyboard focus outlines and reduced-motion behavior.

### Don't:

- **Don't** interpret region-ID colors as height or derive height from the fixed palette's luminance.
- **Don't** describe a selected or highlighted region as proof of AI accuracy.
- **Don't** replace the compact tool layout with decorative cards or promotional hero styling.
- **Don't** remove the approximate-preview caption or confidence qualification.
- **Don't** use color alone to identify a region or reviewed state.
