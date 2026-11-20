"""Game detection and game-specific tagging / prompt rules.
Ported from PeakCut (MIT) to support game stream clipping, including GTA VI launch presets.
"""

from __future__ import annotations
import re
from typing import Optional, List, Tuple

# name, words that mean it, tags to put on the post
GAMES: List[Tuple[str, List[str], List[str]]] = [
    ("Grand Theft Auto VI", ["grand theft auto vi", "grand theft auto 6", "gta vi", "gta 6", "gta6"],
     ["GTA6", "GTA6Game", "ViceCity", "RockstarGames", "GTA6Launch"]),
    ("Grand Theft Auto V", ["grand theft auto v", "grand theft auto 5", "gta online", "gta v", "gta 5", "gta5", "gtav"],
     ["GTA5", "GTAOnline", "RockstarGames", "GTA5RP"]),
    ("Grand Theft Auto IV", ["grand theft auto iv", "gta 4", "gta4"], ["GTA4", "RockstarGames"]),
    ("Fortnite", ["fortnite"], ["Fortnite", "FortniteOG", "BattleRoyale"]),
    ("Minecraft", ["minecraft"], ["Minecraft", "MinecraftGame"]),
    ("Valorant", ["valorant"], ["Valorant", "ValRadiant"]),
    ("League of Legends", ["league of legends", "league of legend"], ["LeagueOfLegends", "LoL", "RiotGames"]),
    ("Counter-Strike", ["counter-strike", "counter strike", "cs2", "csgo"], ["CS2", "CounterStrike", "Esports"]),
    ("Elden Ring", ["elden ring"], ["EldenRing", "SoulsLike", "FromSoftware"]),
    ("Palworld", ["palworld"], ["Palworld", "Survival"]),
    ("Call of Duty", ["call of duty", "warzone"], ["CallOfDuty", "Warzone", "COD"]),
    ("Helldivers 2", ["helldivers 2", "helldivers2"], ["Helldivers2", "StarshipTroopers", "CoOp"]),
    ("Cyberpunk 2077", ["cyberpunk 2077", "cyberpunk"], ["Cyberpunk2077", "NightCity"]),
    ("Starfield", ["starfield"], ["Starfield", "Bethesda"]),
    ("Black Myth Wukong", ["black myth", "wukong"], ["BlackMythWukong", "ActionRPG"]),
    ("Marvel Rivals", ["marvel rivals"], ["MarvelRivals", "Heroes"]),
    ("Overwatch 2", ["overwatch 2", "overwatch"], ["Overwatch2", "OW2", "Blizzard"]),
    ("ARK", ["ark: survival", "ark survival"], ["ARK", "Survival"]),
    ("Dead by Daylight", ["dead by daylight"], ["DeadByDaylight", "Asymmetric"]),
    ("Rocket League", ["rocket league"], ["RocketLeague", "CarSports"]),
    ("Apex Legends", ["apex legends"], ["ApexLegends", "EApex"]),
    ("PUBG", ["pubg", "playerunknown"], ["PUBG", "BattleRoyale"]),
    ("Grand Theft Auto: San Andreas", ["grand theft auto san andreas", "gta sa"], ["GTA", "SanAndreas"]),
]

GENERIC = ["Gaming", "Gameplay", "GamingClips", "StreamHighlights"]

# Longest word first so "gta 6" is read before "gta"
_ALIASES: List[Tuple[str, str, List[str]]] = sorted(
    ((alias, name, tags) for name, aliases, tags in GAMES for alias in aliases),
    key=lambda a: -len(a[0]),
)

_WORD = re.compile(r"[^a-z0-9]+")

def _norm(text: str) -> str:
    return _WORD.sub(" ", str(text or "").lower()).strip()

def detect(*texts: Any) -> Tuple[Optional[str], List[str]]:
    """Detect game named in text and the associated hashtags.
    Returns (None, []) when no known game is found.
    """
    hay = _norm(" ".join(str(t or "") for t in texts))
    if not hay:
        return None, []
    for alias, name, tags in _ALIASES:
        # Match as whole phrase
        pattern = r"(?:^| )" + re.escape(_norm(alias)) + r"(?: |$)"
        if re.search(pattern, hay):
            return name, list(tags)
    return None, []

def name_of(game: Optional[str]) -> str:
    """Returns canonical name of game or original string."""
    if not game:
        return ""
    g = _norm(game)
    for name, aliases, _tags in GAMES:
        if g == _norm(name) or g in {_norm(a) for a in aliases}:
            return name
    return str(game)[:40]

def tags_of(game: Optional[str]) -> List[str]:
    """Returns tags for a game."""
    if not game:
        return []
    g = _norm(game)
    for name, aliases, tags in GAMES:
        if g == _norm(name) or g in {_norm(a) for a in aliases} or g in {_norm(t) for t in tags}:
            return list(tags)
    clean = re.sub(r"\W", "", str(game))[:30]
    return [clean] if clean else []

def get_game_rules(game: Optional[str]) -> str:
    """Returns prompt rules for AI describing moments for this game."""
    proper_name = name_of(game)
    if not proper_name:
        return ""
    tags = tags_of(proper_name)
    tag_str = ", ".join(f"#{t}" for t in tags) if tags else "#Gaming"
    return (
        f"This stream is {proper_name}. Pick the moments that only mean something with that game in mind:\n"
        f"- A play, a death, a jump scare, a glitch, a discovery, or the streamer reacting to one.\n"
        f"- The hook is what was said at that moment, or, if nothing was said, the name of what "
        f"happened in two or three words ('1 VS 3', 'THE SHOT', 'HE GOT ME', 'CLUTCH'). Never a sentence that needs the game explained.\n"
        f"- The title names the game when the clip is about it.\n"
        f"- The hashtags include {tag_str}."
    )
