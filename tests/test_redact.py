from secret_broker.redact import redact_text


def test_redacts_plaintext_and_encodings():
    secret = "super-secret-value"
    text = f"token={secret} also {secret}"
    out, changed = redact_text(text, [secret])
    assert changed
    assert secret not in out
    assert out.count("[REDACTED]") >= 1
