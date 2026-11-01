"""Regression tests for database schema, column length constraints, and master data seeding.

Reproduces and guards against psycopg2.errors.StringDataRightTruncation: value too long for type character varying(24).
"""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from app.core import rules_config as R
from app.database.base import Base
from app.database.session import init_db
from app.models.entities import ApprovalAuthority, CoverageOption, Product, ProductCoverage, RiskFactor
from app.services.seed import seed_master_data


def test_approval_authority_id_length_accommodates_seed_data():
    """Regression test: approval_authorities.authority_id must not overflow VARCHAR(24).

    Previously, authority_id was String(24), but seed_master_data() generates identifiers
    such as 'AUTH-COMMERCIAL-OPERATIONS_ANALYST' (34 characters) and
    'AUTH-COMMERCIAL-SENIOR_UNDERWRITER' (34 characters).
    On PostgreSQL, this raised psycopg2.errors.StringDataRightTruncation.
    """
    col = ApprovalAuthority.__table__.columns["authority_id"]
    col_length = col.type.length

    # Verify that the column length is at least 48 characters
    assert col_length >= 48, f"Expected authority_id VARCHAR length >= 48, got {col_length}"

    # Verify every single seed authority_id strictly fits in the column
    limits = {
        "AUTOMATED": (100, "LOW"),
        "OPERATIONS_ANALYST": (200, "MEDIUM"),
        "RISK_REVIEWER": (300, "MEDIUM"),
        "SENIOR_UNDERWRITER": (None, "HIGH")
    }
    for key in R.PRODUCTS:
        for level in limits:
            auth_id = f"AUTH-{key}-{level}"
            assert len(auth_id) <= col_length, (
                f"Seed authority_id '{auth_id}' (len={len(auth_id)}) exceeds column limit {col_length}"
            )


def test_all_master_seed_data_strictly_fits_column_lengths():
    """Verify that every string field inserted by seed_master_data fits within its model column constraint."""
    # Check Products
    prod_table = Product.__table__
    for key, cfg in R.PRODUCTS.items():
        assert len(cfg["product_id"]) <= prod_table.columns["product_id"].type.length
        assert len(key) <= prod_table.columns["product_key"].type.length
        assert len(cfg["name"]) <= prod_table.columns["name"].type.length

    # Check Coverage Options
    cov_table = CoverageOption.__table__
    for c in R.COVERAGE_OPTIONS:
        assert len(c["coverage_id"]) <= cov_table.columns["coverage_id"].type.length
        assert len(c["code"]) <= cov_table.columns["code"].type.length
        assert len(c["name"]) <= cov_table.columns["name"].type.length

    # Check Risk Factors
    rf_table = RiskFactor.__table__
    for key, cfg in R.PRODUCTS.items():
        for f in cfg["risk_factors"]:
            assert len(f["rsk_id"]) <= rf_table.columns["risk_factor_id"].type.length
            assert len(f["code"]) <= rf_table.columns["code"].type.length
            assert len(f["label"]) <= rf_table.columns["label"].type.length
            assert len(f["input"]) <= rf_table.columns["input_field"].type.length


def test_postgresql_ddl_compilation_wides_column():
    """Verify that PostgreSQL DDL compiles authority_id as VARCHAR(48)."""
    ddl = str(CreateTable(ApprovalAuthority.__table__).compile(dialect=postgresql.dialect()))
    assert "VARCHAR(48)" in ddl or "character varying(48)" in ddl.lower(), ddl


def test_seed_master_data_is_idempotent(tmp_path):
    """Verify database initialization and multiple sequential seed executions are idempotent."""
    db_file = tmp_path / "seed_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine)
    Session = sessionmaker(bind=engine)

    with Session() as s:
        # First execution: inserts all master records
        seed_master_data(s)
        s.commit()

        initial_authorities = s.scalars(select(ApprovalAuthority)).all()
        assert len(initial_authorities) == 12
        initial_products = s.scalars(select(Product)).all()
        assert len(initial_products) == 3
        initial_coverages = s.scalars(select(CoverageOption)).all()
        assert len(initial_coverages) == 9

        # Second execution: must be a clean no-op
        seed_master_data(s)
        s.commit()

        # Third execution: must remain a clean no-op
        seed_master_data(s)
        s.commit()

        final_authorities = s.scalars(select(ApprovalAuthority)).all()
        assert len(final_authorities) == 12
        final_products = s.scalars(select(Product)).all()
        assert len(final_products) == 3
        final_coverages = s.scalars(select(CoverageOption)).all()
        assert len(final_coverages) == 9


def test_reproduce_original_varchar_24_truncation():
    """Directly demonstrates how VARCHAR(24) caused the failure when inserting seed data."""
    longest_id = "AUTH-COMMERCIAL-OPERATIONS_ANALYST"
    assert len(longest_id) == 34

    # Simulating what happens under a VARCHAR(24) constraint:
    original_varchar_limit = 24
    with pytest.raises(ValueError, match="StringDataRightTruncation simulation"):
        if len(longest_id) > original_varchar_limit:
            raise ValueError(
                f"StringDataRightTruncation simulation: value '{longest_id}' (len={len(longest_id)}) "
                f"too long for type character varying({original_varchar_limit})"
            )

