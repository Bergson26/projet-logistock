import pytest
import json
import os
import tempfile
from app import app, init_db, DB_PATH

# Configuration de l'environnement de test
@pytest.fixture
def client():
    # Utilisation d'une base de donnees temporaire isolee pour les tests
    db_tmp = tempfile.mktemp(suffix='.db')
    import app as app_module
    app_module.DB_PATH = db_tmp

    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            app_module.init_db()
        yield client

    # Nettoyage apres chaque test
    if os.path.exists(db_tmp):
        os.remove(db_tmp)


# --- Tests fonctionnels ---

class TestHealthCheck:
    def test_health_retourne_200(self, client):
        """Le health check doit repondre 200 OK"""
        reponse = client.get('/health')
        assert reponse.status_code == 200

    def test_health_retourne_statut_ok(self, client):
        """Le health check doit retourner le statut ok"""
        reponse = client.get('/health')
        data = json.loads(reponse.data)
        assert data['statut'] == 'ok'
        assert data['service'] == 'logistock-api'


class TestApiArticles:
    def test_liste_articles_vide(self, client):
        """La liste des articles doit etre vide au demarrage"""
        reponse = client.get('/api/articles')
        assert reponse.status_code == 200
        data = json.loads(reponse.data)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_ajout_article(self, client):
        """Un article ajoute doit apparaitre dans la liste"""
        payload = {'nom': 'Casque de chantier', 'quantite': 10}
        reponse = client.post(
            '/api/articles',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert reponse.status_code == 201
        data = json.loads(reponse.data)
        assert data['message'] == 'Article ajoute avec succes'

    def test_ajout_puis_lecture(self, client):
        """Un article ajoute via POST doit etre retrouve via GET"""
        payload = {'nom': 'Gants de securite', 'quantite': 25}
        client.post(
            '/api/articles',
            data=json.dumps(payload),
            content_type='application/json'
        )
        reponse = client.get('/api/articles')
        data = json.loads(reponse.data)
        assert len(data) == 1
        assert data[0]['nom'] == 'Gants de securite'
        assert data[0]['quantite'] == 25

    def test_ajout_multiple_articles(self, client):
        """Plusieurs articles doivent pouvoir etre ajoutes"""
        articles = [
            {'nom': 'Casque', 'quantite': 10},
            {'nom': 'Gants', 'quantite': 20},
            {'nom': 'Gilet', 'quantite': 15},
        ]
        for article in articles:
            client.post(
                '/api/articles',
                data=json.dumps(article),
                content_type='application/json'
            )
        reponse = client.get('/api/articles')
        data = json.loads(reponse.data)
        assert len(data) == 3

    def test_article_possede_les_bons_champs(self, client):
        """Chaque article doit avoir les champs id, nom et quantite"""
        payload = {'nom': 'Botte de securite', 'quantite': 5}
        client.post(
            '/api/articles',
            data=json.dumps(payload),
            content_type='application/json'
        )
        reponse = client.get('/api/articles')
        data = json.loads(reponse.data)
        article = data[0]
        assert 'id' in article
        assert 'nom' in article
        assert 'quantite' in article


class TestMetriques:
    def test_endpoint_metrics_accessible(self, client):
        """L'endpoint /metrics doit etre accessible pour Prometheus"""
        reponse = client.get('/metrics')
        assert reponse.status_code == 200

    def test_metrics_contient_compteur_requetes(self, client):
        """Les metriques doivent contenir le compteur de requetes LogiStock"""
        client.get('/api/articles')
        reponse = client.get('/metrics')
        assert b'logistock_requetes_total' in reponse.data
