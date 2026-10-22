import requests
import os                          # lets you read environment variables
import pyodbc                      # talks to the database (through the ODBC driver)
from dotenv import load_dotenv     # reads your .env file

load_dotenv()                      # loads DB_SERVER, DB_NAME... from .env

server = os.getenv("DB_SERVER")
database = os.getenv("DB_NAME")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")

connection_string = (
    "Driver={ODBC Driver 18 for SQL Server};"
    f"Server=tcp:{server},1433;"
    f"Database={database};"
    f"Uid={user};"
    f"Pwd={password};"
    "Encrypt=yes;"
)


class Champion:
    def __init__(self, id, name, internal_name, title, blurb, partype, tags):
        self.id = id
        self.name = name
        self.internal_name = internal_name
        self.title = title
        self.blurb = blurb
        self.partype = partype
        self.tags = tags


class ChampionStats:
    def __init__(self, internal_name, ratings, stats):
        self.internal_name = internal_name

        self.attack = ratings["attack"]
        self.defense = ratings["defense"]
        self.magic = ratings["magic"]
        self.difficulty = ratings["difficulty"]

        self.hp = stats["hp"]
        self.hp_per_level = stats["hpperlevel"]
        self.mp = stats["mp"]
        self.mp_per_level = stats["mpperlevel"]
        self.move_speed = stats["movespeed"]
        self.armor = stats["armor"]
        self.armor_per_level = stats["armorperlevel"]
        self.spellblock = stats["spellblock"]
        self.spellblock_per_level = stats["spellblockperlevel"]
        self.attack_range = stats["attackrange"]
        self.hp_regen = stats["hpregen"]
        self.hp_regen_per_level = stats["hpregenperlevel"]
        self.mp_regen = stats["mpregen"]
        self.mp_regen_per_level = stats["mpregenperlevel"]
        self.crit = stats["crit"]
        self.crit_per_level = stats["critperlevel"]
        self.attack_damage = stats["attackdamage"]
        self.attack_damage_per_level = stats["attackdamageperlevel"]
        self.attack_speed = stats["attackspeed"]
        self.attack_speed_per_level = stats["attackspeedperlevel"]


class PatchRepository:
    def __init__(self, patch):
        self.patch = patch
        self.champions = {}

    def add_champion(self, champion):
        self.champions[champion.internal_name] = {}
        self.champions[champion.internal_name]["champion"] = champion

    def add_stats(self, stats):
        self.champions[stats.internal_name]["stats"] = stats

    def get_all(self):
        return self.champions

class Repository:
    def __init__(self):
        self.repository = {}

    def get_all(self):
        return self.repository

    def add_patch(self, patchrepository):
        self.repository[patchrepository.patch] = patchrepository

response = requests.get("https://ddragon.leagueoflegends.com/api/versions.json")
patches = response.json()

latest_patch = patches[0]

repository = Repository()

for version in patches[:10]:

    response = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json")
    champion_data = response.json()["data"]

    repo = PatchRepository(version)

    for internal_name, info in champion_data.items():
        repo.add_champion(Champion(
            id=int(info["key"]),
            name=info["name"],
            internal_name=internal_name,
            title=info["title"],
            blurb=info["blurb"],
            partype=info["partype"],
            tags=info["tags"],
        ))
        repo.add_stats(ChampionStats(
            internal_name=internal_name,
            ratings=info["info"],
            stats=info["stats"],
        ))

    repository.add_patch(repo)

print(repository.get_all())
print(f"Patch {repository.get_all()[latest_patch].patch}: loaded {len(repository.get_all()[latest_patch].get_all())} champions")
print(f"{repository.get_all()[latest_patch].get_all()["Ahri"]["stats"]}")
print(f"{repository.get_all()[latest_patch].get_all()["Aatrox"]["champion"]}")

response = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest_patch}/data/en_US/champion.json")
champion_data = response.json()
print(champion_data)


conn = pyodbc.connect(connection_string)   # opens the connection to Azure
cursor = conn.cursor()                     # the object that runs SQL for you

cursor.fast_executemany = True


# -- patches --
# list_patches_tuples = []
# for patch in patches:
#     list_patches_tuples.append((patch,))
# cursor.executemany("INSERT INTO PATCH (PatchID) VALUES (?)", list_patches_tuples)
# conn.commit()

# -- champions --
# list_champion_tuples = []
# for champion in repository.get_all()[latest_patch].get_all():
#     champion_object = repository.get_all()[latest_patch].get_all()[champion]["champion"]
#     list_champion_tuples.append((champion_object.id, champion_object.name, champion_object.internal_name, champion_object.title, champion_object.blurb, champion_object.partype))
#
#
# cursor.executemany("INSERT INTO CHAMPION (ChampionID, Name, InternalName, Title, Blurb, Partype) VALUES (?, ?, ?, ?, ?, ?)", list_champion_tuples)
# conn.commit()


# -- championstats --
# list_champion_stats_tuples = []
# for patch1 in repository.get_all():
#     for champion in repository.get_all()[patch1].get_all():
#         stats_object = repository.get_all()[patch1].get_all()[champion]["stats"]
#         champion_object = repository.get_all()[patch1].get_all()[champion]["champion"]
#         if champion_object.id >= 60000:
#             continue
#         list_champion_stats_tuples.append((patch1, champion_object.id,
#                                            stats_object.attack,
#                                            stats_object.defense,
#                                            stats_object.magic,
#                                            stats_object.difficulty,
#
#                                            stats_object.hp,
#                                            stats_object.hp_per_level,
#                                            stats_object.mp,
#                                            stats_object.mp_per_level,
#                                            stats_object.move_speed,
#                                            stats_object.armor,
#                                            stats_object.armor_per_level,
#                                            stats_object.spellblock,
#                                            stats_object.spellblock_per_level,
#                                            stats_object.attack_range,
#                                            stats_object.hp_regen,
#                                            stats_object.hp_regen_per_level,
#                                            stats_object.mp_regen,
#                                            stats_object.mp_regen_per_level,
#                                            stats_object.crit,
#                                            stats_object.crit_per_level,
#                                            stats_object.attack_damage,
#                                            stats_object.attack_damage_per_level,
#                                            stats_object.attack_speed_per_level,
#                                            stats_object.attack_speed,
#                                            ))
#
# cursor.executemany("INSERT INTO Patch_Champion (PatchID, ChampionID, Attack, Defense, Magic, Difficulty, Hp, Hpperlevel, Mp, Mpperlevel, Movespeed, Armor, Armorperlevel, Spellblock, Spellblockperlevel, Attackrange, Hpregen, Hpregenperlevel, Mpregen, Mpregenperlevel, Crit, Critperlevel, Attackdamage, Attackdamageperlevel, Attackspeedperlevel, Attackspeed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", list_champion_stats_tuples)
# conn.commit()

print(repository.get_all()[latest_patch].get_all())

# -- tags --
# list_tags = []
# for champion in repository.get_all()[latest_patch].get_all():
#     champion_obj = repository.get_all()[latest_patch].get_all()[champion]["champion"]
#     for tag in champion_obj.tags:
#         if tag not in list_tags:
#             list_tags.append(tag)
#             cursor.execute("INSERT INTO Tag (TagName) VALUES (?)", tag)
#         cursor.execute("INSERT INTO Champion_Tag(ChampionID, TagID) VALUES (?,?)", (champion_obj.id, tag))
# conn.commit()
# conn.close()                               # always close when done

