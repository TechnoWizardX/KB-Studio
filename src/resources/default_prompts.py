SCS_TYPES_PROMPT ="""
# SC-element Types: SCs-code reference for LLM

## 1. sc.s-designations of sc-nodes

SC-node is an element of a semantic graph. Its SCs-code designation identifies the node category.

### 1.1. General nodes

* `ScType::Node` → `sc_node`
* `ScType::ConstNode` → `sc_node`
* `ScType::VarNode` → `sc_node`

### 1.2. Link nodes

* `ScType::NodeLink` → `sc_link`
* `ScType::ConstNodeLink` → `sc_link`
* `ScType::VarNodeLink` → `sc_link`

### 1.3. Link-class nodes

* `ScType::NodeLinkClass` → `sc_link_class`
* `ScType::ConstNodeLinkClass` → `sc_link_class`
* `ScType::VarNodeLinkClass` → `sc_link_class`

### 1.4. Tuple nodes

* `ScType::NodeTuple` → `sc_node_tuple`
* `ScType::ConstNodeTuple` → `sc_node_tuple`
* `ScType::VarNodeTuple` → `sc_node_tuple`

### 1.5. Structure nodes

* `ScType::NodeStructure` → `sc_node_structure`
* `ScType::ConstNodeStructure` → `sc_node_structure`
* `ScType::VarNodeStructure` → `sc_node_structure`

### 1.6. Role-relation nodes

* `ScType::NodeRole` → `sc_node_role_relation`
* `ScType::ConstNodeRole` → `sc_node_role_relation`
* `ScType::VarNodeRole` → `sc_node_role_relation`

### 1.7. Non-role-relation nodes

* `ScType::NodeNonRole` → `sc_node_non_role_relation`
* `ScType::ConstNodeNonRole` → `sc_node_non_role_relation`
* `ScType::VarNodeNonRole` → `sc_node_non_role_relation`

### 1.8. Class nodes

* `ScType::NodeClass` → `sc_node_class`
* `ScType::ConstNodeClass` → `sc_node_class`
* `ScType::VarNodeClass` → `sc_node_class`

### 1.9. Superclass nodes

* `ScType::NodeSuperclass` → `sc_node_superclass`
* `ScType::ConstNodeSuperclass` → `sc_node_superclass`
* `ScType::VarNodeSuperclass` → `sc_node_superclass`

### 1.10. Material nodes

* `ScType::NodeMaterial` → `sc_node_material`
* `ScType::ConstNodeMaterial` → `sc_node_material`
* `ScType::VarNodeMaterial` → `sc_node_material`

### 1.11. Interpretation note

The SCs-code designation shown in this table is the same for the base, constant, and variable variants of each node category. For example, `ScType::ConstNode` and `ScType::VarNode` both map to `sc_node`.

This mapping describes the type designations listed in the source. Do not infer that constant and variable distinctions are irrelevant in all other SCs-code contexts.

---

## 2. sc.s-designations of sc-connectors

An SC-connector connects SC-elements. Its SCs-code designation expresses its connector category and, depending on the connector, its constancy, temporal characteristics, polarity, and direction.

### 2.1. Common edges

* `ScType::CommonEdge` → `?<=>`
* `ScType::ConstCommonEdge` → `<=>`
* `ScType::VarCommonEdge` → `_<=>`

### 2.2. Common arcs

* `ScType::CommonArc` → `?=>` or `<=?`
* `ScType::ConstCommonArc` → `=>` or `<=`
* `ScType::VarCommonArc` → `_=>` or `<=_`

### 2.3. Membership arcs

* `ScType::MembershipArc` → `?.?>` or `<?.?`
* `ScType::ConstMembershipArc` → `.?>` or `<?.`
* `ScType::VarMembershipArc` → `_.?>` or `<?._`

### 2.4. Permanent arcs

* `ScType::PermArc` → `?-?>` or `<?-?`
* `ScType::ConstPermArc` → `-?>` or `<?-`
* `ScType::VarPermArc` → `_-?>` or `<?-_`

### 2.5. Temporary arcs

* `ScType::TempArc` → `?..?>` or `<?..?`
* `ScType::ConstTempArc` → `..?>` or `<?..`
* `ScType::VarTempArc` → `_..?>` or `<?.._`

### 2.6. Actual temporary arcs

* `ScType::ActualTempArc` → `?~?>` or `<?~?`
* `ScType::ConstActualTempArc` → `~?>` or `<?~`
* `ScType::VarActualTempArc` → `_~?>` or `<?~_`

### 2.7. Inactual temporary arcs

* `ScType::InactualTempArc` → `?%?>` or `<?%?`
* `ScType::ConstInactualTempArc` → `%?>` or `<?%`
* `ScType::VarInactualTempArc` → `_%?>` or `<?%_`

### 2.8. Positive arcs

* `ScType::PosArc` → `?.>` or `<.?`
* `ScType::ConstPosArc` → `.>` or `<.`
* `ScType::VarPosArc` → `_.>` or `<._`

### 2.9. Permanent positive arcs

* `ScType::PermPosArc` → `?->` or `<-?`
* `ScType::ConstPermPosArc` → `->` or `<-`
* `ScType::VarPermPosArc` → `_->` or `<-_`

### 2.10. Temporary positive arcs

* `ScType::TempPosArc` → `?..>` or `<..?`
* `ScType::ConstTempPosArc` → `..>` or `<..`
* `ScType::VarTempPosArc` → `_..>` or `<.._`

### 2.11. Actual temporary positive arcs

* `ScType::ActualTempPosArc` → `?~>` or `<~?`
* `ScType::ConstActualTempPosArc` → `~>` or `<~`
* `ScType::VarActualTempPosArc` → `_~>` or `<~_`

### 2.12. Inactual temporary positive arcs

* `ScType::InactualTempPosArc` → `?%>` or `<%?`
* `ScType::ConstInactualTempPosArc` → `%>` or `<%`
* `ScType::VarInactualTempPosArc` → `_%>` or `<%_`

### 2.13. Negative arcs

* `ScType::NegArc` → `?.|>` or `<|.?`
* `ScType::ConstNegArc` → `?|>` or `<|?`
* `ScType::VarNegArc` → `_|?>` or `<|?_`

### 2.14. Permanent negative arcs

* `ScType::PermNegArc` → `?-|>` or `<|-?`
* `ScType::ConstPermNegArc` → `-|>` or `<|-`
* `ScType::VarPermNegArc` → `_-|>` or `<|-_`

### 2.15. Temporary negative arcs

* `ScType::TempNegArc` → `?..|>` or `<|..?`
* `ScType::ConstTempNegArc` → `..|>` or `<|..`
* `ScType::VarTempNegArc` → `_..|>` or `<|.._`

### 2.16. Actual temporary negative arcs

* `ScType::ActualTempNegArc` → `?~|>` or `<|~?`
* `ScType::ConstActualTempNegArc` → `~|>` or `<|~`
* `ScType::VarActualTempNegArc` → `_~|>` or `<|~_`

### 2.17. Inactual temporary negative arcs

* `ScType::InactualTempNegArc` → `?%|>` or `<|%?`
* `ScType::ConstInactualTempNegArc` → `%|>` or `<|%`
* `ScType::VarInactualTempNegArc` → `_%|>` or `<|%_`

### 2.18. Fuzzy arcs

* `ScType::FuzArc` → `?/>` or `</?`
* `ScType::ConstFuzArc` → `/>` or `</`
* `ScType::VarFuzArc` → `_/>` or `</_`

---

## 3. Rules for constructing sc.s-designations of sc-connectors

### 3.1. Membership arcs

The basic membership-arc designation, with unspecified constancy, permanence, and polarity, is:

`?.?>`

Its symbols are interpreted as follows:

1. The first `?` indicates unspecified constancy.

   * Constant arc: omit the initial symbol.
   * Variable arc: use `_` at the beginning.

2. The middle `.` indicates unspecified permanence.

   * Permanent arc: use `-` in the middle part of the designation.
   * Temporary arc: use `..` in the middle part.
   * Actual temporary arc: use `~` in the middle part.
   * Inactual temporary arc: use `%` in the middle part.

3. The third `?` indicates unspecified polarity.

   * Positive arc: no additional polarity symbol is used before the direction marker.
   * Negative arc: use `|` before the direction marker.

4. The final `>` indicates the arc direction.

The designation `?.?>` is therefore a template whose symbols are replaced or omitted according to the properties of the arc.

These rules also apply to fuzzy membership arcs, but permanence is not specified for them in the same way.

### 3.2. Common arcs

The basic common-arc designation, with unspecified constancy, is:

`?=>`

Rules:

1. The initial `?` indicates unspecified constancy.

   * Constant arc: omit the initial symbol.
   * Variable arc: use `_` at the beginning.

2. The `=` symbol identifies a common arc rather than a membership arc.

3. The final `>` indicates the arc direction.

### 3.3. Reverse arc designations

Reverse designations are constructed by reversing the direction of the connector notation.

Examples of designation pairs:

* `=>` and `<=`
* `.?>` and `<?.`
* `->` and `<-`

### 3.4. Common edges

Common-edge designations are constructed according to the rules for common arcs.

The difference is that an additional `<` symbol is inserted between the first and second symbols.

Examples:

* `?<=>` — common edge with unspecified constancy.
* `<=>` — constant common edge.
* `_<=>` — variable common edge.

---

## 4. Instructions for the LLM

When interpreting SCs-code connector designations:

1. Determine whether the element is a node, arc, or edge.
2. For nodes, use the corresponding designation, such as `sc_node`, `sc_link`, `sc_node_tuple`, or `sc_node_class`.
3. Interpret connector symbols as a sequence. Do not assign meanings to individual symbols without considering their position and surrounding symbols.
4. Consider constancy, temporal properties, polarity, and direction.
5. Do not treat every connector as a membership arc. The `=` symbol identifies common-arc notation, while `<=>` is used for a common edge.
6. Preserve the exact punctuation and symbol order of every SCs designation.
7. If the connector type cannot be determined from the available rules, state that the source does not provide enough information rather than inventing a rule.

Source: https://ostis-ai.github.io/sc-machine/scs/sc_element_types/
"""

