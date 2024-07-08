import requests
import json
import copy
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
LEAGUE = 'college-football'
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

def fetch_latest_season():
    response = core_api_call(['/seasons'])
    season = pure_api_call(response['items'][0]['$ref'])
    return season['year'] 

def fetch_current_week():
    

def convert_date(iso_date):
    return datetime.strptime(iso_date, "%Y-%m-%dT%H:%MZ").strftime("%Y%m%d")

def update_games():
    # see if any games are finished that are not yet pickled
    current_season = fetch_latest_season()
    current_week = fetch_current_week()


    # pickle any newly-finshed unpickled games


     

if __name__ == "__main__":
    # get any games that just finished
    update_games()


    # find circle of suck



    # find potential circles of suck



    # if circle or potential circle, make graphic



    # share tweet