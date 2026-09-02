from lark import Lark, UnexpectedToken, UnexpectedCharacters
import sys

GRAMMAR = r"""
start: sentence+

sentence: element edge element sentence_suffix END_SENTENCE

sentence_suffix: ":" element_list
               |

element: primary_element sub_structure?
       | sub_structure

primary_element: identifier
               | compound
               | set
               | link
               | sc_structure
               | unnamed
               | string_literal

compound: "(" element edge element ")"

sub_structure: "(*" internal_sentence* "*)"

internal_sentence: edge element end_of_construction

set: "{" element_list? "}"

link: "[" link_content? "]"
link_content: /[^\]]+/

sc_structure: "[*" sentence* "*]"

unnamed: "..."

identifier: visibility? ID

visibility: "_" | "." | ".."

string_literal: STRING

element_list: element (SEP element)*

end_of_construction: SEP
                   | END_SENTENCE

edge: "<-"
    | "->"
    | "<="
    | "=>"
    | "<-_"
    | "_->"
    | "_=>"
    | "<="

ID: /[a-zA-Z_][a-zA-Z0-9_]*/
STRING: /"([^"\\]|\\.)*"/

SEP: ";"
END_SENTENCE: ";;"

WS: /[ \t\n\r]+/
COMMENT: /\/\/[^\n]*/

%ignore WS
%ignore COMMENT
"""

TEST_CASES = {
    "Level 1 - Basic triples": [
        "concept_A -> concept_B;;",
        "concept_C <- concept_D;;",
        "nrel_example => concept_E;;",
        "concept_F <= nrel_example;;",
        "a -> b;; c -> d;; e -> f;;",
    ],
    "Level 2 - Positive edges and compound": [
        'nrel_image -> (fruit => "file://apple.png");;',
        "nrel_main_idtf -> (concept_A => [apple]);;",
        "set -> (item -> subitem);;",
        "a -> (b -> c);;",
        "nrel_example -> (x <- y);;",
    ],
    "Level 3 - Quintuple (attributes)": [
        "a -> c: b;;",
        "a => c: b; d; e;;",
        "nrel_idtf -> concept: [text];;",
        "set -> item: sub1; sub2; sub3;;",
        "a <- c: b; d;;",
        "nrel_example -> concept: (a -> b); (c -> d); [text];;",
    ],
    "Level 4 - Negative/variable edges": [
        "a <-_ b;;",
        "a _-> b;;",
        "a _=> b;;",
        "nrel_example _-> (a -> b);;",
    ],
    "Level 5 - Substructures (*...*)": [
        "set -> item (* -> subitem;; *);;",
        "concept_A -> concept_B (* <- concept_C;; => concept_D;; *);;",
        "a -> b (* -> c;; <- d;; *);;",
        "complex -> node (* -> child1;; -> child2;; *);;",
        "a -> b (* -> c;; *) (* -> d;; *);;",
        "parent -> child (* -> grandchild;; <- _parent;; *);;",
    ],
    "Level 6 - Sets, SC-structures, links as elements": [
        "a -> { concept_A; concept_B; concept_C };;",
        "{ a; b; c } -> set;;",
        "a -> [some text content];;",
        "[link_content] -> concept;;",
        "a -> [* b -> c;; d -> e;; *];;",
        "a -> [* [* nested -> inner;; *] -> outer;; *];;",
        "outer -> [* _var -> .local;; [text];; *];;",
    ],
    "Visibility prefixes": [
        "_var -> _other;;",
        ".hidden -> visible;;",
        "..local -> global;;",
        "_x -> .y;;",
        "..a -> _b (* -> ..c;; *);;",
    ],
    "Unnamed objects": [
        "... -> concept_A;;",
        "set -> ...;;",
        "... -> ...;;",
        "a -> b (* ... -> c;; *);;",
        "{ ...; a; _b } -> set;;",
    ],
    "Strings with escaping": [
        "a -> [simple text];;",
        'a -> "hello world";;',
        'a -> "say \\"hello\\" to me";;',
        'a -> "line1\\nline2";;',
        'nrel_idtf -> (concept => "multi\\nline\\ttext");;',
    ],
    "Comments and whitespace": [
        "a -> b;; // comment",
        "// start\na -> b;;\n// middle\nc -> d;;\n// end",
        "a   ->   b   ;;",
        "a->b;;",
        "/* not a comment */ a -> b;;",
    ],
    "Deep nesting and combinations": [
        "nrel_image -> (fruit => \"file://apple.png\");;\nnrel_main_idtf -> (fruit => [apple]);;",
        "set -> item (*\n    -> child1;;\n    -> child2 (* -> grandchild;; *);;\n*);;",
        "{\n    a;\n    b (* -> c;; *);\n    [text]\n} -> container;;",
        "_input -> processor (*\n    -> stage1;;\n    -> stage2 (* -> substage;; *);;\n    -> output;;\n*);;",
        "a -> (b -> (c -> d);;);;",
        "root -> [* leaf -> value;; branch -> { leaf1; leaf2 };; *];;",
        "meta -> [* _subject -> _object (* => attr: val;; *) ;; *];;",
    ],
    "Should fail - syntax errors": [
        ("a b;;", "no edge between elements"),
        ("a -> b;", "single ; instead of ;;"),
        ("-> a b;;", "no subject"),
        ("a -> ;;", "no object"),
        ("a -> b c;;", "two objects without separator"),
        ("(* a -> b;; *)", "substructure without context"),
        ("a -> b :;;", "empty list after :"),
        ("[", "unclosed bracket"),
        ('"unclosed string', "unclosed string"),
        ("a -> (* b;; *)", "internal sentence without edge"),
        ("{ a; b; c };;", "set without edge is not a sentence"),
        ("[* a -> b;; *];;", "sc-structure without edge is not a sentence"),
        ("a -> (* => c: b;; *)", "quintuple inside substructure"),
        ("a -> (* ... -> b;; *)", "subject inside substructure (implied)"),
    ],
}

