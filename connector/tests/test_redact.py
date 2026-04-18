from connector.redact import PiiRedactor


def test_phone_email_roundtrip():
    r = PiiRedactor()
    text = "Call me at 13812345678 or email alice@example.com."
    red = r.apply(text)
    assert "13812345678" not in red.text
    assert "alice@example.com" not in red.text
    assert "<<CN_PHONE_1>>" in red.text
    assert "<<EMAIL_1>>" in red.text
    restored = r.rehydrate(red.text, red.reverse_map)
    assert restored == text


def test_cn_id_and_bank_luhn():
    r = PiiRedactor()
    # 17 digits + X checksum (not a real ID, format-only)
    text = "id 11010519491231002X and card 4539578763621486 and bad 1234567890123456"
    red = r.apply(text)
    assert "<<CN_ID_1>>" in red.text
    # Valid Luhn bank number is tokenized
    assert "<<BANK_1>>" in red.text
    # 1234567890123456 fails Luhn → untouched
    assert "1234567890123456" in red.text


def test_rehydrate_nested_structures():
    r = PiiRedactor()
    red = r.apply("ping alice@example.com")
    payload = {"contacts": [{"email_token": "<<EMAIL_1>>", "notes": "hi <<EMAIL_1>>"}]}
    out = r.rehydrate(payload, red.reverse_map)
    assert out["contacts"][0]["email_token"] == "alice@example.com"
    assert out["contacts"][0]["notes"] == "hi alice@example.com"
