from PySide6.QtCore import Signal, QObject

class Signals(QObject):
    selected_new_project_folder = Signal(str)
    selected_new_file = Signal(str)
    select_project_requested = Signal()
    create_file_act = Signal()
    create_dir_act = Signal()
    execute_create_file = Signal(str)
    execute_create_dir = Signal(str)
    delete_act = Signal()
    save_file_act = Signal()
    
    message_context_count_updated = Signal(int)
    startup_message_count_updated = Signal(int)
    theme_changed = Signal(str)
    auto_save_changed = Signal(bool)
    
    error_occured = Signal(str)

    show_left_bar = Signal(bool)
    show_bottom_bar = Signal(bool)
    show_right_bar = Signal(bool)

    add_file_to_context = Signal(str)

    # Emitted after files/folders are created, renamed or deleted so the
    # quick-search index can refresh without rescanning on every keystroke.
    project_files_changed = Signal()

    # Short-lived feedback for the shared status bar ("Created file …").
    status_message = Signal(str)

    update_status_bar = Signal(dict)
signals = Signals()
