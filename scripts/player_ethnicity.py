#!/usr/bin/env python3
"""
Assign each player a race + skin-tone bucket for portrait generation.

Distribution models real men's D1 basketball demographics (for authenticity):

  RACE            black 55% | white 35% | other 10%
  black sub       normal 50 | light 35 | dark 15
  white sub       normal 60 | tan/olive 30 | pale/scandinavian 10
  other sub       asian 50 | hispanic 25 | ambiguous 25

Name override: an OBVIOUS ethnic-signal name locks the race (and sometimes the
sub-tone) — Asian/Hispanic surnames, distinctive Black given names, European
surnames / Anglo given names, with Scandinavian surnames biasing to pale.
Everyone else is assigned by UUID-seeded weighted random (stable across runs,
independent of the expression seed).

    from player_ethnicity import assign_ethnicity
    e = assign_ethnicity(first, last, player_id)
    # -> {"race","skin","ethnicity_label","skin_prompt"}
"""
import re
import hashlib

RACE_WEIGHTS = [("black", 60), ("white", 30), ("other", 10)]
BLACK_SUB = [("normal", 50), ("light", 35), ("dark", 15)]
WHITE_SUB = [("normal", 60), ("tan", 30), ("pale", 10)]
OTHER_SUB = [("asian", 50), ("hispanic", 25), ("ambiguous", 25)]

# NB-usable skin/feature fragment per final bucket.
SKIN_PROMPT = {
    "black-normal": "a Black man with medium-brown skin",
    "black-light":  "a light-skinned Black man with light-brown skin",
    "black-dark":   "a dark-skinned Black man with deep dark-brown skin",
    "white-normal": "a white man with fair skin",
    "white-pale":   "a white man with very pale fair skin and Scandinavian features",
    "white-tan":    "a white man with tan olive Mediterranean skin",
    "asian":        "an East Asian man",
    "hispanic":     "a Hispanic Latino man with light-brown skin",
    "ambiguous":    "a man of racially ambiguous, mixed ethnicity",
}

