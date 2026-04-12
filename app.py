import sqlite3
import os
from flask import Flask, request, jsonify, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# Chemin de la base de donnees dans le volume Docker
DB_PATH = os.path.join('/app/data', 'inventaire.db')

# Definition des metriques applicatives exposees a Prometheus
REQUETES_TOTALES = Counter(
    'logistock_requetes_total',
    "Nombre total de requetes HTTP recues par l'API",
    ['methode', 'route', 'statut']
)

LATENCE_REQUETES = Histogram(
    'logistock_latence_secondes',
    'Temps de traitement des requetes en secondes',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)


# Fonction pour initialiser la base de donnees au demarrage
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS articles
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, quantite INTEGER)''')
    conn.commit()
    conn.close()


# Route 1 : API REST — Voir tous les articles
@app.route('/api/articles', methods=['GET'])
def get_articles():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM articles")
    lignes = c.fetchall()
    conn.close()
    resultat = [{"id": row[0], "nom": row[1], "quantite": row[2]} for row in lignes]
    REQUETES_TOTALES.labels(methode='GET', route='/api/articles', statut='200').inc()
    return jsonify(resultat)


# Route 2 : API REST — Ajouter un article
@app.route('/api/articles', methods=['POST'])
def add_article():
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO articles (nom, quantite) VALUES (?, ?)", (data['nom'], data['quantite']))
    conn.commit()
    conn.close()
    REQUETES_TOTALES.labels(methode='POST', route='/api/articles', statut='201').inc()
    return jsonify({"message": "Article ajoute avec succes"}), 201


# Route 3 : Health Check utilise par la supervision
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"statut": "ok", "service": "logistock-api"}), 200


# Route 4 : Exposition des metriques applicatives pour Prometheus
@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
