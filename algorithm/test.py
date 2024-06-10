def hamiltonian_cycle(graph):
    n = len(graph)
    memo = {}
    path = []

    def visit(node, visited):
        # If all nodes are visited, check if there's an edge back to the start node
        if visited == (1 << n) - 1:
            if graph[node][0] == 1:
                path.append(0)  # Add the start node to complete the cycle
                return True
            else:
                return False

        if (node, visited) in memo:
            return memo[(node, visited)]

        for next_node in range(n):
            if graph[node][next_node] == 1 and not (visited & (1 << next_node)):
                path.append(next_node)
                if visit(next_node, visited | (1 << next_node)):
                    memo[(node, visited)] = True
                    return True
                path.pop()  # Backtrack if the cycle is not completed

        memo[(node, visited)] = False
        return False

    # Start the search from node 0, with only node 0 visited
    path.append(0)
    if visit(0, 1 << 0):
        return path
    else:
        return None

import random

def generate_random_directed_graph(num_nodes, num_edges):
    graph = [[0] * num_nodes for _ in range(num_nodes)]
    edges = set()

    while len(edges) < num_edges:
        u = random.randint(0, num_nodes - 1)
        v = random.randint(0, num_nodes - 1)
        if u != v and (u, v) not in edges:
            edges.add((u, v))
            graph[u][v] = 1

    return graph

# Example to generate a random graph with 30 nodes and 500 edges
num_nodes = 30
num_edges = 200
graph = generate_random_directed_graph(num_nodes, num_edges)
print(graph)


result = hamiltonian_cycle(graph)
if result:
    print("Hamiltonian Cycle found:", result)
else:
    print("No Hamiltonian Cycle found")
