from __future__ import annotations

import re

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

EDGE_TYPES = {
    "->", "<-", "=>", "<=", "<=>", "_=>", "?->", "-?>", "<-?", "_->",
    "<-_", "?=>", "-|>", "<|-", "_-|>", "<|-_", "?-|>", "<|-?", "?|>",
    "<|?", "_?|>", "<|?_", "..>", "<..", "_..>", "<.._", "?..>", "<..?",
    "..|>", "<|..", "_..|>", "<|.._", "?..|>", "<|..?", "/>", "</",
    "_/>", "</_", "?/>", "</?", "~>", "<~", "_~>", "<~_", "?~>", "<~?",
    "~?>", "<?~", "_~?>", "<?~_", "?~?>", "<?~?", "%>", "<%", "_%>",
    "<%_", "?%>", "<%?", "%?>", "<?%", "_%?>", "<?%_", "?%?>", "<?%?",
    "<?-", "<?-?", "?-?>",
}
_EDGE_TOKEN_PATTERN = "|".join(
    re.escape(edge_type)
    for edge_type in sorted(EDGE_TYPES, key=len, reverse=True)
)
SIMPLE_RELATION = re.compile(
    rf"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+({_EDGE_TOKEN_PATTERN})\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*;;\s*(?://.*)?$"
)
SIMPLE_NODE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*;;\s*(?://.*)?$")

GWF_STRUCTURE_NODES = (
    # SCg 2.0 (OSTIS standard) spelled node types, e.g.
    # "node/const/perm/general" as written by KBE and ostis tools.
    ("SCg general node", "node/const/perm/general"),
    ("SCg group node", "node/const/perm/group"),
    ("SCg relation node", "node/const/perm/relation"),
)

GWF_MEMBERSHIP_CONNECTORS = (
    # Connectors as they appear in real-world .gwf documents.
    ("SCg membership pair", "pair/const/pos/perm/orient/membership", "pair", "=>"),
    ("SCg oriented pair", "pair/const/-/perm/orient", "pair", "=>"),
    ("SCg unoriented pair", "pair/const/-/perm/noorien", "pair", "<=>"),
)

NODE_TYPES = (
    ("Undefined constant", "node/const/not_define"),
    ("Constant general node", "node/const/general_node"),
    ("Constant abstract node", "node/const/predmet"),
    ("Constant material node", "node/const/material"),
    ("Constant structural node", "node/const/nopredmet"),
    ("Constant tuple node", "node/const/symmetry"),
    ("Constant role node", "node/const/attribute"),
    ("Constant relation node", "node/const/relation"),
    ("Constant asymmetric tuple node", "node/const/asymmetry"),
    ("Constant atom node", "node/const/atom"),
    ("Constant group node", "node/const/group"),
    ("Undefined variable", "node/var/not_define"),
    ("Variable general node", "node/var/general_node"),
    ("Variable abstract node", "node/var/predmet"),
    ("Variable material node", "node/var/material"),
    ("Variable structural node", "node/var/nopredmet"),
    ("Variable tuple node", "node/var/symmetry"),
    ("Variable role node", "node/var/attribute"),
    ("Variable relation node", "node/var/relation"),
    ("Variable asymmetric tuple node", "node/var/asymmetry"),
    ("Variable atom node", "node/var/atom"),
    ("Variable group node", "node/var/group"),
    ("Undefined meta node", "node/meta/not_define"),
    ("Meta general node", "node/meta/general_node"),
    ("Meta abstract node", "node/meta/predmet"),
    ("Meta structural node", "node/meta/nopredmet"),
    ("Meta tuple node", "node/meta/symmetry"),
    ("Meta asymmetric tuple node", "node/meta/asymmetry"),
    ("Meta role node", "node/meta/attribute"),
    ("Meta relation node", "node/meta/relation"),
    ("Meta atom node", "node/meta/atom"),
    ("Meta group node", "node/meta/group"),
) + GWF_STRUCTURE_NODES

CONNECTOR_TYPES = (
    ("Oriented relation", "arc/-/-", "arc", "->"),
    ("Constant positive permanent arc", "arc/const/pos", "arc", "->"),
    ("Variable positive permanent arc", "arc/var/pos", "arc", "_->"),
    ("Meta positive permanent arc", "arc/meta/pos", "arc", "?->"),
    ("Constant negative permanent arc", "arc/const/neg", "arc", "-|>"),
    ("Variable negative permanent arc", "arc/var/neg", "arc", "_-|>"),
    ("Meta negative permanent arc", "arc/meta/neg", "arc", "?-|>"),
    ("Constant fuzzy permanent arc", "arc/const/fuz", "arc", "/>"),
    ("Variable fuzzy permanent arc", "arc/var/fuz", "arc", "_/>"),
    ("Meta fuzzy permanent arc", "arc/meta/fuz", "arc", "?/>"),
    ("Constant positive temporary arc", "arc/const/pos/temp", "arc", "..>"),
    ("Variable positive temporary arc", "arc/var/pos/temp", "arc", "_..>"),
    ("Meta positive temporary arc", "arc/meta/pos/temp", "arc", "?..>"),
    ("Constant negative temporary arc", "arc/const/neg/temp", "arc", "..|>"),
    ("Variable negative temporary arc", "arc/var/neg/temp", "arc", "_..|>"),
    ("Meta negative temporary arc", "arc/meta/neg/temp", "arc", "?..|>"),
    ("Constant fuzzy temporary arc", "arc/const/fuz/temp", "arc", "~?>"),
    ("Variable fuzzy temporary arc", "arc/var/fuz/temp", "arc", "_~?>"),
    ("Meta fuzzy temporary arc", "arc/meta/fuz/temp", "arc", "?~?>"),
    ("Undirected pair", "pair/noorient", "pair", "<=>"),
    ("Oriented pair", "pair/orient", "pair", "=>"),
    ("Constant undirected pair", "pair/const/synonym", "pair", "<=>"),
    ("Variable undirected pair", "pair/var/noorient", "pair", "<=>"),
    ("Meta undirected pair", "pair/meta/noorient", "pair", "<=>"),
    ("Constant oriented pair", "pair/const/orient", "pair", "=>"),
    ("Variable oriented pair", "pair/var/orient", "pair", "?=>"),
    ("Meta oriented pair", "pair/meta/orient", "pair", "?=>"),
) + GWF_MEMBERSHIP_CONNECTORS


_NODE_STRUCTURE_ALIASES = {
    "not_define": "not_define",
    "general": "general",
    "general_node": "general",
    "predmet": "abstract",
    "abstract": "abstract",
    "material": "material",
    "terminal": "material",
    "nopredmet": "struct",
    "struct": "struct",
    "symmetry": "tuple",
    "asymmetry": "tuple",
    "attribute": "role",
    "role": "role",
    "relop": "relation",
    "relation": "relation",
    "group": "group",
    "atom": "group",
}

# The ostis-ai sc-builder gwf→scs converter
# (sc-tools/sc-builder/src/sc_scg_to_scs_types_converter.cpp) accepts only
# its own spellings: everything else throws "No matching sc.s-node type".
# Internal graph types keep the kbe legacy vocabulary; serialisation maps
# the stored type onto the nearest builder accepted spelling with the help
# of the tables below.
_BUILDER_TYPE_FIXES = {
    # "node/const/not_define" has no entry in the converter; KBE itself
    # aliases the constant undefined node onto "node/-/not_define".
    "node/const/not_define": "node/-/not_define",
    # "node/var/not_define" is likewise missing; the variable general node
    # produces the same sc_node and keeps the editor glyph on round trip.
    "node/var/not_define": "node/var/general_node",
    # Meta undefined nodes are not in any converter table either; the
    # sideless undefined node paints identically.
    "node/meta/not_define": "node/-/not_define",
    # Only "node/var/symmetry" is listed among legacy aliases.
    "node/const/symmetry": "node/const/tuple",
    # "atom" is absent from every converter table; KBE treats it as a group.
    "node/const/atom": "node/const/group",
    "node/var/atom": "node/var/group",
    # Meta arcs do not exist in the converter; KBE itself turns the
    # sc-meta membership arc into a meta pair.
    "arc/meta/pos": "pair/meta/pos/perm/orient/membership",
    "arc/meta/neg": "pair/meta/neg/perm/orient/membership",
    "arc/meta/fuz": "pair/meta/fuz/perm/orient/membership",
    "arc/meta/pos/temp": "pair/meta/pos/temp/orient/membership",
    "arc/meta/neg/temp": "pair/meta/neg/temp/orient/membership",
    "arc/meta/fuz/temp": "pair/meta/fuz/temp/orient/membership",
    # Three-part meta pairs are unknown; the converter supports the full
    # "pair/meta/-/<period>/<orientation>" spellings.
    "pair/meta/noorient": "pair/meta/-/perm/noorien",
    "pair/meta/orient": "pair/meta/-/perm/orient",
}

# Legacy structure names may appear in types loaded from kbe documents;
# they are rewritten onto the canonical converter structures.
_BUILDER_NODE_STRUCTURES = {
    "general": "general_node",
    "predmet": "struct",
    "nopredmet": "struct",
    "material": "terminal",
    "symmetry": "tuple",
    "asymmetry": "tuple",
    "atom": "group",
    "relop": "relation",
    "super_group": "superclass",
}

# Spelled ("node/<side>/<period>/<structure>") types accept the same
# structure tokens as the unsupported converter table, where "general"
# and "super_group" are the spelled forms and "superclass" is unknown.
_BUILDER_SPELLED_NODE_STRUCTURES = {
    "predmet": "struct",
    "nopredmet": "struct",
    "material": "terminal",
    "symmetry": "tuple",
    "asymmetry": "tuple",
    "atom": "group",
    "superclass": "super_group",
}

_BUILDER_META_CONNECTOR_ORIENTATIONS = {
    "orient": "orient",
    "membership": "orient",
    "noorien": "noorien",
    "noorient": "noorien",
    "synonym": "noorien",
}


def builder_safe_node_type(gwf_type: str) -> str:
    """Maps a stored node type onto a spelling the sc-builder accepts."""
    fixed = _BUILDER_TYPE_FIXES.get(gwf_type, gwf_type)
    parts = fixed.split("/")
    if not parts or parts[0] != "node" or len(parts) < 3:
        return fixed
    if len(parts) == 3:
        structure = _BUILDER_NODE_STRUCTURES.get(parts[2], parts[2])
        if parts[1] == "meta":
            # Meta nodes must be spelled with an explicit period segment.
            return f"node/meta/perm/{structure}"
        return f"{parts[0]}/{parts[1]}/{structure}"
    if len(parts) > 4:
        return fixed
    structure = _BUILDER_SPELLED_NODE_STRUCTURES.get(parts[3], parts[3])
    if structure == "not_define":
        return "node/-/not_define"
    return f"{parts[0]}/{parts[1]}/{parts[2]}/{structure}"


def builder_safe_connector_type(tag: str, gwf_type: str) -> str:
    """Maps a stored connector type onto a spelling the sc-builder accepts."""
    fixed = _BUILDER_TYPE_FIXES.get(gwf_type, gwf_type)
    parts = fixed.split("/")
    if len(parts) > 2 and parts[0] == tag and parts[1] == "meta":
        filtered = [
            segment for segment in parts[2:] if segment not in {"perm", "temp"}
        ]
        polarity = next(
            (token for token in ("pos", "neg", "fuz") if token in filtered),
            "",
        )
        orientation = (
            _BUILDER_META_CONNECTOR_ORIENTATIONS.get(filtered[-1], "orient")
            if filtered
            else "orient"
        )
        period = "temp" if "temp" in parts[2:] else "perm"
        if polarity:
            return f"pair/meta/{polarity}/{period}/orient/membership"
        return f"pair/meta/-/{period}/{orientation}"
    return fixed


def node_type_parts(gwf_type: str) -> tuple[str, str]:
    parts = gwf_type.split("/")
    if len(parts) < 2 or parts[0] != "node":
        return "const", "not_define"
    permanence = parts[1]
    # Skip period segment(s) ("perm", "temp") used by SCg 2.0 spelled types
    # such as "node/const/perm/general".
    structure_segments = [
        segment
        for segment in parts[2:]
        if segment not in {"perm", "temp"}
    ]
    structure = (
        structure_segments[-1] if structure_segments else "general"
    )
    structure = _NODE_STRUCTURE_ALIASES.get(structure, structure)
    if permanence == "meta":
        permanence = "const" if structure == "not_define" else "var"
    if permanence not in {"const", "var"}:
        permanence = "const"
    # kbe maps "node/var/not_define" onto the variable general node, the
    # small "not defined" circle is only used for constants
    if permanence == "var" and structure == "not_define":
        structure = "general"
    return permanence, structure


def connector_parts(tag: str, gwf_type: str) -> tuple[str, bool] | None:
    """Разбирает gwf-тип коннектора.

    Возвращает ("level_prefix", oriented), где level_prefix — "" для
    константных, "_" для переменных и "?" для мета-коннекторов, или None,
    если тип не распознан. Понимает и краткие kbe-формы
    ("pair/const/orient"), и полные SCg 2.0 записи
    ("pair/const/pos/perm/orient/membership", "pair/const/-/perm/noorien").
    """
    if tag not in {"arc", "pair"}:
        return None
    parts = gwf_type.split("/")
    if not parts or parts[0] != tag:
        return None
    permanence = parts[1] if len(parts) > 1 else ""
    if permanence in {"const", "var", "meta", "-"}:
        prefix = {"const": "", "var": "_", "meta": "?", "-": ""}[permanence]
        rest = parts[2:]
    elif len(parts) == 1:
        return "", False if tag == "pair" else True
    elif permanence in {"noorient", "orient", "synonym"}:
        return "", tag == "arc" or permanence == "orient"
    else:
        return None
    if not rest:
        return prefix, tag == "arc"
    polarity = rest[0] if rest[0] in {"pos", "neg", "fuz", "-"} else None
    if polarity is not None:
        rest = rest[1:]
    if tag == "arc" and not rest:
        return prefix, True
    period = rest[0] if rest and rest[0] in {"perm", "temp"} else None
    if period is not None:
        rest = rest[1:]
    if tag == "arc" and not rest:
        return prefix, True
    if tag == "arc":
        return prefix, rest[0] != "noorient" if rest else True
    # pair: последний сегмент задаёт направленность.
    orientation = rest[-1] if rest else "orient"
    oriented = orientation in {"orient", "membership"}
    if not oriented and orientation not in {"noorient", "noorien", "synonym"}:
        return None
    return prefix, oriented


def relation_for_gwf(tag: str, gwf_type: str) -> str:
    token = _GWF_RELATIONS.get((tag, gwf_type))
    if token is not None:
        return token
    parsed = connector_parts(tag, gwf_type)
    if parsed is None:
        return "->"
    prefix, oriented = parsed
    if tag == "arc":
        return "->"
    base = "=>" if oriented else "<=>"
    candidate = prefix + base
    if candidate in EDGE_TYPES:
        return candidate
    return base


_GWF_RELATIONS = {
    (tag, gwf_type): token
    for _, gwf_type, tag, token in CONNECTOR_TYPES
}
