from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt
from src.lark_syntax.parser import SCSParser
from lark import Tree, Token
from lark.exceptions import UnexpectedInput


class SCSHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for SCs code - highlights ONLY brackets/delimiters and errors."""

    # Only bracket/delimiter tokens with distinct colors per type (dark theme)
    # Muted, pleasant colors for dark theme - inspired by VS Code / One Dark
    BRACKET_COLORS_DARK = {
        # Round brackets ( ) - warm orange/amber
        'LPAREN': '#d49b4f',
        'RPAREN': '#d49b4f',
        # Sub-structure brackets (* *) - teal/cyan
        'LPAREN_STAR': '#4db8c7',
        'STAR_RPAREN': '#4db8c7',
        # Square brackets [ ] - muted green
        'LBRACKET': '#7ab87a',
        'RBRACKET': '#7ab87a',
        # SC-structure brackets [* *] - soft magenta/pink
        'LBRACKET_STAR': '#c678dd',
        'STAR_RBRACKET': '#c678dd',
        # Curly braces { } - warm yellow/gold
        'LBRACE': '#e5c07b',
        'RBRACE': '#e5c07b',
        # Angle brackets < > - soft blue
        'LANGLE': '#61afef',
        'RANGLE': '#61afef',
        # Ellipsis ... - muted purple
        'ELLIPSIS': '#b388d6',
    }

    # Light theme - distinct colors per bracket type
    BRACKET_COLORS_LIGHT = {
        'LPAREN': '#cc6600',      # dark orange
        'RPAREN': '#cc6600',
        'LPAREN_STAR': '#00aaaa', # dark cyan
        'STAR_RPAREN': '#00aaaa',
        'LBRACKET': '#66aa00',    # dark green
        'RBRACKET': '#66aa00',
        'LBRACKET_STAR': '#cc00cc', # dark magenta
        'STAR_RBRACKET': '#cc00cc',
        'LBRACE': '#ccaa00',      # dark yellow
        'RBRACE': '#ccaa00',
        'LANGLE': '#0066cc',      # dark blue
        'RANGLE': '#0066cc',
        'ELLIPSIS': '#8800cc',    # dark purple
    }

    # Tokens to highlight (only brackets/delimiters)
    BRACKET_TOKENS = frozenset(BRACKET_COLORS_DARK.keys())

    def __init__(self, document, parser: SCSParser):
        super().__init__(document)
        self.parser = parser
        self._formats = {}
        self._error_format = QTextCharFormat()
        self._error_format.setUnderlineColor(QColor('#f14c4c'))
        self._error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        self._error_positions = []  # List of (start, end) positions
        self._theme = 'dark'
        self._cached_tokens = []  # Cache tokens from last successful parse
        self._build_formats()

    def _build_formats(self):
        """Create QTextCharFormat for each bracket type based on current theme."""
        colors = self.BRACKET_COLORS_DARK if self._theme == 'dark' else self.BRACKET_COLORS_LIGHT
        
        self._formats.clear()
        for token_type, color in colors.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(QFont.Weight.Bold)
            self._formats[token_type] = fmt
        
        # No default format - we don't highlight anything else

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
        """Extract only bracket/delimiter tokens from a Lark parse tree."""
        tokens = []
        
        def walk(node):
            if isinstance(node, Token):
                # Only include bracket tokens that have position info
                if node.type in self.BRACKET_TOKENS and hasattr(node, 'start_pos') and node.start_pos is not None:
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
            pass
        except Exception:
            # Other errors - clear cache
            self._cached_tokens = []

    def highlightBlock(self, text: str):
        """Highlight a single block (line) of text - only brackets and errors."""
        if not text:
            return

        # Get full document text
        full_text = self.document().toPlainText()
        if not full_text:
            return

        # Update token cache if needed
        if not self._cached_tokens:
            self._update_token_cache(full_text)

        block_start = self.currentBlock().position()
        block_end = block_start + len(text)

        # Highlight bracket tokens from cache
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

        # Highlight errors (underline)
        for err_start, err_end in self._error_positions:
            if err_end <= block_start or err_start >= block_end:
                continue
            start = max(0, err_start - block_start)
            length = min(err_end, block_end) - max(err_start, block_start)
            if length > 0:
                self.setFormat(start, length, self._error_format)

    def refresh_tokens(self):
        """Force token cache refresh - call after text changes."""
        full_text = self.document().toPlainText()
        if full_text:
            self._update_token_cache(full_text)
            self.rehighlight()