# --- high-precision name lists (only obvious signals; the rest -> random) -----
ASIAN_SUR = {
    # Chinese
    "li", "wang", "zhang", "liu", "chen", "yang", "huang", "zhao", "wu", "zhou",
    "xu", "sun", "ma", "zhu", "hu", "guo", "lin", "he", "gao", "luo", "zheng",
    "xie", "tang", "deng", "feng", "cao", "peng", "wong", "chan", "cheng",
    "chiang", "chin", "chow", "chu", "kwan", "kwok", "lam", "lau", "leung", "ng",
    "tam", "tsang", "yip", "yuen", "chang", "chung", "tsai", "hsu", "hsieh",
    "kwong", "sung", "chao", "bae", "yeung", "cheung",
    # Korean
    "kim", "park", "choi", "jung", "kang", "cho", "yoon", "jang", "lim", "han",
    "shin", "kwon", "hwang", "ahn", "song", "ryu", "seo",
    # Japanese
    "tanaka", "sato", "suzuki", "takahashi", "watanabe", "ito", "yamamoto",
    "nakamura", "kobayashi", "kato", "yoshida", "yamada", "sasaki", "yamaguchi",
    "matsumoto", "inoue", "kimura", "hayashi", "shimizu", "mori", "abe", "ikeda",
    "hashimoto", "ishikawa", "ogawa", "goto", "okada", "murakami", "kondo",
    "saito", "sakamoto", "fujita", "fujii", "okamoto", "matsuda", "nakajima",
    # Vietnamese / SE Asian
    "nguyen", "tran", "pham", "huynh", "hoang", "phan", "vu", "vo", "dang",
    "bui", "ngo", "duong", "dao", "dinh",
}
HISPANIC_SUR = {
    "garcia", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez",
    "gonzales", "perez", "sanchez", "ramirez", "torres", "flores", "rivera",
    "gomez", "diaz", "reyes", "morales", "cruz", "ortiz", "gutierrez", "chavez",
    "ramos", "vasquez", "vazquez", "castillo", "jimenez", "moreno", "romero",
    "herrera", "medina", "aguilar", "vargas", "guerrero", "mendoza", "salazar",
    "mendez", "ruiz", "alvarez", "castro", "contreras", "guzman", "delgado",
    "pena", "rios", "ayala", "cabrera", "cortez", "cortes", "dominguez",
    "escobar", "estrada", "fuentes", "ibarra", "juarez", "luna", "maldonado",
    "marquez", "munoz", "navarro", "nunez", "ochoa", "orozco", "padilla",
    "pacheco", "quintero", "robles", "rojas", "salinas", "santana", "soto",
    "trejo", "valdez", "vega", "velasquez", "velez", "zamora", "acosta",
    "aguirre", "arias", "barajas", "bautista", "carrillo", "cervantes",
    "corona", "deleon", "duran", "espinoza", "figueroa", "galvan", "gallegos",
    "camacho", "campos", "cardenas", "cuevas",
}
HISPANIC_GIVEN = {
    "jose", "juan", "carlos", "miguel", "luis", "jesus", "alejandro", "javier",
    "eduardo", "jorge", "ramon", "raul", "hector", "cesar", "pedro", "pablo",
    "enrique", "francisco", "gerardo", "gustavo", "ignacio", "arturo",
    "armando", "rodrigo", "salvador", "guillermo", "rafael", "esteban",
    "felipe", "joaquin", "alonso", "emilio", "diego", "fernando", "ricardo",
    "roberto", "mateo", "sergio", "ernesto",
}
BLACK_GIVEN = {
    "deangelo", "deandre", "deshawn", "dashawn", "deshaun", "demarcus",
    "demario", "deonte", "jamal", "jamar", "jabari", "jaylen", "jaylon",
    "javon", "jaquan", "jaquez", "keyshawn", "kwame", "malik", "marquis",
    "marquise", "rashad", "rashawn", "tyrell", "tyrese", "tyrone", "terrell",
    "darnell", "davon", "devonte", "devonta", "donte", "lamar", "lavar",
    "lamont", "jermaine", "trayvon", "tremaine", "shaquille", "jaheim",
    "keshawn", "daquan", "cordell", "jalen", "jamarion", "jamari", "jamir",
    "tyshawn", "keontae", "deonta", "darius", "jaquon",
}
# Distinctly Nordic surnames -> white AND bias to pale (not anglicized -son).
SCANDINAVIAN_SUR = {
    "holmstrom", "swensen", "swenson", "sorensen", "larsen", "hansen",
    "nielsen", "jensen", "pedersen", "andersen", "kristiansen", "johansen",
    "olsen", "lindqvist", "bergstrom", "lindberg", "sandberg", "nordstrom",
    "dahl", "hagen", "bakke", "lund", "ekberg", "sjoberg", "engstrom",
    "forsberg", "hedlund", "holm", "isaksson", "karlsson", "nilsson",
    "ericsson", "gustafsson", "jonsson", "mattsson",
}
EURO_SUR = {
    # German
    "schmidt", "mueller", "muller", "schneider", "fischer", "weber", "meyer",
    "wagner", "becker", "hoffmann", "koch", "richter", "klein", "wolf",
    "schroder", "neumann", "schwarz", "zimmermann", "braun", "kruger",
    "hofmann", "hartmann", "krause", "lehmann", "kohler", "konig", "huber",
    "kaiser", "fuchs", "scholz",
    # Irish
    "obrien", "oconnor", "oneill", "murphy", "kelly", "ryan", "sullivan",
    "walsh", "mccarthy", "gallagher", "doyle", "kennedy", "lynch", "murray",
    "quinn", "fitzgerald", "brennan", "burke", "flanagan", "donnelly",
    "mcmahon", "boyle", "healy", "mcgrath", "mcdonald", "macdonald",
    # Italian
    "rossi", "russo", "ferrari", "esposito", "bianchi", "romano", "colombo",
    "ricci", "marino", "greco", "bruno", "gallo", "conti", "deluca", "mancini",
    "giordano", "rizzo", "lombardi", "moretti", "barbieri", "fontana",
    "santoro", "rinaldi", "caruso", "ferrara", "galli", "leone", "vitale",
    "lombardo", "coppola", "damore", "dangelo", "marchetti", "parisi", "conte",
    # Polish
    "kowalski", "nowak", "wojcik", "kowalczyk", "kaminski", "zielinski",
    "wozniak", "kozlowski", "jankowski", "mazur", "kwiatkowski", "krawczyk",
    "kaczmarek", "piotrowski", "grabowski", "michalski", "jablonski",
    "malinowski", "jaworski", "wrobel", "zajac",
    # Greek
    "papadopoulos", "nikolaidis", "georgiou", "papas",
}
ANGLO_GIVEN = {
    "brad", "bradley", "chad", "cody", "colton", "hunter", "tanner", "wyatt",
    "cole", "cooper", "chase", "brody", "brock", "brett", "clint", "dalton",
    "dawson", "dillon", "dustin", "garrett", "grady", "gunner", "holden",
    "jed", "kip", "landon", "mason", "zane", "beau", "buck", "cash", "duke",
    "remington", "ryder", "tucker", "waylon", "weston", "gunnar", "fritz",
    "hans", "klaus", "lars", "sven", "magnus", "bjorn", "anders", "nils",
    "thor", "chip", "chuck", "hank",
}


