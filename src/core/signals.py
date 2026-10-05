from PySide6.QtCore import Signal, QObject

class Signals(QObject):
    # str: error 
    gaps_appeared = Signal(str)

    gaps_resolved = Signal()

    selected_new_project_folder = Signal(str)

    selected_new_file = Signal(str)

    create_file_act = Signal()
    create_dir_act = Signal()

    execute_create_file = Signal(str)
    execute_create_dir = Signal(str)

signals = Signals()