import random

def weighted_random_from_dict(weight_dict):
    total = sum(weight_dict.values())
    roll = random.uniform(0, total)
    upto = 0
    for key, weight in weight_dict.items():
        if upto + weight >= roll:
            return key
        upto += weight
    return random.choice(list(weight_dict.keys()))  # fallback