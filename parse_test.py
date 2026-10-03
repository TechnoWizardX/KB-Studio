"""Тесты SCs-парсера.

В отличие от прежней версии, грамматика НЕ дублируется здесь, а берётся
из src/lark_syntax/grammar.lark через SCSParser — иначе тесты проверяют
не тот парсер, что использует редактор.

Запуск:  python parse_test.py
"""
import re
import sys
from pathlib import Path

from lark.exceptions import UnexpectedToken, UnexpectedCharacters

from src.lark_syntax.parser import SCSParser

# (код, причина) — причина указывается только для кейсов, которые ДОЛЖНЫ падать
TEST_CASES = {
    "Level 2 - коннекторы и compound": [
        "concept_A -> concept_B;;",
        "concept_C <- concept_D;;",
        "nrel_example => concept_E;;",
        "concept_F <= nrel_example;;",
        "a -> b;; c -> d;; e -> f;;",
        'nrel_image -> (fruit => "file://apple.png");;',
        "nrel_main_idtf -> (concept_A => [apple]);;",
        "set -> (item -> subitem);;",
        "a -> (b -> c);;",
        "nrel_example -> (x <- y);;",
        "(a -> b) -> (c <- d);;",
        "(a -> b);;",
        "(a -> b: c);;",
        "banana <- fruit;;",
    ],
    "Level 2 - расширенная таблица коннекторов": [
        "a <=> b;;",
        "a _<=> b;;",
        "a ..> b;;",
        "a <.. b;;",
        "a -|> b;;",
        "a <|- b;;",
        "a /> b;;",
        "a </ b;;",
        "a ~> b;;",
        "a %|> b;;",
        "a .> b;;",
        "a _.> b;;",
        "a ??|> b;;",
        "a ?=> b;;",
        "a ?-> b;;",
        "a _..> b;;",
        "a _%|> b;;",
        "a <?? b;;",
        "a </? b;;",
        "a ?=> b;;",
    ],
    "Level 3 - квинтупли (атрибуты : и ::)": [
        "a -> c: b;;",
        "a => c: b; d; e;;",
        "nrel_idtf -> concept: [text];;",
        "set -> item: sub1; sub2; sub3;;",
        "a <- c: b; d;;",
        "nrel_example -> concept: (a -> b); (c -> d); [text];;",
        "a -> c:: b;;",
        "a <=> c: d:: b;;",
        "apple => nrel_image: \"file://apple.png\";;",
        "a -> c: d: b: e;;",
    ],
    "Level 4 - цепочки через ;": [
        "fruit -> apple; -> banana;;",
        "a -> c: d: b; -> e; -> g: f;;",
        "set -> a; b; c;;",
        "x\n-> y;\n<- z;\n=> h: r;;",
        "scs\n<- test;\n=> test2;;",
        "@a -> b; -> c;;",
    ],
    "Level 4/5 - переменные и негативные дуги": [
        "a <-_ b;;",
        "a _-> b;;",
        "a _=> b;;",
        "nrel_example _-> (a -> b);;",
    ],
    "Level 5 - подструктуры (*...*)": [
        "set -> item (* -> subitem;; *);;",
        "concept_A -> concept_B (* <- concept_C;; => concept_D;; *);;",
        "a -> b (* -> c;; <- d;; *);;",
        "complex -> node (* -> child1;; -> child2;; *);;",
        "a -> b (* -> c;; *) (* -> d;; *);;",
        "parent -> child (* -> grandchild;; <- _parent;; *);;",
        "a -> b (* => r: [x];; *);;",
        "set -> attr: item (* -> subitem;; -> attr2: subitem2;; *);;",
        "sc_element => nrel_main_idtf: [sc-element] (* <- lang_en;; *);;",
    ],
    "Level 6 - множества, структуры, линки": [
        "a -> { concept_A; concept_B; concept_C };;",
        "{ a; b; c } -> set;;",
        "a -> [some text content];;",
        "[link_content] -> concept;;",
        "a -> [* b -> c;; d -> e;; *];;",
        "a -> [* [* nested -> inner;; *] -> outer;; *];;",
        "outer -> [* _var -> .local;; [text];; *];;",
        "root -> [* leaf -> value;; branch -> { l1; l2 };; *];;",
        "x -> [^\"int: 5\"];;",
        "x -> [^\"float: 435.2346\"];;",
        "x -> [this is a\n multiline text];;",
        "x -> [see [1]];;",
        "x -> [];;",
        "meta -> [* _subject -> _object (* => attr: val;; *) ;; *];;",
        # множества уровня 6
        "@set = { element1; attr2: element2 };;",
        "@oriented = < element1; attr2: element2 >;;",
        "x -> { a; b: c };;",
        "x -> < a; b >;;",
        "{\n  a;\n  b (* -> c;; *);\n  [text]\n} -> container;;",
    ],
    "Алиасы (@name = value;;)": [
        '@file_alias = "file://...";;',
        "@link_alias = [];;",
        "@element_alias = element_idtf;;",
        "@arc_alias = (c -> b);;",
        "@alias_to_alias = @element_alias;;",
        "@s = { a; b };;",
        "@st = [* set -> item;; *];;",
        "@a -> b;;",
        "@arc_alias -> x;;",
    ],
    "Имена и visibility (#names)": [
        "_var -> _other;;",
        ".hidden -> visible;;",
        "..local -> global;;",
        "_x -> .y;;",
        ".._x -> y;;",
        "... -> concept_A;;",
        "set -> ...;;",
        "... -> ...;;",
        "{ ...; a; _b } -> set;;",
        "my_node -> y;;",
    ],
    "Кейноды-типы": [
        "a <- sc_node_class;;",
        "a _-> _b;;",
        "_b <- sc_node_material;;",
        "_x => nrel_y: t;;",
        "nrel_y <- sc_node_non_role_relation;;",
    ],
    "Строки с экранированием": [
        "a -> [simple text];;",
        'a -> "hello world";;',
        'a -> "say \\"hello\\" to me";;',
        'a -> "line1\\nline2";;',
        'nrel_idtf -> (concept => "multi\\nline\\ttext");;',
        'a -> "file://apple.png";;',
    ],
    "Комменты и пробелы": [
        "a -> b;; // comment",
        "// start\na -> b;;\n// middle\nc -> d;;\n// end",
        "a   ->   b   ;;",
        "a->b;;",
        "/* not a comment */ a -> b;;",
        "/* Multiline\n * comment\n */\nfruit -> apple;;",
        "/* a */ x -> y; // b\n z;;",
        "",
    ],
    "Глубокая вложенность": [
        'nrel_image -> (fruit => "file://apple.png");;\nnrel_main_idtf -> (fruit => [apple]);;',
        "set -> item (*\n    -> child1;;\n    -> child2 (* -> grandchild;; *);;\n*);;",
        "_input -> processor (*\n    -> stage1;;\n    -> stage2 (* -> substage;; *);;\n    -> output;;\n*);;",
    ],
    "Должно НЕ парситься": [
        ("a b;;", "нет коннектора между элементами"),
        ("a -> b;", "одиночный ; вместо ;;"),
        ("-> a b;;", "нет subject"),
        ("a -> ;;", "нет object"),
        ("a -> b c;;", "два object без разделителя"),
        ("a -> b :;;", "пустой атрибут после :"),
        ("[", "незакрытая скобка линка"),
        ('"unclosed string', "незакрытая строка"),
        ("a -> (* b;; *)", "внутреннее предложение без коннектора"),
        ("a -> (* ... -> b;; *)", "subject внутри (* *), он подразумевается"),
        ("a -> (b -> (c -> d);;);;", ";; внутри compound — по спеке там нет ;;"),
        ("fruit apple;;", "два идентификатора подряд"),
        ("!!!", "мусор"),
        ("a -> b;;;", "лишняя ;"),
        ("a -> (b;;", "незакрытая скобка compound"),
        ("@ = b;;", "алиас без имени"),
        ("@a =;;", "алиас без значения"),
        ("a <=> c: ;;", "пустой атрибут"),
    ],
}


