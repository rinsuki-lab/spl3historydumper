import os
import requests
import re
import json
import base64
from glob import iglob
from getpass import getpass

current_token = None
should_skip_force_renew = False

def get_token(force_renew = False):
    TOKENS_JSON_NAME = "tokens.json"
    global current_token, should_skip_force_renew
    if not force_renew:
        if current_token is not None:
            return current_token
        if os.path.exists(TOKENS_JSON_NAME):
            try:
                with open(TOKENS_JSON_NAME, "r") as f:
                    current_token = json.load(f)
                    if type(current_token) is dict:
                        if "http" in current_token:
                            should_skip_force_renew = True
                            current_token = requests.get(current_token["http"]["url"], headers=current_token["http"]["headers"])
                            current_token.raise_for_status()
                            current_token = current_token.json()["token"]
                            if current_token.startswith("Bearer "):
                                current_token = current_token[len("Bearer "):]
                    return current_token
            except Exception as e:
                print("Failed to load tokens.json...", e)
    if should_skip_force_renew:
        print("seems your token API endpoint returns expired token, so please update your endpoint!")
        exit(1)
    while True:
        t = getpass("Input Token (from /api/graphql's Authorization header, token will not echo): ").strip()
        try:
            if t.startswith("Bearer "):
                t = t[len("Bearer "):]
            token = base64.urlsafe_b64decode(t)
            if len(token) > 8:
                break
            print("Token too short...")
        except Exception as e:
            print(e)
            print("It seems Invalid Token... Retry!")
    current_token = t
    while True:
        yn = input("Do you want to save token to tokens.json? (y/n):").strip().lower()
        if yn == "y":
            with open(TOKENS_JSON_NAME, "w") as f:
                json.dump(current_token, f)
            break
        elif yn == "n":
            break
    return current_token

# referer may not be needed
def graphql(version: int, hash: str, referer_path: str, variables: dict = {}):
    if "https://" in referer_path:
        raise Exception("wrong referer_path: " + referer_path)
    elif not referer_path.startswith("/"):
        referer_path = "/" + referer_path
    r = requests.post("https://api.lp1.av5ja.srv.nintendo.net/api/graphql", json={
        "extensions": {
            "persistedQuery": {
                "version": version,
                "sha256Hash": hash,
            }
        },
        "variables": variables,
    }, headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)",
        "x-web-view-ver": "1.0.0-5e2bcdfb",
        "Origin": "https://api.lp1.av5ja.srv.nintendo.net",
        "Referer": "https://api.lp1.av5ja.srv.nintendo.net" + referer_path,
        "Authorization": "Bearer " + get_token(),
    })
    if not r.ok:
        print(f"--- FAIL REQUEST (HTTP {r.status_code}) ---")
        print(r.text)
        if r.status_code == 401:
            while True:
                yn = input("potentially token expired. do you want to re-set token? (y/n):").strip().lower()
                if yn == "y":
                    get_token(force_renew=True)
                    return graphql(version, hash, referer_path, variables)
                elif yn == "n":
                    break
        r.raise_for_status()
    return r.json()

def deid(id: str):
    try:
        return HISTORY_DETAIL_REGEX.match(base64.b64decode(id).decode("ascii")).group(1)
    except:
        # print(id)
        raise

def save_vs_detail(hid: str):
    file_id = deid(hid)
    json_path = f"data/{file_id}.json"
    if not os.path.exists(json_path):
        print("dumping", json_path)
        j = graphql(1, VS_DETAIL_QUERY_ID, "/history/latest", {
            "vsResultId": hid
        })
        j["x-vs-detail-query-id"] = VS_DETAIL_QUERY_ID
        with open(json_path, "w") as f:
            json.dump(j, f, ensure_ascii=False, indent=4)

def save_group(t: str, sg: dict):
    for history_group in sg["historyGroups"]["nodes"]:
        for hd in history_group["historyDetails"]["nodes"]:
            save_vs_detail(hd["id"])
        history_group["x-battle-ids"] = list(map(lambda x:deid(x["id"]), history_group["historyDetails"]["nodes"]))
        for saved_group in iglob(f"data/groups/{t}.*.json"):
            with open(saved_group, "r") as sgf:
                saved_group = json.load(sgf)
            this_group = False
            for battle_id in saved_group["x-battle-ids"]:
                if this_group:
                    if battle_id not in history_group["x-battle-ids"]:
                        print(saved_group["x-battle-ids"][-1], "not_in", battle_id)
                        history_group["x-battle-ids"].append(battle_id)
                elif battle_id in history_group["x-battle-ids"]:
                    this_group = True
            if this_group:
                break
        first_id = history_group["x-battle-ids"][-1]
        hg = history_group.copy()
        del hg["historyDetails"]
        with open(f"data/groups/{t}.{first_id}.json", "w") as f:
            json.dump(hg, f, ensure_ascii=False, indent=4)

HISTORY_DETAIL_REGEX = re.compile(r"(?:Coop|Vs)HistoryDetail-u-[a-z0-9]+(?::(?:RECENT|BANKARA|REGULAR|PRIVATE))?:(20[0-9]{6}T[0-9]{6}_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
VS_DETAIL_QUERY_ID = "2b085984f729cd51938fc069ceef784a"
current_token = get_token()

def main():
    print("fetching latest battles...")
    latest_battles_res = graphql(1, "80585ad4e4ecb674c3d8cd278adb1d21", "/history/latest")
    print("fetched!")
    for history_group in latest_battles_res["data"]["latestBattleHistories"]["historyGroups"]["nodes"]:
        for history_detail in history_group["historyDetails"]["nodes"]:
            # print(history_detail)
            save_vs_detail(history_detail["id"])

    print("fetching regular match groups...")
    regular_res = graphql(1, "333d0a48071b0036449e35ece577b06f", "/history/regular")
    save_group("regular", regular_res["data"]["regularBattleHistories"])

    print("fetching bankara match groups...")
    bankara_res = graphql(1, "d8a8662345593bbbcd63841c91d4c6f5", "/history/bankara")
    save_group("bankara", bankara_res["data"]["bankaraBattleHistories"])

    print("fetching private match groups...")
    private_res = graphql(1, "b304e707648f0669a939943d46febce1", "/history/private")
    save_group("private", private_res["data"]["privateBattleHistories"])

    print("fetching latest attendance...")
    latest_attendance_res = graphql(1, "a5692cf290ffb26f14f0f7b6e5023b07", "/coop")
    for history_group in latest_attendance_res["data"]["coopResult"]["historyGroups"]["nodes"]:
        history_group_data = history_group.copy()
        del history_group_data["historyDetails"]
        for history_detail in history_group["historyDetails"]["nodes"]:
            file_id = HISTORY_DETAIL_REGEX.match(base64.b64decode(history_detail["id"]).decode("ascii")).group(1)
            json_path = f"data/salmon/{file_id}.json"
            if not os.path.exists(json_path):
                print("dumping", json_path)
                j = graphql(1, "f3799a033f0a7ad4b1b396f9a3bafb1e", "/coop", {
                    "coopHistoryDetailId": history_detail["id"]
                })
                j["x-history-group"] = history_group_data
                with open(json_path, "w") as f:
                    json.dump(j, f, ensure_ascii=False, indent=4)
    print("done!")

if __name__ == "__main__":
    main()
