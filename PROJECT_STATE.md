# AlgoLens — Project State & Architecture

This document serves as the single source of truth for the current state, architecture, and behavior of the AlgoLens project.

## 1. High-Level Architecture

The AlgoLens is an educational tool designed to dynamically visualize algorithmic execution. It uses a **Semantic-First Visualization Engine**: visualizations emerge directly from runtime behavior and memory addresses, not just variable names.

The application is split into two main halves:
*   **Backend (`tracer.py`)**: A Python tracing engine that hooks into execution, intercepts memory state, and emits execution frames.
*   **Frontend (Next.js / React)**: A semantic analyzer and rendering engine that classifies data structures and animates them using Framer Motion.

---

## 2. Core Systems

### A. The Backend Tracer (`tracer.py`)
*   **Execution Hooking**: Uses `sys.settrace` to record local variables, line numbers, and object references (`obj_id`) at every step.
*   **Polyfills**: Built-in Python modules with fast C-implementations (like `heapq`) are polyfilled with pure-Python equivalents. 
    *   *Recent Upgrade*: The `heapq` polyfill was modified to perform logical element **swaps** instead of temporary hole-filling copies. This ensures the visualizer correctly animates values shifting without duplicating nodes.
*   **JSON Serialization**: Emits a compressed, diff-based JSON array of frames to the frontend.

### B. The Semantic Analyzer (`semanticAnalyzer.ts`)
*   **Behavioral Scoring**: Instead of relying on variable names, arrays and structures are scored based on how they are accessed and mutated.
*   **Roles**: Containers accumulate points for roles like `STACK`, `QUEUE`, `DEQUE`, and `HEAP`. 
*   **Hysteresis & Locking**: Once a container is proven to be a `HEAP` (e.g., scoring reaches the `Infinity` margin lock), it permanently retains that visual identity.
*   **Memory Aliasing (`obj_id`)**: The analyzer binds semantic roles to the native CPython memory ID (`obj_id`), ensuring that if a list is passed into a function under a different parameter name (e.g., `h` -> `heap`), it retains its semantic role.

### C. The Rendering Pipeline (`VisualizationCanvas.tsx`)
*   **Component Routing**: Maps the primary semantic role to the appropriate React component (`HeapVisualizer`, `StackVisualizer`, `ArrayVisualizer`, etc.).
*   **Stable Mounts**: Component React `key`s are bound exclusively to the `obj_id` (e.g., `key={'heap-' + vis.details.obj_id}`). This prevents catastrophic unmounting/remounting when variable names change across function boundaries.

---

## 3. The Graph Rendering Engine

The project utilizes a unified, agnostic rendering engine for all tree-like topologies: **`GraphTreeRenderer.tsx`**. 

### `TreeVisualizer.tsx` vs `HeapVisualizer.tsx`
Rather than both components implementing their own complex math and DOM logic, they now act as **thin topology adapters**. 
*   `TreeVisualizer` parses node/left/right structures and passes them to `GraphTreeRenderer`.
*   `HeapVisualizer` maps 1D array math (`2*i + 1`, `2*i + 2`) into physical node coordinates via an Inorder layout algorithm and passes them to `GraphTreeRenderer`.

### Framer Motion & Layout Stability
Animations are strictly controlled to prevent layout distortion:
1.  **Absolute Math**: Node coordinates are calculated using absolute math (e.g., `HORIZONTAL_SPACING = 60`) rather than CSS flexbox or percentages.
2.  **No Projection Engine**: The Framer Motion `layoutId` attribute is **disabled** for graph nodes. This prevents the projection engine from erroneously scaling or flashing nodes when the SVG container expands.
3.  **Stationary Isolation**: `GraphTreeRenderer` computes a `hasMoved` state during render. Nodes whose `x` and `y` coordinates do not physically change receive a transition duration of `0`. This guarantees that stationary nodes do not pulse or bounce when unrelated properties (like pointer shadows) change during a swap.

---

## 3.5. Dynamic Programming (DP) Visualization System

The project incorporates a dynamic detection, execution tracing, and rendering pipeline specifically designed for Dynamic Programming (DP) algorithms (both Tabulation and Memoization).

### A. Detection & Classification Layer (`dp_classifier.py`)
Two independent pure-function AST classifiers automatically identify DP patterns:
*   **Tabulation (`classify_tabulation`)**: Permissive, single-signal classifier detecting loop variables index mutations inside subscript assignments (e.g. `dp[i] = dp[i-1] + dp[i-2]`).
*   **Memoization (`classify_memoization`)**: Strict, multi-signal classifier requiring the coexistence of recursion, cache check (via decorators or manual lookup), cache write, and parameter-derived keys.

### B. Trace Processing & Annotations (`dp_tracer.py`)
Intercepts execution steps and packages them into rich visualization-ready outputs:
*   **Tabulation post-processor**: Resolves array shape bounds (`table_shape`) and highlights the target index vs source cell dependencies. 
    *   *Sequencing Fix*: Replaced structural Pydantic step comparison (`steps.index(step)`) with exact sequence tracking (`enumerate(steps)`) to eliminate frame update offsets and ensure values are visualized in the grid during writes.
*   **Memoization tracing engine**:
    *   Tracks recursive step sequences (`call`, `cache_hit`, `cache_write` events) along with local scopes and return values.
    *   *Line Number Propagation Fix*: Integrated call stack and frame inspection (`sys._getframe(2)` / `frame.f_lineno`) to track and pass the active code line numbers to the steps. This enables active line highlighting in Monaco and dynamic step explanations in the Inspector.