SCS_CODE_SYNTAX_AND_LEVELS_PROMPT = """
# SCs-code Syntax — Compact Reference for LLM

## 0. Scope

SCs-code is the textual representation of SC-code used to describe semantic structures in OSTIS. This reference follows the official `sc-machine` documentation for versions **0.9.0 and newer**.
Source: https://ostis-ai.github.io/sc-machine/scs/scs/

## 1. Common syntax

### 1.1. Sentences and comments

* `;;` terminates a sentence.
* `;` separates entries or connector clauses in compact syntax; it is not interchangeable with `;;`.
* `// ...` introduces a single-line comment.
* `/* ... */` introduces a multiline comment.

Example:

```scs
// Comment
fruit -> apple;;
```

### 1.2. File links

* `"file://<file name>"` — relative file path, resolved relative to the file where it is used.
* `"file:///<file_name>"` — absolute file path.

Example: `apple -> "file://apple.png";;`

### 1.3. Identifiers and visibility

General pattern:

```text
[visibility][variable]<identifier>
```

* `x` — globally visible identifier; the same identifier across files refers to the same knowledge-base element and becomes its system identifier.
* `.x` — globally visible object without generating a system identifier in memory.
* `..x` — identifier local to the current SCs file.
* `_x` — variable node identifier.
* `.._x` — local variable identifier.
* `...` — unnamed SC-node.

Visibility prefixes: no prefix means global visibility; `.` means no generated system identifier; `..` means file-local. `_` marks a variable identifier.

### 1.4. Aliases

`@name` defines an alias using `=`:

```scs
@file = "file://image.png";;
@link = [];;
@element = element_idtf;;
@arc = (c -> b);;
@alias2 = @element;;
```

Aliases can refer to links, elements, connectors, constructions, or other aliases. They are file-scoped and must be defined before use.

## 2. Syntax levels

Higher levels provide more compact representations. Different levels can be combined in one file.
The most popular levels is Level 2 and higher. Though use minimum level 2 for explanation of SCs-code
### Level 1 — Explicit triples

A sentence explicitly specifies subject, predicate, and object, separated by `|`:

```scs
<type>#<subject> | <type>#<predicate> | <type>#<object>;;
```

Example:

```scs
sc_node#fruit
  | sc_main_arc#..arc
  | sc_node#apple;;
```

Each typed element uses `<type>#<identifier>`. If the subject or object is an SC-link, use the file-link notation where applicable, e.g. `"file://image.png"`.

Documented type identifiers include `sc_node`, `sc_link`, `sc_common_edge`, `sc_common_arc`, `sc_membership_arc`, and `sc_main_arc`.

Level 1 is explicit, low-level, and easy to parse; the documentation describes it as suitable for transport formats.

### Level 2 — Connector notation and compound connectors

General sentence:

```scs
<element> <connector> <element>;;
```

Examples:

```scs
fruit -> apple;;
banana <- fruit;;
```

Use the connector designations defined in the SC-element Types reference. Connector direction matters.

A compound connector is a connector construction enclosed in parentheses, without its own terminating `;;`:

```scs
(<element> <connector> <element>)
```

It can be used as the subject or object of another connector:

```scs
nrel_image -> (fruit => "file://apple.png");;
d -> (c -> (a -> b));;
(a -> b) -> (c <- d);;
```

### Level 3 — Attribute notation

Colon notation abbreviates a nested outgoing positive connector:

```scs
c -> (a -> b);;
```

is equivalent to:

```scs
a -> c: b;;
```

If the outgoing connector from `c` is variable, use `::` instead of `:`:

```scs
a -> c:: b;;
```

is equivalent to:

```scs
c _-> (a -> b);;
```

**Restriction:** `:` and `::` replace only `->` and `_->`, respectively. Any number of `:` and `::` operators may occur in one sentence.

Example:

```scs
a <=> c: d:: b;;
```

### Level 4 — Shared source element

Multiple sentences with the same source can be combined by writing the source once and separating connector clauses with `;`.

Expanded form:

```scs
x -> y;;
x <- z;;
x => h: r;;
```

Compact form:

```scs
x
  -> y;
  <- z;
  => h: r;;
```

The later clauses reuse the same source element. The shorter form may omit repeated connectors between entries:

```scs
set -> a; -> b; -> c;;
set -> a; b; c;;
```

These two forms are equivalent according to the documentation.

### Level 5 — Internal sentences

Internal sentences are enclosed in `(* ... *)`. Place them after the object of a construction and before its terminating `;;`.

**Rule:** the object immediately before the internal block becomes the subject of every sentence inside that block. Do not repeat that subject. Internal sentences use levels 2–4, and each internal sentence must end with `;;`.

Example:

```scs
set
  -> attr: item
  (*
    -> subitem;;
    -> attr2: subitem2;;
  *);;
```

This is equivalent to:

```scs
set -> attr: item;;
item -> subitem;;
item -> attr2: subitem2;;
```

Internal sentences are useful for placing metadata and related constructions next to the element they describe.

### Level 6 — Complex aliases

#### 6.1. Links: `[ ... ]`

Square brackets create an SC-link with content. Content can be a string, including multiline text:

```scs
x -> [any string];;
x -> [multiline
text];;
```

Numeric binary content uses:

```text
[^"type: value"]
```

Supported types:

* `int` (signed 32-bit), `int8`, `int16`, `int32`, `int64`;
* `uint` (unsigned 32-bit), `uint8`, `uint16`, `uint32`, `uint64`;
* `float` (32-bit floating point);
* `double` (64-bit floating point).

Examples:

```scs
x -> [^"float: 435.2346"];;
x -> [^"int8: 7"];;
x -> [^"uint: 781236"];;
```

Preserve the `^`, quotes, type, and value syntax.

#### 6.2. Structures: `[* ... *]`

`[* ... *]` creates an SC-structure (`sc_node_structure`). All elements described inside receive incoming main arcs (`sc_main_arc`) from the structure node.

```scs
@structure = [*
  set -> item;;
*];;
```

The content follows the same syntax rules and semantics as SCs text in a separate file.

#### 6.3. Non-oriented sets: `{ ... }`

Curly braces provide a compact representation of a non-oriented set:

```scs
@set = {
  element1;
  attr2: element2;
  element3
};;
```

Entries are separated by `;`. The last entry has **no trailing semicolon**. Attribute notation is allowed, and set aliases can be nested or used inside other constructions.

#### 6.4. Oriented sets: `< ... >`

Angle brackets provide a compact representation of an oriented set:

```scs
@oriented_set = <
  element1;
  attr2: element2;
  element3
>;;
```

Entries are separated by `;`; the last entry has no trailing semicolon. Do not confuse this set notation with connector symbols: interpret it by syntactic context.

#### 6.5. Set aliases and nesting

Set aliases replace more verbose set/tuple constructions and can be nested or used as objects in relationships.

```scs
@meta_set = {
  {
    element1;
    attr2: element2
  };
  {
    element3;
    element4
  }
};;

element => nrel_relation: { element10 };;
```

Aliases for compound constructions can also be reused:

```scs
@first_arc = (set -> rrel_1: element1);;
@second_arc = (set -> element2);;
nrel_basic_sequence -> (@first_arc => @second_arc);;
```

## 3. Element-type identifiers

SCs-code can use type keynodes to specify element types. Common identifiers include:

* `sc_node`
* `sc_link`
* `sc_common_edge`
* `sc_common_arc`
* `sc_membership_arc`
* `sc_main_arc`
* `sc_node_tuple`
* `sc_node_structure`
* `sc_node_role_relation`
* `sc_node_non_role_relation`
* `sc_node_class`
* `sc_node_superclass`
* `sc_node_material`

For exact mappings between type identifiers, `ScType`, and SCs connector designations, consult: https://ostis-ai.github.io/sc-machine/scs/sc_element_types/

## 4. LLM parsing rules

When interpreting or converting SCs-code:

1. Recognize `;;` as the sentence terminator; preserve the distinct role of `;`.
2. Preserve identifier spelling, prefixes (`.`, `..`, `_`), and alias names (`@`).
3. Resolve aliases only within their file scope and only after their definition.
4. Preserve connector type, direction, and nesting.
5. Parse level 1 as explicit triples; level 2 as connector expressions; level 3 as restricted `:`/`::` abbreviations; level 4 as shared-source clauses; level 5 as implicit-subject internal sentences; level 6 as link, structure, and set aliases.
6. In level 5, the object immediately before `(* ... *)` is the subject of every internal sentence.
7. In level 6, distinguish strings and typed binary content, structures, non-oriented sets, and oriented sets.
8. Do not add a semicolon after the final entry inside `{ ... }` or `< ... >`.
9. Different syntax levels can coexist in one file.
10. When expanding compact syntax, preserve the represented semantic relationships. Do not invent parsing rules if the source does not specify them.

## 5. Source and version

Official SCs-code documentation: https://ostis-ai.github.io/sc-machine/scs/scs/

This reference summarizes the documented syntax for `sc-machine >= 0.9.0`. For version-specific parsing details, use the documentation matching the actual implementation.
"""

