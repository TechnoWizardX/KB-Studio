"""Content editor dialog for SCg nodes (link/files, kbe-style)."""
from __future__ import annotations

import base64
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.graph_editor.gwf_codec import (
    build_content_element,
    empty_content_element,
    guess_content_mime,
)

if TYPE_CHECKING:
    from src.gui.graph_editor.graph_items import GraphNode


class _ContentDialog(QDialog):
    """Editor for node content: link text, attached file and visibility.

    Mirrors the kbe SCg content dialogs: the text field edits string content
    (type 1), ``Attach file...`` replaces the content with raw file data
    (type 4, base64 in GWF) and the checkbox controls whether the content
    label is drawn under the node. ``OK`` is disabled until something to
    save remains.
    """

    def __init__(self, node: GraphNode, parent: QWidget | None = None):
        super().__init__(parent)
        self.node = node
        element = node.content_element()
        self._c_type = element.get("type", "0") if element is not None else "0"
        self._mime = element.get("mime_type", "") if element is not None else ""
        self._file_name = (
            element.get("file_name", "") if element is not None else ""
        )
        self._attached: tuple[str, str, str] | None = None
        self._deleted = False
        # File content (type 4) is shown with a disabled text field: OK with
        # an untouched payload must reuse the original data, not drop it.
        self._original_payload = (
            element.text or "" if self._c_type == "4" and element is not None else ""
        )
        visible = self._c_type != "0" and element.get(
            "content_visibility", "false"
        ) == "true"

        self.setWindowTitle(f"Content of {node.identifier}")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Text:", self))
        self.text_edit = QPlainTextEdit(self)
        if self._c_type in {"1", "2", "3"}:
            self.text_edit.setPlainText(element.text or "")
        else:
            self.text_edit.setPlainText("")
        self.text_edit.setPlaceholderText("Term or content text…")
        layout.addWidget(self.text_edit, 1)

        file_row = QHBoxLayout()
        self.attach_button = QPushButton("Attach file…", self)
        self.attach_button.clicked.connect(self._attach_file)
        self.file_label = QLabel("", self)
        self.file_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        file_row.addWidget(self.attach_button)
        file_row.addWidget(self.file_label, 1)
        layout.addLayout(file_row)
        self._update_file_label()
        if self._c_type == "4":
            self.text_edit.setEnabled(False)

        self.visible_checkbox = QCheckBox(
            "Show content under the node", self
        )
        self.visible_checkbox.setChecked(visible or self._c_type == "0")
        layout.addWidget(self.visible_checkbox)

        buttons = QHBoxLayout()
        self.remove_button = QPushButton("Remove content", self)
        self.remove_button.setEnabled(node.has_content())
        self.remove_button.clicked.connect(self._remove_content)
        ok_button = QPushButton("OK", self)
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def _update_file_label(self) -> None:
        if self._attached is not None:
            _mime, name, data = self._attached
            size = len(data) * 3 // 4
            self.file_label.setText(f"📎 {name} ({size} B)")
            return
        if self._c_type == "4":
            element = self.node.content_element()
            size = len((element.text or "")) * 3 // 4 if element is not None else 0
            self.file_label.setText(
                f"📎 {self._file_name or 'file'} ({size} B)"
            )
        else:
            self.file_label.setText("No file attached")

    def _attach_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach content file", ""
        )
        if not path:
            return
        try:
            raw = Path(path).read_bytes()
        except OSError as error:
            QMessageBox.warning(self, "Cannot attach file", str(error))
            return
        self._attached = (
            guess_content_mime(os.path.basename(path)),
            os.path.basename(path),
            base64.b64encode(raw).decode("ascii"),
        )
        self.text_edit.setEnabled(False)
        self._update_file_label()

    def _remove_content(self) -> None:
        self._deleted = True
        self.accept()

    def result_content(self) -> ET.Element | None:
        """``<content>`` element to store, or None for removal.

        Rules, like the kbe writer: an attached file wins over the text; an
        empty text marks content as removed; string content keeps the type
        and MIME of the original numeric content when the value still parses.
        """
        if self._deleted:
            return None
        visible = self.visible_checkbox.isChecked()
        if self._attached is not None:
            mime, file_name, data = self._attached
            return build_content_element("4", mime, visible, file_name, data)
        text = self.text_edit.toPlainText().strip()
        if not text:
            if self._c_type == "4":
                # The payload is not editable in this dialog; an empty text
                # field keeps the attached file data as-is.
                return build_content_element(
                    "4", self._mime, visible, self._file_name,
                    self._original_payload,
                )
            return empty_content_element()
        c_type, mime = self._string_type(text)
        return build_content_element(c_type, mime, visible, "", text)

    def _string_type(self, text: str) -> tuple[str, str]:
        if self._c_type == "2":
            try:
                int(text)
            except ValueError:
                return "1", self._mime or "content/term"
            return "2", self._mime or "content/int"
        if self._c_type == "3":
            try:
                float(text)
            except ValueError:
                return "1", self._mime or "content/term"
            return "3", self._mime or "content/real"
        return "1", self._mime or "content/term"
