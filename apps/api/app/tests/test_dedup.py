import uuid

from app.core.dedup import find_duplicate_company, normalize_website
from app.models import Company


def test_normalize_website_strips_scheme_and_www():
    assert normalize_website("https://www.Acme.com/path") == "acme.com"


def test_normalize_website_handles_bare_domain():
    assert normalize_website("acme.com") == "acme.com"


def test_normalize_website_none_and_empty():
    assert normalize_website(None) is None
    assert normalize_website("") is None


def test_find_duplicate_company_by_external_id(db_session):
    org_id = uuid.uuid4()
    db_session.add(Company(organization_id=org_id, name="Acme", external_id="place-1"))
    db_session.commit()

    match = find_duplicate_company(db_session, org_id, "place-1", None)
    assert match is not None
    assert match.name == "Acme"


def test_find_duplicate_company_by_normalized_website(db_session):
    org_id = uuid.uuid4()
    db_session.add(
        Company(organization_id=org_id, name="Acme", website="https://www.acme.com", external_id="place-1")
    )
    db_session.commit()

    match = find_duplicate_company(db_session, org_id, "different-place-id", "http://acme.com/")
    assert match is not None


def test_find_duplicate_company_no_match(db_session):
    org_id = uuid.uuid4()
    db_session.add(Company(organization_id=org_id, name="Acme", external_id="place-1"))
    db_session.commit()

    match = find_duplicate_company(db_session, org_id, "place-2", "https://other.com")
    assert match is None


def test_find_duplicate_company_scoped_to_organization(db_session):
    other_org_id = uuid.uuid4()
    db_session.add(Company(organization_id=other_org_id, name="Acme", external_id="place-1"))
    db_session.commit()

    match = find_duplicate_company(db_session, uuid.uuid4(), "place-1", None)
    assert match is None