def _norm(s):
    return re.sub(r"[^a-z]", "", str(s or "").lower())


def _seed(pid, salt):
    return int(hashlib.md5(f"{pid}|{salt}".encode()).hexdigest(), 16)


def _pick(seed, weighted):
    total = sum(w for _, w in weighted)
    r = seed % total
    c = 0
    for name, w in weighted:
        c += w
        if r < c:
            return name
    return weighted[-1][0]


def name_signal(first, last):
    """(race, forced_sub_or_None, reason) from an obvious name, else (None,..)."""
    f, l = _norm(first), _norm(last)
    if l in ASIAN_SUR:
        return "other", "asian", f"surname:{l}"
    if l in HISPANIC_SUR:
        return "other", "hispanic", f"surname:{l}"
    if f in HISPANIC_GIVEN:
        return "other", "hispanic", f"given:{f}"
    if f in BLACK_GIVEN:
        return "black", None, f"given:{f}"
    if l in SCANDINAVIAN_SUR:
        return "white", "pale", f"surname:{l}"
    if l in EURO_SUR:
        return "white", None, f"surname:{l}"
    if l.endswith("ski") or l.endswith("wski") or l.endswith("czyk"):
        return "white", None, f"surname-suffix:{l}"   # Polish -> white
    if f in ANGLO_GIVEN:
        return "white", None, f"given:{f}"
    return None, None, None


def compute_random_weights(players, name_of=None):
    """Weights for the RANDOM (unmatched) pool so the GLOBAL race split hits
    RACE_WEIGHTS once name-matched players are counted toward the quota.

    Without this, random players get 55/35/10 *on top of* the name matches,
    overshooting whichever race the generated name pool favors. Here, matches
    count against the target and the random pool fills only the residual.
    """
    name_of = name_of or (lambda p: (p.get("first_name"), p.get("last_name")))
    n = len(players)
    target = {r: w / sum(w for _, w in RACE_WEIGHTS) * n for r, w in RACE_WEIGHTS}
    matched = {"black": 0, "white": 0, "other": 0}
    for p in players:
        r, _, _ = name_signal(*name_of(p))
        if r:
            matched[r] += 1
    residual = {r: max(0.0, target[r] - matched[r]) for r in target}
    # scale to integer-ish weights (order preserved for _pick)
    return [(r, max(0, round(residual[r]))) for r, _ in RACE_WEIGHTS]


def assign_ethnicity(first, last, pid, random_weights=None):
    race, forced_sub, reason = name_signal(first, last)
    source = reason or "random"
    if race is None:
        race = _pick(_seed(pid, "race"), random_weights or RACE_WEIGHTS)
    if race == "black":
        sub = forced_sub or _pick(_seed(pid, "sub"), BLACK_SUB)
        key = f"black-{sub}"
        label = f"black/{sub}"
    elif race == "white":
        sub = forced_sub or _pick(_seed(pid, "sub"), WHITE_SUB)
        key = f"white-{sub}"
        label = f"white/{sub}"
    else:  # other
        sub = forced_sub or _pick(_seed(pid, "sub"), OTHER_SUB)
        key = sub  # asian / hispanic / ambiguous
        label = f"other/{sub}"
    return {"race": race, "skin": key, "ethnicity_label": label,
            "skin_prompt": SKIN_PROMPT[key], "source": source}
