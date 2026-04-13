from app.services.parser import parse_submission_text


def test_parse_valid_minimal_message() -> None:
    parsed = parse_submission_text("@carlos #insta360recomendado")
    assert parsed.parse_valid is True
    assert parsed.inviter_username == "carlos"
    assert parsed.hashtag_present is True


def test_parse_valid_with_extra_text_and_case_insensitive_hashtag() -> None:
    parsed = parse_submission_text("Me invitó @Carlos #Insta360Recomendado gracias")
    assert parsed.parse_valid is True
    assert parsed.inviter_username == "carlos"
    assert parsed.hashtag_present is True


def test_parse_invalid_without_username() -> None:
    parsed = parse_submission_text("#insta360recomendado only")
    assert parsed.parse_valid is False
    assert parsed.inviter_username is None
    assert parsed.hashtag_present is True


def test_parse_invalid_without_hashtag() -> None:
    parsed = parse_submission_text("@carlos only")
    assert parsed.parse_valid is False
    assert parsed.inviter_username == "carlos"
    assert parsed.hashtag_present is False

