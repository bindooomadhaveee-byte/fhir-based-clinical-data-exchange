# FHIR-Based Clinical Data Exchange (Base Project)

A small FHIR R4 REST server (Flask + SQLite) plus a demo client that exchanges a
patient's clinical record between two independent systems.

## Features
- Resources: `Patient`, `Observation`, `Condition`
- CRUD with versioning (`meta.versionId`), `OperationOutcome` errors
- Search: `Patient?family=&gender=&identifier=`, `Observation?patient=&code=`
- `Patient/{id}/$everything`
- Transaction Bundle at `POST /` (atomic, resolves `urn:uuid` references)
- `GET /metadata` CapabilityStatement
- Basic structural validation (`app/validation.py`)

## Run
```bash
pip install -r requirements.txt
python run.py 5000                 # System A
python run.py 5001                 # System B (second terminal)
python client/exchange_demo.py     # third terminal: A -> B exchange
pytest                             # run tests
```
Pass a file path as 2nd arg for persistence: `python run.py 5000 a.db`

## Example
```bash
curl -X POST localhost:5000/ -H "Content-Type: application/fhir+json" -d @sample_data/bundle.json
curl "localhost:5000/Patient?family=Reddy"
```

## Next steps
Add auth (SMART on FHIR / OAuth2), full validation (HAPI or `fhir.resources`),
more resources (Encounter, MedicationRequest), pagination, audit logging (AuditEvent), HTTPS.

> Educational base project - not for real patient data.
