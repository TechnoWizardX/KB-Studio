# Changelog

## [1.5.0] - Unreleased

### Added

- Added the SCg graph editor built with PySide6: typed constant, variable, and
  meta nodes; typed directed and undirected connectors attached to node borders
  or other connectors; editable buses and contours; GWF 1.6/2.0 load and save
  preserving unedited GWF metadata and route points; SCs round trip for simple
  statements; node search; zoom; fit-to-view; and PNG export.
- Added the editor selector in the top bar that switches between the SCs text
  editor and the SCg graph editor; opening a `.gwf` file now activates the
  graph editor automatically.
- Added full undo and redo in the graph editor (Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y)
  covering node, connector, bus, and contour creation, deletion, moving,
  renaming, and type changes.
- Added inplace node renaming on double click with SCs identifier validation.
- Added connector route editing: waypoints can be added and removed with a
  double click and dragged with the mouse; changes are undoable and persisted
  in GWF route points.
- Added a canvas context menu for creating nodes, renaming, changing node and
  connector types, reversing pair direction, and deleting objects.
- Added graph arrangers: grid, vertical and horizontal lines, and a circle
  arrangement for the neighbours of the selected node.
- Added connector attachment to contour borders: arcs and pairs can start or
  end on a contour, the attachment point follows the contour while it moves,
  deleting the contour removes its connectors (undoable), and GWF load/save
  keeps contour references including accurate `b_x`/`b_y`/`e_x`/`e_y`.
- Added toolbar icons (Lucide SVG assets embedded through the application
  resource bundle) with tooltips for every graph editor action.
- The graph editor understands SCg 2.0 spelled GWF types: nodes
  (`node/const/perm/general`, `.../group`, `.../relation`, and any other
  `node/<side>/<permanence>/<structure>` form) and connectors
  (`pair/...orient/.../membership`, `pair/const/-/perm/noorien`, and similar
  arc/pair spellings). Such files open with all relations drawn, and saving
  keeps object types and the original element order.
- Connector attach points (GWF dot balances) are editable: when a connector
  that is attached to another connector is selected, circle handles appear at
  its endpoints and can be dragged along the parent connector; the change is
  undoable and is saved back through `dotBBalance`/`dotEBalance`.

### Changed

- The editor selector in the top bar switches between the SCs text editor and the
  SCg graph editor.
- Graph editor actions moved from text buttons to theme-aware toolbar icons.
- The contour tool now closes the shape by clicking anywhere near the first
  vertex instead of requiring an exact click on the preview line; the preview
  turns green when the click would close the contour. Double-click and Enter
  still finish the contour as before.
- Nodes and connectors follow the KBE reference visuals more closely: node
  glyphs are larger (30 px icons, 4 px borders, thicker glyph strokes,
  hatching) so node structures (rrel/nrel roles, relations, groups, abstract,
  ...) are clearly distinguishable; "atom" maps to the group glyph and
  `node/var/not_define` renders as a variable node like in KBE.
- Connector arrowheads are solid triangles drawn over lines that stop at the
  arrow base (KBE behaviour), so arrows never sink into the line; connectors
  attached to other connectors paint above their parents so their arrowheads
  are not covered.
- Nodes and connectors show tooltips with identifier/type info, and dragging
  no longer lags on large graphs (per-item repaint updates, deferred
  model-change notifications and cached pens/styles).
- Nodes and connectors are drawn with the canonical SCg visual alphabet
  (extracted into `scg_painter.py`, following the OSTIS KBE reference
  implementation): constant nodes are circles and variable nodes are rectangles
  with the structure glyph (dot, hatching, cross, ...) drawn inside; arcs and
  membership pairs are thin lines with filled arrowheads, dashes for
  variable/temporary connectors and tick marks for negative/fuzzy ones; binary
  pairs are thick hollow lines. Connector types without a distinct visual form
  are signed with their SCs token next to the line.

## [1.4.0] - Unreleased

### Added

- Added a Settings dialog with controls for application appearance, editor, and AI chat.
- Added live switching between light and dark application themes.
- Added an editor auto-save setting.
- Added AI chat settings for the number of messages loaded at startup and the number of messages included as context.
- Added migration of the previous startup message-count setting to the renamed configuration key.
- Added more detailed AI guidance about SC-code syntax, levels, and types.

### Changed

- Disabled line wrapping in the SC-code editor.
- Refresh toolbar and chat icons when the application theme changes.

### Fixed

- Stop and wait for the AI worker thread before closing the application; prevent closing while a request is active.
- Added `cryptography` to the declared runtime dependencies.
- Corrected the AI chat history-clear command.
