"""Unit tests for the SCs parser used by the editor."""
import re
from pathlib import Path

from lark.exceptions import UnexpectedInput
import unittest

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


def _edge_connectors() -> list[str]:
    """Return every string literal declared for EDGE_T in grammar.lark."""
    grammar = Path(__file__).parent.parent / "src" / "lark_syntax" / "grammar.lark"
    text = grammar.read_text(encoding="utf-8")
    block = re.search(r"^EDGE_T:(.*?)(?=^\S|\Z)", text, re.S | re.M)
    if not block:
        raise RuntimeError("EDGE_T terminal not found in grammar.lark")
    return re.findall(r'"((?:[^"\\]|\\.)*)"', block.group(1))


class SCSParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = SCSParser()

    def test_valid_examples(self):
        for group_name, cases in TEST_CASES.items():
            if group_name == "Должно НЕ парситься":
                continue
            for case in cases:
                with self.subTest(group=group_name, code=case):
                    self.parser.parse(case)

    def test_invalid_examples_are_rejected(self):
        for code, reason in TEST_CASES["Должно НЕ парситься"]:
            with self.subTest(code=code, reason=reason):
                with self.assertRaises(UnexpectedInput, msg=reason):
                    self.parser.parse(code)

    def test_every_declared_edge_connector_parses(self):
        connectors = _edge_connectors()
        self.assertTrue(connectors, "grammar.lark must declare EDGE_T connectors")
        for connector in connectors:
            with self.subTest(connector=connector):
                self.parser.parse(f"a {connector} b;;")


if __name__ == "__main__":
    unittest.main()
