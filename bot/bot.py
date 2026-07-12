import sys
import os
import requests
import json
import pickle
from datetime import datetime, timezone
from anytree import RenderTree
from anytree.util import commonancestors

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

def bot(SPORT, LEAGUE, SEASON_YEAR, SEASON_TYPE = 2, GROUP_EXTENSION = '', scrape_only=False):

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
        item_responses = []
        if 'groups' in root_response:
            groups_response = pure_api_call(root_response['groups']['$ref'])
            for item in groups_response['items']:
                item_response = pure_api_call(item['$ref'])
                group_node = GroupNode(item_response['name'], item_response['abbreviation'] if 'abbreviation' in item_response else None, root)
                groups_dict[group_node.name] = group_node
                item_responses.append(item_response)
            for item_response in item_responses:
                group_node = groups_dict[item_response['name']]
                construct_tree(group_node, item_response, groups_dict, teams_dict)
        elif 'children' in root_response:
            print("Scraping", root_response['name'] + '...')
            children_response = pure_api_call(root_response['children']['$ref'])
            for item in children_response['items']:
                item_response = pure_api_call(item['$ref'])
                group_node = GroupNode(item_response['name'], item_response['abbreviation'] if 'abbreviation' in item_response else None, root)
                groups_dict[group_node.name] = group_node
                item_responses.append(item_response)
            for item_response in item_responses:
                group_node = groups_dict[item_response['name']]
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

    # fetches completed (and upcoming) games and adds them to the Tree to the lowest common ancestor group node for the two teams
    def decorate_tree(root, groups_dict, teams_dict, finished_games_ids = set(), upcoming_games_ids = set()):

        print(f'\nFetching new {LEAGUE} {SEASON_YEAR} games...')

        current_week = fetch_current_week()
        print(f'Current Week: {current_week}\n')

        # for each team in our league hierarchy
        for name, team_node in teams_dict.items():
            print("Scraping", team_node.name + '...')
            
            # fetch team's schedule
            response = base_api_call([f'/teams/{team_node.id}/schedule?season={SEASON_YEAR}?pageSize={PAGE_SIZE}'])
            team_schedule = response['events']

            # for each game in the team's schedule
            for event in team_schedule:
                        
                # * skip games past week 8
                # if 'week' in event and int(event['week']['text'][5:]) > 8:
                #     continue

                # check if game was previously scraped
                if event['id'] not in finished_games_ids and event['competitions'][0]['status']['type']['completed']:

                    # get games from upcoming week
                    # if event['id'] not in upcoming_games_ids and not event['competitions'][0]['status']['type']['completed']:

                    # if 'week' in event and int(event['week']['text'][5:]) == 8:

                        # upcoming_games_ids.add(event['id'])

                        # # collect game info and results
                        # home_id = event['competitions'][0]['competitors'][0]['id']
                        # away_id = event['competitions'][0]['competitors'][1]['id']

                        # if home_id not in teams_dict or away_id not in teams_dict: # TODO: or date in the past!!! 
                        #     continue

                        # game_info = UpcomingGame(
                        #     event['id'],
                        #     event['date'],
                        #     event['week']['text'] if 'week' in event else '0',
                        #     teams_dict[home_id],
                        #     teams_dict[away_id],
                        # )
                        # insert_upcoming_game(game_info, groups_dict)
                        # print(game_info)
                    
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

    def make_tree(tree_path):
        # create root node of tree
        league_response = core_api_call('')
        league_name = league_response['name']
        league_abbreviation = league_response['abbreviation']
        root = GroupNode(league_name, league_abbreviation, None)
        groups_dict = {}
        groups_dict[root.name] = root

        print(f'Constructing {LEAGUE} {SEASON_YEAR} tree...\n')

        # construct the skeleton of the tree (conferences & teams)
        root_response = core_api_call([f'/seasons/{SEASON_YEAR}/types/{SEASON_TYPE}{GROUP_EXTENSION}'])
        tree, teams_dict, groups_dict = construct_tree(root, root_response, groups_dict)

        # decorate the tree skeleton with game results
        tree, finished_game_ids = decorate_tree(tree, groups_dict, teams_dict)
        
        # print the tree (debug purposes)
        print('\nLeague Structure:')
        for pre, fill, node in RenderTree(tree):
            print("%s%s" % (pre, node))
        print('Groups Dict:')
        for key, value in groups_dict.items():
            print(f'id: {key}, Group: {value.name}')
        print('Teams Dict:')
        for key, value in teams_dict.items():
            print(f'id: {key}, Team: {value.name}')
        print('Tree (with games):')
        print(Tree(tree, teams_dict, groups_dict, finished_game_ids))

        # save the tree (pickled)
        with open(tree_path, 'wb') as file:
            pickle.dump(tree, file)
            pickle.dump(teams_dict, file)
            pickle.dump(groups_dict, file)
            pickle.dump(finished_game_ids, file)
            
        return tree

    def load_tree(tree_path):
        with open(tree_path, 'rb') as file:
            tree = pickle.load(file)
            teams_dict = pickle.load(file)
            groups_dict = pickle.load(file)
            finished_game_ids = pickle.load(file)
            return tree, teams_dict, groups_dict, finished_game_ids

    # create data subdirectories if they don't already exist
    directory_path = f'data/{SPORT}/{LEAGUE}/{SEASON_YEAR}'
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    # if tree has not yet been constructed for this season
    tree_path = f'{directory_path}/tree.pkl'
    if not os.path.exists(tree_path):
        make_tree(tree_path)

    def fetch_tree():

        tree, teams_dict, groups_dict, finished_game_ids = load_tree(tree_path)

        print(f'Loaded {LEAGUE} {SEASON_YEAR} tree:')
        print(Tree(tree, teams_dict, groups_dict, finished_game_ids))

        tree, finished_game_ids = decorate_tree(tree, groups_dict, teams_dict, finished_game_ids)

        return Tree(tree, teams_dict, groups_dict, finished_game_ids)

    # ==================================================
    #                     automation
    # ==================================================

    def find_circles_of_suck(tree):

        def save_circle_of_suck(circle_of_suck, suck_subtree):
            
            suck_subtree['suck'] = circle_of_suck.to_dict()

            with open(suck_tree_path, 'w') as file:
                json.dump(suck_tree, file, indent=4)
        
        # open suck tree
        suck_tree_path = f'data/{SPORT}/{LEAGUE}/{SEASON_YEAR}/suck_tree.json'
        if not os.path.exists(suck_tree_path):
            with open(suck_tree_path, 'w') as file:
                # add leagues to suck tree
                suck_tree = {}
                # recursively add groups to suck tree
                def add_groups_to_suck_tree(group_node, subtree):
                    if not group_node.is_leaf and group_node.name not in subtree:
                        subtree[group_node.name] = {}
                    for child in group_node.children:
                        add_groups_to_suck_tree(child, subtree[group_node.name])
                add_groups_to_suck_tree(tree.root, suck_tree)
                json.dump(suck_tree, file)

        with open(suck_tree_path, 'r') as file:
            suck_tree = json.load(file)

        print('\nFinding circles of suck...\n')

        # recursively check each group node for circle of suck
        for group_node in tree.groups.values():

            print(f'Searching for {group_node.name} circle of suck...')

            # recursively traverse the suck tree to find the corresponding subtree for this group node
            suck_subtree = suck_tree
            for subgroup_node in group_node.path:
                # stop when we reach the corresponding group
                if group_node.name in suck_subtree:
                    suck_subtree = suck_subtree[group_node.name]
                    break
                # otherwise go deeper
                suck_subtree = suck_subtree[subgroup_node.name]

            # skip this group if circle of suck already exists or if it has too many teams
            if 'suck' in suck_subtree:
                print(f'Circle of suck already exists for {group_node.name}.\n')
                continue
            if len(group_node.leaves) > 50:
                print(f'Skipping {group_node.name} because it has more than 50 teams.\n')
                continue

            # find if circle of suck exists for this subtree
            circle_of_suck = suck(group_node)

            if circle_of_suck is not None:

                save_circle_of_suck(circle_of_suck, suck_subtree)

                # tweet

            # else:

                # find if potential circle of suck exists for this subtree
                # potential_circle_of_suck = resuck(group_node, tree.game_ids)

                # if potential_circle_of_suck is not None:

                    # save_potential_circle_of_suck(potential_circle_of_suck, suck_subtree)

                    # tweet


        return

    season_response = fetch_season()
    if not season_active(season_response):
        print(f'{SEASON_YEAR} {LEAGUE} is not currently active...')
        # return
    
    tree = fetch_tree()

    if not scrape_only:
        find_circles_of_suck(tree)

