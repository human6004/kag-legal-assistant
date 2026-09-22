from typing import Literal
POSSIBLE_ENTITIES = [
    "Disease",
    "Symptom",
    "Treatment",
    "Chemical",
    "PlantPart",
    "Nutrient",
]

POSSIBLE_RELATIONS = [
    "CAUSES",
    "HAS_SYMPTOM",
    "TREATED_BY",
    "AFFECTS",
]


# Unpack list thành Literal bằng dấu *
entities = Literal[tuple(POSSIBLE_ENTITIES)]
relations = Literal[tuple(POSSIBLE_RELATIONS)]