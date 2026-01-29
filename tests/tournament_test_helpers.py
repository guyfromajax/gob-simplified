"""Shared helpers for tournament tests. Step 3: ObjectId bracket, resolve at edges."""

from BackEnd.db import teams_collection


def seed_teams_ah():
    names = ["A", "B", "C", "D", "E", "F", "G", "H"]
    teams_collection.delete_many({"name": {"$in": names}})
    for n in names:
        teams_collection.insert_one({"name": n})
