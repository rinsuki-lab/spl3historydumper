from dump import deid
from glob import glob
from datetime import datetime
import json
import os
import re

for filename in glob("data/20*.json"):
    if re.search(r"\.wrong\.content\.movedat\.[0-9]+\.json$", filename) is not None:
        continue
    with open(filename, "r") as f:
        fj = json.load(f)
    expected_fn = deid(fj["data"]["vsHistoryDetail"]["id"]) + ".json"
    if not filename.endswith(expected_fn):
        print("wrong id: ", filename)
        new_fn = f"{filename}.wrong.content.movedat.{int(datetime.now().timestamp())}.json"
        os.rename(filename, new_fn)
        print("renamed to", new_fn)