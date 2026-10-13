# KB-Studio
This is the Knowledge Base Studio for editing SC.s-code

## Chat history and input safety

Chat messages are stored locally in `chat_history.sqlite3` in the application's
data directory. SQLite values are passed with query placeholders (`?`), not
inserted into SQL strings; keep using parameterized queries for any new database
operations. User messages and attached file contents are also treated as
untrusted model input. This reduces prompt-injection risk but cannot guarantee
that an AI model will ignore every malicious instruction.