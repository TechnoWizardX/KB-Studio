# parser.py - Загрузка грамматики из файла

import os
from pathlib import Path
from lark import Lark
from typing import Optional

class SCSParser:
    """Парсер для SCs-кода с загрузкой грамматики из файла"""
    
    def __init__(self, grammar_path: Optional[str] = None):
        """
        Инициализация парсера
        
        Args:
            grammar_path: путь к файлу грамматики (.lark)
                         если не указан, ищет в той же директории
        """
        if grammar_path is None:
            current_dir = Path(__file__).parent
            grammar_path = current_dir / "grammar.lark"
        else:
            grammar_path = Path(grammar_path)
        
        if not grammar_path.exists():
            raise FileNotFoundError(f"Файл грамматики не найден: {grammar_path}")
        
        with open(grammar_path, 'r', encoding='utf-8') as f:
            grammar_text = f.read()
        
        self.parser = Lark(
            grammar_text,
            parser='lalr',          # Быстрый LALR-парсер
            start='start',          # Начальное правило
            propagate_positions=True, # Сохранять позиции
            maybe_placeholders=False, # Отключаем плейсхолдеры
            cache=True              # Кешировать для скорости
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