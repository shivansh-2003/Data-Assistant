## graphify — RAG Knowledge Graph

This project has a graphify knowledge graph at `graphify-out/`. Use it as the primary RAG system before reading raw source files.

### When to query the graph

- **Architecture or codebase questions** — read `graphify-out/GRAPH_REPORT.md` first for god nodes and community structure
- **Finding where something is implemented** — query `graphify-out/graph.json` by node label instead of grepping raw files
- **Understanding relationships between modules** — traverse edges in the graph rather than tracing imports manually
- **Any question about "how does X work" or "where is Y defined"** — check the graph before opening files

### How to query

```python
# BFS from a concept - broad context
python3 -c "
import json
from networkx.readwrite import json_graph
import networkx as nx
from pathlib import Path

G = json_graph.node_link_graph(json.loads(Path('graphify-out/graph.json').read_text()), edges='links')
terms = ['your', 'search', 'terms']
scored = sorted([(sum(1 for t in terms if t in G.nodes[n].get('label','').lower()), n) for n in G.nodes()], reverse=True)
start = [n for _, n in scored[:3] if _ > 0]
visited, frontier = set(start), set(start)
for _ in range(3):
    nxt = set()
    for node in frontier:
        for nb in G.neighbors(node):
            if nb not in visited:
                nxt.add(nb)
                print(f'  {G.nodes[node][\"label\"]} --{G.edges[node,nb].get(\"relation\",\"\")}-> {G.nodes[nb][\"label\"]} [{G.nodes[nb].get(\"source_file\",\"\")}]')
    visited |= nxt; frontier = nxt
"
```

### Navigation hierarchy (use in order)

1. `graphify-out/GRAPH_REPORT.md` — god nodes, community map, surprising connections
2. `graphify-out/wiki/index.md` — per-community articles (if it exists)
3. `graphify-out/graph.json` — raw graph for programmatic traversal
4. Raw source files — only after the graph points you to a specific file/line

### Keeping the graph current

After modifying code files in this session, rebuild:
```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```
