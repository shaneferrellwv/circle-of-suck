import requests
import json

def fetch_mlb_data(api_url):
    response = requests.get(api_url)
    response.raise_for_status()  # Raise an error for bad responses
    return response.json()

def parse_mlb_data(data):
    games = []
    for date_info in data['dates']:
        date = date_info['date']
        for game in date_info['games']:
            home_team = game['teams']['home']['team']['name']
            away_team = game['teams']['away']['team']['name']
            home_score = game['teams']['home'].get('score', 0)
            away_score = game['teams']['away'].get('score', 0)
            games.append({
                'date': date,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score
            })
    return games

def print_parsed_games(games):
    for game in games:
        print(f"Date: {game['date']}")
        print(f"{game['away_team']} vs {game['home_team']}")
        print(f"Score: {game['away_score']} - {game['home_score']}")
        print()

# Define the API URL
api_url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2024&startDate=2024-03-30&endDate=2024-06-12"

# Fetch and parse the MLB data
data = fetch_mlb_data(api_url)
parsed_games = parse_mlb_data(data)

# Print the parsed games
print_parsed_games(parsed_games)
