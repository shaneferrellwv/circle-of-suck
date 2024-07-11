import os
import requests
import json
import pickle
from anytree import NodeMixin, RenderTree, PreOrderIter
from anytree.util import commonancestors

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from algorithm.data import Tree, GroupNode, TeamNode, Game
from algorithm.circle_of_suck import suck

# ==================================================
#                 utility functions
# ==================================================

def pretty_print(data):
    print(json.dumps(data, indent=4))

def bot(SPORT, LEAGUE, SEASON_YEAR):

    # ==================================================
    #                    API calls
    # ==================================================

    PAGE_SIZE = 1000
    BASE_URL = 'https://site.api.espn.com/apis/site/v2/sports'
    CORE_URL = 'https://sports.core.api.espn.com/v2/sports'
    BASE_API_URL = f'{BASE_URL}/{SPORT}/{LEAGUE}'
    CORE_API_URL = f'{CORE_URL}/{SPORT}/leagues/{LEAGUE}'

    def pure_api_call(api_url):
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()

    def base_api_call(params):
        params = '/'.join(params)
        api_url = f'{BASE_API_URL}{params}'
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()

    def core_api_call(params):
        params = '/'.join(params)
        api_url = f'{CORE_API_URL}{params}'
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()

    # ==================================================
    #                   Data Scraping
    # ==================================================

    # recursive function to collect league hierarchy
    def construct_tree(root, root_response, groups_dict, teams_dict = {}):
        if 'groups' in root_response:
            groups_response = pure_api_call(root_response['groups']['$ref'])
            for item in groups_response['items']:
                item_response = pure_api_call(item['$ref'])
                group_node = GroupNode(item_response['name'], item_response['abbreviation'] if 'abbreviation' in item_response else None, root)
                groups_dict[group_node.name] = group_node
                construct_tree(group_node, item_response, groups_dict, teams_dict)
        elif 'children' in root_response:
            print("Scraping", root_response['name'] + '...')
            children_response = pure_api_call(root_response['children']['$ref'])
            for item in children_response['items']:
                item_response = pure_api_call(item['$ref'])
                group_node = GroupNode(item_response['name'], item_response['abbreviation'] if 'abbreviation' in item_response else None, root)
                groups_dict[group_node.name] = group_node
                construct_tree(group_node, item_response, groups_dict, teams_dict)
        else:
            print("Scraping", root_response['name'] + '...')
            teams_list = pure_api_call(root_response['teams']['$ref'])
            for team_response in teams_list['items']:
                team = pure_api_call(team_response['$ref'] + '?pageSize={PAGE_SIZE}')
                team_node = TeamNode(
                    team['id'],
                    team['displayName'],
                    team['abbreviation'] if 'abbreviation' in team else None,
                    team['logos'][0]['href'] if 'logos' in team else None,
                    root
                )
                teams_dict[team['id']] = team_node
        return root, teams_dict, groups_dict

    # adds game info to lowest common ancestor group node for the two teams
    def insert_game(game_info, groups_dict):
        home_team = game_info.home_team
        away_team = game_info.away_team
        group_name = commonancestors(home_team, away_team)[-1].name
        group_node = groups_dict[group_name]
        group_node.games.add(game_info)

    def decorate_tree(root, groups_dict, teams_dict, SEASON_YEAR):
        finished_games_ids = set()
        # for each team in our league hierarchy
        for name, team_node in teams_dict.items():
            print("Scraping", team_node.name + '...')
            
            # fetch team's schedule
            response = base_api_call([f'/teams/{team_node.id}/schedule?season={SEASON_YEAR}'])
            team_schedule = response['events']
            for event in team_schedule:

                # check if game was previously scraped
                if event['id'] not in finished_games_ids:
                    
                    # skip this game if we do not have info for one of the teams
                    home_id = event['competitions'][0]['competitors'][0]['id']
                    away_id = event['competitions'][0]['competitors'][1]['id']
                    if home_id not in teams_dict or away_id not in teams_dict:
                        continue
                    finished_games_ids.add(event['id'])

                    # collect game info and results
                    game_info = Game(
                        event['id'],
                        event['date'],
                        event['week']['text'],
                        teams_dict[home_id],
                        teams_dict[away_id],
                        int(event['competitions'][0]['competitors'][0]['score']['value']),
                        int(event['competitions'][0]['competitors'][1]['score']['value'])
                    )
                    insert_game(game_info, groups_dict)

        return root, finished_games_ids

    # ==================================================
    #                     pickling
    # ==================================================

    def fetch_tree(SEASON_YEAR, season_type = 2):
        # create data subdirectories if they don't already exist
        directory_path = f'data/{LEAGUE}/{SEASON_YEAR}'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            os.makedirs(directory_path + '/suck')

        tree_path = f'data/{LEAGUE}/{SEASON_YEAR}/tree.pkl'

        # if tree has already been constructed for this season
        if os.path.exists(tree_path):
            with open(tree_path, 'rb') as file:
                tree = pickle.load(file)
                teams_dict = pickle.load(file)
                groups_dict = pickle.load(file)
                finished_game_ids = pickle.load(file)

        # if tree has not been constructed for this season
        else:
            # create root node of tree
            league_response = core_api_call('')
            league_name = league_response['name']
            league_abbreviation = league_response['abbreviation']
            root = GroupNode(league_name, league_abbreviation, None)
            groups_dict = {}
            groups_dict[root.name] = root

            # construct the skeleton of the tree (conferences & teams)
            root_response = core_api_call([f'/seasons/{SEASON_YEAR}/types/{season_type}'])
            tree, teams_dict, groups_dict = construct_tree(root, root_response, groups_dict)

            # decorate the tree skeleton with game results
            tree, finished_game_ids = decorate_tree(tree, groups_dict, teams_dict, SEASON_YEAR)
            
            # print the tree (debug purposes)
            print('Tree:')
            for pre, fill, node in RenderTree(tree):
                print("%s%s" % (pre, node))
            print('Groups Dict:')
            for key, value in groups_dict.items():
                print(f'id: {key}, Group: {value.name}')
            print('Teams Dict:')
            for key, value in teams_dict.items():
                print(f'id: {key}, Team: {value.name}')
            print('Tree (with games):')
            for pre, fill, node in RenderTree(tree):
                print("%s%s" % (pre, node))
                if isinstance(node, GroupNode):
                    for item in node.games:
                        print(item)

            # save the tree
            with open(tree_path, 'wb') as file:
                pickle.dump(tree, file)
                pickle.dump(teams_dict, file)
                pickle.dump(groups_dict, file)
                pickle.dump(finished_game_ids, file)
        return Tree(tree, teams_dict, groups_dict, finished_game_ids)

    def save_circles_of_suck(tree, SEASON_YEAR):

        # encoder to write Circle of Suck, Team Nodes, and Game Nodes to JSON
        def custom_encoder(obj):
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        for name, group_node in tree.groups.items():
            # if circle of suck does not yet exist for this group
            group_path = group_node.name
            group_path = group_path.replace(' ', '_').lower()
            suck_path = f'data/{LEAGUE}/{SEASON_YEAR}/suck/{group_path}.json'
            if not os.path.exists(suck_path):
                # find if circle of suck exists for this subtree
                circle_of_suck = suck(group_node)

                # if circle of suck exists
                if circle_of_suck is not None:
                    # save circle of suck
                    with open(suck_path, 'w') as file:
                        json.dump(circle_of_suck, file, default=custom_encoder, indent=4)

                # TODO
                # else if no circle of suck exists
                    # if potential circles of suck exist
                        # save potential circles of suck
        return

    tree = fetch_tree(SEASON_YEAR)
    print(tree)
    save_circles_of_suck(tree, SEASON_YEAR)

if __name__ == "__main__":
    sport = 'football'
    league = 'nfl'
    season_year = 2023
    
    bot(sport, league, season_year)