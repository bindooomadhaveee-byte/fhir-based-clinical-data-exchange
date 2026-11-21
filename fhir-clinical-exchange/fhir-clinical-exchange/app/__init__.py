import json
import uuid

from flask import Flask, Response, request

from .store import Store
from .validation import SUPPORTED, validate

FHIR_JSON = "application/fhir+json"


def outcome(severity, code, text):
    return {"resourceType": "OperationOutcome",
            "issue": [{"severity": severity, "code": code, "diagnostics": text}]}


def fhir(body, status=200):
    return Response(json.dumps(body), status=status, mimetype=FHIR_JSON)


def ref_id(ref):
    """'Patient/123' -> '123'"""
    return ref.split("/")[-1] if isinstance(ref, str) else None


def create_app(db_path=":memory:"):
    app = Flask(__name__)
    store = Store(db_path)

    @app.errorhandler(404)
    def _404(_):
        return fhir(outcome("error", "not-found", "Resource not found"), 404)

    @app.get("/metadata")
    def metadata():
        return fhir({
            "resourceType": "CapabilityStatement", "status": "active",
            "fhirVersion": "4.0.1", "kind": "instance", "format": ["json"],
            "rest": [{"mode": "server",
                      "resource": [{"type": t, "interaction": [
                          {"code": c} for c in ("read", "create", "update", "delete", "search-type")]}
                          for t in sorted(SUPPORTED)]}],
        })

    # ---------- CRUD ----------
    @app.post("/<rtype>")
    def create(rtype):
        if rtype not in SUPPORTED:
            return fhir(outcome("error", "not-supported", f"Unknown type {rtype}"), 404)
        body = request.get_json(silent=True)
        errs = validate(body, rtype)
        if errs:
            return fhir(outcome("error", "invalid", "; ".join(errs)), 400)
        res = store.create(rtype, body)
        r = fhir(res, 201)
        r.headers["Location"] = f"/{rtype}/{res['id']}"
        return r

    @app.get("/<rtype>/<rid>")
    def read(rtype, rid):
        res = store.read(rtype, rid)
        return fhir(res) if res else fhir(outcome("error", "not-found", f"{rtype}/{rid}"), 404)

    @app.put("/<rtype>/<rid>")
    def update(rtype, rid):
        body = request.get_json(silent=True)
        errs = validate(body, rtype)
        if errs:
            return fhir(outcome("error", "invalid", "; ".join(errs)), 400)
        if body.get("id") not in (None, rid):
            return fhir(outcome("error", "invalid", "Body id must match URL id"), 400)
        res, created = store.update(rtype, rid, body)
        return fhir(res, 201 if created else 200)

    @app.delete("/<rtype>/<rid>")
    def delete(rtype, rid):
        if store.delete(rtype, rid):
            return "", 204
        return fhir(outcome("error", "not-found", f"{rtype}/{rid}"), 404)

    # ---------- Search ----------
    @app.get("/<rtype>")
    def search(rtype):
        if rtype not in SUPPORTED:
            return fhir(outcome("error", "not-supported", f"Unknown type {rtype}"), 404)
        results = store.all(rtype)
        q = request.args
        if rtype == "Patient":
            if "family" in q:
                results = [r for r in results if any(
                    q["family"].lower() in n.get("family", "").lower() for n in r.get("name", []))]
            if "gender" in q:
                results = [r for r in results if r.get("gender") == q["gender"]]
            if "identifier" in q:
                v = q["identifier"].split("|")[-1]
                results = [r for r in results if any(i.get("value") == v for i in r.get("identifier", []))]
        else:
            pid = q.get("patient") or q.get("subject")
            if pid:
                results = [r for r in results if ref_id(r.get("subject", {}).get("reference")) == ref_id(pid)]
            if "code" in q:
                c = q["code"].split("|")[-1]
                results = [r for r in results if any(
                    cd.get("code") == c for cd in r.get("code", {}).get("coding", []))]
        return fhir({"resourceType": "Bundle", "type": "searchset", "total": len(results),
                     "entry": [{"fullUrl": f"{rtype}/{r['id']}", "resource": r} for r in results]})

    # ---------- Patient $everything ----------
    @app.get("/Patient/<pid>/$everything")
    def everything(pid):
        patient = store.read("Patient", pid)
        if not patient:
            return fhir(outcome("error", "not-found", f"Patient/{pid}"), 404)
        entries = [patient]
        for t in ("Observation", "Condition"):
            entries += [r for r in store.all(t) if ref_id(r.get("subject", {}).get("reference")) == pid]
        return fhir({"resourceType": "Bundle", "type": "searchset", "total": len(entries),
                     "entry": [{"fullUrl": f"{r['resourceType']}/{r['id']}", "resource": r} for r in entries]})

    # ---------- Transaction Bundle (data exchange endpoint) ----------
    @app.post("/")
    def transaction():
        bundle = request.get_json(silent=True)
        if not bundle or bundle.get("resourceType") != "Bundle" or \
                bundle.get("type") not in ("transaction", "batch"):
            return fhir(outcome("error", "invalid", "Expected Bundle of type transaction|batch"), 400)
        entries = bundle.get("entry", [])

        # Validate everything first so the transaction is all-or-nothing.
        for i, e in enumerate(entries):
            errs = validate(e.get("resource"))
            if errs:
                return fhir(outcome("error", "invalid", f"entry[{i}]: " + "; ".join(errs)), 400)

        # Assign server ids to urn:uuid fullUrls and rewrite references.
        idmap, types = {}, {}
        for e in entries:
            fu = e.get("fullUrl", "")
            if fu.startswith("urn:uuid:"):
                idmap[fu] = str(uuid.uuid4())
                types[fu] = e["resource"]["resourceType"]
        responses = []
        for e in entries:
            text = json.dumps(e["resource"])
            for urn, new_id in idmap.items():
                text = text.replace(f'"{urn}"', f'"{types[urn]}/{new_id}"')
            res = json.loads(text)
            method = e.get("request", {}).get("method", "POST").upper()
            if method == "PUT" and res.get("id"):
                saved, _ = store.update(res["resourceType"], res["id"], res)
            else:
                saved = store.create(res["resourceType"], res, idmap.get(e.get("fullUrl")))
            responses.append({"response": {
                "status": "201 Created" if method == "POST" else "200 OK",
                "location": f"{saved['resourceType']}/{saved['id']}"}})
        return fhir({"resourceType": "Bundle", "type": f"{bundle['type']}-response",
                     "entry": responses})

    return app
