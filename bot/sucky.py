from collections import deque
from ortools.sat.python import cp_model

# ---------- core: works on 0..n-1 ----------
def _strongly_connected(n, edges):
    """Cheap SCC + degree sanity. edges: list[(u,v)] with 0<=u,v<n and u!=v."""
    adj = [[] for _ in range(n)]
    radj = [[] for _ in range(n)]
    indeg = [0]*n
    outdeg = [0]*n
    for u, v in edges:
        adj[u].append(v)
        radj[v].append(u)
        outdeg[u] += 1
        indeg[v] += 1

    # trivial impossibility
    if any(indeg[i] == 0 or outdeg[i] == 0 for i in range(n)):
        return False

    def bfs(graph, s):
        seen = [False]*n
        q = deque([s]); seen[s] = True
        while q:
            x = q.popleft()
            for y in graph[x]:
                if not seen[y]:
                    seen[y] = True
                    q.append(y)
        return seen

    start = 0
    if not all(bfs(adj, start)): return False
    if not all(bfs(radj, start)): return False
    return True

def _find_hc_indexed(n, edges, time_limit=30.0, workers=8):
    """
    Find Hamiltonian cycle over nodes 0..n-1 using CP-SAT AddCircuit.
    edges: list of (u,v), u!=v.
    Returns list of node indices in cycle order (length n) or None.
    """
    edges = [(u, v) for (u, v) in edges if 0 <= u < n and 0 <= v < n and u != v]
    if n == 0:
        return []
    if not _strongly_connected(n, edges):
        return None

    model = cp_model.CpModel()
    arc_vars = {}
    arcs_for_circuit = []
    in_cnt = [0]*n
    out_cnt = [0]*n
    for (u, v) in edges:
        x = model.NewBoolVar(f"x_{u}_{v}")
        arc_vars[(u, v)] = x
        arcs_for_circuit.append((u, v, x))
        out_cnt[u] += 1
        in_cnt[v] += 1

    if any(in_cnt[i] == 0 or out_cnt[i] == 0 for i in range(n)):
        return None

    # One single circuit visiting all nodes (no self-loops included).
    model.AddCircuit(arcs_for_circuit)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_search_workers = max(1, int(workers))
    solver.parameters.log_search_progress = True   # progress every few hundred ms
    # solver.EnableOutput()                          # route logs to stdout

    status = solver.Solve(model)
    print(solver.ResponseStats())                  # summary at the end
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    succ = [-1]*n
    for (u, v), var in arc_vars.items():
        if solver.Value(var) == 1:
            succ[u] = v

    # Build tour, canonical start at node 0
    tour = []
    cur = 0
    seen = set()
    for _ in range(n):
        if cur in seen or succ[cur] == -1:
            return None
        tour.append(cur)
        seen.add(cur)
        cur = succ[cur]
    if cur != 0:
        return None
    return tour

# ---------- wrapper: accepts arbitrary node labels ----------
def find_hamiltonian_cycle_labels(nodes, edges, *, time_limit=30.0, workers=8, strict=True, start="input"):
    """
    nodes: iterable of hashable labels (e.g., strings, ints).
    edges: iterable of (u_label, v_label) directed arcs.
    strict: if True, raise on edges referencing unknown labels; if False, ignore them.
    start: 'input' (cycle starts at the first node in `nodes`) or 'lex' (smallest label by str()).

    Returns: list of labels in cycle order or None if no Hamiltonian cycle exists.
    """
    # Preserve input order, de-duplicate
    labels = list(dict.fromkeys(nodes))
    index_of = {lab: i for i, lab in enumerate(labels)}
    n = len(labels)

    edges_idx = []
    unknown = set()
    for (u, v) in edges:
        if u not in index_of or v not in index_of:
            if strict:
                unknown.add(u if u not in index_of else v)
            continue  # if strict, we’ll raise after the loop; else silently drop
        if u != v:
            edges_idx.append((index_of[u], index_of[v]))

    if strict and unknown:
        raise ValueError(f"Edges reference unknown node labels: {sorted(unknown)!r}")

    idx_cycle = _find_hc_indexed(n, edges_idx, time_limit=time_limit, workers=workers)
    if idx_cycle is None:
        return None

    # Optionally rotate the cycle start
    if start == "lex":
        # Rotate so the lexicographically smallest label is first
        labels_cycle = [labels[i] for i in idx_cycle]
        k = min(range(n), key=lambda i: str(labels_cycle[i]))
        return labels_cycle[k:] + labels_cycle[:k]
    else:
        # 'input': starts at labels[0] because core starts at node 0
        return [labels[i] for i in idx_cycle]

# ---- example ----
if __name__ == "__main__":
    nodes = ["A","B","C","D","E"]
    edges = [
        ("A","B"),("B","C"),("C","D"),("D","E"),("E","A"),  # a Hamiltonian cycle
        ("A","C"),("B","D"),("C","E")                       # extras
    ]
    cycle = find_hamiltonian_cycle_labels(nodes, edges, start="lex")
    print("Cycle:", cycle)  # e.g., ['A','B','C','D','E']
