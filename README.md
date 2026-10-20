# KB-Studio

## About

KB-Studio is a desktop application for working with OSTIS knowledge bases. It
combines a project file browser, an SCs-code editor with syntax parsing and
highlighting, and an AI chat assistant in one interface.

The editor works with `.scs` files, the text representation of SC-code. The AI
assistant can answer questions about OSTIS and SCs-code and can use files
explicitly attached by the user as request context. AI providers and models
are configured in the application.

The editor selector in the top bar switches between the SCs text editor and a
PySide6 SCg graph editor. The graph editor supports typed constant, variable,
and meta nodes; typed directed and undirected connectors attached to node
borders or other connectors (SCg relation attributes); and editable buses and
contours. It opens and writes GWF 1.6/2.0 while preserving unedited GWF metadata
and route points. Graphical `.scs` import is not enabled yet; use the SCs text
editor to view and edit `.scs` files.

Use the canvas tools to create nodes by clicking, connectors by dragging from
a node or connector to another node or connector, buses by dragging from an
owner node, and contours by placing vertices (finish with Enter or a
double-click). Middle-mouse drag pans the canvas; hold Space and drag with the
left mouse button for the same action. Select objects to move, change their
SCg types, rename nodes, or delete them. Double-click a node to rename it in
place; double-click a connector to add or remove route waypoints and drag a
waypoint square to reshape the route. Right-click opens the context menu for
creating nodes, renaming, changing types, reversing pair direction, and
deleting. The toolbar arrangers lay the graph out as a grid, vertical line,
horizontal line, or circle around the neighbours of the selected node. All
editing actions support undo and redo (Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y). The
graph editor also provides node search, zoom, fit-to-graph, and PNG export.
Toolbar actions use theme-aware icons from the embedded Lucide icon set
(ISC license, see `src/resources/icons/`). Unsupported GWF elements are
preserved as unmodified document elements.

## Build on Linux

Build the application on the target operating system and architecture. The
current PyInstaller spec creates a single-file executable:

```bash
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller --noconfirm KB-Studio.spec
```

The executable is written to `dist/KB-Studio`. Run it with:

```bash
./dist/KB-Studio
```

## Linux compatibility

Linux compatibility depends on the executable architecture, the system
libraries that remain external to the PyInstaller bundle, and the GNU C
Library (glibc) version required by the executable and bundled native
libraries.

Inspect the executable architecture and ELF interpreter:

```bash
file dist/KB-Studio
```

Inspect glibc symbol-version requirements visible in the executable:

```bash
readelf --version-info dist/KB-Studio \
  | grep -o 'GLIBC_[0-9.]*' \
  | sort -Vu
```

The highest `GLIBC_x.y` value shown is the highest glibc symbol version
referenced by that ELF file. This is a useful initial check, but it does not
prove that the complete PyInstaller application runs on a distribution:
PyInstaller bundles Python, Qt, and other native libraries, each of which may
have its own system-library requirements. `ldd dist/KB-Studio` only reports
the executable's direct dynamic dependencies and does not fully audit every
library packed inside a one-file bundle.

For the broadest compatibility with glibc-based distributions, build on the
oldest Linux distribution you intend to support, then test the generated
executable on that distribution and on the other target distributions. Test
the actual application, including its GUI, bundled resources, and file
operations. A build made on a newer distribution is not guaranteed to run on
older ones.

Build and test separately for each target operating system and architecture.
A Linux executable is not a Windows or macOS build.
