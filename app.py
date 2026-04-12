import sqlite3
import os
from flask import Flask, request, jsonify, Response, render_template_string
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

# Template HTML de l'interface utilisateur
TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LogiStock - Gestion d'inventaire</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; }
        form { background: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        input { padding: 8px; margin: 5px; border: 1px solid #ddd; border-radius: 4px; }
        button { background: #3498db; color: white; padding: 8px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #2980b9; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th { background: #3498db; color: white; padding: 12px; text-align: left; }
        td { padding: 10px 12px; border-bottom: 1px solid #eee; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: #f0f7ff; }
        .badge { background: #27ae60; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.85em; }
        .empty { text-align: center; color: #999; padding: 20px; }
    </style>
</head>
<body>
    <h1>LogiStock — Gestion d'inventaire</h1>

    <h2>Ajouter un article</h2>
    <form method="POST" action="/ajouter">
        <label>Nom de l'article :</label><br>
        <input type="text" name="nom" placeholder="Ex: Casque de chantier" required>
        <label>Quantite :</label>
        <input type="number" name="quantite" placeholder="Ex: 50" min="0" required>
        <button type="submit">Ajouter</button>
    </form>

    <h2>Inventaire actuel</h2>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Article</th>
                <th>Quantite</th>
            </tr>
        </thead>
        <tbody>
            {% if articles %}
                {% for article in articles %}
                <tr>
                    <td>{{ article[0] }}</td>
                    <td>{{ article[1] }}</td>
                    <td><span class="badge">{{ article[2] }}</span></td>
                </tr>
                {% endfor %}
            {% else %}
                <tr><td colspan="3" class="empty">Aucun article dans l'inventaire.</td></tr>
            {% endif %}
        </tbody>
    </table>
</body>
</html>
"""

# Fonction pour initialiser la base de donnees au demarrage
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS articles
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, quantite INTEGER)''')
    conn.commit()
    conn.close()

# Route 1 : Interface web accessible depuis un navigateur
@app.route('/', methods=['GET'])
def index():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM articles")
    articles = c.fetchall()
    conn.close()
    REQUETES_TOTALES.labels(methode='GET', route='/', statut='200').inc()
    return render_template_string(TEMPLATE_HTML, articles=articles)

# Route 2 : Ajout via le formulaire web
@app.route('/ajouter', methods=['POST'])
def ajouter():
    nom = request.form.get('nom', '').strip()
    quantite = request.form.get('quantite', 0)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO articles (nom, quantite) VALUES (?, ?)", (nom, int(quantite)))
    conn.commit()
    conn.close()
    REQUETES_TOTALES.labels(methode='POST', route='/ajouter', statut='302').inc()
    from flask import redirect
    return redirect('/')

# Route 3 : API REST — Voir tous les articles (pour le CI/CD et les tests)
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

# Route 4 : API REST — Ajouter un article (pour le CI/CD et les tests)
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

# Route 5 : Health Check utilise par le pipeline CI/CD et la supervision
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"statut": "ok", "service": "logistock-api"}), 200

# Route 6 : Exposition des metriques applicatives pour Prometheus
@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    init_db()
    # host='0.0.0.0' est crucial pour que l'application soit accessible depuis l'exterieur du conteneur
    app.run(host='0.0.0.0', port=5000)
