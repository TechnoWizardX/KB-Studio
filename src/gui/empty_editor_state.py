"""Placeholder shown in the editor area while no document is open."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.signals import signals
from src.resources.icons import Icons


class EmptyEditorState(QFrame):
    """Centered invitation with the actions that make sense with no tabs.

    The widget only reports what the user asked for; opening documents stays
    in :class:`EditorWorkspace` and in the project tree.
    """

    new_graph_requested = Signal()
    new_file_requested = Signal()
    open_project_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("emptyState")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)

        card = QFrame()
        card.setObjectName("emptyStateCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(0)

        badge = QFrame()
        badge.setObjectName("emptyStateBadge")
        badge.setFixedSize(72, 72)
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel()
        self.icon_label.setObjectName("emptyStateIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(self.icon_label)
        card_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        self._refresh_icon()

        card_layout.addSpacing(18)

        title = QLabel("No file open")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        card_layout.addSpacing(6)

        hint = QLabel("Open a file or start something new.")
        hint.setObjectName("emptyStateHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        card_layout.addWidget(hint)

        card_layout.addSpacing(22)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)

        self.new_graph_button = self._action_button(
            "New graph", "Create an empty SCg graph", primary=True
        )
        self.new_graph_button.clicked.connect(self.new_graph_requested.emit)
        buttons.addWidget(self.new_graph_button)

        self.new_file_button = self._action_button(
            "New file", "Create a file in the project"
        )
        self.new_file_button.clicked.connect(self.new_file_requested.emit)
        buttons.addWidget(self.new_file_button)

        self.open_project_button = self._action_button(
            "Open folder…", "Choose the project folder to work in"
        )
        self.open_project_button.clicked.connect(
            self.open_project_requested.emit
        )
        buttons.addWidget(self.open_project_button)

        buttons.addStretch(1)
        card_layout.addLayout(buttons)

        card_layout.addSpacing(18)

        tip = QLabel(
            "Double-click a file in the project tree to open it here."
        )
        tip.setObjectName("emptyStateTip")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setWordWrap(True)
        card_layout.addWidget(tip)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)

        signals.theme_changed.connect(self._refresh_icon)

    @staticmethod
    def _action_button(
        text: str, tooltip: str, primary: bool = False
    ) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("emptyStateButton")
        button.setToolTip(tooltip)
        if primary:
            button.setProperty("primary", True)
        return button

    def _refresh_icon(self, _theme: str = "") -> None:
        self.icon_label.setPixmap(Icons.new_graph().pixmap(QSize(36, 36)))
