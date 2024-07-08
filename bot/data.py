import requests
import json
from datetime import datetime

# ==================================================
#                 utility functions
# ==================================================

def pretty_print(data):
    print(json.dumps(data, indent=4))

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

def convert_date(iso_date):
    return datetime.strptime(iso_date, "%Y-%m-%dT%H:%MZ").strftime("%Y%m%d")

def fetch_latest_season():
    response = core_api_call(['/seasons'])
    season = pure_api_call(response['items'][0]['$ref'])
    return season['year'] 

def fetch_season_dates(year):
    response = core_api_call([f'/seasons/{year}'])
    start_date = response['startDate']
    end_date = response['endDate']
    return convert_date(start_date), convert_date(end_date)

def fetch_season_weeks(year, season_type):
    weeks = []
    response = core_api_call([f'/seasons/{year}/types/{season_type}/weeks'])
    for week_url in response['items']:
        weeks.append(pure_api_call(week_url['$ref']))
    return weeks

def fetch_week_events(week_events_url):
    events = []
    response = core_api_call(week_events_url)
    for event in response['items']:
        events.append(pure_api_call(event['$ref']))
    return events

def fetch_season_events(year, season_type = 2):
    events = []
    weeks = fetch_season_weeks(year, season_type)
    for week in weeks:
        events.append(fetch_week_events(week['events']['$ref']))
    return events

def fetch_teams(year, conference_name = None, season_type = 2):
    def construct_tree(root, conferences_chain = []):
        teams = []
        if 'groups' in root:
            groups_response = pure_api_call(root['groups']['$ref'])
            for item in groups_response['items']:
                item_reponse = pure_api_call(item['$ref'])
                for team in construct_tree(item_reponse, conferences_chain.copy()):
                    teams.append(team)
        elif 'children' in root:
            print("Scraping", root['name'] + '...')
            conferences_chain.append(root['name'])
            children_response = pure_api_call(root['children']['$ref'])
            for item in children_response['items']:
                item_reponse = pure_api_call(item['$ref'])
                for team in construct_tree(item_reponse, conferences_chain.copy()):
                    teams.append(team)
        else:
            print("Scraping", root['name'] + '...')
            teams_list = pure_api_call(root['teams']['$ref'])
            conferences_chain.append(root['name'])
            for team_response in teams_list['items']:
                team = pure_api_call(team_response['$ref'] + '?pageSize={PAGE_SIZE}')
                team_info = {
                    'name': team['displayName'],
                    'abbreviation': team['abbreviation'],
                    'logo': team['logos'][0]['href'] if 'logos' in team else None,
                    'conferences': conferences_chain,
                }
                if conference_name is None or conference_name in conferences_chain:
                    teams.append(team_info)
        return teams
        
    fbs_response = core_api_call([f'/seasons/{year}/types/{season_type}'])
    return construct_tree(fbs_response)
    
def fetch_games(season_year, season_type = 2):
    game_ids = []
    games = []

    teams = fetch_teams(season_year, season_type)
    pretty_print(teams)
    # for team in teams:
    #     response = base_api_call([f'/teams/{team['abbreviation']}/schedule?season={season_year}'])

    #     for game in response['events']:
    #         game_id = game['id']
    #         if game_id not in game_ids:
    #             game_ids.append(game_id)

    #             for competitor in game['competitions'][0]['competitors']:
    #                 if competitor['homeAway'] == 'home':
    #                     home_team = {
    #                         'name': competitor['team']['displayName'],
    #                         'id': 
    #                     }

    #             game_info = {
    #                 'name': game['name'],
    #                 'date': game['date'],
                    
    #                 'completed': game['competitions'][0]['status']['type']['completed'],
    #             }
    return games

# ==================================================
#              initialize data tree
# ==================================================

if __name__ == "__main__":
    current_season = fetch_latest_season()
    # games = fetch_games(current_season)
    teams = fetch_teams(2023)
    pretty_print(teams)
    print(len(teams))