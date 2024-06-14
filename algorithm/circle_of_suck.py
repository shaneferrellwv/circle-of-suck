import requests

def fetch_mlb_data(api_url):
    response = requests.get(api_url)
    response.raise_for_status()  # raise error for bad response
    return response.json()

def parse_mlb_data(data):
    # extract game scores
    game_results = []
    for date_info in data['dates']:
        date = date_info['date']
        for game in date_info['games']:
            if game['gameType'] == 'R':  # ignore non-regular season games
                home_team = game['teams']['home']['team']['name']
                away_team = game['teams']['away']['team']['name']
                home_score = game['teams']['home'].get('score', 0)
                away_score = game['teams']['away'].get('score', 0)
                game_results.append({
                    'date': date,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': home_score,
                    'away_score': away_score
                })

    # extract team names
    team_names = set()
    for game in game_results:
        team_names.add(game['home_team'])
        team_names.add(game['away_team'])

    return game_results, list(team_names)

def print_parsed_games(games):
    for game in games:
        print(f"Date: {game['date']}")
        print(f"{game['away_team']} vs {game['home_team']}")
        print(f"Score: {game['away_score']} - {game['home_score']}")
        print()

def construct_graph(game_results, team_names):
    num_teams = len(team_names)
    team_to_index = {team: i for i, team in enumerate(team_names)}
    adj_matrix = [[0] * num_teams for _ in range(num_teams)]
    edges = {}

    for game in game_results:
        if game['home_score'] is not None and game['away_score'] is not None:
            home_index = team_to_index[game['home_team']]
            away_index = team_to_index[game['away_team']]
            
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

def print_parsed_data(graph, team_names, edges):
    n = len(graph)
    for i in range(n):
        print(f"{team_names[i]}:")
        for j in range(n):
            if graph[i][j] == 1:
                edge = edges[(i, j)]
                print(f"  -> {team_names[j]} on {edge['date']} with score {edge['score']}")
        print()

def suck(adj_matrix):
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

def print_circle_of_suck(cycle, team_names, edges):
    if cycle:
        print("Circle of Suck found:")
        for i in range(len(cycle) - 1):
            u = cycle[i]
            v = cycle[i + 1]
            edge = edges[(u, v)]
            print(f"{team_names[u]} -> {team_names[v]} on {edge['date']} with score {edge['score']}")
    else:
        print("Unable to find Circle of Suck")

if __name__ == "__main__":
    api_url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2024&startDate=2024-03-30&endDate=2024-06-12"
    data = fetch_mlb_data(api_url)
    game_results, team_names = parse_mlb_data(data)

    adjacency_matrix, edges = construct_graph(game_results, team_names)
    # print_parsed_data(adjacency_matrix, team_names, edges)

    circle_of_suck = suck(adjacency_matrix)
    print_circle_of_suck(circle_of_suck, team_names, edges)
