"""CENTRALISED BUSINESS RULES  (illustrative synthetic rules - NOT real insurer policy).

Every threshold, rate table, factor, weight, limit and authority level used by the
deterministic engines lives here. Engines import from this module only; no business
constants may be hard-coded elsewhere. Bump RULES_VERSION when anything changes.
"""
from __future__ import annotations

RULES_VERSION = "RULES-1.0.0"
PREMIUM_FORMULA_VERSION = "PREM-1.0.0"
UW_ENGINE_VERSION = "UW-1.0.0"

CURRENCY = "USD"
ID_YEAR = 2026                      # year segment of deterministic IDs (APP-2026-000001)
AS_OF_YEAR = 2026                   # default reference year for asset-age derivation
PREMIUM_TOLERANCE = 0.01            # reconciliation tolerance (currency units)
QUOTE_VALIDITY_DAYS = 30
RENEWAL_WINDOW_DAYS = 60            # renewal may be generated this many days before expiry
TERMS_VERSION = "TERMS-DEMO-1.0"

# ---------------------------------------------------------------- risk scoring
RISK_THRESHOLDS = {"low_max": 30, "medium_max": 70}   # >70 => HIGH
DECLINE_RISK_SCORE = 85.0           # score >= this is declined automatically
MISSING_RISK_PENALTY = 60.0         # missing/unrecognised input is NEVER scored as 0
UNKNOWN_CLAIMS_FACTOR = 1.10        # premium claims-factor when claims history unknown

# ---------------------------------------------------------- approval authority
AUTHORITY_LEVELS = ["AUTOMATED", "OPERATIONS_ANALYST", "RISK_REVIEWER", "SENIOR_UNDERWRITER"]
ROLE_AUTHORITY = {                  # highest authority each role may exercise
    "CUSTOMER": None,
    "OPERATIONS_ANALYST": "OPERATIONS_ANALYST",
    "RISK_REVIEWER": "RISK_REVIEWER",
    "ADMINISTRATOR": "SENIOR_UNDERWRITER",
}
RISK_CATEGORY_AUTHORITY = {         # minimum authority implied by risk category
    "LOW": "AUTOMATED",
    "MEDIUM": "OPERATIONS_ANALYST",
    "HIGH": "SENIOR_UNDERWRITER",
}
EXCEPTION_RULES = {                 # referral conditions that raise minimum authority
    "UW-REF-CLAIMS": {"field": "previous_claims", "min": 3, "authority": "RISK_REVIEWER",
                      "message": "3 or more prior claims requires risk/compliance review"},
}

# --------------------------------------------------------------- geography
DEFAULT_LOCATION_TIER = "MEDIUM"
LOCATION_RISK_TIER = {
    "Alderbrook": "LOW", "Hillcrest": "LOW", "Maplewood": "LOW",
    "Riverton": "MEDIUM", "Lakeside": "MEDIUM", "Fairview": "MEDIUM",
    "Harborview": "HIGH", "Deltaport": "HIGH", "Stormvale": "HIGH",
}

# fields whose string values are normalised to UPPER CASE on ingestion
ENUM_FIELDS = ["vehicle_type", "property_type", "construction_type", "flood_exposure",
               "fire_exposure", "business_category", "industry_hazard_class"]
# fields that must be integers when present
INT_FIELDS = ["previous_accidents", "previous_claims", "number_of_locations",
              "manufacturing_year", "year_built"]

EXPOSURE_LEVELS = ["NONE", "LOW", "MODERATE", "HIGH"]
EXPOSURE_SCORE = {"NONE": 0, "LOW": 20, "MODERATE": 55, "HIGH": 95}
COUNT_BANDS = [(0, 0, 5), (1, 1, 40), (2, 2, 70), (3, 999, 100)]     # accidents / claims
LOCATION_SCORE = {"LOW": 10, "MEDIUM": 40, "HIGH": 85}

# premium factor tables shared by all products
CLAIMS_FACTOR = [(0, 0, 1.00), (1, 1, 1.15), (2, 2, 1.35), (3, 999, 1.70)]
RISK_CATEGORY_FACTOR = {"LOW": 1.00, "MEDIUM": 1.15, "HIGH": 1.40}

