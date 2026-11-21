"""Demo: export a patient's record from System A and import it into System B.

Start two servers first:
    python run.py 5000      # System A (source)
    python run.py 5001      # System B (destination)
Then:  python client/exchange_demo.py
"""
import json
import pathlib
import uuid

import requests

A, B = "http://localhost:5000", "http://localhost:5001"
H = {"Content-Type": "application/fhir+json"}


def main():
    seed = json.loads((pathlib.Path(__file__).parent.parent / "sample_data" / "bundle.json").read_text())

    # 1. Load sample data into System A
    r = requests.post(A + "/", json=seed, headers=H)
    r.raise_for_status()
    pid = r.json()["entry"][0]["response"]["location"].split("/")[1]
    print("System A: created Patient", pid)

    # 2. Export full record from A ($everything)
    export = requests.get(f"{A}/Patient/{pid}/$everything").json()
    print("Exported", export["total"], "resources from System A")

    # 3. Convert the searchset into a transaction Bundle for B
    #    (urn:uuid fullUrls let B re-link internal references on import)
    urn = {e["resource"]["id"]: f"urn:uuid:{uuid.uuid4()}" for e in export["entry"]}
    entries = []
    for e in export["entry"]:
        res = json.loads(json.dumps(e["resource"]))
        old_id = res.pop("id")
        res.pop("meta", None)
        text = json.dumps(res)
        for oid, u in urn.items():
            text = text.replace(f'"Patient/{oid}"', f'"{u}"')
        res = json.loads(text)
        entries.append({"fullUrl": urn[old_id], "resource": res,
                        "request": {"method": "POST", "url": res["resourceType"]}})
    tx = {"resourceType": "Bundle", "type": "transaction", "entry": entries}

    # 4. Import into System B
    r = requests.post(B + "/", json=tx, headers=H)
    r.raise_for_status()
    print("System B imported:", [x["response"]["location"] for x in r.json()["entry"]])

    # 5. Verify on B
    found = requests.get(B + "/Patient", params={"family": "Reddy"}).json()
    new_pid = found["entry"][0]["resource"]["id"]
    full = requests.get(f"{B}/Patient/{new_pid}/$everything").json()
    print("Verified on System B:", full["total"], "resources for Patient", new_pid)


if __name__ == "__main__":
    main()