### C. Frontend Visualization (`DPVisualizer.tsx` - BUILD-14)
Renders a custom UI separate from standard data structures:
*   **Tabulation**: Renders a fixed-size ghost matrix mapping the DP table shape. Target cells highlight in Electric Indigo, while source cells highlight in Emerald.
*   **Memoization**: Tracks recursive caches.
    *   *Call Stack Fix*: Updated depth tracking (`depth = d.call_depth`) to correctly render multi-level active recursion breadcrumbs (e.g., `5 → 4 → 3 → 1`) instead of a single element.
    *   Hit events pulse existing cache entries dynamically without duplicates.

---

## 4. Current File Map

### Python Backend
*   `run_tracer.py`: The entrypoint script for executing code and calling the tracer.
*   `tracer.py`: The core tracing class and polyfills.
*   `dp_classifier.py`: Pure-function AST classifiers for DP detection.
*   `dp_tracer.py`: Post-processors and recursion tracing engines for DP visualization.
*   `generate_mocks.py`: Mock data generator to export static visualizer JSON runs.

### Frontend Components (`/frontend/src/components/`)
*   `VisualizationCanvas.tsx`: The primary orchestrator handling canvas state and component routing.
*   `CodeEditor.tsx`: Monaco Editor Python syntax and active line highlighter.
*   `visualizers/GraphTreeRenderer.tsx`: The highly-optimized master rendering engine for trees and heaps.
*   `visualizers/HeapVisualizer.tsx`: The topology adapter bridging a 1D array into the GraphTreeRenderer.
*   `visualizers/TreeVisualizer.tsx`: The topology adapter for object-based trees.
*   `visualizers/ArrayVisualizer.tsx`: Standard 1D flexbox array rendering.
*   `visualizers/DPVisualizer.tsx`: Visualizer component for DP tabulation grids and memoization logs.
*   *(Other Visualizers)*: `StackVisualizer.tsx`, `QueueVisualizer.tsx`, `DequeVisualizer.tsx`, `LinkedListVisualizer.tsx`.

### Core Application pages (`/frontend/src/app/`)
*   `page.tsx`: The landing page layout, Canvas error boundary, routing controls, and iris reveal animation.
*   `Environment.tsx`: Custom Cursor, CursorLight, Constellation particle field wrapper, and R3F material extend handlers.
*   `shaders.ts`: The background warper simplex noise GLSL shaders.
*   `studio/page.tsx`: The main Studio workspace UI and execution handler.

### Logic & Types
*   `/frontend/src/utils/semanticAnalyzer.ts`: The behavioral heuristics engine.
*   `/frontend/test_heap.ts`: Diagnostic TS script used for debugging math and layout logic.

---

## 5. WebGL & Deployment Audit (LAN/Mobile Support)

We recently identified and resolved several critical runtime and layout failures that occurred when accessing the visualizer over a Local Area Network (LAN IP) or from mobile/touch-enabled devices:

1. **Shader NaN Resolution**: Fixed a divide-by-zero risk in `shaders.ts` where calling `normalize(uCursor - uv)` with a static or uninitialized cursor generated `NaN` vectors on the GPU, causing the background shader to crash and render blank.
2. **Turbopack Tree-Shaking Guard**: Added explicit client-side Three.js `extend({ BackgroundShaderMaterial })` in `Environment.tsx` to prevent Next.js from shaking off custom shader classes during production compilation.
3. **Monaco Editor Navigation Stability**: Bypassed race conditions where `CodeEditor.tsx` tried to reference `window.monaco.Range` during fast route changes before the Monaco bundle was fully registered. It now uses a local reference `monacoRef` initialized inside `onMount`.
4. **Resilience to Asset CDN Blocks**: Wrapped `<EnvLogger />` (which relies on external CDNs for HDR presets) in a React `<ErrorBoundary fallback={null}>` to prevent network blocks, Pi-holes, or DNS failures on local Wi-Fi from crashing the whole Canvas render loop.
5. **Interactive Pointer Event Alignment**: Changed custom cursor position trackers from mouse-only (`mousemove`, `mouseover`) to pointer events (`pointermove`, `pointerover`) to support touchscreen inputs on LAN tablets and mobile phones.
6. **Mobile WebKit Prefixes**: Integrated `-webkit-backdrop-filter` for logo lens blurs and added `will-change: clip-path` + `transform: translateZ(0)` hardware acceleration tags to the Studio page transition overlay to fix WebKit layout render freezes.
7. **Animation Throttling Fallback**: Built in robust fallback timeouts (4s) to the transition animation. If mobile browsers throttle `requestAnimationFrame` (e.g., in battery-saver mode), the router forces navigation to prevent users from getting stuck.
8. **WebGL Thread Throttling**: Added dynamic `frameloop={appState === 'studio' ? 'never' : 'always'}` to the `<Canvas>` wrapper to pause rendering while in the code editor, freeing GPU resources and extending mobile battery life.
9. **Git Index Ignore Rules**: Configured `.gitignore` to prevent generated screenshot outputs (`*.png`), static JSON mock files (`frontend/public/mocks/`), and local script tools (`scratch_*.py`, `query_*.py`, `generate_mocks.py`) from cluttering the working tree. Untracked them from git cache across `main` and `v1.4` branches.

---

## 6. Upcoming Roadmap

With the current Heap/Array system, the unified `GraphTreeRenderer` now rock-solid, and remote LAN/Mobile execution completely stabilized, the next planned targets are:
*   **AVL Trees**
*   **Red-Black Trees**
*   **Tries** 

These will cleanly slot into the existing architecture by writing thin adapters that calculate standard node positions and pipe them directly into `GraphTreeRenderer`.
Updated buttons and settings 