# --------------------------------------------------------- coverage options
# rate_multiplier scales the base rate for richer cover; limits are per-policy sums insured.
COVERAGE_OPTIONS = [
    dict(coverage_id="COV-001", code="MOTOR_THEFT_FIRE", product_key="MOTOR",
         name="Theft & Fire", min_limit=2000, max_limit=150000, rate_multiplier=0.60),
    dict(coverage_id="COV-002", code="MOTOR_COMPREHENSIVE", product_key="MOTOR",
         name="Comprehensive", min_limit=2000, max_limit=150000, rate_multiplier=1.00),
    dict(coverage_id="COV-003", code="MOTOR_COMPREHENSIVE_PLUS", product_key="MOTOR",
         name="Comprehensive Plus", min_limit=5000, max_limit=150000, rate_multiplier=1.25),
    dict(coverage_id="COV-004", code="PROP_BUILDING_BASIC", product_key="PROPERTY",
         name="Building Basic", min_limit=50000, max_limit=2000000, rate_multiplier=0.80),
    dict(coverage_id="COV-005", code="PROP_BUILDING_PLUS", product_key="PROPERTY",
         name="Building Plus (incl. flood)", min_limit=50000, max_limit=2000000, rate_multiplier=1.00),
    dict(coverage_id="COV-006", code="PROP_BUILDING_CONTENTS", product_key="PROPERTY",
         name="Building & Contents", min_limit=50000, max_limit=2000000, rate_multiplier=1.20),
    dict(coverage_id="COV-007", code="COMM_PROPERTY_ONLY", product_key="COMMERCIAL",
         name="Property Only", min_limit=50000, max_limit=3000000, rate_multiplier=0.90),
    dict(coverage_id="COV-008", code="COMM_PROPERTY_BI", product_key="COMMERCIAL",
         name="Property + Business Interruption", min_limit=50000, max_limit=3000000, rate_multiplier=1.15),
    dict(coverage_id="COV-009", code="COMM_ALL_RISKS", product_key="COMMERCIAL",
         name="All Risks", min_limit=100000, max_limit=3000000, rate_multiplier=1.40),
]
COVERAGE_BY_CODE = {c["code"]: c for c in COVERAGE_OPTIONS}
MAX_COVERAGE_TO_VALUE_RATIO = 1.0     # requested sum insured <= declared value x ratio

# ----------------------------------------------------------------- products
def _factor(rsk, code, label, inp, weight, mandatory, scorer):
    return dict(rsk_id=rsk, code=code, label=label, input=inp, weight=weight,
                mandatory=mandatory, scorer=scorer)


_EXPOSURE = {"map": EXPOSURE_SCORE}
_COUNT = {"bands": COUNT_BANDS}
_LOC = {"map": LOCATION_SCORE}

