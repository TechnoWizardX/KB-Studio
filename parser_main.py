from lark import Lark
from src.lark_syntax import parser

# Вариант 1: читаем из файла
with open('src/lark_syntax/grammar.lark', 'r', encoding='utf-8') as f:
    grammar_text = f.read()

if __name__ == "__main__": 
    parser = parser.SCSParser()
    test = """  nrel_idtf -> concept: [text];;
 concept_test <= nrel_test_nrel: [this is test nrel] (* <- lang_en (* <- concept_language_type ;; *);; *);;"""
    print(parser.parse(test).pretty())