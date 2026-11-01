import copy
from datetime import datetime
import pytest

from app.core.security import Actor
from app.database.session import init_db, make_engine, make_session_factory
from app.services.demo_scenarios import BY_ID
from app.services.seed import seed_master_data

NOW = datetime(2026, 3, 1, 10, 0, 0)
CUSTOMER = Actor("cust-A", "CUSTOMER", customer_key="key-A")
OTHER_CUSTOMER = Actor("cust-B", "CUSTOMER", customer_key="key-B")
ANALYST = Actor("analyst1", "OPERATIONS_ANALYST")
REVIEWER = Actor("reviewer1", "RISK_REVIEWER")
ADMIN = Actor("admin1", "ADMINISTRATOR")


@pytest.fixture()
def session():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    s = make_session_factory(engine)()
    seed_master_data(s)
    s.commit()
    yield s
    s.close()


def scenario(sid, **over):
    p = copy.deepcopy(BY_ID[sid]["payload"])
    p.update(over)
    return p


# ------------------------------------------------------------------ API fixtures
from fastapi.testclient import TestClient  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

STAFF_CODE = "test-staff-code"


@pytest.fixture()
def api(tmp_path):
    settings = Settings(database_url="sqlite:///:memory:", session_secret="test-secret",
                        staff_access_code=STAFF_CODE, data_dir=str(tmp_path / "data"))
    app = create_app(settings, make_engine("sqlite:///:memory:"))
    with TestClient(app) as c:
        c.app_ref = app
        yield c


def login(api, role, name=None):
    body = {"role": role, "display_name": name}
    if role != "CUSTOMER":
        body["access_code"] = STAFF_CODE
    r = api.post("/api/auth/demo-session", json=body)
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture()
def cust_a(api): return login(api, "CUSTOMER")
@pytest.fixture()
def cust_b(api): return login(api, "CUSTOMER")
@pytest.fixture()
def analyst(api): return login(api, "OPERATIONS_ANALYST", "ann")
@pytest.fixture()
def reviewer(api): return login(api, "RISK_REVIEWER", "rev")
@pytest.fixture()
def admin(api): return login(api, "ADMINISTRATOR", "root")
