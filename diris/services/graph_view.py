"""Graph views + export for visualization (M14).

Reads the user's graph from Neo4j (via the graph store) and can serialize it to
GraphML for interoperability with tools like Gephi / yEd.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from ..db.models import User
from ..graph import get_graph_store


def get_full_graph(user: User, limit: int = 200) -> dict:
    return get_graph_store().full_graph(user.id, limit=limit)


def get_path(user: User, source_id: int, target_id: int) -> dict:
    return get_graph_store().shortest_path(user.id, source_id, target_id)


def to_graphml(graph: dict) -> str:
    """Serialize {nodes, edges} to a GraphML XML string."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="name" for="node" attr.name="name" attr.type="string"/>',
        '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
        '  <key id="rtype" for="edge" attr.name="type" attr.type="string"/>',
        '  <graph edgedefault="directed">',
    ]
    for node in graph["nodes"]:
        lines.append(
            f'    <node id="{node["entity_id"]}">'
            f'<data key="name">{escape(str(node["name"]))}</data>'
            f'<data key="type">{escape(str(node["type"]))}</data></node>'
        )
    for i, edge in enumerate(graph["edges"]):
        lines.append(
            f'    <edge id="e{i}" source="{edge["source"]}" target="{edge["target"]}">'
            f'<data key="rtype">{escape(str(edge["type"]))}</data></edge>'
        )
    lines += ["  </graph>", "</graphml>"]
    return "\n".join(lines)
