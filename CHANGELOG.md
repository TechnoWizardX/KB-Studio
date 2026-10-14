# Changelog

## [1.4.0] - Unreleased

### Added

- Added a Settings dialog with controls for application appearance, editor, and AI chat.
- Added live switching between light and dark application themes.
- Added an editor auto-save setting.
- Added AI chat settings for the number of messages loaded at startup and the number of messages included as context.
- Added migration of the previous startup message-count setting to the renamed configuration key.
- Added more detailed AI guidance about SC-code syntax, levels, and types.

### Changed

- Disabled line wrapping in the SC-code editor.
- Refresh toolbar and chat icons when the application theme changes.

### Fixed

- Stop and wait for the AI worker thread before closing the application; prevent closing while a request is active.
- Added `cryptography` to the declared runtime dependencies.
- Corrected the AI chat history-clear command.
