from lark import Lark

# Вариант 1: читаем из файла
with open('src/lark_syntax/grammar.lark', 'r', encoding='utf-8') as f:
    grammar_text = f.read()

# Пробуем создать парсер
try:
    parser = Lark(grammar_text, parser='lalr', start='start')
    print("✅ Грамматика загружена успешно!")
    
    # Тестируем
    test = """
    nrel_idtf -> concept: [text];;
    concept_test <= nrel_test_nrel: [this is test nrel] (* <- lang_en (* <- concept_language_type ;; *);; *);;"""
    tree = parser.parse(test)
    print(tree.pretty())
    
except Exception as e:
    print(f"❌ Ошибка: {e}")