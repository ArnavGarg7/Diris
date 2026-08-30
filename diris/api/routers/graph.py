"""Graph visualization + export endpoints (M14). User-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse

from ...db.models import User
from ...services.graph_view import get_full_graph, get_path, to_graphml
from ..deps import get_current_user
from ..schemas import GraphEdgeOut, GraphNodeOut, GraphOut, PathOut

router = APIRouter(prefix="/graph", tags=["graph"])


def _graph_out(graph: dict) -> GraphOut:
    return GraphOut(
        nodes=[GraphNodeOut(**n) for n in graph["nodes"]],
        edges=[GraphEdgeOut(**e) for e in graph["edges"]],
    )


def _safe(fn):
    """Run a graph-store call, turning connection errors into 503."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Graph store unavailable: {exc}",
        )


@router.get("", response_model=GraphOut)
def full_graph(
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
) -> GraphOut:
    return _graph_out(_safe(lambda: get_full_graph(current_user, limit=limit)))


@router.get("/path", response_model=PathOut)
def path(
    source_id: int,
    target_id: int,
    current_user: User = Depends(get_current_user),
) -> PathOut:
    result = _safe(lambda: get_path(current_user, source_id, target_id))
    return PathOut(
        found=result["found"],
        nodes=[GraphNodeOut(**n) for n in result["nodes"]],
        edges=[GraphEdgeOut(**e) for e in result["edges"]],
    )


@router.get("/export")
def export_graph(
    format: str = Query("json", pattern="^(json|graphml)$"),
    limit: int = Query(1000, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
):
    graph = _safe(lambda: get_full_graph(current_user, limit=limit))
    if format == "graphml":
        return Response(
            content=to_graphml(graph),
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=graph.graphml"},
        )
    return graph  # JSON


@router.get("/view", response_class=HTMLResponse)
def graph_view() -> HTMLResponse:
    """A minimal standalone graph explorer (dev/preview tool; superseded by the M16 UI)."""
    return HTMLResponse(_VIEW_HTML)


_VIEW_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>DIRIS Graph</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  body{font-family:system-ui,sans-serif;margin:0}
  #bar{padding:10px;background:#111;color:#eee;display:flex;gap:8px;align-items:center}
  #bar input{flex:1;padding:6px;border-radius:4px;border:1px solid #555;background:#222;color:#eee}
  #bar button{padding:6px 14px;border:0;border-radius:4px;background:#3b82f6;color:#fff;cursor:pointer}
  #net{height:calc(100vh - 52px)}
  #msg{color:#f87171;padding:0 10px}
</style></head>
<body>
  <div id="bar">
    <span>Paste your JWT (from POST /auth/login):</span>
    <input id="token" placeholder="Bearer token"/>
    <button onclick="load()">Load graph</button>
    <span id="msg"></span>
  </div>
  <div id="net"></div>
<script>
const COLORS={PERSON:'#60a5fa',ORGANIZATION:'#34d399',LOCATION:'#fbbf24',EVENT:'#f472b6',
  CONCEPT:'#a78bfa',TECHNOLOGY:'#22d3ee',OBJECT:'#f97316',TOPIC:'#94a3b8',WORK:'#e879f9'};
async function load(){
  const t=document.getElementById('token').value.trim();
  const msg=document.getElementById('msg'); msg.textContent='';
  try{
    const r=await fetch('/graph?limit=500',{headers:{Authorization:'Bearer '+t}});
    if(!r.ok){msg.textContent='HTTP '+r.status;return;}
    const g=await r.json();
    const nodes=g.nodes.map(n=>({id:n.entity_id,label:n.name,title:n.type,
      color:COLORS[n.type]||'#94a3b8'}));
    const edges=g.edges.map(e=>({from:e.source,to:e.target,label:e.type,arrows:'to',font:{size:10}}));
    if(!nodes.length){msg.textContent='No entities yet — upload & process a document first.';}
    new vis.Network(document.getElementById('net'),
      {nodes:new vis.DataSet(nodes),edges:new vis.DataSet(edges)},
      {physics:{stabilization:true},nodes:{shape:'dot',size:14,font:{color:'#111'}}});
  }catch(err){msg.textContent=String(err);}
}
</script>
</body></html>"""
