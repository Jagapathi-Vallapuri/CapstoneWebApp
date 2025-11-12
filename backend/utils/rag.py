from typing import Optional
from models.medical_profile import MedicalProfile


def profile_to_context(profile: Optional[MedicalProfile]) -> str:
    if not profile:
        return ""

    parts = []
    def add(label, value):
        if value:
            parts.append(f"{label}: {value}")

    add("Present conditions", profile.present_conditions)
    add("Diagnosed conditions", profile.diagnosed_conditions)
    add("Medications (current)", profile.medications_current)
    add("Medications (past)", profile.medications_past)
    add("Allergies", profile.allergies)
    add("Medical history", profile.medical_history)
    add("Family history", profile.family_history)
    add("Surgeries", profile.surgeries)
    add("Immunizations", profile.immunizations)
    add("Lifestyle factors", profile.lifestyle_factors)

    if not parts:
        return ""

    header = "User medical profile (use as context for answering; do not reveal private identifiers):"
    return header + "\n" + "\n".join(parts)