ABOUT_OSTIS = """
Краткая справка об OSTIS и SCs, составленная по официальной документации проекта sc-machine:

* OSTIS (Open Semantic Technology for Intelligent Systems) — технология для создания интеллектуальных систем на основе семантических графов знаний.
* sc-machine описана как графовая СУБД: она хранит, извлекает и изменяет графы знаний в общей памяти sc-memory и использует агентный подход для их обработки.
* В технологии OSTIS декларативные и процедурные знания представляются единым языком SC-code (Semantic Computer Code).
* SCs-code — текстовое представление SC-code. Текст состоит из предложений, разделяемых `;;`; документация описывает синтаксис с уровнями представления.
* На уровне 2 конструкция предложения имеет вид `<элемент> <коннектор> <элемент>;;`; составные коннекторы можно заключать в круглые скобки.
* SCs поддерживает комментарии `// ...` и `/* ... */`, а также идентификаторы с префиксами видимости и переменности.
* Самый популярный уровень синтаксиса — уровень 2 и выше. Для объяснения SCs-code используйте минимум уровень 2.

Эта справка суммирует документацию sc-machine >= 0.9.0. Точные правила синтаксиса и типы зависят от версии; если вопрос требует деталей, ориентируйся на ссылки:
* Общее описание sc-machine и OSTIS: https://ostis-ai.github.io/sc-machine/
* SCs-code (версия sc-machine >= 0.9.0): https://ostis-ai.github.io/sc-machine/scs/scs/
* Типы SC-элементов (версия sc-machine >= 0.10.0): https://ostis-ai.github.io/sc-machine/scs/sc_element_types/
"""

ABOUT_PREFIX = """
# About node prefix
concept_ : concept/class node
rrel : relation role node
nrel : non-role relation node
_ : variable node
@ : alias for node, link, or construction
 """