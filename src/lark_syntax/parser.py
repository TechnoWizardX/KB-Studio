from importlib.resources import files
from lark import Lark
from typing import Optional

class SCSParser:
    """Парсер для SCs-кода с загрузкой грамматики из пакета src.lark_syntax"""
    def __init__(self, grammar_path: Optional[str] = None):
        """
        Инициализация парсера
        Args:
            grammar_path: путь к файлу грамматики (.lark)
                         если не указан, загружает из пакета src.lark_syntax
        """
        if grammar_path is None:
            grammar_text = files("src.lark_syntax").joinpath("grammar.lark").read_text(encoding="utf-8")
        else:
            with open(grammar_path, 'r', encoding='utf-8') as f:
                grammar_text = f.read()

        self.parser = Lark(
            grammar_text,
            parser='lalr',     
            start='start',          
            propagate_positions=True,
            maybe_placeholders=False, 
            cache=True            
        )

    def parse(self, text: str):
        """
        Парсит SCs-текст
        Args:
            text: строка с SCs-кодом
        Returns:
            дерево разбора Lark
        """
        return self.parser.parse(text)
    
    def parse_file(self, filepath: str):
        """
        Парсит SCs-файл
        Args:
            filepath: путь к .scs файлу
        Returns:
            дерево разбора Lark
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        return self.parse(text)

    def lex(self, text: str):
        """
        Токенизация без полного парсинга
        Args:
            text: строка с SCs-кодом
        Returns:
            список токенов
        """
        return list(self.parser.lex(text))