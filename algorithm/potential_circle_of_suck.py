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

    n = len(adj_matrix)
    cycles = []
    path = [0]

    def visit(node, visited):
        # All vertices have been visited
        if visited == (1 << n) - 1:
            if adj_matrix[node][0] == 1:
                cycles.append(path.copy() + [0])
            return

        for next_node in range(1, n):
            if (
                adj_matrix[node][next_node] == 1
                and not visited & (1 << next_node)
            ):
                path.append(next_node)
                visit(next_node, visited | (1 << next_node))
                path.pop()

    visit(0, 1)
    return cycles

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