# Changelog

## [1.5.0] - Unreleased

### Added

- Added a content display toggle for node attachments on the `C` key: compact
  mode shows only the node glyph with the violet marker, expanded mode replaces
  the glyph with a square form carrying the content inside — string content as
  wrapped text, image attachments as a picture preview and other files as an
  independently sized file caption; connectors attach to the square edges. The
  toggle applies to the selected nodes when something is selected (one node if
  it is the only selection; mixed selections expand or collapse together), and
  to the whole graph when the selection is empty; display-only change, and
  connected connectors reroute to the new glyph shape right away (both on
  collapse and after changing content of an expanded node).
- Added node content (attachments/links) support in the graph editor, matching
  the KBE GWF conventions: string content (type 1, `content/term`) shows as a
  word-wrapped label under the node when `content_visibility` is true, file
  content (type 4) shows the file name with its size; the violet marker is
  drawn for any non-empty content. A context menu command
  ("Add content…"/"Edit content…") opens a content dialog with the text field,
  an "Attach file…" button (file data is stored base64 with `file_name` and a
  MIME type), a visibility checkbox and content removal. Content edits are
  undoable (Ctrl+Z/Ctrl+Shift+Z) and round-trip through GWF save/load.
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
- Added connector attachment to buses (as in the KBE reference): arcs and
  pairs can start or end on the bus polyline, the attach point is computed
  from the drop position and follows the bus when its owner node is moved or
  the bus itself is dragged (the bus start stays glued to the owner node
  border); deleting the bus or its owner removes the connectors attached to
  it (undoable); GWF files written by KBE (arcs with `id_b`/`id_e` pointing
  to a bus and bus dots in `dotBBalance`/`dotEBalance`) load with all such
  connectors attached, and saving keeps the bus reference and attach dots.
- Added toolbar icons (Lucide SVG assets embedded through the application
  resource bundle) with tooltips for every graph editor action.
- Added `Ctrl+S` in the graph editor to save the current graph without
  reaching for the toolbar save button.

### Changed

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

- Connectors now attach radially: every connector end anchored to a node or a
  contour border aims at the actual attach point reached on the other side
  (the junction of the other endpoint for buses and parent connectors), so
  arcs and pairs approach the node centre instead of grazing the border
  tangentially. Routes drawn through waypoints keep the KBE behaviour.
- Smoother dragging of large selections: edges shared between several dragged
  nodes are refreshed once per mouse event (with all nodes already at their
  final positions) instead of once per moved node, and the connector anchor
  bisection was made ~3× cheaper (12 iterations instead of 32, about 0.7px
  accuracy at a 3000px offset); node glyphs are now built once and cached so
  repeated anchor lookups do not rebuild the shape. Dragging 31 selected nodes
  over the AI-Structure sample went from ~38 ms per frame (with a third of
  frames over the 40 ms budget) to ~21 ms with none over budget.
- New colour scheme for readability on the dark canvas: node interiors are
  filled dark while the bright border colour encodes the node kind (constants
  near-white, variables blue, meta violet); connectors and buses are a lighter
  grey (`#c9d1d9`) with a solid 2 px bus line and a dashed contour; selection
  is highlighted in orange (`#ffa657`) for nodes, connectors, and dot handles.
- Added an event-loop stall recorder behind `KB_CAPTURE_STALLS=1`: when the
  editor event loop freezes for 150 ms or longer, the current Python call
  stacks of all threads are dumped to stderr (faulthandler/SIGUSR2), so a
  hard-to-reproduce freeze can be captured with the exact offending code.
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

### Fixed

- Fixed a permanent one-stall-per-second loop in the SCs code editor: the
  syntax parse changed text formats with its own error/token highlighting,
  which fired `textChanged` and re-armed the 500 ms parse debounce timer, so
  every open editor re-parsed itself (a ~150 ms UI stall with large files,
  the whole UI thread burning CPU) forever, even while the app was idle or
  the graph editor was used. The parse now never re-arms its own timer; one
  parse runs per actual text change.

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
