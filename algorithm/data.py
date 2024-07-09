from anytree import NodeMixin
from datetime import datetime

# ==================================================
#              custom data structures
# ==================================================

class GroupNode(NodeMixin):
    def __init__(self, name, abbreviation, parent=None):
        self.name = name
        self.abbreviation = abbreviation
        self.parent = parent
        self.games = set()

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    def __repr__(self):
        return self.__str__()

class TeamNode(NodeMixin):
    def __init__(self, id, name, abbreviation, logo=None, parent=None):
        self.id = id
        self.name = name
        self.abbreviation = abbreviation
        self.logo = logo
        self.parent = parent

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return self.__str__()

class Game(NodeMixin):
    def __init__(self, id, date, home_team, away_team, home_score, away_score):
        self.id = id
        self.date = date
        self.home_team = home_team
        self.away_team = away_team
        self.home_score = home_score
        self.away_score = away_score

    def __str__(self):
        return f"{self.date} {self.home_team.abbreviation} vs {self.away_team.abbreviation}: {self.home_score}-{self.away_score}"

    def __repr__(self):
        return self.__str__()
    
class Tree:
    def __init__(self, root, teams, groups, game_ids):
        self.root = root
        self.teams = teams
        self.groups = groups
        self.game_ids = game_ids

        
def convert_date(date_str):
    date_obj = datetime.strptime(date_str, '%Y-%m-%dT%H:%MZ')
    formatted_date = date_obj.strftime('%b %d, %Y').replace(" 0", " ")
    return formatted_date

class CircleOfSuck:
    def __init__(self, group_name, cycle, edges, teams):
        self.group_name = group_name
        self.teams = []
        self.games = []

        team_mapping = {i: team for i, team in enumerate(teams)}

        for index in cycle:
            self.teams.append(team_mapping[index])

        for i in range(len(cycle) - 1):
            u = cycle[i]
            v = cycle[i + 1]
            game = edges[(u, v)]
            self.games.append(game)

    def __str__(self):
        str = ''
        for game in self.games:
            if game.home_score > game.away_score:
                winning_team = game.home_team
                winner_score = game.home_score
                losing_team = game.away_team
                loser_score = game.away_score
            else:
                winning_team = game.away_team
                winner_score = game.away_score
                loser_score = game.home_score
                losing_team = game.home_team
            str += f'{convert_date(game.date)} {winning_team} -> {losing_team}: {winner_score}-{loser_score}\n'
        return str

    def __repr__(self):
        return self.__str__()