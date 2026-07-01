from app.services.llm.oauth.pkce import generate_code_challenge, generate_code_verifier, generate_oauth_state


def test_pkce_challenge_is_url_safe_and_verifiable() -> None:
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)

    assert len(verifier) >= 43
    assert "=" not in challenge
    assert generate_code_challenge(verifier) == challenge


def test_oauth_state_is_unique() -> None:
    states = {generate_oauth_state() for _ in range(20)}
    assert len(states) == 20
