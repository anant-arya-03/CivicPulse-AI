"""Read-only FHIR facts. Calendar resources are intentionally ignored."""

import json
from functools import lru_cache
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1] / "data" / "clinic_bundle.json"


@lru_cache
def resources():
    return {
        r["resourceType"] + "/" + r["id"]: r
        for entry in json.loads(BUNDLE.read_text())["entry"]
        if (r := entry["resource"])
    }


def name(resource):
    n = resource["name"][0]
    return " ".join([*n.get("prefix", []), *n["given"], n["family"]])


def summary(pid):
    patient = resources()["Patient/" + pid]
    gp = resources()[patient["generalPractitioner"][0]["reference"]]
    return {
        "name": name(patient),
        "language": patient["communication"][0]["language"]["text"],
        "doctor": name(gp),
        "doctor_id": gp["id"],
    }


def clinical(pid, kind):
    return [
        r
        for r in resources().values()
        if r["resourceType"] == kind and r["subject"]["reference"] == "Patient/" + pid
    ]


def labs(pid):
    return [
        {
            "test_id": r["id"],
            "test": r["code"]["coding"][0]["display"],
            "date": r["effectiveDateTime"],
            "loinc": r["code"]["coding"][0]["code"],
            "status": "available"
            if r["status"] in {"final", "amended", "corrected"}
            else "pending",
        }
        for r in clinical(pid, "Observation")
    ]


def medications(pid):
    return [
        r["medicationCodeableConcept"]["text"]
        for r in clinical(pid, "MedicationRequest")
        if r["status"] == "active"
    ]
