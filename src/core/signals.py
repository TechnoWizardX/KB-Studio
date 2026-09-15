from PySide6.QtCore import Signal, QObject

class Signals(QObject):
    # str: error 
    gaps_appeared = Signal(str)

    gaps_resolved = Signal()


signals = Signals()