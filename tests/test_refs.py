import pytest

from secret_broker.refs import RefError, parse_ref


def test_parse_full_ref():
    ref = parse_ref("secret://aws/prod/db#password")
    assert ref.store == "aws"
    assert ref.path == "prod/db"
    assert ref.field == "password"
    assert ref.display() == "secret://aws/prod/db#password"


def test_parse_shorthand():
    ref = parse_ref("env/API_TOKEN")
    assert ref.store == "env"
    assert ref.path == "API_TOKEN"
    assert ref.field is None


def test_parse_rejects_bad_scheme():
    with pytest.raises(RefError):
        parse_ref("https://evil.example/x")


def test_parse_rejects_incomplete():
    with pytest.raises(RefError):
        parse_ref("secret://aws")
