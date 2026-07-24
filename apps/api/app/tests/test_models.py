from app.models import Company, Organization, ProviderSearchLog, User


def test_create_organization_and_user(db_session):
    org = Organization(name="Acme Inc")
    db_session.add(org)
    db_session.flush()

    user = User(organization_id=org.id, email="founder@acme.com", hashed_password="hashed", role="owner")
    db_session.add(user)
    db_session.commit()

    fetched = db_session.get(User, user.id)
    assert fetched is not None
    assert fetched.organization.name == "Acme Inc"


def test_company_external_id_persists(db_session):
    org = Organization(name="Acme Inc")
    db_session.add(org)
    db_session.flush()

    company = Company(organization_id=org.id, name="Acme Corp", external_id="place-123")
    db_session.add(company)
    db_session.commit()

    fetched = db_session.get(Company, company.id)
    assert fetched.external_id == "place-123"


def test_provider_search_log_persists(db_session):
    org = Organization(name="Acme Inc")
    db_session.add(org)
    db_session.flush()

    log = ProviderSearchLog(organization_id=org.id, provider="google_places")
    db_session.add(log)
    db_session.commit()

    fetched = db_session.get(ProviderSearchLog, log.id)
    assert fetched.provider == "google_places"
    assert fetched.created_at is not None
