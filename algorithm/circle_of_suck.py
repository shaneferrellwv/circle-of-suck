import data as scores
from datetime import datetime
import networkx as nx
from python_tsp.heuristics import solve_tsp_lin_kernighan

import numpy as np
from scipy.sparse import csr_matrix, lil_matrix

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


# def atsp_to_stsp():
    

def circle_of_suck(graph):
    sparse_asymmetric_tsp_matrix = nx.adjacency_matrix(graph)
    # dense_symmetric_tsp_matrix = sparse_atsp_to_dense_stsp(sparse_asymmetric_tsp_matrix)
    # np.set_printoptions(threshold=np.inf, linewidth=np.inf)
    # print(dense_symmetric_tsp_matrix)

    teams = {idx: team for idx, team in enumerate(list(graph.nodes()))}
    print(teams)

    permutation, distance = solve_tsp_lin_kernighan(distance_matrix=dense_symmetric_tsp_matrix, verbose=True)
    print(permutation)
    print(distance)

    i = 0
    for game in permutation:
        winning_team = teams[permutation[i] % 30]
        losing_team = teams[permutation[i + 1] % 30]
        winning_score = graph[winning_team][losing_team]['winning_score']
        losing_score = graph[winning_team][losing_team]['losing_score']
        date = graph[winning_team][losing_team]['date']
        print(i)
        print(winning_team)
        print(losing_team)
        print(winning_score)
        print(losing_score)
        print(date)
        i = i + 1


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