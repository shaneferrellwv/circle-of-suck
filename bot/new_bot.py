import os
import json
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ==================================================
#                 utility functions
# ==================================================

def pretty_print(data):
    print(json.dumps(data, indent=4))

def to_new_york_time(timestr: str, fmt: str = "%Y-%m-%dT%H:%MZ") -> str:
    dt_utc = datetime.strptime(timestr, fmt).replace(tzinfo=ZoneInfo("UTC"))
    dt_ny = dt_utc.astimezone(ZoneInfo("America/New_York"))
    
    return dt_ny.strftime("%Y-%m-%dT%H:%M%z")

def todays_date_in_range(item):
    start_date_str = item['startDate']
    end_date_str = item['endDate']
    start_date = datetime.strptime(start_date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    current_date = datetime.now(timezone.utc)

    return start_date <= current_date <= end_date

def is_today(time_str: str, use_local_tz: bool = False) -> bool:
    dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    today = datetime.now(timezone.utc).date()
    return dt.date() == today

def today_is_past(item):
    start_date_str = item['startDate']
    start_date = datetime.strptime(start_date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    current_date = datetime.now(timezone.utc)

    return start_date <= current_date

def bot(LEAGUE_NAME, SPORT, SEASON_YEAR, SEASON_TYPE, GROUP_EXTENSION = ''):

    # ==================================================
    #                 pure API calls
    # ==================================================

    PAGE_SIZE = 1000
    BASE_URL = 'https://site.api.espn.com/apis/site/v2/sports'
    CORE_URL = 'https://sports.core.api.espn.com/v2/sports'
    BASE_API_URL = f'{BASE_URL}/{SPORT}/{LEAGUE_NAME}'
    CORE_API_URL = f'{CORE_URL}/{SPORT}/leagues/{LEAGUE_NAME}'

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
    #            tree and graph construction
    # ==================================================

    def make_league_tree():
        # league root
        league_response = core_api_call('')
        root = {
            "type": "group",
            "name": league_response.get("name"),
            "abbreviation": league_response.get("abbreviation")
        }

        # entry point for the given season/type
        root_response = core_api_call([f"/seasons/{SEASON_YEAR}/types/{SEASON_TYPE}{GROUP_EXTENSION}"])
        league_tree = construct_tree(root, root_response)

        return league_tree

    # recursive builder
    def construct_tree(node, node_response):
        # branch: nested groups via 'groups'
        if "groups" in node_response:
            groups_response = pure_api_call(node_response["groups"]["$ref"])
            for item in groups_response.get("items", []):
                item_response = pure_api_call(item["$ref"])
                child = {
                    "type": "group",
                    "name": item_response.get("name"),
                    "abbreviation": item_response.get("abbreviation"),
                }
                if 'children' not in node:
                    node['children'] = []
                node["children"].append(child)
                construct_tree(child, item_response)

        # branch: nested groups via 'children'
        elif "children" in node_response:
            print("Scraping", f"{node_response.get('name','<unnamed>')}...")
            children_response = pure_api_call(node_response["children"]["$ref"])
            for item in children_response.get("items", []):
                item_response = pure_api_call(item["$ref"])
                child = {
                    "type": "group",
                    "name": item_response.get("name"),
                    "abbreviation": item_response.get("abbreviation"),
                }
                if 'children' not in node:
                    node['children'] = []
                node["children"].append(child)
                construct_tree(child, item_response)

        # leaf: teams live here
        else:
            print("Scraping", f"{node_response.get('name','<unnamed>')}...")
            teams_ref = node_response.get("teams", {}).get("$ref")
            if not teams_ref:
                return node  # nothing to add
            teams_list = pure_api_call(teams_ref)
            for team_item in teams_list.get("items", []):
                team = pure_api_call(team_item["$ref"] + f"?pageSize={PAGE_SIZE}")
                if 'teams' not in node:
                    node['teams'] = []
                node["teams"].append({
                    "type": "team",
                    "id": team.get("id"),
                    "name": team.get("displayName"),
                    "abbreviation": team.get("abbreviation"),
                    "logo": (team.get("logos") or [{}])[0].get("href") if team.get("logos") else None
                })

        return node
    

    # adds game result to all ancestor group nodes of the teams
    def save_result(results, new_result):

        # constructs mapping from team to all its group nodes
        def build_index(root):
            index = {}
            
            def dfs(node, path):
                cur = path + [node]
                for t in node.get('teams', []):
                    index[t['id']] = {'team': t, 'path': cur}
                for child in node.get('children', []):
                    dfs(child, cur)
                    
            dfs(root, [])
            return index
        
        # return list of shared ancestors
        def _shared_ancestor_chain(paths):
            chain = []
            for nodes in zip(*paths):
                if len({id(n) for n in nodes}) == 1:
                    chain.append(nodes[0])
                else:
                    break
            return chain
        
        index = build_index(results)
        try:
            paths = [index[new_result['home_id']]['path'], index[new_result['away_id']]['path']]
        except KeyError as e:
            raise ValueError(f"Unknown team id: {e.args[0]}")
        chain = _shared_ancestor_chain(paths)
        if not chain:
            raise ValueError("No shared ancestor for the given team ids.")
        for node in chain:
            node.setdefault('results', []).append(new_result)
        results.setdefault('completed_game_ids', []).append(new_result['id'])
        return results
    
    # ==================================================
    #                   data scraping
    # ==================================================

    # fetches cached season info
    # only updates season info once per day
    def fetch_season_info():

        print('Updating season info')

        season_info_path = f"data/{LEAGUE_NAME}/{SEASON_YEAR}/{SEASON_TYPE}/season_info.json"

        # create season_info.json file if it doesn't exist yet
        os.makedirs(os.path.dirname(season_info_path), exist_ok=True)
        if not os.path.exists(season_info_path):
            with open(season_info_path, "x") as f:
                pass

        # fetch cached season info if it exists and was updated today
        with open(season_info_path, "r") as f:
            content = f.read().strip()
            if content:
                season_info = json.loads(content)
                if "last_updated" in season_info:
                    if is_today(season_info["last_updated"]):
                        print(f'\tusing season info updated at {to_new_york_time(season_info['last_updated'])}')
                        return season_info
                    else:
                        print(f'\t{LEAGUE_NAME} has not been refreshed since {to_new_york_time(season_info['last_updated'])}')

        # otherwise fetch today's season info
        print(f"Fetching {LEAGUE_NAME} {SEASON_YEAR} {SEASON_TYPE} season info...")

        # save it
        season_info = core_api_call([f"/seasons/{SEASON_YEAR}/types/{SEASON_TYPE}"])
        season_info["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        with open(season_info_path, "w") as f:
            json.dump(season_info, f, indent=4)

        return season_info
    
    # fetches cached league info
    # only updates at start of season
    def fetch_league_tree():

        league_tree_path = f"data/{LEAGUE_NAME}/{SEASON_YEAR}/{SEASON_TYPE}/league_tree.json"

        # create league_tree.json file if it doesn't exist yet
        os.makedirs(os.path.dirname(league_tree_path), exist_ok=True)
        if not os.path.exists(league_tree_path):
            with open(league_tree_path, "w") as f:
                pass

        # open league_tree.json file
        with open(league_tree_path, "r") as f:
            content = f.read().strip()

            # if it has not been constructed yet for this season, make it
            if not content:
                print(f"Fetching {LEAGUE_NAME} {SEASON_YEAR} {SEASON_TYPE} league structure...")
                league_tree = make_league_tree()

                # cache it
                with open(league_tree_path, "w") as f:
                    json.dump(league_tree, f, ensure_ascii=False, indent=4)

        # otherwise fetch league's info
        with open(league_tree_path, "r") as f:
            content = f.read().strip()
            league_tree = json.loads(content)

    def fetch_scores(current_week):

        results_path = f"data/{LEAGUE_NAME}/{SEASON_YEAR}/{SEASON_TYPE}/results.json"
        league_tree_path = f"data/{LEAGUE_NAME}/{SEASON_YEAR}/{SEASON_TYPE}/league_tree.json"

        # create results.json file if it doesn't exist yet
        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        if not os.path.exists(results_path):
            try:
                with open(league_tree_path, 'r') as f_in:
                    data = json.load(f_in) 
                    data.setdefault("completed_game_ids", [])
                    weeks = list(range(1, current_week + 1))
                with open(results_path, 'w') as f_out:
                    json.dump(data, f_out, indent=4)
                print(f"'{league_tree_path}' copied to '{results_path}' successfully.")
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON format in '{league_tree_path}'.")
            except Exception as e:
                print(f"An error occurred: {e}")
        else:
            weeks = [current_week]

        # fetch this season's results if it exists
        with open(results_path, "r") as f:
            content = f.read().strip()
            if content:
                results = json.loads(content)

        # fetch scoreboard per week
        for week in weeks:   
            # fetch scoreboard
            print(f"Fetching {LEAGUE_NAME} {SEASON_YEAR} {SEASON_TYPE} Week #{week} scoreboard...")
            scoreboard_response = base_api_call([f"/scoreboard?dates={SEASON_YEAR}&seasontype={SEASON_TYPE}&week={week}"])

            # find completed games that have not been scraped yet
            did_fetch_new_results = False
            for event in scoreboard_response['events']:
                if event['status']['type']['completed']:
                    if event['id'] not in results['completed_game_ids']:
                        did_fetch_new_results = True
                        # add it to results.json
                        new_result = {
                            'id': event['id'],
                            'date': event['date'],
                            'week': week,
                            'home_id': event['competitions'][0]['competitors'][0]['id'],
                            'home_name': event['competitions'][0]['competitors'][0]['team']['displayName'],
                            'home_score': int(event['competitions'][0]['competitors'][0]['score']),
                            'away_id': event['competitions'][0]['competitors'][1]['id'],
                            'away_name': event['competitions'][0]['competitors'][1]['team']['displayName'],
                            'away_score': int(event['competitions'][0]['competitors'][1]['score']),
                            'home_team_won': event['competitions'][0]['competitors'][0]['winner']
                        }
                        print(f"Saving completed game: {new_result['away_name']} vs {new_result['home_name']}: {new_result['away_score']} vs {new_result['home_score']}")
                        results = save_result(results, new_result)
                        pass
                else:
                    new_event = {
                        'id': event['id'],
                        'date': event['date'],
                        'week': week,
                        'home_id': event['competitions'][0]['competitors'][0]['id'],
                        'home_name': event['competitions'][0]['competitors'][0]['team']['displayName'],
                        'home_score': int(event['competitions'][0]['competitors'][0]['score']),
                        'away_id': event['competitions'][0]['competitors'][1]['id'],
                        'away_name': event['competitions'][0]['competitors'][1]['team']['displayName'],
                        'away_score': int(event['competitions'][0]['competitors'][1]['score']),
                    }
                    print(f"Awaiting final score: {new_event['away_name']} vs {new_event['home_name']}: {new_event['away_score']} vs {new_event['home_score']}")

        # update results.json
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=4)

        return did_fetch_new_results, results

    # ============= script entry here: ===============
        
    # get info for this season
    # contains 
    season_info = fetch_season_info()

    # check if season is active
    if not todays_date_in_range(season_info):
        return
    
    # get league structure
    fetch_league_tree()

    # update game results
    did_fetch_new_results, results = fetch_scores(current_week=season_info['week']['number'])

    if did_fetch_new_results:
        suck(results)

if __name__ == "__main__":
    leagues = [
        # {
        #     'name': 'nfl',
        #     'sport': 'football',
        #     'season_year': '2025',
        #     'season_type': 2,
        #     'group': '',
        # },
        {
            'name': 'college-football',
            'sport': 'football',
            'season_year': '2025',
            'season_type': 2,
            'group': '/groups/90',
        }
    ]

    # for each league
    for league in leagues:
        
        # run a bot instance
        bot(league['name'], league['sport'], league['season_year'], league['season_type'], league['group'])