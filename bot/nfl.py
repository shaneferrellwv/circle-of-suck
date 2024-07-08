import os
import requests
import json
from datetime import datetime
from anytree import NodeMixin, RenderTree, PreOrderIter
from anytree.util import commonancestors
import pickle

# ==================================================
#                 utility functions
# ==================================================

def pretty_print(data):
    print(json.dumps(data, indent=4))

# ==================================================
#              custom data structures
# ==================================================

class GroupNode(NodeMixin):
    def __init__(self, name, abbreviation, parent=None):
        self.name = name
        self.abbreviation = abbreviation
        self.parent = parent
        self.games = set()

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    def __repr__(self):
        return self.__str__()

class TeamNode(NodeMixin):
    def __init__(self, id, name, abbreviation, logo=None, parent=None):
        self.id = id
        self.name = name
        self.abbreviation = abbreviation
        self.logo = logo
        self.parent = parent

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    def __repr__(self):
        return self.__str__()

class Game(NodeMixin):
    def __init__(self, id, date, home_team, away_team, home_score, away_score):
        self.id = id
        self.date = date
        self.home_team = home_team
        self.away_team = away_team
        self.home_score = home_score
        self.away_score = away_score

    def __str__(self):
        return f"{self.date} {self.home_team.abbreviation} vs {self.away_team.abbreviation}: {self.home_score}-{self.away_score}"

    def __repr__(self):
        return self.__str__()
    
class Tree:
    def __init__(self, root, groups, teams, game_ids):
        self.root = root
        self.groups = groups
        self.teams = teams
        self.game_ids = game_ids

# ==================================================
#                API functionality
# ==================================================

PAGE_SIZE = 1000

PREFIX = 'replay'
SPORT = 'football'
LEAGUE = 'nfl'
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
#                 API functionality
# ==================================================

def construct_tree(root, root_response, teams_dict = {}, groups_dict = {}):
    groups_dict[root.name] = root
    if 'groups' in root_response:
        groups_response = pure_api_call(root_response['groups']['$ref'])
        for item in groups_response['items']:
            item_reponse = pure_api_call(item['$ref'])
            group_node = GroupNode(item_reponse['name'], item_reponse['abbreviation'], root)
            groups_dict[group_node.name] = group_node
            construct_tree(group_node, item_reponse, teams_dict, groups_dict)
    elif 'children' in root_response:
        print("Scraping", root_response['name'] + '...')
        children_response = pure_api_call(root_response['children']['$ref'])
        for item in children_response['items']:
            item_reponse = pure_api_call(item['$ref'])
            group_node = GroupNode(item_reponse['name'], item_reponse['abbreviation'], root)
            groups_dict[group_node.name] = group_node
            construct_tree(group_node, item_reponse, teams_dict, groups_dict)
    else:
        print("Scraping", root_response['name'] + '...')
        teams_list = pure_api_call(root_response['teams']['$ref'])
        for team_response in teams_list['items']:
            team = pure_api_call(team_response['$ref'] + '?pageSize={PAGE_SIZE}')
            team_node = TeamNode(
                team['id'],
                team['displayName'],
                team['abbreviation'],
                team['logos'][0]['href'] if 'logos' in team else None,
                root
            )
            teams_dict[team['id']] = team_node
    return root, teams_dict, groups_dict

def insert_game(game_info, groups_dict):
    home_team = game_info.home_team
    away_team = game_info.away_team
    group_name = commonancestors(home_team, away_team)[-1].name
    group_node = groups_dict[group_name]
    group_node.games.add(game_info)

def decorate_tree(root, groups_dict, teams_dict, season_year):
    finished_games_ids = set()
    for name, team_node in teams_dict.items():
        print("Scraping", team_node.name + '...')
        response = base_api_call([f'/teams/{team_node.id}/schedule?season={season_year}'])
        team_schedule = response['events']
        for event in team_schedule:
            if event['id'] not in finished_games_ids:
                finished_games_ids.add(event['id'])
                game_info = Game(
                    event['id'],
                    event['date'],
                    teams_dict[event['competitions'][0]['competitors'][0]['id']],
                    teams_dict[event['competitions'][0]['competitors'][1]['id']],
                    int(event['competitions'][0]['competitors'][0]['score']['value']),
                    int(event['competitions'][0]['competitors'][1]['score']['value'])
                )
                insert_game(game_info, groups_dict)
    return root, finished_games_ids

# ==================================================
#                     pickling
# ==================================================

def fetch_tree(season_year, season_type = 2):
    tree_path = f'data/{LEAGUE}/{season_year}/tree.pkl'
    if os.path.exists(tree_path):
        with open(tree_path, 'rb') as file:
            tree = pickle.load(file)
            teams_dict = pickle.load(file)
            groups_dict = pickle.load(file)
            finished_game_ids = pickle.load(file)
    else:
        root = GroupNode('National Football League', 'NFL', None)
        root_response = core_api_call([f'/seasons/{season_year}/types/{season_type}'])
        tree, teams_dict, groups_dict = construct_tree(root, root_response)
        tree, finished_game_ids = decorate_tree(tree, groups_dict, teams_dict, season_year)
        
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

        with open(tree_path, 'wb') as file:
            pickle.dump(tree, file)
            pickle.dump(teams_dict, file)
            pickle.dump(groups_dict, file)
            pickle.dump(finished_game_ids, file)
    return Tree(tree, teams_dict, groups_dict, finished_game_ids)

if __name__ == "__main__":
    season_year = 2023
    nfl_tree = fetch_tree(season_year)
    for group in nfl_tree.groups:
        games = set()
        for node in PreOrderIter(group):
            
    