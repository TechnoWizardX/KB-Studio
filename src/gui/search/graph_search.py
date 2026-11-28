"""Searching SCg nodes and node classes.

The class filters are a small registry instead of a hard-coded ``if`` chain.
Adding ``#myclass`` is one :class:`NodeClassFilter` entry; an unknown
``#foo`` automatically falls back to "identifier starts with foo", so the
grammar stays useful even for project-specific naming conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.gui.graph_editor.graph_items import GraphNode
from src.gui.graph_editor.graph_types import node_type_parts


@dataclass(frozen=True)
class NodeClassFilter:
    key: str
    aliases: tuple[str, ...]
    label: str
    hint: str
    predicate: Callable[[GraphNode], bool]


def _structure(node: GraphNode) -> str:
    return node_type_parts(node.gwf_type)[1]


def _permanence(node: GraphNode) -> str:
    return node_type_parts(node.gwf_type)[0]


def _starts_with(prefix: str) -> Callable[[GraphNode], bool]:
    folded = prefix.casefold()
    return lambda node: node.identifier.casefold().startswith(folded)


def _has_structure(*structures: str) -> Callable[[GraphNode], bool]:
    wanted = set(structures)
    return lambda node: _structure(node) in wanted


NODE_CLASS_FILTERS: tuple[NodeClassFilter, ...] = (
    NodeClassFilter(
        "var",
        ("variable", "variables"),
        "Variable nodes",
        "node/var/... nodes",
        lambda node: node.gwf_type.startswith("node/var")
        or _permanence(node) == "var",
    ),
    NodeClassFilter(
        "const",
        ("constant", "constants"),
        "Constant nodes",
        "node/const/... nodes",
        lambda node: node.gwf_type.startswith("node/const")
        or _permanence(node) == "const",
    ),
    NodeClassFilter(
        "meta",
        ("metanode", "meta_node"),
        "Meta nodes",
        "node/meta/... nodes",
        lambda node: node.gwf_type.startswith("node/meta"),
    ),
    NodeClassFilter(
        "concept",
        ("concepts",),
        "Concepts",
        "identifiers starting with concept_",
        _starts_with("concept_"),
    ),
    NodeClassFilter(
        "nrel",
        ("nrels",),
        "nrel relations",
        "nrel_* identifiers or relation nodes",
        lambda node: node.identifier.casefold().startswith("nrel_")
        or _structure(node) == "relation",
    ),
    NodeClassFilter(
        "rrel",
        ("rrels",),
        "rrel roles",
        "rrel_* identifiers or attribute nodes",
        lambda node: node.identifier.casefold().startswith("rrel_")
        or _structure(node) == "attribute",
    ),
    NodeClassFilter(
        "relation",
        ("relations",),
        "Relation nodes",
        "structure: relation",
        _has_structure("relation"),
    ),
    NodeClassFilter(
        "attribute",
        ("attributes",),
        "Attribute nodes",
        "structure: attribute",
        _has_structure("attribute"),
    ),
    NodeClassFilter(
        "class",
        ("classes",),
        "Class nodes",
        "structure: class",
        _has_structure("class"),
    ),
    NodeClassFilter(
        "struct",
        ("structure", "structures"),
        "Structure nodes",
        "structure: struct",
        _has_structure("struct"),
    ),
    NodeClassFilter(
        "role",
        ("roles",),
        "Role nodes",
        "structure: role",
        _has_structure("role"),
    ),
    NodeClassFilter(
        "tuple",
        ("tuples",),
        "Tuple nodes",
        "structure: tuple",
        _has_structure("tuple"),
    ),
    NodeClassFilter(
        "atom",
        ("atoms",),
        "Atom nodes",
        "structure: atom",
        _has_structure("atom"),
    ),
    NodeClassFilter(
        "material",
        ("materials",),
        "Material nodes",
        "structure: material",
        _has_structure("material"),
    ),
    NodeClassFilter(
        "abstract",
        ("abstractions",),
        "Abstract nodes",
        "structure: abstract",
        _has_structure("abstract"),
    ),
)


@dataclass(frozen=True)
class ResolvedNodeFilter:
    """A parsed ``#...`` expression: a predicate plus an optional term."""

    label: str
    predicate: Callable[[GraphNode], bool]
    query: str = ""
    key: str = ""


