from anytree import PreOrderIter
from algorithm.data import PotentialCircleOfSuck, GroupNode, TeamNode, Game

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
    
def find_all_hamiltonian_cycles(adj_matrix):
    if hamiltonian_sufficiency_check(adj_matrix) is False:
        return []

    memo = {}
    path = []
    all_cycles = []

    def visit(node, visited):
        # base case:
        # if all nodes are visited
        if visited == (1 << len(adj_matrix)) - 1:
            # and if there's an edge back to the start node
            if adj_matrix[node][0] == 1:
                # valid cycle found, add the first node to complete the cycle
                all_cycles.append(path[:] + [0])
            return  # continue searching for other cycles

        # get result if already cached
        if (node, visited) in memo:
            return memo[(node, visited)]

        # explore possible next nodes
        for next_node in range(len(adj_matrix)):
            # if next_node is connected to node and not yet visited
            if adj_matrix[node][next_node] == 1 and not (visited & (1 << next_node)):
                path.append(next_node)

                # recursive step: explore from next_node
                visit(next_node, visited | (1 << next_node))

                # backtrack
                path.pop()

        # cache the exploration result (not used for early termination now)
        memo[(node, visited)] = False

    # start search with node 0
    path.append(0)
    visit(0, 1 << 0)

    return all_cycles

def extract_games(root):
    games = []
    teams = []
    for node in PreOrderIter(root):
        if len(node.children) == 0:
            teams.append(node)
        else:
            for game in node.games:
                games.append(game)
            for game in node.upcoming_games: 
                home_win = Game(
                    game.id,
                    game.date,
                    game.week,
                    game.home_team,
                    game.away_team,
                    0,
                    0,
                    True
                )
                away_win = Game(
                    game.id,
                    game.date,
                    game.week,
                    game.home_team,
                    game.away_team,
                    0,
                    0,
                    False
                )
                games.append(home_win)
                games.append(away_win)
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

# function to find potential circle of suck from a league hierarchy tree decorated with games
# returns CircleOfSuck if circle of suck is found, returns None if no circle of suck found
def resuck(root, finished_game_ids):
    games, teams = extract_games(root)
    adjacency_matrix, edges = construct_graph(games, teams)
    circles_of_suck = find_all_hamiltonian_cycles(adjacency_matrix)

    print(root.name)
    if len(circles_of_suck) > 0:
        group_name = root.name
        for potential_circle_of_suck in circles_of_suck:
            circle_of_suck = PotentialCircleOfSuck(group_name, potential_circle_of_suck, edges, teams, finished_game_ids)
            print("Potential Circle of Suck")
            print(circle_of_suck)
    else:
        print("Unable to find Potential Circle of Suck\n")
    
    return circle_of_suck