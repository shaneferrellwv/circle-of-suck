import requests
import json
from datetime import datetime

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

def fetch_season_dates(year):
    response = core_api_call([f'/seasons/{year}'])
    start_date = response['startDate']
    end_date = response['endDate']
    return convert_date(start_date), convert_date(end_date)

def fetch_season_weeks(year):
    weeks = []
    response = core_api_call([f'/seasons/{year}/types/2/weeks'])
    for week_url in response['items']:
        weeks.append(pure_api_call(week_url['$ref']))
    return weeks

def fetch_week_events(week_events_url):
    events = []
    response = core_api_call(week_events_url)
    for event in response['items']:
        events.append(pure_api_call(event['$ref']))
    return events

def fetch_season_events(year):
    events = []
    weeks = fetch_season_weeks(year)
    i = 0
    for week in weeks:
        events.append(fetch_week_events(week['events']['$ref']))
    return events

def fetch_teams():
    teams = []
    repsonse = base_api_call(['/teams'])
    for team in repsonse['sports'][0]['leagues'][0]['teams']:
        teams.append(team['team']['displayName'])
    return teams
    


def parse_season_scoreboards(response):
    game_results = []
    upcoming_games = []
    return game_results, upcoming_games

if __name__ == "__main__":
    # pretty_print()
    print(fetch_teams())