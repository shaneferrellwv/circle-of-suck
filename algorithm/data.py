import requests

BASE_URL = 'https://statsapi.mlb.com/api/v1'

def fetch_previous_scores(date):
    url = f'{BASE_URL}/schedule?sportId=1&season=2024&startDate=2024-03-30&endDate={date}'
    response = requests.get(url)

    if response.status_code == 200:
        schedule = response.json()
        games = schedule['dates']
        return games
    else:
        print(f"Failed to fetch data: {response.status_code} - {response.text}")