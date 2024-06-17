import requests

BASE_URL = 'https://statsapi.mlb.com/api/v1'

def fetch_mlb_data(api_url):
    response = requests.get(api_url)
    response.raise_for_status()  # raise error for bad response
    return response.json()

def parse_mlb_data(data):
    # extract game scores
    game_results = []
    for date_info in data['dates']:
        date = date_info['date']
        for game in date_info['games']:
            if game['gameType'] == 'R':  # ignore non-regular season games
                home_team = game['teams']['home']['team']['name']
                away_team = game['teams']['away']['team']['name']
                home_score = game['teams']['home'].get('score', 0)
                away_score = game['teams']['away'].get('score', 0)
                game_results.append({
                    'date': date,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': home_score,
                    'away_score': away_score
                })

    # extract team names
    team_names = set()
    for game in game_results:
        team_names.add(game['home_team'])
        team_names.add(game['away_team'])

    return game_results, list(team_names)

def print_parsed_games(games):
    for game in games:
        print(f"Date: {game['date']}")
        print(f"{game['away_team']} vs {game['home_team']}")
        print(f"Score: {game['away_score']} - {game['home_score']}")
        print()

def dates_by_season(league, season):
    

def fetch_season_data(league, division, season):
    start_date, end_date = dates_by_season(league, season)

    api_url = f'{BASE_URL}/schedule?sportId=1&season={season}&startDate=2024-03-30&endDate={date}'
    data = fetch_mlb_data(api_url)
    game_results, team_names = parse_mlb_data(data)
    return game_results, team_names