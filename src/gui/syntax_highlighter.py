from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt
from src.lark_syntax.parser import SCSParser
from lark import Tree, Token
from lark.exceptions import UnexpectedInput


class SCSHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for SCs code using Lark parse tree tokens."""

    # Token type -> (category, color) mapping for dark theme
    TOKEN_COLORS_DARK = {
        'ID': '#4ec9b0',           # teal - identifiers
        'ALIAS': '#dcdcaa',        # yellow - @alias
        'STRING': '#ce9178',       # orange - "string literal"
        'EDGE_T': '#569cd6',       # blue - edges =>, <=, <=>, etc.
        'UNNAMED': '#c586c0',      # purple - ...
        'COMMENT': '#6a9955',      # green - // comments
        'COMMENT_BLOCK': '#6a9955', # green - /* block comments */
        'EQUALS': '#d4d4d4',       # white - =
        'COLON': '#d4d4d4',        # white - :
        'DCOLON': '#d4d4d4',       # white - ::
        'SEP': '#808080',          # gray - ;
        'END_SENTENCE': '#808080', # gray - ;;
        'VISIBILITY': '#c586c0',   # purple - . .. _
    }

    TOKEN_COLORS_LIGHT = {
        'ID': '#0070c1',           # blue - identifiers
        'ALIAS': '#af6f00',        # dark yellow - @alias
        'STRING': '#a31515',       # red - "string literal"
        'EDGE_T': '#0070c1',       # blue - edges
        'UNNAMED': '#af00db',      # purple - ...
        'COMMENT': '#008000',      # green - comments
        'COMMENT_BLOCK': '#008000', # green - block comments
        'EQUALS': '#000000',       # black - =
        'COLON': '#000000',        # black - :
        'DCOLON': '#000000',       # black - ::
        'SEP': '#666666',          # gray - ;
        'END_SENTENCE': '#666666', # gray - ;;
        'VISIBILITY': '#af00db',   # purple - . .. _
    }

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
        """Create QTextCharFormat for each token type based on current theme."""
        colors = self.TOKEN_COLORS_DARK if self._theme == 'dark' else self.TOKEN_COLORS_LIGHT
        
        self._formats.clear()
        for token_type, color in colors.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if token_type in ('EDGE_T', 'VISIBILITY', 'UNNAMED', 'ALIAS'):
                fmt.setFontWeight(QFont.Weight.Bold)
            self._formats[token_type] = fmt
        
        # Default format for unknown tokens / whitespace
        default_color = colors.get('ID', '#d4d4d4' if self._theme == 'dark' else '#000000')
        self._default_fmt = QTextCharFormat()
        self._default_fmt.setForeground(QColor(default_color))

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
        """Extract all tokens from a Lark parse tree with their positions."""
        tokens = []
        
        def walk(node):
            if isinstance(node, Token):
                # Only include tokens that have position info
                if hasattr(node, 'start_pos') and node.start_pos is not None:
                    tokens.append(node)
            elif isinstance(node, Tree):
                for child in node.children:
                    walk(child)
        
        walk(tree)
        return tokens

    def _update_token_cache(self, text: str):
        """Parse text and cache tokens for highlighting."""
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
        """Highlight a single block (line) of text."""
        if not text:
            return

        # Get full document text
        full_text = self.document().toPlainText()
        if not full_text:
            return

        # Update token cache if needed (parse on first highlight or after text change)
        # We parse lazily to avoid blocking UI on every keystroke
        if not self._cached_tokens:
            self._update_token_cache(full_text)

        block_start = self.currentBlock().position()
        block_end = block_start + len(text)

        # Highlight tokens from cache
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
                fmt = self._formats.get(token.type, self._default_fmt)
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