def resolve_node_filter(text: str) -> ResolvedNodeFilter | None:
    """Turn ``var concept`` / ``prefix:concept_`` into a node predicate.

    Returns ``None`` for an empty expression so the caller can show the list
    of available filters.
    """
    text = text.strip()
    if not text:
        return None

    first, _, rest = text.partition(" ")
    rest = rest.strip()
    key = first.casefold()

    if key.startswith("prefix:"):
        prefix = first[len("prefix:") :]
        if not prefix:
            return None
        return ResolvedNodeFilter(
            label=f"identifier starts with {prefix}",
            predicate=_starts_with(prefix),
            query=rest,
            key=first,
        )

    if key.startswith("type:"):
        gwf_type = first[len("type:") :].casefold()
        if not gwf_type:
            return None
        return ResolvedNodeFilter(
            label=f"type contains {gwf_type}",
            predicate=lambda node: gwf_type in node.gwf_type.casefold(),
            query=rest,
            key=first,
        )

    for node_filter in NODE_CLASS_FILTERS:
        if key == node_filter.key or key in node_filter.aliases:
            return ResolvedNodeFilter(
                label=node_filter.label,
                predicate=node_filter.predicate,
                query=rest,
                key=node_filter.key,
            )

    # Unknown #foo: treat it as an identifier prefix. This keeps the grammar
    # open for project-specific conventions such as #my_domain_.
    return ResolvedNodeFilter(
        label=f"identifier starts with {first}",
        predicate=_starts_with(first),
        query=rest,
        key=first,
    )


def available_filters() -> list[tuple[str, str, str]]:
    """``(key, label, hint)`` tuples for the empty ``#`` suggestion list."""
    rows = [
        (node_filter.key, node_filter.label, node_filter.hint)
        for node_filter in NODE_CLASS_FILTERS
    ]
    rows.append(
        (
            "prefix:",
            "Custom prefix",
            "#prefix:concept_ — identifier prefix",
        )
    )
    rows.append(("type:", "Custom type", "#type:node/var — GWF type"))
    return rows


def node_content_text(node: GraphNode) -> str:
    try:
        return node._content_viewer_text()
    except Exception:  # pragma: no cover - content is user supplied
        return ""


def node_fields(node: GraphNode) -> tuple[str, ...]:
    return (
        node.identifier,
        node.gwf_idtf,
        node.gwf_type,
        node_content_text(node),
    )


def score_node(
    node: GraphNode, query: str, *, case_sensitive: bool = False
) -> int:
    """Relevance score for a node against a free-text query."""
    if not query:
        return 1
    needle = query if case_sensitive else query.casefold()

    def fold(value: str) -> str:
        return value if case_sensitive else value.casefold()

    identifier = fold(node.identifier)
    idtf = fold(node.gwf_idtf)
    content = fold(node_content_text(node))

    if identifier == needle:
        return 120
    if identifier.startswith(needle):
        return 100
    if needle in identifier:
        return 80
    if idtf == needle:
        return 75
    if idtf.startswith(needle):
        return 70
    if needle in idtf:
        return 55
    if needle in content:
        return 30
    return 0


def search_nodes(
    nodes,
    query: str,
    *,
    case_sensitive: bool = False,
    predicate: Callable[[GraphNode], bool] | None = None,
) -> list[GraphNode]:
    """Filter and rank *nodes* by free text and an optional predicate."""
    scored: list[tuple[int, float, float, str, GraphNode]] = []
    for node in nodes:
        if predicate is not None and not predicate(node):
            continue
        score = score_node(node, query, case_sensitive=case_sensitive)
        if score <= 0:
            continue
        position = node.scenePos()
        scored.append(
            (score, position.y(), position.x(), node.identifier.casefold(), node)
        )

    scored.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    return [item[-1] for item in scored]