def run_tests():
    print("=" * 60)
    print("   SCs-CODE: COMPLEX TEST SUITE (FIXED)")
    print("=" * 60)

    try:
        parser = Lark(GRAMMAR, parser="lalr", start="start")
        print("Grammar compiled (LALR)")
    except Exception as e:
        print(f"Grammar compilation error: {e}")
        sys.exit(1)

    total_pass = 0
    total_fail = 0
    total_expected_fail = 0

    for group_name, cases in TEST_CASES.items():
        print(f"\n{'-' * 60}")
        print(f"  {group_name}")
        print(f"{'-' * 60}")

        for case in cases:
            if isinstance(case, tuple):
                code, reason = case
                should_fail = True
            else:
                code = case
                reason = ""
                should_fail = False

            code_clean = code.strip()
            if not code_clean:
                continue

            try:
                tree = parser.parse(code_clean)
                if should_fail:
                    print(f"  WARN: Expected failure but parsed:")
                    print(f"     Code: {code_clean[:60]}...")
                    print(f"     Reason: {reason}")
                    total_fail += 1
                else:
                    print(f"  OK  {code_clean[:55]}...")
                    total_pass += 1
            except (UnexpectedToken, UnexpectedCharacters, Exception) as e:
                if should_fail:
                    print(f"  OK  Correctly rejected: {code_clean[:40]}...")
                    print(f"      ({reason})")
                    total_expected_fail += 1
                else:
                    print(f"  FAIL Unexpected error:")
                    print(f"     Code: {code_clean[:60]}...")
                    print(f"     Error: {str(e)[:80]}")
                    total_fail += 1

    print(f"\n{'=' * 60}")
    print(f"   RESULTS")
    print(f"{'=' * 60}")
    print(f"  Parsed successfully:     {total_pass}")
    print(f"  Correctly rejected:      {total_expected_fail}")
    print(f"  Unexpected errors:       {total_fail}")
    print(f"  Total tests:             {total_pass + total_expected_fail + total_fail}")

    if total_fail == 0:
        print(f"\n  ALL TESTS PASSED!")
    else:
        print(f"\n  ISSUES: {total_fail} unexpected errors")

    print(f"{'=' * 60}")

if __name__ == "__main__":
    run_tests()
