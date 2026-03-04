"""
Tests unitaires pour le module de validation des fichiers.
Tests essentiels : encodage, taille, CSV, JSON, batch validation.
"""
import json
import csv
import pytest
from src.ingestion.validator import validate_file, validate_files_batch


class TestValidation:
    """Tests de validation des fichiers (7 tests essentiels)"""
    
    def test_fichier_texte_valide(self, tmp_path):
        """Test 1: Fichier texte/markdown valide avec encodage UTF-8 correct"""
        fichier = tmp_path / "lore.md"
        content = """# Personnages du Royaume

## Héros Principal
**Nom**: Aldric le Brave
**Classe**: Paladin
**Description**: Un noble chevalier dévoué à la justice et à la protection des innocents.
"""
        fichier.write_text(content, encoding='utf-8')
        
        result = validate_file(str(fichier))
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_fichier_encodage_invalide(self, tmp_path):
        """Test 2: Rejet d'un fichier avec encodage non UTF-8"""
        fichier = tmp_path / "bad_encoding.txt"
        with open(fichier, 'wb') as f:
            # Bytes qui ne sont pas du UTF-8 valide
            f.write(b'\xff\xfe\xfd\x00Invalid UTF-8 content')
        
        result = validate_file(str(fichier))
        assert not result.is_valid
        assert any("encodage" in error.lower() for error in result.errors)
    
    def test_fichier_trop_petit_ou_vide(self, tmp_path):
        """Test 3: Rejet des fichiers trop petits ou vides"""
        # Fichier trop petit
        fichier_petit = tmp_path / "tiny.txt"
        fichier_petit.write_text("ab", encoding='utf-8')
        result = validate_file(str(fichier_petit))
        assert not result.is_valid
        assert any("trop petit" in error.lower() for error in result.errors)
        
        # Fichier vide
        fichier_vide = tmp_path / "empty.txt"
        fichier_vide.write_text("", encoding='utf-8')
        result = validate_file(str(fichier_vide))
        assert not result.is_valid
    
    def test_csv_valide_et_invalide(self, tmp_path):
        """Test 4: Validation CSV - structure correcte vs données manquantes"""
        # CSV valide
        fichier_valide = tmp_path / "pnj.csv"
        with open(fichier_valide, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['nom', 'role', 'description'])
            writer.writerow(['Jean le Forgeron', 'marchand', 'Vend des armes'])
            writer.writerow(['Marie la Sage', 'quête', 'Donne des conseils'])
        
        result = validate_file(str(fichier_valide))
        assert result.is_valid
        
        # CSV sans données (seulement en-tête)
        fichier_invalide = tmp_path / "empty.csv"
        with open(fichier_invalide, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['nom', 'description'])
        
        result = validate_file(str(fichier_invalide))
        assert not result.is_valid
        assert any("données" in error.lower() for error in result.errors)
    
    def test_json_valide_et_invalide(self, tmp_path):
        """Test 5: Validation JSON - structure correcte vs syntaxe invalide"""
        # JSON valide
        fichier_valide = tmp_path / "items.json"
        data = [
            {"id": 1, "nom": "Potion de vie", "type": "consommable", "prix": 25},
            {"id": 2, "nom": "Épée longue", "type": "arme", "prix": 100}
        ]
        fichier_valide.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        
        result = validate_file(str(fichier_valide))
        assert result.is_valid
        
        # JSON syntaxiquement invalide
        fichier_invalide = tmp_path / "bad.json"
        fichier_invalide.write_text('{"nom": "test", "bad": }', encoding='utf-8')
        
        result = validate_file(str(fichier_invalide))
        assert not result.is_valid
        assert any("invalide" in error.lower() for error in result.errors)
    
    def test_validation_par_lot(self, tmp_path):
        """Test 6: Validation de plusieurs fichiers simultanément"""
        # Créer 3 fichiers : 1 valide, 1 invalide (trop petit), 1 valide JSON
        fichier1 = tmp_path / "valide.txt"
        fichier1.write_text("Contenu de test suffisamment long et valide", encoding='utf-8')
        
        fichier2 = tmp_path / "invalide.txt"
        fichier2.write_text("ab", encoding='utf-8')  # Trop petit
        
        fichier3 = tmp_path / "data.json"
        fichier3.write_text(json.dumps({"nom": "item", "description": "test"}), encoding='utf-8')
        
        results = validate_files_batch([str(fichier1), str(fichier2), str(fichier3)])
        
        assert len(results) == 3
        assert results[str(fichier1)].is_valid
        assert not results[str(fichier2)].is_valid
        assert results[str(fichier3)].is_valid
    
    def test_fichier_inexistant(self):
        """Test 7: Gestion des fichiers inexistants"""
        result = validate_file("/chemin/qui/nexiste/pas/fichier.txt")
        assert not result.is_valid
        assert any("n'existe pas" in error for error in result.errors)
