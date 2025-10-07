#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find Hamiltonian cycles in directed graphs built from sports results.

- Nodes: teams in a group (division/conference/etc.)
- Directed edges: winner -> loser for games in that group's `results`
- Each run stops at the first Hamiltonian cycle found or times out
- Prints the chain of games (teams, score, week) realizing the cycle

Usage:
  python find_hamiltonian_cycles.py path/to/data.json
  # or pipe JSON on stdin:
  cat data.json | python find_hamiltonian_cycles.py
"""

import argparse
import json
import sys
import time
from collections import defaultdict, deque

# === Tunables ===
TIME_LIMIT_SECONDS = 5.0  # <== easily changeable timeout per group
PICK_EARLIEST_GAME = True  # if multiple games for same edge, pick earliest by week/date

# ================= Utilities over the data =================

def _collect_team_map(group):
    """Return dict team_id -> {id, name, abbreviation, ...} for the entire subtree."""
    acc = {}
    def dfs(g):
        for t in g.get("teams", []) or []:
            acc[str(t["id"])] = t
        for ch in g.get("children", []) or []:
            dfs(ch)
    dfs(group)
    return acc

def _team_ids_in_group(group):
    """Return the set of team ids that belong to this group (direct or union of children)."""
    if group.get("teams"):
        return {str(t["id"]) for t in group["teams"]}
    # If a group has no direct teams, we take the union of its children's teams (so conferences still work)
    s = set()
    for ch in group.get("children", []) or []:
        s |= _team_ids_in_group(ch)
    return s

def _iter_groups(group, path=None):
    """
    Yield (path_str, group_obj) for all group nodes (including top-level),
    so we can attempt cycles at divisions, conferences, or any other group.
    """
    path = path or [f'{group.get("name","?")}']
    yield (" > ".join(path), group)
    for ch in group.get("children", []) or []:
        yield from _iter_groups(ch, path + [ch.get("name","?")])

def _normalize_results(results):
    """Ensure IDs are str; results may appear across multiple levels with duplicates by id."""
    seen = set()
    out = []
    for r in results or []:
        rid = str(r["id"])
        if rid in seen:
            continue
        seen.add(rid)
        rr = dict(r)
        rr["id"] = rid
        rr["home_id"] = str(rr["home_id"])
        rr["away_id"] = str(rr["away_id"])
        out.append(rr)
    return out

def _winner_loser(r):
    """Return (winner_id, loser_id, winner_score, loser_score)."""
    home_won = bool(r["home_team_won"])
    if home_won:
        return r["home_id"], r["away_id"], r["home_score"], r["away_score"]
    return r["away_id"], r["home_id"], r["away_score"], r["home_score"]

def _score_str(win_score, lose_score):
    return f"{win_score}-{lose_score}"

def _best_game(games):
    """Pick one game for an edge. Earliest by week then by date if requested; else arbitrary."""
    if not games:
        return None
    if PICK_EARLIEST_GAME:
        # Some records might miss 'week' or 'date', so handle robustly
        def keyfn(x):
            wk = x.get("week", 10**9)
            dt = x.get("date", "9999-12-31T23:59Z")
            return (wk, dt)
        return sorted(games, key=keyfn)[0]
    return games[0]

# ================= Graph construction =================

def build_group_graph(group, all_teams_in_subtree, completed_ids=None):
    """
    Build a directed multigraph for this group using only this group's results
    and only games where both teams are in all_teams_in_subtree.
    Returns:
        nodes (list of team_ids),
        adj (dict: u -> set(v)),
        indeg (dict), outdeg (dict),
        edge_games (dict: (u,v) -> list of result dicts),
        team_name (dict: team_id -> team_name)
    """
    completed_ids = set(map(str, completed_ids or []))
    team_ids = set(all_teams_in_subtree)
    nodes = sorted(team_ids)

    # Prepare containers
    adj = {u: set() for u in nodes}
    indeg = {u: 0 for u in nodes}
    outdeg = {u: 0 for u in nodes}
    edge_games = defaultdict(list)

    # Only the results directly attached to this group
    results = _normalize_results(group.get("results", []))

    # Filter to completed ids if provided (optional safety)
    if completed_ids:
        results = [r for r in results if r["id"] in completed_ids]

    for r in results:
        w, l, ws, ls = _winner_loser(r)
        if w in team_ids and l in team_ids:
            adj[w].add(l)
            outdeg[w] += 1
            indeg[l] += 1
            edge_games[(w, l)].append({
                "game_id": r["id"],
                "week": r.get("week"),
                "date": r.get("date"),
                "winner_id": w,
                "loser_id": l,
                "winner_score": ws,
                "loser_score": ls,
                "home_id": r.get("home_id"),
                "away_id": r.get("away_id"),
            })

    return nodes, adj, indeg, outdeg, edge_games

# ================= Feasibility / sufficiency checks =================

def _strongly_connected(nodes, adj):
    """Check strong connectivity via two BFS (forward and on reversed graph)."""
    if not nodes:
        return False
    # forward
    start = nodes[0]
    seen = set()
    dq = deque([start])
    while dq:
        u = dq.popleft()
        if u in seen: continue
        seen.add(u)
        for v in adj.get(u, ()):
            if v not in seen:
                dq.append(v)
    if len(seen) != len(nodes):
        return False
    # reverse
    radj = {u: set() for u in nodes}
    for u in nodes:
        for v in adj.get(u, ()):
            radj[v].add(u)
    seen = set()
    dq = deque([start])
    while dq:
        u = dq.popleft()
        if u in seen: continue
        seen.add(u)
        for v in radj.get(u, ()):
            if v not in seen:
                dq.append(v)
    return len(seen) == len(nodes)

def quick_checks(nodes, indeg, outdeg, adj):
    """
    Fast necessary checks. Return (ok, reason).
    If ok=False, there's no chance (we bail early).
    """
    n = len(nodes)
    if n < 2:
        return False, "Fewer than 2 teams."
    # Every node must have at least one in-edge and one out-edge
    for u in nodes:
        if outdeg.get(u, 0) == 0:
            return False, f"Team {u} has out-degree 0 (never beat any team in this group)."
        if indeg.get(u, 0) == 0:
            return False, f"Team {u} has in-degree 0 (never lost to any team in this group)."
    # Strong connectivity (necessary for a directed Hamiltonian cycle)
    if not _strongly_connected(nodes, adj):
        return False, "Graph is not strongly connected."
    # Optional: a sufficient condition for existence (if it holds, we can even skip the search)
    # Ghouila-Houri-style sufficient condition (loose check):
    # If for every node min(in_deg, out_deg) >= n/2 then Hamiltonian cycle exists.
    min_in = min(indeg.values())
    min_out = min(outdeg.values())
    if min(min_in, min_out) >= (n // 2 if n % 2 == 0 else (n // 2) + 0):  # integer-safe floor(n/2)
        return True, "Sufficient-degree condition met; cycle should exist."
    # Otherwise, proceed to search.
    return True, "Proceed to search."

# ================= Hamiltonian cycle search =================

def find_hamiltonian_cycle(nodes, adj, time_limit_sec):
    """
    Backtracking search with simple heuristics and a wall-clock timeout.
    Returns: list of node ids representing a cycle (v0..v_{n-1}, v0), or None.
    """
    start_time = time.time()
    n = len(nodes)
    if n == 0:
        return None

    # Order nodes by out-degree to start from the most constrained
    outdeg = {u: len(adj.get(u, ())) for u in nodes}
    start = min(nodes, key=lambda u: outdeg[u] if outdeg[u] > 0 else 10**9)
    path = [start]
    used = {start}

    # Precompute neighbor ordering: fewest out-degree first (fail-fast)
    neighbor_order_cache = {}
    def neighbors(u):
        if u in neighbor_order_cache:
            return neighbor_order_cache[u]
        nbrs = list(adj.get(u, ()))
        nbrs.sort(key=lambda v: (len(adj.get(v, ())), v))
        neighbor_order_cache[u] = nbrs
        return nbrs

    def timed_out():
        return (time.time() - start_time) > time_limit_sec

    def dfs(u):
        if timed_out():
            raise TimeoutError()
        if len(path) == n:
            # close the cycle?
            if path[0] in adj.get(u, ()):
                return True
            return False
        for v in neighbors(u):
            if v in used:
                continue
            # Trivial pruning: v must have at least one outgoing edge to some unvisited (or to start if it will be last)
            remaining = n - len(path) - 1
            if remaining == 0:
                # next must connect back to start
                if path[0] not in adj.get(v, ()):
                    continue
            else:
                # v must have some edge to unvisited nodes
                if not any((w not in used and w != v) for w in adj.get(v, ())):
                    continue
            used.add(v)
            path.append(v)
            if dfs(v):
                return True
            path.pop()
            used.remove(v)
        return False

    try:
        if dfs(start):
            return path + [path[0]]
    except TimeoutError:
        return None
    return None

# ================= Formatting output =================

def realize_cycle_games(cycle, edge_games, team_map):
    """
    For each edge in the node cycle, pick a specific game and render an entry.
    """
    chain = []
    for i in range(len(cycle) - 1):
        u, v = cycle[i], cycle[i+1]
        g = _best_game(edge_games.get((u, v), []))
        if not g:
            # Shouldn't happen if we built edges consistently, but guard anyway.
            chain.append({
                "from_team": team_map[u]["name"],
                "to_team": team_map[v]["name"],
                "week": None,
                "score": None,
                "game_id": None
            })
            continue
        score = _score_str(g["winner_score"], g["loser_score"])
        chain.append({
            "from_team": team_map[u]["name"],
            "to_team": team_map[v]["name"],
            "week": g.get("week"),
            "score": score,
            "game_id": g["game_id"]
        })
    return chain

# ================= Orchestration per group =================

def run_group(group_path, group_obj, team_map, completed_ids):
    """
    Build graph for this group and try to find a Hamiltonian cycle.
    Returns dict summarizing the attempt for this group.
    """
    teams_in_group = _team_ids_in_group(group_obj)
    # Only run if group has at least 2 teams and has results
    if len(teams_in_group) < 2 or not group_obj.get("results"):
        return {
            "group": group_path,
            "status": "skipped",
            "reason": "No teams or no results at this group."
        }

    nodes, adj, indeg, outdeg, edge_games = build_group_graph(
        group_obj, teams_in_group, completed_ids
    )

    # If there are teams but zero edges inside the group, bail.
    if sum(len(s) for s in adj.values()) == 0:
        return {
            "group": group_path,
            "status": "no-cycle",
            "reason": "No intra-group wins/losses (no edges)."
        }

    ok, reason = quick_checks(nodes, indeg, outdeg, adj)
    if not ok:
        return {
            "group": group_path,
            "status": "no-cycle",
            "reason": reason
        }

    # If the sufficient-degree condition was met, we still run the search to actually produce a cycle chain.
    cycle = find_hamiltonian_cycle(nodes, adj, TIME_LIMIT_SECONDS)

    if not cycle:
        # Could be timeout or simply no cycle. Be explicit if trivial cause exists.
        return {
            "group": group_path,
            "status": "no-cycle",
            "reason": "Timed out or no Hamiltonian cycle found within the limit."
        }

    chain = realize_cycle_games(cycle, edge_games, team_map)
    return {
        "group": group_path,
        "status": "found",
        "team_count": len(nodes),
        "cycle_nodes": cycle,  # list of team ids with wrap-around
        "chain": chain         # list of {from_team, to_team, week, score, game_id}
    }

# ================= Main =================

def main():
    global TIME_LIMIT_SECONDS
    parser = argparse.ArgumentParser(description="Hamiltonian cycle finder for sports data groups.")
    parser.add_argument("json_file", nargs="?", help="Path to JSON data file. If not given, reads stdin.")
    parser.add_argument("--timeout", type=float, default=TIME_LIMIT_SECONDS, help="Per-group timeout in seconds.")
    parser.add_argument("--print_all", action="store_true", help="Print results for all groups, not only 'found'/'no-cycle'.")
    args = parser.parse_args()

    TIME_LIMIT_SECONDS = args.timeout

    raw = None
    if args.json_file:
        with open(args.json_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = json.load(sys.stdin)

    # Root can be a single group object (like the NFL example)
    root = raw
    team_map = _collect_team_map(root)
    completed_ids = set(map(str, root.get("completed_game_ids", [])))

    results = []
    for path, grp in _iter_groups(root):
        res = run_group(path, grp, team_map, completed_ids)
        if args.print_all or res["status"] in ("found", "no-cycle"):
            results.append(res)

    # Pretty print JSON
    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")

if __name__ == "__main__":
    main()