PRODUCTS = {
    "MOTOR": dict(
        product_id="PROD-001", name="Motor Insurance", asset_type="VEHICLE",
        base_rate=0.040, applicant_age=(18, 80), insured_value=(2000, 150000),
        max_asset_age=20, age_field="manufacturing_year",
        mandatory=["applicant_age", "declared_value", "requested_coverage", "coverage_code",
                   "location", "vehicle_type", "asset_age_years", "registration_location",
                   "previous_accidents"],
        allowed_values={"vehicle_type": ["HATCHBACK", "SEDAN", "SUV", "TRUCK", "MOTORCYCLE", "SPORTS"]},
        fixed_charges={"policy_fee": 25.0, "stamp_duty": 10.0},
        age_factor=[(0, 3, 0.95), (4, 8, 1.00), (9, 14, 1.20), (15, 999, 1.45)],
        location_factor={"LOW": 0.95, "MEDIUM": 1.00, "HIGH": 1.25},
        auto_approval_limit=40000, analyst_limit=75000, reviewer_limit=120000,
        risk_factors=[
            _factor("RSK-001", "PREVIOUS_ACCIDENTS", "Previous accidents", "previous_accidents", 0.30, True, _COUNT),
            _factor("RSK-002", "VEHICLE_AGE", "Vehicle age (years)", "asset_age_years", 0.15, True,
                    {"bands": [(0, 3, 10), (4, 8, 25), (9, 14, 55), (15, 999, 85)]}),
            _factor("RSK-003", "LOCATION_RISK", "Geographic risk tier", "location_tier", 0.20, True, _LOC),
            _factor("RSK-004", "PREVIOUS_CLAIMS", "Previous claims", "previous_claims", 0.20, False, _COUNT),
            _factor("RSK-005", "VEHICLE_TYPE", "Vehicle type", "vehicle_type", 0.15, True,
                    {"map": {"HATCHBACK": 20, "SEDAN": 25, "SUV": 35, "TRUCK": 45, "MOTORCYCLE": 60, "SPORTS": 80}}),
        ],
    ),
    "PROPERTY": dict(
        product_id="PROD-002", name="Property Insurance", asset_type="PROPERTY",
        base_rate=0.0035, applicant_age=(18, 85), insured_value=(50000, 2000000),
        max_asset_age=100, age_field="year_built",
        mandatory=["applicant_age", "declared_value", "requested_coverage", "coverage_code",
                   "location", "property_type", "construction_type", "asset_age_years",
                   "flood_exposure", "fire_exposure"],
        allowed_values={
            "property_type": ["HOUSE", "APARTMENT", "TOWNHOUSE", "VILLA"],
            "construction_type": ["CONCRETE", "MASONRY", "STEEL", "MIXED", "TIMBER"],
            "flood_exposure": EXPOSURE_LEVELS, "fire_exposure": EXPOSURE_LEVELS,
        },
        fixed_charges={"policy_fee": 40.0, "stamp_duty": 15.0},
        age_factor=[(0, 10, 0.95), (11, 30, 1.00), (31, 60, 1.20), (61, 999, 1.50)],
        location_factor={"LOW": 0.95, "MEDIUM": 1.00, "HIGH": 1.35},
        auto_approval_limit=250000, analyst_limit=500000, reviewer_limit=1000000,
        risk_factors=[
            _factor("RSK-006", "FLOOD_EXPOSURE", "Flood exposure", "flood_exposure", 0.25, True, _EXPOSURE),
            _factor("RSK-007", "FIRE_EXPOSURE", "Fire exposure", "fire_exposure", 0.20, True, _EXPOSURE),
            _factor("RSK-008", "BUILDING_AGE", "Building age (years)", "asset_age_years", 0.15, True,
                    {"bands": [(0, 10, 10), (11, 30, 30), (31, 60, 60), (61, 999, 85)]}),
            _factor("RSK-009", "CONSTRUCTION", "Construction material", "construction_type", 0.20, True,
                    {"map": {"CONCRETE": 10, "STEEL": 15, "MASONRY": 15, "MIXED": 40, "TIMBER": 70}}),
            _factor("RSK-010", "LOCATION_RISK", "Geographic risk tier", "location_tier", 0.10, True, _LOC),
            _factor("RSK-011", "PREVIOUS_CLAIMS", "Previous claims", "previous_claims", 0.10, False, _COUNT),
        ],
    ),
    "COMMERCIAL": dict(
        product_id="PROD-003", name="Commercial Insurance", asset_type="COMMERCIAL_ASSET",
        base_rate=0.0060, applicant_age=(18, 85), insured_value=(50000, 3000000),
        max_asset_age=None, age_field=None,
        mandatory=["applicant_age", "declared_value", "requested_coverage", "coverage_code",
                   "location", "business_category", "industry_hazard_class", "fire_exposure"],
        allowed_values={
            "business_category": ["OFFICE_SERVICES", "RETAIL", "HOSPITALITY", "LOGISTICS",
                                  "MANUFACTURING", "CONSTRUCTION"],
            "industry_hazard_class": ["LOW", "MODERATE", "HIGH"],
            "fire_exposure": EXPOSURE_LEVELS,
        },
        fixed_charges={"policy_fee": 60.0, "stamp_duty": 20.0},
        age_factor=None,
        location_factor={"LOW": 0.95, "MEDIUM": 1.00, "HIGH": 1.30},
        auto_approval_limit=300000, analyst_limit=750000, reviewer_limit=1500000,
        risk_factors=[
            _factor("RSK-012", "INDUSTRY_RISK", "Industry hazard class", "industry_hazard_class", 0.30, True,
                    {"map": {"LOW": 15, "MODERATE": 50, "HIGH": 85}}),
            _factor("RSK-013", "FIRE_EXPOSURE", "Fire exposure", "fire_exposure", 0.20, True, _EXPOSURE),
            _factor("RSK-014", "ASSET_CONCENTRATION", "Number of insured locations", "number_of_locations",
                    0.15, False, {"bands": [(1, 1, 80), (2, 3, 45), (4, 999, 20)]}),
            _factor("RSK-015", "BUSINESS_CATEGORY", "Business category", "business_category", 0.15, True,
                    {"map": {"OFFICE_SERVICES": 15, "RETAIL": 35, "HOSPITALITY": 50, "LOGISTICS": 55,
                             "MANUFACTURING": 65, "CONSTRUCTION": 75}}),
            _factor("RSK-016", "LOCATION_RISK", "Geographic risk tier", "location_tier", 0.10, True, _LOC),
            _factor("RSK-017", "PREVIOUS_CLAIMS", "Previous claims", "previous_claims", 0.10, False, _COUNT),
        ],
    ),
}
PRODUCT_BY_ID = {p["product_id"]: k for k, p in PRODUCTS.items()}

