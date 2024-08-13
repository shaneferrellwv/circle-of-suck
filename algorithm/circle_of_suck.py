from anytree import PreOrderIter
from algorithm.data import CircleOfSuck, GroupNode, TeamNode, Game

# check for any winless or undefeated teams
def hamiltonian_sufficiency_check(matrix):
    def has_win_and_loss(arr):
        has_one = False
        has_zero = False
        for value in arr:
            if value == 1:
                has_one = True
            elif value == 0:
                has_zero = True
            if has_one and has_zero:
                return True
        return False

    for row in matrix:
        if not has_win_and_loss(row):
            return False
    for col in range(len(matrix[0])):
        column = [matrix[row][col] for row in range(len(matrix))]
        if not has_win_and_loss(column):
            return False
    return True

def find_hamiltonian_cycle(adj_matrix):
    if hamiltonian_sufficiency_check(adj_matrix) is False:
        return None

    memo = {}
    path = []

    def visit(node, visited):
        # base case:
        # if all nodes are visited
        if visited == (1 << len(adj_matrix)) - 1:
            # and if there's an edge back to the start node
            if adj_matrix[node][0] == 1:
                # circle of suck found, add the first node to path
                path.append(0) 
                return True
            else:
                return False

        # get result if already cached
        if (node, visited) in memo:
            return memo[(node, visited)]

        # explore possible next nodes
        for next_node in range(len(adj_matrix)):
            # if next_node is connected to node and not yet visited
            if adj_matrix[node][next_node] == 1 and not (visited & (1 << next_node)):
                path.append(next_node)

                # recursive step:
                # explore from next_node
                if visit(next_node, visited | (1 << next_node)):
                    # cache the result
                    memo[(node, visited)] = True
                    return True
                
                # backtrack
                path.pop() 

        # cache failure to find hamiltonian cycle from this node
        memo[(node, visited)] = False
        return False

    # start search with node 0
    path.append(0)
    if visit(0, 1 << 0):
        return path
    else:
        return None
    
# TODO: to be used in the future for mid-season updates
def find_all_hamiltonian_paths(adj_matrix):
    memo = {}
    paths = []
    path = []

    def visit(node, visited):
        # base case: if all nodes are visited
        if visited == (1 << len(adj_matrix)) - 1:
            paths.append(path.copy())
            return

        # get result if already cached
        if (node, visited) in memo:
            return

        # explore possible next nodes
        for next_node in range(len(adj_matrix)):
            # if next_node is connected to node and not yet visited
            if adj_matrix[node][next_node] == 1 and not (visited & (1 << next_node)):
                path.append(next_node)
                # recursive step: explore from next_node
                visit(next_node, visited | (1 << next_node))
                # backtrack
                path.pop()

        # cache that this node and visited state has been fully explored
        memo[(node, visited)] = True

    # start search from each node to find all paths
    for start_node in range(len(adj_matrix)):
        path.append(start_node)
        visit(start_node, 1 << start_node)
        path.pop()

    return paths

def extract_games(root):
    games = []
    teams = []
    for node in PreOrderIter(root):
        if len(node.children) == 0:
            teams.append(node)
        else:
            for game in node.games:
                games.append(game)
    return games, teams

def construct_graph(games, teams):
    # create mapping to keep track of which team corresponds to each index
    team_to_index = {team.name: i for i, team in enumerate(teams)}

    # initialize zero-filled 2D array and set of edges
    num_teams = len(teams)
    adj_matrix = [[0] * num_teams for _ in range(num_teams)]
    edges = {}

    for game in games:
        home_index = team_to_index[game.home_team.name]
        away_index = team_to_index[game.away_team.name]
        
        if game.home_team_won == 'true':
            winner_index = home_index
            loser_index = away_index
        else:
            winner_index = away_index
            loser_index = home_index
        
        adj_matrix[winner_index][loser_index] = 1
        edges[(winner_index, loser_index)] = game

    return adj_matrix, edges

# function to find circle of suck from a league hierarchy tree decorated with games
# returns CircleOfSuck if circle of suck is found, returns None if no circle of suck found
def suck(root):
    games, teams = extract_games(root)
    adjacency_matrix, edges = construct_graph(games, teams)
    circle_of_suck = find_hamiltonian_cycle(adjacency_matrix)

    print(root.name)
    if circle_of_suck:
        group_name = root.name
        circle_of_suck =  CircleOfSuck(group_name, circle_of_suck, edges, teams)
        print(circle_of_suck)
    else:
        print("Unable to find Circle of Suck\n")
    
    return circle_of_suck