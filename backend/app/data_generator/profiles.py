"""Seeded sampling of applicants, assets and requested coverage. Pure functions of (rng, inputs)."""
from __future__ import annotations
import math

from app.core import rules_config as R

FIRST = ["Aarav", "Maya", "Liam", "Sofia", "Noah", "Priya", "Lucas", "Amara", "Ethan", "Chloe", "Omar", "Elena",
         "Daniel", "Yuki", "Mateo", "Fatima", "Oliver", "Ingrid", "Samuel", "Leila", "Henry", "Nadia", "Victor",
         "Zara", "Felix", "Hana", "Isaac", "Rosa", "Kofi", "Tara", "Jonas", "Mei", "Andre", "Selin", "Ravi",
         "Clara", "Tomas", "Aisha", "Hugo", "Naomi"]
LAST = ["Verma", "Okafor", "Silva", "Hoffmann", "Nakamura", "Rossi", "Johansson", "Haddad", "Petrov", "Mensah",
        "Duarte", "Kowalski", "Chen", "Alvarez", "Brennan", "Sato", "Novak", "Rahman", "Fischer", "Costa",
        "Ibrahim", "Larsen", "Moreau", "Singh", "Tanaka", "Weber", "Yilmaz", "Adeyemi", "Bianchi", "Park"]
BIZ = ["Traders", "Logistics", "Foods", "Works", "Retail", "Holdings", "Supplies", "Services", "Fabrication", "Hospitality"]
LOCS = list(R.LOCATION_RISK_TIER)
LOC_W = [3, 3, 3, 3, 3, 3, 1.5, 1.5, 1.2]          # high-risk cities less frequent


def pick(rng, values, weights):
    return rng.choices(values, weights=weights, k=1)[0]


def _round(x, base):
    return int(round(x / base) * base)


def sample_applicant(idx, rng, product):
    first, last = rng.choice(FIRST), rng.choice(LAST)
    business = product == "COMMERCIAL"
    name = f"{last} {rng.choice(BIZ)}" if business else f"{first} {last}"
    age = int(min(88, max(17, rng.gauss(41, 12))))
    return {"full_name": name, "email": f"{first}.{last}.{idx:05d}@example.test".lower(),
            "phone": "+1555" + "".join(str(rng.randint(0, 9)) for _ in range(7)), "age": age,
            "location": pick(rng, LOCS, LOC_W), "applicant_type": "BUSINESS" if business else "INDIVIDUAL"}


def _band(rng, bands):
    lo, hi = pick(rng, [(b[0], b[1]) for b in bands], [b[2] for b in bands])
    return rng.randint(lo, hi)


def _claims(rng, weights):
    return pick(rng, [0, 1, 2, 3, 4], weights)


def sample_motor(rng, loc):
    vt = pick(rng, ["HATCHBACK", "SEDAN", "SUV", "TRUCK", "MOTORCYCLE", "SPORTS"], [.24, .28, .26, .08, .08, .06])
    age = _band(rng, [(0, 3, .30), (4, 8, .32), (9, 14, .26), (15, 20, .09), (21, 24, .03)])
    base = {"HATCHBACK": 14000, "SEDAN": 22000, "SUV": 34000, "TRUCK": 38000, "MOTORCYCLE": 9000, "SPORTS": 62000}[vt]
    value = max(2500, _round(base * (0.93 ** age) * rng.uniform(0.8, 1.25), 100))
    code = pick(rng, ["MOTOR_COMPREHENSIVE", "MOTOR_THEFT_FIRE", "MOTOR_COMPREHENSIVE_PLUS"], [.55, .25, .20])
    cov = _round(value * rng.uniform(0.75, 1.0), 100)
    if rng.random() < 0.02:
        cov = _round(value * 1.2, 100)                    # over-insured request -> ineligible
    cov = max(cov, R.COVERAGE_BY_CODE[code]["min_limit"])
    attrs = {"vehicle_type": vt, "manufacturing_year": R.AS_OF_YEAR - age,
             "registration_location": loc if rng.random() < 0.9 else pick(rng, LOCS, LOC_W),
             "previous_accidents": _claims(rng, [.74, .17, .06, .02, .01]),
             "previous_claims": _claims(rng, [.70, .18, .08, .03, .01])}
    return value, code, cov, attrs


def sample_property(rng, loc):
    age = _band(rng, [(0, 10, .25), (11, 30, .35), (31, 60, .28), (61, 95, .10), (96, 110, .02)])
    value = _round(min(2_400_000, max(40_000, 120_000 * math.exp(rng.gauss(0.6, 0.55)))), 1000)
    code = pick(rng, ["PROP_BUILDING_BASIC", "PROP_BUILDING_PLUS", "PROP_BUILDING_CONTENTS"], [.35, .45, .20])
    cov = max(_round(value * rng.uniform(0.8, 1.0), 1000), R.COVERAGE_BY_CODE[code]["min_limit"])
    attrs = {"property_type": pick(rng, ["HOUSE", "APARTMENT", "TOWNHOUSE", "VILLA"], [.45, .25, .2, .1]),
             "year_built": R.AS_OF_YEAR - age,
             "construction_type": pick(rng, ["CONCRETE", "MASONRY", "STEEL", "MIXED", "TIMBER"], [.30, .30, .10, .15, .15]),
             "flood_exposure": pick(rng, R.EXPOSURE_LEVELS, [.45, .30, .18, .07]),
             "fire_exposure": pick(rng, R.EXPOSURE_LEVELS, [.25, .45, .22, .08]),
             "previous_claims": _claims(rng, [.78, .15, .05, .02, 0])}
    return value, code, cov, attrs