# ------------------------------------------------------------ endorsements
ENDORSEMENT_TYPES_REQUIRING_LIMIT_CHECK = ["COVERAGE_ADJUSTMENT", "DECLARED_VALUE_CHANGE", "ASSET_MODIFICATION"]

# ------------------------------------------------ customer form metadata (drives the dynamic portal form)
_EXP = [{"value": v, "label": v.title()} for v in EXPOSURE_LEVELS]


def _opts(values):
    return [{"value": v, "label": v.replace("_", " ").title()} for v in values]


ASSET_FORM_FIELDS = {
    "MOTOR": [
        {"name": "vehicle_type", "label": "Vehicle type", "type": "select", "required": True,
         "options": _opts(PRODUCTS["MOTOR"]["allowed_values"]["vehicle_type"])},
        {"name": "manufacturing_year", "label": "Manufacturing year", "type": "number", "required": True, "min": 1980, "max": AS_OF_YEAR},
        {"name": "registration_location", "label": "Registration location", "type": "location", "required": True},
        {"name": "previous_accidents", "label": "Accidents in last 5 years", "type": "number", "required": True, "min": 0, "max": 20},
        {"name": "previous_claims", "label": "Previous claims", "type": "number", "required": False, "min": 0, "max": 20},
    ],
    "PROPERTY": [
        {"name": "property_type", "label": "Property type", "type": "select", "required": True,
         "options": _opts(PRODUCTS["PROPERTY"]["allowed_values"]["property_type"])},
        {"name": "property_age_years", "label": "Property age (years)", "type": "number", "required": True, "min": 0, "max": 150},
        {"name": "construction_type", "label": "Construction type", "type": "select", "required": True,
         "options": _opts(PRODUCTS["PROPERTY"]["allowed_values"]["construction_type"])},
        {"name": "flood_exposure", "label": "Flood exposure", "type": "select", "required": True, "options": _EXP},
        {"name": "fire_exposure", "label": "Fire exposure", "type": "select", "required": True, "options": _EXP},
        {"name": "previous_claims", "label": "Previous claims", "type": "number", "required": False, "min": 0, "max": 20},
    ],
    "COMMERCIAL": [
        {"name": "business_category", "label": "Business category", "type": "select", "required": True,
         "options": _opts(PRODUCTS["COMMERCIAL"]["allowed_values"]["business_category"])},
        {"name": "industry_hazard_class", "label": "Industry hazard class", "type": "select", "required": True,
         "options": _opts(PRODUCTS["COMMERCIAL"]["allowed_values"]["industry_hazard_class"])},
        {"name": "fire_exposure", "label": "Fire exposure", "type": "select", "required": True, "options": _EXP},
        {"name": "number_of_locations", "label": "Number of insured locations", "type": "number", "required": False, "min": 1, "max": 100},
        {"name": "previous_claims", "label": "Previous claims", "type": "number", "required": False, "min": 0, "max": 20},
    ],
}
