/**
 * GENERATED FILE — do not edit.
 *
 * Written by scripts/generate_training_matrix_asset.py from
 * BackEnd/constants/training_shape.py. Editing it by hand puts the tutorial back
 * where it started: showing coaches numbers the engine no longer uses.
 *
 * Regenerate:  python scripts/generate_training_matrix_asset.py
 * Guarded by:  tests/test_training_matrix_asset.py
 */
window.GOB_TRAINING_MATRIX = {
  "positions": [
    "PG",
    "SG",
    "SF",
    "PF",
    "C"
  ],
  "focuses": [
    {
      "value": "standard",
      "label": "Standard"
    },
    {
      "value": "offensive",
      "label": "Offensive"
    },
    {
      "value": "defensive",
      "label": "Defensive"
    },
    {
      "value": "athletic",
      "label": "Athletic"
    },
    {
      "value": "fundamentals",
      "label": "Fundamentals"
    },
    {
      "value": "rebounding",
      "label": "Rebounding"
    }
  ],
  "attributes": [
    {
      "code": "SC",
      "name": "Scoring"
    },
    {
      "code": "SH",
      "name": "Shooting"
    },
    {
      "code": "ID",
      "name": "Inside Defense"
    },
    {
      "code": "OD",
      "name": "Outside Defense"
    },
    {
      "code": "PS",
      "name": "Passing"
    },
    {
      "code": "BH",
      "name": "Ball Handling"
    },
    {
      "code": "RB",
      "name": "Rebounding"
    },
    {
      "code": "ST",
      "name": "Strength"
    },
    {
      "code": "AG",
      "name": "Agility"
    },
    {
      "code": "ND",
      "name": "Endurance"
    },
    {
      "code": "IQ",
      "name": "Basketball IQ"
    },
    {
      "code": "FT",
      "name": "Free Throws"
    }
  ],
  "bands": [
    {
      "key": "full",
      "min": 80,
      "label": "Strong Fit"
    },
    {
      "key": "high",
      "min": 60,
      "label": "Solid Fit"
    },
    {
      "key": "mid",
      "min": 40,
      "label": "Partial"
    },
    {
      "key": "low",
      "min": 0,
      "label": "Poor Fit"
    }
  ],
  "matrix": {
    "PG": {
      "standard": {
        "SC": 40,
        "SH": 45,
        "ID": 25,
        "OD": 70,
        "PS": 85,
        "BH": 100,
        "RB": 25,
        "ST": 35,
        "AG": 83,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "offensive": {
        "SC": 75,
        "SH": 80,
        "ID": 25,
        "OD": 60,
        "PS": 70,
        "BH": 85,
        "RB": 25,
        "ST": 25,
        "AG": 63,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "defensive": {
        "SC": 30,
        "SH": 35,
        "ID": 55,
        "OD": 100,
        "PS": 75,
        "BH": 90,
        "RB": 25,
        "ST": 25,
        "AG": 73,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "athletic": {
        "SC": 35,
        "SH": 40,
        "ID": 25,
        "OD": 60,
        "PS": 68,
        "BH": 85,
        "RB": 25,
        "ST": 70,
        "AG": 100,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "fundamentals": {
        "SC": 35,
        "SH": 45,
        "ID": 25,
        "OD": 70,
        "PS": 100,
        "BH": 100,
        "RB": 25,
        "ST": 35,
        "AG": 73,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "rebounding": {
        "SC": 30,
        "SH": 35,
        "ID": 25,
        "OD": 55,
        "PS": 70,
        "BH": 85,
        "RB": 75,
        "ST": 70,
        "AG": 63,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      }
    },
    "SG": {
      "standard": {
        "SC": 55,
        "SH": 100,
        "ID": 25,
        "OD": 60,
        "PS": 70,
        "BH": 70,
        "RB": 25,
        "ST": 35,
        "AG": 68,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "offensive": {
        "SC": 85,
        "SH": 100,
        "ID": 25,
        "OD": 55,
        "PS": 62,
        "BH": 63,
        "RB": 25,
        "ST": 30,
        "AG": 63,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "defensive": {
        "SC": 45,
        "SH": 90,
        "ID": 55,
        "OD": 90,
        "PS": 60,
        "BH": 60,
        "RB": 25,
        "ST": 25,
        "AG": 58,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "athletic": {
        "SC": 40,
        "SH": 85,
        "ID": 25,
        "OD": 50,
        "PS": 58,
        "BH": 55,
        "RB": 25,
        "ST": 70,
        "AG": 100,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "fundamentals": {
        "SC": 45,
        "SH": 85,
        "ID": 25,
        "OD": 50,
        "PS": 100,
        "BH": 100,
        "RB": 25,
        "ST": 25,
        "AG": 53,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "rebounding": {
        "SC": 45,
        "SH": 85,
        "ID": 25,
        "OD": 50,
        "PS": 55,
        "BH": 55,
        "RB": 75,
        "ST": 70,
        "AG": 48,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      }
    },
    "SF": {
      "standard": {
        "SC": 82,
        "SH": 64,
        "ID": 50,
        "OD": 91,
        "PS": 39,
        "BH": 39,
        "RB": 50,
        "ST": 40,
        "AG": 53,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "offensive": {
        "SC": 100,
        "SH": 90,
        "ID": 45,
        "OD": 81,
        "PS": 34,
        "BH": 34,
        "RB": 45,
        "ST": 35,
        "AG": 44,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "defensive": {
        "SC": 72,
        "SH": 54,
        "ID": 80,
        "OD": 100,
        "PS": 34,
        "BH": 34,
        "RB": 50,
        "ST": 35,
        "AG": 49,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "athletic": {
        "SC": 65,
        "SH": 49,
        "ID": 45,
        "OD": 81,
        "PS": 29,
        "BH": 34,
        "RB": 40,
        "ST": 75,
        "AG": 90,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "fundamentals": {
        "SC": 72,
        "SH": 54,
        "ID": 40,
        "OD": 81,
        "PS": 75,
        "BH": 75,
        "RB": 40,
        "ST": 30,
        "AG": 41,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "rebounding": {
        "SC": 67,
        "SH": 49,
        "ID": 45,
        "OD": 81,
        "PS": 34,
        "BH": 34,
        "RB": 90,
        "ST": 75,
        "AG": 33,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      }
    },
    "PF": {
      "standard": {
        "SC": 55,
        "SH": 47,
        "ID": 67,
        "OD": 35,
        "PS": 35,
        "BH": 25,
        "RB": 100,
        "ST": 99,
        "AG": 45,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "offensive": {
        "SC": 85,
        "SH": 77,
        "ID": 57,
        "OD": 30,
        "PS": 30,
        "BH": 25,
        "RB": 90,
        "ST": 89,
        "AG": 25,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "defensive": {
        "SC": 45,
        "SH": 37,
        "ID": 97,
        "OD": 65,
        "PS": 30,
        "BH": 25,
        "RB": 90,
        "ST": 89,
        "AG": 30,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "athletic": {
        "SC": 45,
        "SH": 37,
        "ID": 62,
        "OD": 30,
        "PS": 30,
        "BH": 25,
        "RB": 94,
        "ST": 100,
        "AG": 85,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "fundamentals": {
        "SC": 45,
        "SH": 37,
        "ID": 57,
        "OD": 25,
        "PS": 75,
        "BH": 65,
        "RB": 90,
        "ST": 89,
        "AG": 25,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "rebounding": {
        "SC": 54,
        "SH": 47,
        "ID": 67,
        "OD": 35,
        "PS": 35,
        "BH": 25,
        "RB": 100,
        "ST": 100,
        "AG": 45,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      }
    },
    "C": {
      "standard": {
        "SC": 68,
        "SH": 40,
        "ID": 100,
        "OD": 40,
        "PS": 33,
        "BH": 25,
        "RB": 100,
        "ST": 77,
        "AG": 25,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "offensive": {
        "SC": 95,
        "SH": 70,
        "ID": 100,
        "OD": 25,
        "PS": 25,
        "BH": 25,
        "RB": 83,
        "ST": 60,
        "AG": 25,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "defensive": {
        "SC": 58,
        "SH": 30,
        "ID": 100,
        "OD": 80,
        "PS": 28,
        "BH": 25,
        "RB": 95,
        "ST": 67,
        "AG": 25,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "athletic": {
        "SC": 50,
        "SH": 25,
        "ID": 100,
        "OD": 28,
        "PS": 25,
        "BH": 25,
        "RB": 90,
        "ST": 100,
        "AG": 65,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "fundamentals": {
        "SC": 48,
        "SH": 25,
        "ID": 100,
        "OD": 25,
        "PS": 75,
        "BH": 65,
        "RB": 80,
        "ST": 65,
        "AG": 25,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      },
      "rebounding": {
        "SC": 58,
        "SH": 35,
        "ID": 100,
        "OD": 37,
        "PS": 28,
        "BH": 25,
        "RB": 100,
        "ST": 100,
        "AG": 25,
        "ND": 100,
        "IQ": 100,
        "FT": 100
      }
    }
  }
};
