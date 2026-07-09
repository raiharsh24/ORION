# ATLAS: Futuristic Interactive Knowledge Graph Engine

ATLAS is the central next-generation Knowledge Graph Engine for the **FRIDAY AI Operating System**. It acts as a unified visual portal to explore and navigate everything FRIDAY knows—from user conversation memories and workflow pipelines, to agent collaboration maps and codebase files.

---

## Technical Architecture

The engine is built on a clean decoupled architecture:

1.  **Providers (`providers/`)**: Employs a unified `GraphProvider` interface enabling specific graphs to load datasets dynamically (Mock, Vector DB, SQLite, or Git repo).
2.  **Engine Orchestrator (`engine/`)**: Centralizes fuzzy search filters, viewports bounds culling evaluation, and layout dispatchers.
3.  **Layouts (`layouts/`)**: Encapsulates math layout calculations behind the `GraphLayout` interface, yielding Force, Circle, Rings, Hex, Chronological Timeline, and Layered System Architecture geometries.
4.  **Visual Components (`components/`)**: Includes the custom canvas draw orchestrator (`GraphCanvas`), sliders controllers, minimaps locator, and collapsible inspectors.

---

## Performance Optimizations (10,000+ Nodes at 60 FPS)

ATLAS incorporates two major graphics rendering strategies to deliver desktop-grade performance:

1.  **Level of Detail (LOD) Scaling**:
    *   *High Zoom*: Draws complete glowing outlines, active flow particle animations, and labels.
    *   *Medium Zoom*: Disables particle flows, renders labels only for key application and agent nodes.
    *   *Low Zoom*: Restricts nodes to simple color-coded dots, hides labels entirely, and skips drawing minor leaves (memory fragments/imports) to conserve rendering frames.
2.  **Frustum Viewport Culling**:
    *   Skips computing and drawing nodes whose coordinates lie outside the canvas coordinate boundaries.

---

## User Control & Shortcuts

*   **Keyboard Shortcut `/`**: Instantly focuses the fuzzy search bar. Use Arrow keys to navigate results, and `Enter` to select and center the camera on the target node.
*   **Mouse Drag**: Drag nodes to pin/re-heat simulation.
*   **Concentric Rings Layout**: Center manifests (`FRIDAY.md`) -> clustered Skills petals -> Memory glowing particles -> routines orbits -> outer applications.