def _edge_connectors() -> list:
    """Все строковые литералы терминала EDGE_T из src/lark_syntax/grammar.lark."""
    grammar = Path(__file__).parent / "src" / "lark_syntax" / "grammar.lark"
    text = grammar.read_text(encoding="utf-8")
    block = re.search(r"EDGE_T:(.*?)\n\nID:", text, re.S)
    if not block:
        raise RuntimeError("терминал EDGE_T не найден в grammar.lark")
    return re.findall(r'"((?:[^"\\]|\\.)*)"', block.group(1))


def run_tests() -> int:
    print("=" * 60)
    print("   SCs-CODE: TEST SUITE (против grammar.lark)")
    print("=" * 60)

    try:
        parser = SCSParser()
        print("Грамматика загружена: src/lark_syntax/grammar.lark (LALR)")
    except Exception as e:
        print(f"Ошибка компиляции грамматики: {e}")
        return 1

    total_pass = total_rejected = total_fail = 0

    for group_name, cases in TEST_CASES.items():
        print(f"\n{'-' * 60}\n  {group_name}\n{'-' * 60}")

        for case in cases:
            if isinstance(case, tuple):
                code, reason = case
                should_fail = True
            else:
                code, reason, should_fail = case, "", False

            if not code.strip() and not should_fail:
                # пустой файл — отдельный кейс, парсится в позитивном списке
                if code != "":
                    continue

            try:
                parser.parse(code)
                if should_fail:
                    print(f"  FAIL ожидалась ошибка: {code.strip()[:45]!r}")
                    print(f"       причина: {reason}")
                    total_fail += 1
                else:
                    print(f"  OK   {code.strip()[:52] or '(пусто)'!r}")
                    total_pass += 1
            except (UnexpectedToken, UnexpectedCharacters, Exception) as e:
                if should_fail:
                    print(f"  OK   отклонено: {code.strip()[:40]!r}")
                    print(f"       ({reason})")
                    total_rejected += 1
                else:
                    print(f"  FAIL неожиданная ошибка: {code.strip()[:45]!r}")
                    print(f"       {str(e).splitlines()[0][:90]}")
                    total_fail += 1

    # Сплошная проверка таблицы коннекторов: каждый терминал EDGE_T из
    # grammar.lark обязан разбираться в предложении вида `a <conn> b;;`.
    print(f"\n{'-' * 60}\n  Вся таблица EDGE_T (сплошная проверка)\n{'-' * 60}")
    conns = _edge_connectors()
    conn_fail = 0
    for c in conns:
        try:
            parser.parse(f"a {c} b;;")
            total_pass += 1
        except Exception as e:
            conn_fail += 1
            total_fail += 1
            print(f"  FAIL {c!r}: {str(e).splitlines()[0][:70]}")
    print(f"  Коннекторов в EDGE_T: {len(conns)}, упавших: {conn_fail}")
    if conn_fail == 0:
        total_pass += 0  # каждый уже посчитан выше
        print(f"  OK   все {len(conns)} коннекторов разбираются")

    print(f"\n{'=' * 60}\n   RESULTS\n{'=' * 60}")
    print(f"  Разобрано:                {total_pass}")
    print(f"  Корректно отклонено:      {total_rejected}")
    print(f"  Ошибок:                   {total_fail}")
    print(f"  Всего:                    {total_pass + total_rejected + total_fail}")
    print(f"\n  {'ALL TESTS PASSED!' if total_fail == 0 else f'ISSUES: {total_fail}'}")
    print("=" * 60)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
