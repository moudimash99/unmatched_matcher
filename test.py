import json, os

with open("input/fighters.json") as f:
    data = json.load(f)

for fighter in data["fighters"]:
    path = fighter["image_url"].lstrip("/")  # remove leading slash
    exists = os.path.exists(path)
    print(f"{fighter['id']:20}  {'OK' if exists else 'MISSING'}  ->  {path}")
