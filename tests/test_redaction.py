"""B3: redact() masks phones, Lebanese IDs, emails and introduced names; keeps hotlines/meds."""
import pytest
from ai.redaction import redact


def test_ticket_example():
    out = redact("أنا محمد رقمي 70123456")
    assert "70123456" not in out and "محمد" not in out


@pytest.mark.parametrize("raw", [
    "70123456", "03 123 456", "+961 70 123 456", "00961-3-123456",
    "01/234567", "٧٠١٢٣٤٥٦", "+961 (71) 12-34-56",
])
def test_phones_masked(raw):
    out = redact(f"call me {raw} please")
    assert "[PHONE]" in out and not any(c.isdigit() for c in out.replace("[PHONE]", ""))


def test_national_id_masked():
    out = redact("رقم الهوية 123456789012")
    assert "123456789012" not in out and "[ID]" in out


def test_email_masked():
    assert "[EMAIL]" in redact("mail me at a.b@example.com")


@pytest.mark.parametrize("text,name", [
    ("اسمي علي حسن وبدي بطاقة", "علي"),
    ("my name is Karim Haddad and I need help", "Karim"),
    ("je m'appelle Nadine, comment faire", "Nadine"),
    ("ismi Rami w 3ande so2al", "Rami"),
    ("أنا ميرا بدي دوا", "ميرا"),
])
def test_names_masked(text, name):
    out = redact(text)
    assert name not in out and "[NAME]" in out


@pytest.mark.parametrize("text", [
    "أنا مريض وبدي دوا السكري",
    "call 1787 for the hotline",
    "الخط الساخن 1214 و 140",
    "price of Panadol 5000 LBP",
    "je suis enceinte, que faire",
])
def test_non_pii_untouched(text):
    assert redact(text) == text


def test_idempotent_and_empty():
    once = redact("اسمي علي 70123456")
    assert redact(once) == once
    assert redact("") == ""


@pytest.mark.parametrize("raw", ["03  123  456", "03_123_456", "03\u200f123456"])
def test_obfuscated_phones_are_masked(raw):
    assert "[PHONE]" in redact(f"my number is {raw}")
