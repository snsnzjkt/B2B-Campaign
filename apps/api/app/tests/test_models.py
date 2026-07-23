from app.models import Organization, User


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
