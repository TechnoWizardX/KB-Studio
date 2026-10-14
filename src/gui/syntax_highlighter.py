import re

from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt
from src.lark_syntax.parser import SCSParser
from lark import Tree, Token
from lark.exceptions import UnexpectedInput


class SCSHighlighter(QSyntaxHighlighter):
    """Syntax highlighting for SCs tokens, comments, and parser errors."""

    # Only bracket/delimiter tokens with distinct colors per type (dark theme)
    BRACKET_COLORS_DARK = {
        # Round brackets ( ) - warm amber (warning color)
        'LPAREN': '#cca700',
        'RPAREN': '#cca700',
        # Sub-structure brackets (* *) - teal/cyan (success color)
        'LPAREN_STAR': '#4ec9b0',
        'STAR_RPAREN': '#4ec9b0',
        # Square brackets [ ] - muted green
        'LBRACKET': '#7ab87a',
        'RBRACKET': '#7ab87a',
        # SC-structure brackets [* *] - soft magenta/pink
        'LBRACKET_STAR': '#c678dd',
        'STAR_RBRACKET': '#c678dd',
        # Curly braces { } - warm yellow/gold
        'LBRACE': '#e5c07b',
        'RBRACE': '#e5c07b',
        # Angle brackets < > - accent blue
        'LANGLE': '#007acc',
        'RANGLE': '#007acc',
        # Ellipsis ... - muted purple
        'ELLIPSIS': '#b388d6',
    }

    # Light theme - distinct colors per bracket type
    # Colors aligned with VS Code Light 2026 palette
    BRACKET_COLORS_LIGHT = {
        'LPAREN': '#bf8803',      # warning amber
        'RPAREN': '#bf8803',
        'LPAREN_STAR': '#16825d', # success teal
        'STAR_RPAREN': '#16825d',
        'LBRACKET': '#66aa00',    # dark green
        'RBRACKET': '#66aa00',
        'LBRACKET_STAR': '#cc00cc', # dark magenta
        'STAR_RBRACKET': '#cc00cc',
        'LBRACE': '#ccaa00',      # dark yellow
        'RBRACE': '#ccaa00',
        'LANGLE': '#007acc',      # accent blue
        'RANGLE': '#007acc',
        'ELLIPSIS': '#8800cc',    # dark purple
    }

    # Tokens to highlight (only brackets/delimiters)
    BRACKET_TOKENS = frozenset(BRACKET_COLORS_DARK.keys())
    SEMANTIC_TOKENS = frozenset({"LINK_CONTENT"})
    COMMENT_STATE = 1
    IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9_.]+")
    EDGE_TOKENS = (
        "<>",
        ">",
        "<",
        "..>",
        "<..",
        "->",
        "<-",
        "<=>",
        "=>",
        "<=",
        "-|>",
        "<|-",
        "-/>",
        "</-",
        "~>",
        "<~",
        "~|>",
        "<|~",
        "~/>",
        "</~",
        "=",
    )
    EDGE_PATTERN = re.compile(
        "|".join(
            re.escape(token)
            for token in sorted(
                EDGE_TOKENS + tuple(f"_{token}" for token in EDGE_TOKENS),
                key=len,
                reverse=True,
            )
        )
    )

    def __init__(self, document, parser: SCSParser):
        super().__init__(document)
        self.parser = parser
        self._formats = {}
        self._comment_format = QTextCharFormat()
        self._string_format = QTextCharFormat()
        self._error_format = QTextCharFormat()
        self._error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        self._error_positions = []  # List of (start, end) positions
        self._theme = 'dark'
        self._cached_tokens = []  # Cache tokens from last successful parse
        self._cached_text: str | None = None
        self._build_formats()

    def _build_formats(self):
        """Create QTextCharFormat for each bracket type based on current theme."""
        colors = self.BRACKET_COLORS_DARK if self._theme == 'dark' else self.BRACKET_COLORS_LIGHT
        error_color = '#f14c4c' if self._theme == 'dark' else '#cd3131'
        semantic_colors = (
            {
                "ID": "#ce9178",
                "ALIAS": "#c586c0",
                "EDGE_T": "#ff0080",
                "STRING": "#6a9955",
                "LINK_CONTENT": "#c678dd",
            }
            if self._theme == "dark"
            else {
                "ID": "#800000",
                "ALIAS": "#7f3fbf",
                "EDGE_T": "#d00070",
                "STRING": "#008000",
                "LINK_CONTENT": "#7a378b",
            }
        )
        
        self._formats.clear()
        for token_type, color in colors.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            # Normal weight (not bold) for brackets
            self._formats[token_type] = fmt

        semantic_formats = {
            token_type: QTextCharFormat()
            for token_type in ("ID", "ALIAS", "EDGE_T", "STRING", "LINK_CONTENT")
        }
        for token_type, fmt in semantic_formats.items():
            fmt.setForeground(QColor(semantic_colors[token_type]))
            self._formats[token_type] = fmt

        comment_color = "#858585" if self._theme == "dark" else "#6a737d"
        self._comment_format.setForeground(QColor(comment_color))
        self._string_format = semantic_formats["STRING"]
        
        # Update error format with theme-appropriate color
        self._error_format.setUnderlineColor(QColor(error_color))
        

    def set_theme(self, theme_name: str):
        """Update highlighter colors for a new theme."""
        if theme_name in ('dark', 'light'):
            self._theme = theme_name
        else:
            self._theme = 'dark'
        self._build_formats()
        self.rehighlight()

    def set_error_positions(self, positions: list[tuple[int, int]]):
        """Set error positions for underline highlighting."""
        self._error_positions = positions
        self.rehighlight()

    def clear_errors(self):
        """Clear error highlights."""
        self._error_positions = []
        self.rehighlight()

    def _extract_tokens(self, tree):
        """Extract bracket delimiters and link content from a Lark parse tree."""
        tokens = []
        
        def walk(node):
            if isinstance(node, Token):
                if (
                    node.type in self.BRACKET_TOKENS | self.SEMANTIC_TOKENS
                    and node.start_pos is not None
                ):
                    tokens.append(node)
            elif isinstance(node, Tree):
                for child in node.children:
                    walk(child)
        
        walk(tree)
        return tokens

    def _update_token_cache(self, text: str):
        """Parse text and cache bracket tokens for highlighting."""
        try:
            tree = self.parser.parse(text)
            self._cached_tokens = self._extract_tokens(tree)
        except UnexpectedInput:
            # Parse error - keep old tokens, errors will be shown via error positions
            self._cached_text = text
        except Exception:
            # Other errors - clear cache
            self._cached_tokens = []
            self._cached_text = text
        else:
            self._cached_text = text

    def highlightBlock(self, text: str):
        """Highlight one line using tokens from the last valid SCs parse."""
        if not text:
            self.setCurrentBlockState(self.previousBlockState())
            return

        # Get full document text
        full_text = self.document().toPlainText()
        if not full_text:
            return

        # Update the token cache once per document revision.
        if self._cached_text != full_text:
            self._update_token_cache(full_text)

        block_start = self.currentBlock().position()
        block_end = block_start + len(text)

        self._highlight_lexical_tokens(text)

        # Highlight bracket tokens and link content from the parse cache.
        for token in self._cached_tokens:
            token_start = token.start_pos
            token_end = token.end_pos

            # Check if token overlaps with this block
            if token_end <= block_start or token_start >= block_end:
                continue

            # Calculate relative positions within block
            start = max(0, token_start - block_start)
            length = min(token_end, block_end) - max(token_start, block_start)

            if length > 0:
                fmt = self._formats.get(token.type)
                if fmt:
                    self.setFormat(start, length, fmt)

        self._highlight_comments_and_strings(text)

        # Highlight errors (underline)
        for err_start, err_end in self._error_positions:
            if err_end <= block_start or err_start >= block_end:
                continue
            start = max(0, err_start - block_start)
            length = min(err_end, block_end) - max(err_start, block_start)
            if length > 0:
                self.setFormat(start, length, self._error_format)

    def _highlight_lexical_tokens(self, text: str) -> None:
        for match in self.IDENTIFIER_PATTERN.finditer(text):
            self.setFormat(
                match.start(), match.end() - match.start(), self._formats["ID"]
            )
        for match in self.EDGE_PATTERN.finditer(text):
            self.setFormat(
                match.start(), match.end() - match.start(), self._formats["EDGE_T"]
            )

    def _highlight_comments_and_strings(self, text: str) -> None:
        position = 0
        in_block_comment = self.previousBlockState() == self.COMMENT_STATE
        self.setCurrentBlockState(0)

        while position < len(text):
            if in_block_comment:
                comment_end = text.find("*/", position)
                if comment_end == -1:
                    self.setFormat(
                        position, len(text) - position, self._comment_format
                    )
                    self.setCurrentBlockState(self.COMMENT_STATE)
                    return
                comment_end += 2
                self.setFormat(
                    position, comment_end - position, self._comment_format
                )
                position = comment_end
                in_block_comment = False
                continue

            if text.startswith("//", position):
                self.setFormat(
                    position, len(text) - position, self._comment_format
                )
                return

            if text.startswith("/*", position):
                in_block_comment = True
                continue

            if text[position] == '"':
                string_end = position + 1
                while string_end < len(text):
                    if text[string_end] == "\\":
                        string_end += 2
                        continue
                    if text[string_end] == '"':
                        string_end += 1
                        break
                    string_end += 1
                self.setFormat(
                    position,
                    min(string_end, len(text)) - position,
                    self._string_format,
                )
                position = string_end
                continue

            position += 1

    def refresh_tokens(self):
        """Force token cache refresh - call after text changes."""
        full_text = self.document().toPlainText()
        if full_text:
            self._update_token_cache(full_text)
            self.rehighlight()