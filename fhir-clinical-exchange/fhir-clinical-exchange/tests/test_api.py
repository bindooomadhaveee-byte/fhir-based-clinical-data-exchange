import json
import pathlib

import pytest

from app import create_app

SEED = json.loads((pathlib.Path(__file__).parent.parent / "sample_data" / "bundle.json").read_text())


@pytest.fixture
def client():
    return create_app().test_client()


def test_metadata(client):
    assert client.get("/metadata").get_json()["resourceType"] == "CapabilityStatement"


def test_patient_crud(client):
    p = {"resourceType": "Patient", "name": [{"family": "Rao"}], "gender": "male"}
    r = client.post("/Patient", json=p)
    assert r.status_code == 201
    pid = r.get_json()["id"]
    assert client.get(f"/Patient/{pid}").get_json()["name"][0]["family"] == "Rao"
    p["gender"] = "other"
    r = client.put(f"/Patient/{pid}", json=p)
    assert r.get_json()["meta"]["versionId"] == "2"
    assert client.delete(f"/Patient/{pid}").status_code == 204
    assert client.get(f"/Patient/{pid}").status_code == 404


def test_validation_error(client):
    r = client.post("/Observation", json={"resourceType": "Observation"})
    assert r.status_code == 400
    assert r.get_json()["resourceType"] == "OperationOutcome"


def test_transaction_and_everything(client):
    r = client.post("/", json=SEED)
    assert r.status_code == 200
    pid = r.get_json()["entry"][0]["response"]["location"].split("/")[1]
    bundle = client.get(f"/Patient/{pid}/$everything").get_json()
    assert bundle["total"] == 3
    obs = client.get(f"/Observation?patient={pid}&code=8867-4").get_json()
    assert obs["total"] == 1


def test_transaction_is_atomic(client):
    bad = {"resourceType": "Bundle", "type": "transaction", "entry": [
        {"fullUrl": "urn:uuid:a", "resource": SEED["entry"][0]["resource"]},
        {"fullUrl": "urn:uuid:b", "resource": {"resourceType": "Observation"}}]}
    assert client.post("/", json=bad).status_code == 400
    assert client.get("/Patient").get_json()["total"] == 0
