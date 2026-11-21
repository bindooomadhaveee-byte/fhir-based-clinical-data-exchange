"""Minimal structural validation (a real system would use a full FHIR validator)."""

SUPPORTED = {"Patient", "Observation", "Condition"}


def validate(res, expected_type=None):
    """Return a list of error strings (empty list = valid)."""
    errors = []
    if not isinstance(res, dict):
        return ["Body must be a JSON object"]
    rtype = res.get("resourceType")
    if rtype not in SUPPORTED:
        return [f"Unsupported resourceType: {rtype!r}"]
    if expected_type and rtype != expected_type:
        errors.append(f"resourceType {rtype} does not match endpoint {expected_type}")

    if rtype == "Patient":
        if not res.get("name") and not res.get("identifier"):
            errors.append("Patient requires at least a name or identifier")
        if res.get("gender") not in (None, "male", "female", "other", "unknown"):
            errors.append("Patient.gender must be male|female|other|unknown")
    elif rtype == "Observation":
        if "status" not in res:
            errors.append("Observation.status is required")
        if "code" not in res:
            errors.append("Observation.code is required")
    elif rtype == "Condition":
        if "subject" not in res:
            errors.append("Condition.subject is required")
        if "clinicalStatus" not in res and "code" not in res:
            errors.append("Condition requires code or clinicalStatus")
    return errors
