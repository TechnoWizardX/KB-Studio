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
- Added toolbar icons (Lucide SVG assets embedded through the application
  resource bundle) with tooltips for every graph editor action.

### Changed

- The editor selector in the top bar switches between the SCs text editor and the
  SCg graph editor.
- Graph editor actions moved from text buttons to theme-aware toolbar icons.

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
