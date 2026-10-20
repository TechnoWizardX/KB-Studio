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
)

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
)


def node_type_parts(gwf_type: str) -> tuple[str, str]:
    parts = gwf_type.split("/")
    if len(parts) < 3 or parts[0] != "node":
        return "const", "not_define"
    permanence, structure = parts[1:3]
    structure = {
        "not_define": "not_define",
        "general_node": "general",
        "predmet": "abstract",
        "nopredmet": "struct",
        "symmetry": "tuple",
        "asymmetry": "tuple",
        "attribute": "role",
    }.get(structure, structure)
    if permanence == "meta":
        permanence = "const" if structure == "not_define" else "var"
    if permanence not in {"const", "var"}:
        permanence = "const"
    return permanence, structure


def relation_for_gwf(tag: str, gwf_type: str) -> str:
    return _GWF_RELATIONS.get((tag, gwf_type), "->")


_GWF_RELATIONS = {
    (tag, gwf_type): token
    for _, gwf_type, tag, token in CONNECTOR_TYPES
}
