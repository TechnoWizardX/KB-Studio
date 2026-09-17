from PySide6.QtCore import Signal, QObject

class Signals(QObject):
    # str: error 
    gaps_appeared = Signal(str)

    gaps_resolved = Signal()

    selected_new_project_folder = Signal(str)

    selected_new_file = Signal(str)

signals = Signals()