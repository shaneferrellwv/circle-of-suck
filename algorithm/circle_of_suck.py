from anytree import PreOrderIter
from bot.data import CircleOfSuck, GroupNode, TeamNode, Game
from datetime import datetime

def construct_graph_old(game_results, team_names):
    num_teams = len(team_names)
    team_to_index = {team['id']: i for i, team in enumerate(team_names)}
    adj_matrix = [[0] * num_teams for _ in range(num_teams)]
    edges = {}

    for game in game_results:
        if game['home_score'] is not None and game['away_score'] is not None:
            home_index = team_to_index[game['home_team_id']]
            away_index = team_to_index[game['away_team_id']]
            
            if game['home_score'] > game['away_score']:
                winner_index = home_index
                loser_index = away_index
                score = (game['home_score'], game['away_score'])
            else:
                winner_index = away_index
                loser_index = home_index
                score = (game['away_score'], game['home_score'])
            
            adj_matrix[winner_index][loser_index] = 1
            edges[(winner_index, loser_index)] = {
                'date': game['date'],
                'score': score
            }

    return adj_matrix, edges

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

# def find_potential_circles_of_suck(paths, teams, edges, upcoming_games = None):
#     if paths:
#         for path in paths:
#             ;

def print_potential_circles_of_suck(paths, teams, edges, upcoming_games = None):
    if paths:
        for path in paths:
            for i in range(len(path) - 1):
                u = path[i]
                v = path[i + 1]
                edge = edges[(u, v)]
                print(f"{teams[u]['school']} -> {teams[v]['school']} on {convert_date(edge['date'])} with score {edge['score']}")
            print('\n')
    else:
        print("Unable to find any potential Circles of Suck")

def convert_date(date_str):
    date_obj = datetime.strptime(date_str, '%Y-%m-%dT%H:%MZ')
    formatted_date = date_obj.strftime('%b %d, %Y').replace(" 0", " ")
    return formatted_date

def suck_old(game_results, teams):
    adjacency_matrix, edges = construct_graph(game_results, teams)
    circle_of_suck = find_hamiltonian_cycle(adjacency_matrix)
    # if circle_of_suck:
    print_circle_of_suck(circle_of_suck, teams, edges)
    # else:
    # potential_cirlces_of_suck = find_all_hamiltonian_paths(adjacency_matrix)
    # print_potential_circles_of_suck(potential_cirlces_of_suck, teams, edges)

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
    num_teams = len(teams)
    team_to_index = {team.name: i for i, team in enumerate(teams)}
    adj_matrix = [[0] * num_teams for _ in range(num_teams)]
    edges = {}

    for game in games:
        home_index = team_to_index[game.home_team.name]
        away_index = team_to_index[game.away_team.name]
        
        if game.home_score > game.away_score:
            winner_index = home_index
            loser_index = away_index
        else:
            winner_index = away_index
            loser_index = home_index
        
        adj_matrix[winner_index][loser_index] = 1
        edges[(winner_index, loser_index)] = game

    return adj_matrix, edges

def print_circle_of_suck(cycle, edges, teams, group_name):
    if cycle:
        print("Circle of Suck found:")
        index_to_team = {i: team for i, team in enumerate(teams)}
        for i in range(len(cycle) - 1):
            u = cycle[i]
            v = cycle[i + 1]
            game = edges[(u, v)]
            if game.home_score > game.away_score:
                winner_score = game.home_score
                loser_score = game.away_score
            else:
                winner_score = game.away_score
                loser_score = game.home_score
            print(f"{index_to_team[u].name} -> {index_to_team[v].name} on {convert_date(game.date)} with score {winner_score}-{loser_score}")
    else:
        print("Unable to find Circle of Suck")
    print()

def suck(root):
    games, teams = extract_games(root)
    adjacency_matrix, edges = construct_graph(games, teams)
    circle_of_suck = find_hamiltonian_cycle(adjacency_matrix)

    print(root.name)
    if circle_of_suck:
        group_name = root.name
        print_circle_of_suck(circle_of_suck, edges, teams, group_name)
        circle_of_suck =  CircleOfSuck(group_name, circle_of_suck, edges)
    
    return circle_of_suck