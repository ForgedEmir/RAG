"""Tests unitaires — PII Masker (regex uniquement)."""
from src.security.pii_masker import masquer


def test_masque_email():
    result = masquer("Contactez admin@example.com pour plus d'infos.")
    assert "[EMAIL]" in result
    assert "admin@example.com" not in result


def test_masque_ip():
    result = masquer("Le serveur est sur 192.168.1.42")
    assert "[IP]" in result
    assert "192.168.1.42" not in result


def test_masque_carte_bancaire():
    result = masquer("Carte : 4111 1111 1111 1111")
    assert "[CARTE]" in result
    assert "4111" not in result


def test_masque_plusieurs_pii():
    texte = "Email: test@lore.fr, IP: 10.0.0.1"
    result = masquer(texte)
    assert "[EMAIL]" in result
    assert "[IP]" in result


def test_masque_telephone_international():
    result = masquer("Appelle-moi au +33 6 12 34 56 78")
    assert "[TEL]" in result


def test_masque_telephone_local():
    result = masquer("Mon numéro : 06 12 34 56 78")
    assert "[TEL]" in result


def test_texte_vide():
    assert masquer("") == ""
    assert masquer(None) is None


def test_noms_personnages_non_masques():
    """Les noms propres fictifs du lore ne doivent pas être masqués."""
    assert "Lucas" in masquer("Comment s'appelle Lucas dans le lore ?")
    assert "Aethon" in masquer("Qui est le Maître Aethon ?")


def test_nombres_lore_non_masques():
    """Les nombres isolés du lore ne doivent pas être masqués comme téléphone."""
    assert "300" in masquer("Le Maître Aethon est né en l'an 300.")
    assert "1234567" in masquer("Il règne depuis 1234567 ans.")
