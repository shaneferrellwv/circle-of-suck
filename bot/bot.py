import os
import requests
import json
import pickle
from datetime import datetime, timezone
from anytree import RenderTree
from anytree.util import commonancestors

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from algorithm.data import Tree, GroupNode, TeamNode, Game, UpcomingGame
from algorithm.circle_of_suck import suck
from algorithm.potential_circle_of_suck import resuck

# ==================================================
#                 utility functions
# ==================================================

def pretty_print(data):
    print(json.dumps(data, indent=4))

def todays_date_in_range(item):
    start_date_str = item['startDate']
    end_date_str = item['endDate']
    start_date = datetime.strptime(start_date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    current_date = datetime.now(timezone.utc)

    return start_date <= current_date <= end_date

def bot(SPORT, LEAGUE, SEASON_YEAR, SEASON_TYPE, GROUP_EXTENSION = ''):

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

    def fetch_season():
        return core_api_call([f'/seasons/{SEASON_YEAR}/types/{SEASON_TYPE}'])
        
    def season_active(season_response):
        if season_response['type'] == SEASON_TYPE:
            if todays_date_in_range(season_response):
                return True
        return False
    
    def fetch_current_week():
        season_response = fetch_season()
        if 'week' in season_response:
            return season_response['week']['text']
        else:
            return 0

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

    # adds upcoming game info to lowest common ancestor group node for the two teams
    def insert_upcoming_game(game_info, groups_dict):
        home_team = game_info.home_team
        away_team = game_info.away_team
        group_name = commonancestors(home_team, away_team)[-1].name
        group_node = groups_dict[group_name]
        group_node.upcoming_games.add(game_info)

    def decorate_tree(root, groups_dict, teams_dict, SEASON_YEAR, finished_games_ids = set(), upcoming_games_ids = set()):
        current_week = fetch_current_week()

        # for each team in our league hierarchy
        for name, team_node in teams_dict.items():
            print("Scraping", team_node.name + '...')
            
            # fetch team's schedule
            response = base_api_call([f'/teams/{team_node.id}/schedule?season={SEASON_YEAR}?pageSize={PAGE_SIZE}'])
            team_schedule = response['events']
            for event in team_schedule:

                # check if game was previously scraped
                if event['id'] not in finished_games_ids and event['id'] not in upcoming_games_ids:

                    # get games from upcoming week
                    if not event['competitions'][0]['status']['type']['completed']:

                        if 'week' in event and event['week']['text'] == current_week:

                            upcoming_games_ids.add(event['id'])

                            # collect game info and results
                            home_id = event['competitions'][0]['competitors'][0]['id']
                            away_id = event['competitions'][0]['competitors'][1]['id']

                            game_info = UpcomingGame(
                                event['id'],
                                event['date'],
                                event['week']['text'] if 'week' in event else '0',
                                teams_dict[home_id],
                                teams_dict[away_id],
                            )
                            insert_upcoming_game(game_info, groups_dict)
                    
                    # skip this game if we do not have info for one of the teams
                    home_id = event['competitions'][0]['competitors'][0]['id']
                    away_id = event['competitions'][0]['competitors'][1]['id']
                    if home_id not in teams_dict or away_id not in teams_dict or 'score' not in event['competitions'][0]['competitors'][0] or 'score' not in event['competitions'][0]['competitors'][1] or 'winner' not in event['competitions'][0]['competitors'][0] or 'winner' not in event['competitions'][0]['competitors'][1]:
                        continue
                    # skip this game if it is not yet complete
                    if 'status' not in event['competitions'][0] or not event['competitions'][0]['status']['type']['completed']:
                        continue
                    finished_games_ids.add(event['id'])

                    # collect game info and results
                    game_info = Game(
                        event['id'],
                        event['date'],
                        event['week']['text'] if 'week' in event else '0',
                        teams_dict[home_id],
                        teams_dict[away_id],
                        int(event['competitions'][0]['competitors'][0]['score']['value']),
                        int(event['competitions'][0]['competitors'][1]['score']['value']),
                        event['competitions'][0]['competitors'][0]['winner']
                    )
                    insert_game(game_info, groups_dict)

        return root, finished_games_ids

    # ==================================================
    #                     pickling
    # ==================================================

    def fetch_tree(season_type = 2):

        def load_tree(tree_path):
            with open(tree_path, 'rb') as file:
                tree = pickle.load(file)
                teams_dict = pickle.load(file)
                groups_dict = pickle.load(file)
                finished_game_ids = pickle.load(file)
                return tree, teams_dict, groups_dict, finished_game_ids

        def make_tree(tree_path):
            # create root node of tree
            league_response = core_api_call('')
            league_name = league_response['name']
            league_abbreviation = league_response['abbreviation']
            root = GroupNode(league_name, league_abbreviation, None)
            groups_dict = {}
            groups_dict[root.name] = root

            # construct the skeleton of the tree (conferences & teams)
            root_response = core_api_call([f'/seasons/{SEASON_YEAR}/types/{season_type}{GROUP_EXTENSION}'])
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

        # create data subdirectories if they don't already exist
        directory_path = f'data/{LEAGUE}/{SEASON_YEAR}'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        # if tree has not yet been constructed for this season
        tree_path = f'{directory_path}/tree.pkl'
        if not os.path.exists(tree_path):
            make_tree(tree_path)

        tree, teams_dict, groups_dict, finished_game_ids = load_tree(tree_path)

        tree, finished_game_ids = decorate_tree(tree, groups_dict, teams_dict, SEASON_YEAR, finished_game_ids)

        return Tree(tree, teams_dict, groups_dict, finished_game_ids)

    def find_circles_of_suck(tree):

        def save_circle_of_suck(circle_of_suck):
            # add league to suck tree
            if SPORT not in suck_tree:
                suck_tree[SPORT] = {}
            suck_subtree = suck_tree[SPORT]
            if str(SEASON_YEAR) not in suck_subtree:
                suck_subtree[str(SEASON_YEAR)] = {}
            suck_subtree = suck_subtree[str(SEASON_YEAR)]
            for group in list(group_node.path):
                if group.name not in suck_subtree:
                    suck_subtree[group.name] = {}
                suck_subtree = suck_subtree[group.name]
            suck_subtree['suck'] = circle_of_suck.to_dict()

            with open(suck_tree_path, 'w') as file:
                json.dump(suck_tree, file, indent=4)
        
        # open suck tree
        suck_tree_path = 'data/suck_tree.json'
        with open(suck_tree_path, 'r') as file:
            suck_tree = json.load(file)

        for name, group_node in tree.groups.items():
            if len(group_node.leaves) < 50:
                # if circle of suck already exists, break and try next group
                circle_of_suck_exists = True
                if SPORT in suck_tree:
                    if str(SEASON_YEAR) in suck_tree[SPORT]:
                        current_item = suck_tree[SPORT][str(SEASON_YEAR)]
                        for node in list(group_node.path):
                            if node.name not in current_item:
                                circle_of_suck_exists = False
                                break
                            else:
                                current_item = current_item[node.name]
                        if circle_of_suck_exists:
                            if 'suck' in current_item:
                                break

                # find if circle of suck exists for this subtree
                circle_of_suck = suck(group_node)

                # if circle of suck exists
                if circle_of_suck is not None:
                    save_circle_of_suck(circle_of_suck)

                # TODO
                # else if no circle of suck exists
                else:
                    # find if potential circle of suck exists for this subtree
                    potential_circle_of_suck = resuck(group_node, tree.game_ids)
                    # if potential circles of suck exist
                        # save potential circles of suck
        return

    season_response = fetch_season()
    if season_active(season_response):
        tree = fetch_tree()
        find_circles_of_suck(tree)

if __name__ == "__main__":
    sports = {
        'football': [
            {'nfl': {
                'season': '2023',
                'season_type': 2
            }},
            {'college-football': {
                'season': '2023',
                'season_type': 2,
                'group': '/groups/90'
            }},
        ],
        'basketball': [
            {'mens-college-basketball': {
                'season': '2023',
                'season_type': 2
            }},
            {'womens-college-basketball': {
                'season': '2023',
                'season_type': 2,
                'group': '/groups/91'
            }},
            {'nba': {
                'season': '2023',
                'season_type': 2
            }}
        ],
        'baseball': [
            {'mlb': {
                'season': '2024',
                'season_type': 2
            }}
        ]
    }
    
    for sport, leagues in sports.items():
        for league in leagues:
            if isinstance(league, dict):
                for league_name, details in league.items():
                    season = details['season']
                    season_type = details['season_type']
                    group = details.get('group', '')

                    bot(sport, league_name, season, season_type, group)

