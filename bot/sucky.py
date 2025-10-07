#!/usr/bin/env python3
"""
Hamiltonian-cycle finder on sports graphs (winner -> loser).
Optimized for n>30 using OR-Tools CP-SAT with a Circuit constraint.

Install:
  pip install ortools networkx

Tweak:
  TIME_LIMIT_SECONDS  # per-group wall time
"""

from __future__ import annotations
import json
import time
from typing import Dict, List, Tuple, Any, Optional
import networkx as nx
from ortools.sat.python import cp_model

# ======= easy knobs =======
TIME_LIMIT_SECONDS = 450.0     # per-group timeout; set < 60s for your requirement
PREFER_EARLIEST_GAME = True   # choose earliest game when multiple games exist per arc
FILTER_COMPLETED_ONLY = True  # respect completed_game_ids if present
VERBOSE = False               # set True for more debug prints
# ==========================

Game = Dict[str, Any]

# ---------- data helpers ----------
def load_data(obj_or_path: Any) -> Dict[str, Any]:
    if isinstance(obj_or_path, dict):
        return obj_or_path
    with open(obj_or_path, "r", encoding="utf-8") as f:
        return json.load(f)

def all_groups(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    def dfs(node: Dict[str, Any]):
        if node.get("type") == "group":
            out.append(node)
            for child in node.get("children", []) or []:
                dfs(child)
    dfs(root)
    return out

def collect_teams(node: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    teams: Dict[str, Dict[str, Any]] = {}
    def dfs(n: Dict[str, Any]):
        for t in n.get("teams", []) or []:
            teams[t["id"]] = t
        for c in n.get("children", []) or []:
            dfs(c)
    dfs(node)
    return teams

def collect_results(node: Dict[str, Any]) -> Dict[str, Game]:
    """Collect all result objects (id->game) under this node subtree."""
    seen: Dict[str, Game] = {}
    def dfs(n: Dict[str, Any]):
        for g in n.get("results", []) or []:
            seen[g["id"]] = g
        for c in n.get("children", []) or []:
            dfs(c)
    dfs(node)
    return seen

def normalize_game(g: Game) -> Game:
    home_id = g["home_id"]; away_id = g["away_id"]
    home_score = g["home_score"]; away_score = g["away_score"]
    if g["home_team_won"]:
        winner_id, loser_id = home_id, away_id
        winner_score, loser_score = home_score, away_score
    else:
        winner_id, loser_id = away_id, home_id
        winner_score, loser_score = away_score, home_score
    gg = dict(g)
    gg.update({
        "winner_id": winner_id, "loser_id": loser_id,
        "winner_score": winner_score, "loser_score": loser_score
    })
    return gg

def build_group_digraph(group_node: Dict[str, Any], root_completed: set) -> Tuple[nx.DiGraph, Dict[str, Dict[str, Any]]]:
    teams = collect_teams(group_node)
    results = collect_results(group_node)

    # completed ids: prefer group-level, fallback to root-level
    completed_here = set(group_node.get("completed_game_ids", []))
    completed = completed_here or root_completed

    G = nx.DiGraph()
    for tid, info in teams.items():
        G.add_node(tid, **info)

    for gid, raw in results.items():
        if FILTER_COMPLETED_ONLY and completed and gid not in completed:
            continue
        if raw["home_id"] not in teams or raw["away_id"] not in teams:
            continue
        g = normalize_game(raw)
        u, v = g["winner_id"], g["loser_id"]
        if G.has_edge(u, v):
            G[u][v]["games"].append(g)
        else:
            G.add_edge(u, v, games=[g])

    # deterministic per-arc game choice
    for u, v in G.edges():
        G[u][v]["games"].sort(key=lambda gg: (gg.get("week", 10**9), gg.get("date", "")))
        if not PREFER_EARLIEST_GAME:
            G[u][v]["games"].reverse()
    return G, teams

# ---------- fast gates (necessary) ----------
def necessary_gates(G: nx.DiGraph) -> Tuple[bool, str]:
    n = G.number_of_nodes()
    m = G.number_of_edges()
    if n < 2:
        return False, f"n={n} < 2"
    if m < n:
        return False, f"edges={m} < nodes={n}"
    for node in G.nodes():
        if G.in_degree(node) < 1 or G.out_degree(node) < 1:
            return False, f"node {G.nodes[node].get('abbreviation', node)} has in/out-degree 0"
    if not nx.is_strongly_connected(G):
        return False, "graph not strongly connected"
    return True, "ok"

def necessary_perfect_matching(G: nx.DiGraph) -> Tuple[bool, str]:
    """
    Necessary condition: existence of a permutation with one outgoing and one incoming
    per node => perfect matching in bipartite tail/head split.
    """
    from networkx.algorithms import bipartite as bp
    L = [f"L_{u}" for u in G.nodes()]
    R = [f"R_{u}" for u in G.nodes()]
    B = nx.DiGraph()  # will convert to undirected for matching
    BU = nx.Graph()
    BU.add_nodes_from(L, bipartite=0)
    BU.add_nodes_from(R, bipartite=1)
    for u, v in G.edges():
        BU.add_edge(f"L_{u}", f"R_{v}")
    # quick degree pre-checks
    for u in G.nodes():
        if BU.degree[f"L_{u}"] == 0 or BU.degree[f"R_{u}"] == 0:
            return False, "no perfect matching (isolated in bipartite)"

    match = bp.hopcroft_karp_matching(BU, top_nodes=set(L))
    # hopcroft_karp returns both sides; perfect if all L matched
    matched_L = sum(1 for x in L if x in match)
    if matched_L != len(L):
        return False, "no perfect matching (HK failed)"
    return True, "ok"

# ---------- CP-SAT solver ----------
def solve_hc_cpsat(G: nx.DiGraph, time_limit_s: float) -> Optional[List[str]]:
    """Return node-id cycle list or None."""
    nodes = list(G.nodes())
    idx_of = {u: i for i, u in enumerate(nodes)}
    id_of = {i: u for u, i in idx_of.items()}
    n = len(nodes)

    # gather candidate arcs (no self loops)
    arcs: List[Tuple[int,int]] = []
    for u, v in G.edges():
        if u == v:
            continue
        arcs.append((idx_of[u], idx_of[v]))
    if not arcs:
        return None

    model = cp_model.CpModel()
    x = {}  # (i,j) -> BoolVar
    for i, j in arcs:
        x[(i, j)] = model.NewBoolVar(f"x_{i}_{j}")

    # Degree constraints: exactly one out and one in per node
    for i in range(n):
        outs = [x[(i, j)] for (i2, j) in arcs if i2 == i]
        ins  = [x[(i2, i)] for (i2, j) in arcs if j == i]
        if not outs or not ins:
            return None  # impossible quickly
        model.Add(sum(outs) == 1)
        model.Add(sum(ins) == 1)

    # Circuit constraint to eliminate subtours automatically
    circuit_arcs = [(i, j, x[(i, j)]) for (i, j) in arcs]
    model.AddCircuit(circuit_arcs)

    # Symmetry breaking (small nudge): force the smallest-index node to have the
    # smallest-index chosen successor among its candidates.
    smallest = 0
    succs = sorted([j for (i, j) in arcs if i == smallest])
    if succs:
        for j in succs[1:]:
            # if x[0,j] then some earlier j' must be 0; emulate: x[0,j] <= 1 - sum(x[0,j'<j])
            earlier = [x[(smallest, jp)] for jp in succs if jp < j]
            if earlier:
                model.Add(sum(earlier) >= 1).OnlyEnforceIf(x[(smallest, j)])

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.01, float(time_limit_s))
    solver.parameters.num_search_workers = 8  # parallelize
    solver.parameters.cp_model_presolve = True
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # Extract selected arcs
    succ = {}
    for (i, j) in arcs:
        if solver.BooleanValue(x[(i, j)]):
            succ[i] = j

    # Reconstruct the cycle
    cycle_idx = [0]
    seen = {0}
    cur = 0
    while True:
        nxt = succ.get(cur)
        if nxt is None:
            return None
        if nxt == cycle_idx[0]:
            if len(seen) == n:
                break
            else:
                return None
        if nxt in seen:
            return None
        cycle_idx.append(nxt)
        seen.add(nxt)
        cur = nxt

    return [id_of[i] for i in cycle_idx]

def pick_edge_game(G: nx.DiGraph, u: str, v: str) -> Game:
    return G[u][v]["games"][0]

def describe_cycle(G: nx.DiGraph, cycle: List[str]) -> List[str]:
    lines = []
    k = len(cycle)
    for i in range(k):
        u = cycle[i]
        v = cycle[(i + 1) % k]
        g = pick_edge_game(G, u, v)
        winner = G.nodes[u]["name"]
        loser  = G.nodes[v]["name"]
        wsc = g["winner_score"]; lsc = g["loser_score"]
        wk = g.get("week", "?"); dt = g.get("date", "?"); gid = g.get("id", "?")
        lines.append(f"Week {wk}: {winner} {wsc} – {loser} {lsc}  (id={gid}, date={dt})")
    return lines

# ---------- driver ----------
def run(data: Dict[str, Any], time_limit_s: float = TIME_LIMIT_SECONDS) -> None:
    root_completed = set(data.get("completed_game_ids", []))
    for grp in all_groups(data):
        teams = collect_teams(grp)
        if len(teams) < 2:
            continue

        print("=" * 90)
        print(f"Group: {grp.get('name','?')}  (teams={len(teams)})")

        G, _ = build_group_digraph(grp, root_completed)

        ok, why = necessary_gates(G)
        if not ok:
            print(f"  ❌ Insufficient (necessary) conditions: {why}")
            continue

        ok2, why2 = necessary_perfect_matching(G)
        if not ok2:
            print(f"  ❌ Fails perfect-matching screen: {why2}")
            continue

        t0 = time.time()
        cycle = solve_hc_cpsat(G, time_limit_s)
        dt = time.time() - t0

        if cycle is None:
            print(f"  ⚠️  No Hamiltonian cycle found within {time_limit_s:.1f}s.")
            # Optional: quick degree preview
            degs = [(G.nodes[n].get('abbreviation', n), G.in_degree(n), G.out_degree(n)) for n in G.nodes()]
            degs.sort(key=lambda x: (x[1]+x[2], x[2], x[1]))
            if VERBOSE:
                print("  Degree preview:", ", ".join([f"{a}:{i}/{o}" for a,i,o in degs[:8]]), "...")
            continue

        abbr = [G.nodes[n]["abbreviation"] for n in cycle]
        print(f"  ✅ Hamiltonian cycle (n={len(cycle)}) found in {dt:.3f}s:")
        print("    Order:", " → ".join(abbr), f"→ {abbr[0]}")
        print("    Games:")
        for line in describe_cycle(G, cycle):
            print("     -", line)

def sucky(data):
    run(data)
