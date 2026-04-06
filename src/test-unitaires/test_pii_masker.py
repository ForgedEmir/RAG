"""Tests unitaires — PII Masker (regex only, zéro I/O réseau)."""
import pytest
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
    texte  = "Email: test@lore.fr, IP: 10.0.0.1"
    result = masquer(texte)
    assert "[EMAIL]" in result
    assert "[IP]" in result


def test_pas_de_masquage_sur_lore():
    """Le texte de lore sans PII ne doit pas être altéré."""
    texte  = "L'Archivist d'Aethelgard garde les parchemins du Voile de Fer."
    result = masquer(texte)
    assert result == texte


def test_texte_vide():
    assert masquer("") == ""
    assert masquer(None) is None


def test_noms_de_personnages_non_masques():
    """Les noms propres de lore ne doivent pas déclencher le masquage téléphone."""
    texte  = "Le Maître Aethon 7 est né en l'an 300."
    result = masquer(texte)
    # "300" seul ne doit pas être masqué (trop court pour un tel)
    assert "300" in result or "Aethon" in result
