"""Tests unitaires — PII Masker (regex uniquement)."""
from src.security.pii_masker import mask


def test_masque_email():
    result = mask("Contactez admin@example.com pour plus d'infos.")
    assert "[EMAIL]" in result
    assert "admin@example.com" not in result


def test_masque_ip():
    result = mask("Le serveur est sur 192.168.1.42")
    assert "[IP]" in result
    assert "192.168.1.42" not in result


def test_masque_carte_bancaire():
    result = mask("Carte : 4111 1111 1111 1111")
    assert "[CARD]" in result
    assert "4111" not in result


def test_masque_plusieurs_pii():
    texte = "Email: test@lore.fr, IP: 10.0.0.1"
    result = mask(texte)
    assert "[EMAIL]" in result
    assert "[IP]" in result


def test_masque_telephone_international():
    result = mask("Appelle-moi au +33 6 12 34 56 78")
    assert "[PHONE]" in result


def test_masque_telephone_local():
    result = mask("My number: 06 12 34 56 78")
    assert "[PHONE]" in result


def test_empty_text():
    assert mask("") == ""
    assert mask(None) is None


def test_noms_personnages_non_masques():
    """Fictional proper nouns from the lore must not be masked."""
    assert "Lucas" in mask("Comment s'appelle Lucas dans le lore ?")
    assert "Aethon" in mask("Who is Master Aethon?")


def test_nombres_lore_non_masques():
    """Isolated numbers from the lore must not be masked as phones."""
    assert "300" in mask("Master Aethon was born in the year 300.")
    assert "1234567" in mask("He has reigned for 1234567 years.")
