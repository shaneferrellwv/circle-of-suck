from anytree import NodeMixin

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
        return f"{self.name} ({self.abbreviation})"

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

class CircleOfSuck:
    def __init__(self, group_name, cycle, results):
        self.group_name = group_name
        self.cycle = cycle
        self.results = results