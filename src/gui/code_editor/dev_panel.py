from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
)


class DevPanelWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("devPanelWidget")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.buttons_layout)

        self.problems_btn = QPushButton("Problems")
        self.problems_btn.setObjectName("devPanelBtn")
        self.problems_btn.setMaximumSize(100, 60)
        self.buttons_layout.addWidget(self.problems_btn)

        self.problems_wgt = ProblemsWidget()
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.problems_wgt)
        self.main_layout.addWidget(self.stacked_widget)

        self.problems_btn.clicked.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.problems_wgt)
        )


class ProblemsWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.show_diagnostics(None)

    def show_diagnostics(self, error: str | None) -> None:
        self.setText(error if error else "There is no syntax issues")
