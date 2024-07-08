import requests
from algorithm.circle_of_suck import suck
import json

def pretty_print(data):
    print(json.dumps(data, indent=4))

# ==================================================
#                API functionality
# ==================================================

KEY = '0efeacbf418144e8a8dee5defa2c205f'
PREFIX = 'replay'
BASE_URL = f'https://{PREFIX}.sportsdata.io/api/v3'
SPORT = '/cfb'
API_URL = f'{BASE_URL}{SPORT}/scores/json'

def api_call(params):
    params = '/'.join(params)
    api_url = f'{API_URL}{params}?key={KEY}'
    response = requests.get(api_url)
    response.raise_for_status()
    return response.json()

def fetch_current_season():
    response = api_call(['/currentseason'])
    return response

def fetch_current_week():
    response = api_call(['/currentweek'])
    return response

def fetch_season_type():
    response = api_call(['/currentseasontype'])
    return response

def fetch_season():
    current_season = fetch_current_season()
    season_type = fetch_season_type().lower()
    season = f'{current_season}{season_type}'
    return season

def fetch_schedules(season = fetch_season()):
    response = api_call(['/schedulesbasic', season])
    return response

def fetch_teams(conference = None, division = None):
    response = api_call(['/leaguehierarchy'])
    teams_list = []
    for group in response:
        if (conference == None or group['ConferenceName'] == conference) and (division == None or group['DivisionName'] == division):
            for team in group['Teams']:
                team_info = {
                    'id': team['TeamID'],
                    'school': team['School'],
                    'name': team['Name'],
                    'rank': team['CoachesRank']
                }
                teams_list.append(team_info)
    return teams_list

def parse_schedules(schedules = fetch_schedules(), teams = fetch_teams()):
    valid_team_ids = {team['id'] for team in teams}
    game_results = []
    upcoming_games = []
    for game in schedules:
        game_finished = game['Status'] == 'Final'
        game_scheduled = game['Status'] == 'Scheduled'
        conference_game = game['HomeTeamID'] in valid_team_ids and game['AwayTeamID'] in valid_team_ids
        if conference_game and game_finished:
            game_info = {
                'title': game['Title'],
                'date': game['Day'],
                'home_team_id': game['HomeTeamID'],
                'away_team_id': game['AwayTeamID'],
                'home_team': game['HomeTeamName'],
                'away_team': game['AwayTeamName'],
                'home_score': game['HomeTeamScore'],
                'away_score': game['AwayTeamScore']
            }
            game_results.append(game_info)
        elif conference_game and game_scheduled:
            game_info = {
                'title': game['Title'],
                'date': game['Day'],
                'home_team_id': game['HomeTeamID'],
                'away_team_id': game['AwayTeamID'],
                'home_team': game['HomeTeamName'],
                'away_team': game['AwayTeamName'],
            }
            upcoming_games.append(game_info)
    return game_results, upcoming_games

if __name__ == "__main__":
    # selection
    # sport = 'cfb'
    conference = 'Big 12'
    division = None

    # retrieve data
    season = fetch_season()
    current_week = fetch_current_week()
    schedules = fetch_schedules(season) # this contains ALL score info
    teams = fetch_teams(conference, division)
    pretty_print(teams)

    # parse data
    game_results, upcoming_games = parse_schedules(schedules, teams)

    # find existing circle of suck
    suck(game_results, teams)