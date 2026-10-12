from PySide6.QtCore import Signal, QObject

class Signals(QObject):
    selected_new_project_folder = Signal(str)

    selected_new_file = Signal(str)

    create_file_act = Signal()
    create_dir_act = Signal()

    execute_create_file = Signal(str)
    execute_create_dir = Signal(str)

    delete_act = Signal()

    theme_changed = Signal(str)

    error_occured = Signal(str)
signals = Signals()