if __name__ == "__main__":
    sports = {
        'football': [
            {'nfl': {
                'season': '2025',
                'season_type': 2
            }},
            {'nfl': {
                'season': '2024',
                'season_type': 2
            }},
            {'nfl': {
                'season': '2023',
                'season_type': 2
            }},
            {'nfl': {
                'season': '2022',
                'season_type': 2
            }},
            {'nfl': {
                'season': '2021',
                'season_type': 2
            }},
            {'nfl': {
                'season': '2020',
                'season_type': 2
            }},
            {'college-football': {
                'season': '2025',
                'season_type': 2,
                'group': '/groups/90'
            }},
            {'college-football': {
                'season': '2024',
                'season_type': 2,
                'group': '/groups/90'
            }},
            {'college-football': {
                'season': '2023',
                'season_type': 2,
                'group': '/groups/90'
            }},
            {'college-football': {
                'season': '2022',
                'season_type': 2,
                'group': '/groups/90'
            }},
            {'college-football': {
                'season': '2021',
                'season_type': 2,
                'group': '/groups/90'
            }},
            {'college-football': {
                'season': '2020',
                'season_type': 2,
                'group': '/groups/90'
            }},
        ],
        'basketball': [
            {'mens-college-basketball': {
                'season': '2026',
                'season_type': 2
            }},
            {'mens-college-basketball': {
                'season': '2025',
                'season_type': 2
            }},
            {'mens-college-basketball': {
                'season': '2024',
                'season_type': 2
            }},
            {'mens-college-basketball': {
                'season': '2023',
                'season_type': 2
            }},
            {'mens-college-basketball': {
                'season': '2022',
                'season_type': 2
            }},
            {'mens-college-basketball': {
                'season': '2021',
                'season_type': 2
            }},
            {'womens-college-basketball': {
                'season': '2020',
                'season_type': 2,
                'group': '/groups/50'
            }},
            {'nba': {
                'season': '2026',
                'season_type': 2
            }},
            {'nba': {
                'season': '2025',
                'season_type': 2
            }},
            {'nba': {
                'season': '2024',
                'season_type': 2
            }},
            {'nba': {
                'season': '2023',
                'season_type': 2
            }},
            {'nba': {
                'season': '2022',
                'season_type': 2
            }},
            {'nba': {
                'season': '2021',
                'season_type': 2
            }},
            {'nba': {
                'season': '2020',
                'season_type': 2
            }},
        ],
        'baseball': [
            {'mlb': {
                'season': '2026',
                'season_type': 2
            }}
        ]
    }
    
    for sport, leagues in sports.items():

        for league in leagues:

            for league_name, details in league.items():

                season = details['season']
                season_type = details['season_type']
                group = details.get('group', '')

                bot(sport, league_name, season, season_type, group, scrape_only=True)


