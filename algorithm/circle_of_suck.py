import data as scores
from datetime import datetime
import networkx as nx
import numpy as np
from python_tsp.heuristics import solve_tsp_lin_kernighan    

def construct_graph(games):
    G = nx.DiGraph()

    for date in games:
        for game in date['games']:
            home_team = game['teams']['home']['team']['name']
            away_team = game['teams']['away']['team']['name']
            home_score = game['teams']['home'].get('score', 0)
            away_score = game['teams']['away'].get('score', 0)
            game_date = game['officialDate']
            margin = -abs(home_score - away_score)

            if home_score > away_score:
                winning_team = home_team
                losing_team = away_team
                winning_score = home_score
                losing_score = away_score
            elif away_score > home_score:
                winning_team = away_team
                losing_team = home_team
                winning_score = away_score
                losing_score = home_score

            G.add_edge(winning_team, losing_team, weight=margin, winning_score=winning_score, losing_score=losing_score, date=game_date)

    return G

def circle_of_suck(graph):
    matrix = nx.adjacency_matrix(graph)
    permutation, distance = solve_tsp_lin_kernighan(distance_matrix=matrix, verbose=True)
    print('Permutation: ', permutation)
    print('Distance: ', distance)

    node_list = list(graph.nodes)
    ordered_teams = [node_list[i] for i in permutation]
    
    print("Ordered teams based on TSP solution:")
    print(ordered_teams)

    for i in range(len(ordered_teams) - 1):
        winning_team = ordered_teams[i]
        losing_team = ordered_teams[i + 1]
        if graph.has_edge(winning_team, losing_team):
            attrs = graph[winning_team][losing_team]
        else:
            attrs = graph[losing_team][winning_team]
        
        print(f"{winning_team} defeated {losing_team} on {attrs['date']} with a score of {attrs['winning_score']}-{attrs['losing_score']}")

def main():
    # get today's scores
    date = datetime.now().strftime('%Y-%m-%d')
    game_results = scores.fetch_previous_scores(date=date)

    # construct graph from scores
    G = construct_graph(game_results)
    print(G)

    # find circle of suck
    circle_of_suck(G)

if __name__ == "__main__":
    main();