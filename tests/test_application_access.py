from src.application_access import application_status


def test_empty_application_group_is_unknown() -> None:
    status, evidence = application_status(
        {
            "invite_only": 0,
            "application_format": "N/A",
            "deadlines": "NONE",
            "restrictions": "",
        }
    )
    assert (status, evidence) == ("Unknown", False)


def test_affirmative_instructions_are_accepting() -> None:
    status, evidence = application_status(
        {
            "invite_only": 0,
            "application_format": "Submit a letter and project budget",
        }
    )
    assert (status, evidence) == ("Accepting Applications", True)


def test_contact_language_is_not_open_application() -> None:
    status, evidence = application_status(
        {
            "invite_only": 0,
            "restrictions": "Guidelines will be provided upon request",
        }
    )
    assert (status, evidence) == ("Contact First", True)


def test_checkbox_wins() -> None:
    assert application_status({"invite_only": 1}) == ("Invite Only", True)
