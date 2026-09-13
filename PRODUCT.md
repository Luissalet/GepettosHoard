# Sculptor’s Hoard
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
Delegated by Luis: a separate project in any language. TypeScript/React and Three.js for the local editor; Python/FastAPI/scikit-learn for reproducible image processing; local Ollama vision inference for semantic proposals. Local Windows operation.

## Users
Luis prepares Animal Crossing and Pokémon Masters textures in GIMP for displacement in Blender Figure Tools. Recruiters are a secondary audience for the working project and measured results.

## Product Purpose
Reduce manual recoloring, preserve intentional detail and provide a visually compelling AI engineering portfolio project.

## Operating Context
Original and manually recolored textures exist locally. Colors currently encode user-chosen relative heights, not consistent labels across figures. Luis accepts a fixed palette. Figure Tools remains the final displacement/filter application.

## Capabilities and Constraints
Import model and textures, propose reproducible color-connected regions, infer semantic labels and local layer relations from multi-view renders, UV atlases and sampled 3D positions, edit normalized heights, compare original/color/grayscale, export batches at native resolution, and adapt maps into Figure Tools. Approved corrections become local contextual examples, not model training. Never overwrite source assets. No private models/textures published. Semantic results require review; relief preview is approximate and physical scale is set in Blender.

## Evidence on Hand
Heightmapper and AutoProcessor AC inspected. Real Zucker assets tested at up to 8192²: four texture pairs exported in 20.04 seconds; actual Blender 5 + Figure Tools integration produced a diagnostic STL and verified neutral-map drift below 1e-6. Local 27B vision proposals tested, including observed semantic mistakes. See docs/VALIDATION.md; no task-specific model has been trained.

## Product Principles
The figure and its textures lead. Corrections must be quick. Export is deterministic. Clearly distinguish classical proposals, learned predictions and actual evaluation. User delegated implementation and design choices; proceed directly with code.
