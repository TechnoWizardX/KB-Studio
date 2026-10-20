# Graph editor icons

Toolbar SVG icons were downloaded from the [Lucide](https://lucide.io) icon set
(`lucide-static` v0.544.0), licensed under the ISC license
(https://lucide.org/license). The files were renamed for their SCg editor role:

| File                      | Lucide icon    | Action                                  |
| ------------------------- | -------------- | --------------------------------------- |
| `new_graph.svg`           | `file-plus`    | New graph                               |
| `save.svg`                | `save`         | Save graph                              |
| `undo.svg` / `redo.svg`   | `undo-2`/`redo-2` | Undo / redo                          |
| `zoom_in.svg`/`zoom_out.svg` | `zoom-in`/`zoom-out` | Zoom                          |
| `fit.svg`                 | `maximize-2`   | Fit graph to view                       |
| `export_image.svg`        | `image`        | Export PNG                              |
| `find.svg`                | `search`       | Find node                               |
| `rename.svg`              | `pencil`       | Rename node                             |
| `delete.svg`              | `trash-2`      | Delete selection                        |
| `tool_select.svg`         | `mouse-pointer`| Select tool                             |
| `tool_node.svg`           | `circle`       | Node tool                               |
| `tool_connector.svg`      | `spline`       | Connector tool                          |
| `tool_bus.svg`            | `waypoints`    | Bus tool                                |
| `tool_contour.svg`        | `pentagon`     | Contour tool                            |
| `arrange_grid.svg`        | `grid-3x3`     | Grid arrangement                        |
| `arrange_vertical.svg`    | `list`         | Vertical arrangement                    |
| `arrange_horizontal.svg`  | `ellipsis`     | Horizontal arrangement                  |
| `arrange_tuple.svg`       | `share-2`      | Neighbour arrangement                   |

After adding files run `python build_assets.py` to regenerate
`src/resources/resources.qrc` and the compiled `resources_rc.py` module.