def sample_commercial(rng, loc):
    value = _round(min(3_300_000, max(30_000, 150_000 * math.exp(rng.gauss(0.7, 0.7)))), 1000)
    code = pick(rng, ["COMM_PROPERTY_ONLY", "COMM_PROPERTY_BI", "COMM_ALL_RISKS"], [.45, .35, .20])
    cov = max(_round(value * rng.uniform(0.8, 1.0), 1000), R.COVERAGE_BY_CODE[code]["min_limit"])
    attrs = {"business_category": pick(rng, ["OFFICE_SERVICES", "RETAIL", "HOSPITALITY", "LOGISTICS", "MANUFACTURING", "CONSTRUCTION"],
                                       [.22, .26, .14, .14, .16, .08]),
             "industry_hazard_class": pick(rng, ["LOW", "MODERATE", "HIGH"], [.35, .45, .20]),
             "fire_exposure": pick(rng, R.EXPOSURE_LEVELS, [.25, .45, .22, .08]),
             "previous_claims": _claims(rng, [.75, .15, .07, .03, 0])}
    if rng.random() < 0.85:
        attrs["number_of_locations"] = pick(rng, [1, 2, 3, 4, 6, 8], [.45, .20, .15, .10, .06, .04])
    return value, code, cov, attrs


MANDATORY_ASSET_ATTRS = {"MOTOR": ["vehicle_type", "manufacturing_year", "registration_location", "previous_accidents"],
                         "PROPERTY": ["construction_type", "flood_exposure", "fire_exposure", "property_type"],
                         "COMMERCIAL": ["business_category", "industry_hazard_class", "fire_exposure"]}


HIGH_LOCS = [c for c, t in R.LOCATION_RISK_TIER.items() if t == "HIGH"]


def _make_risky(rng, product, attrs, loc):
    """~9% of applicants are high-hazard profiles (drives HIGH-risk referrals and risk-based declines)."""
    loc = rng.choice(HIGH_LOCS)
    if product == "MOTOR":
        attrs.update(vehicle_type=rng.choice(["MOTORCYCLE", "SPORTS", "TRUCK"]), previous_accidents=rng.choice([2, 3, 3, 4]),
                     previous_claims=rng.choice([2, 3, 3, 4]), registration_location=loc,
                     manufacturing_year=R.AS_OF_YEAR - rng.randint(10, 20))
    elif product == "PROPERTY":
        attrs.update(flood_exposure=rng.choice(["MODERATE", "HIGH", "HIGH"]), fire_exposure=rng.choice(["MODERATE", "HIGH"]),
                     construction_type=rng.choice(["TIMBER", "TIMBER", "MIXED"]), previous_claims=rng.choice([1, 2, 3]),
                     year_built=R.AS_OF_YEAR - rng.randint(45, 95))
    else:
        attrs.update(industry_hazard_class="HIGH", fire_exposure=rng.choice(["MODERATE", "HIGH", "HIGH"]),
                     business_category=rng.choice(["MANUFACTURING", "CONSTRUCTION", "LOGISTICS"]),
                     previous_claims=rng.choice([1, 2, 3]), number_of_locations=1)
    return attrs, loc


def sample_quote_payload(rng, product, applicant, missing_rate=0.06, risky_rate=0.09):
    """Returns (payload, fix) where `fix` holds the mandatory attribute withheld (if any) so a later
    information-provision step can legitimately supply it."""
    loc = applicant["location"] if rng.random() < 0.85 else pick(rng, LOCS, LOC_W)
    value, code, cov, attrs = {"MOTOR": sample_motor, "PROPERTY": sample_property, "COMMERCIAL": sample_commercial}[product](rng, loc)
    if rng.random() < risky_rate:
        attrs, loc = _make_risky(rng, product, attrs, loc)
    fix = {}
    if rng.random() < missing_rate:
        key = rng.choice(MANDATORY_ASSET_ATTRS[product])
        fix[key] = attrs.pop(key)
    elif "previous_claims" in attrs and rng.random() < 0.07:
        attrs.pop("previous_claims")                           # optional risk info missing -> penalised, not blocking
    payload = {"product_key": product, "coverage_code": code, "requested_coverage": cov,
               "applicant": dict(applicant), "asset": {"declared_value": value, "location": loc, "attributes": attrs}}
    return payload, fix
