import sqlite3
import os
from flask import Flask, request, jsonify, Response, render_template_string, redirect, url_for
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

DB_PATH = os.path.join('/app/data', 'inventaire.db')

CATEGORIES = [
    "Protection tête",
    "Protection mains",
    "Protection corps",
    "Protection pieds",
    "Protection ouïe",
    "Protection yeux",
    "Protection respiratoire",
    "Autre"
]

ARTICLES_INITIAUX = [
    ("Casque de chantier blanc",         48,  "Protection tête",          10),
    ("Casque de chantier jaune",          32,  "Protection tête",          10),
    ("Casque de chantier rouge",          14,  "Protection tête",          10),
    ("Visière de protection polycarbonate", 9, "Protection tête",           5),
    ("Gants anti-coupure niveau 3 T8",   67,  "Protection mains",         20),
    ("Gants anti-coupure niveau 3 T9",   43,  "Protection mains",         20),
    ("Gants anti-coupure niveau 3 T10",  29,  "Protection mains",         20),
    ("Gants thermo-isolants T9",          6,  "Protection mains",         15),
    ("Gants étanches noirs T9",          38,  "Protection mains",         15),
    ("Gilet haute visibilité classe 2",  54,  "Protection corps",         15),
    ("Gilet haute visibilité classe 3",  21,  "Protection corps",         10),
    ("Harnais antichute 1 point",         7,  "Protection corps",         10),
    ("Harnais antichute 2 points",        4,  "Protection corps",          8),
    ("Combinaison jetable T.L",          28,  "Protection corps",         10),
    ("Combinaison jetable T.XL",         11,  "Protection corps",         10),
    ("Genouillères de chantier",         19,  "Protection corps",          5),
    ("Bottes de sécurité T41",           14,  "Protection pieds",          8),
    ("Bottes de sécurité T42",           12,  "Protection pieds",          8),
    ("Bottes de sécurité T43",            5,  "Protection pieds",          8),
    ("Bottes de sécurité T44",           18,  "Protection pieds",          8),
    ("Bottes de sécurité T45",            9,  "Protection pieds",          8),
    ("Protections auditives jetables",  230,  "Protection ouïe",          50),
    ("Casque anti-bruit SNR 30dB",       19,  "Protection ouïe",           8),
    ("Bouchons d'oreilles réutilisables", 76, "Protection ouïe",          20),
    ("Lunettes de protection incolores", 87,  "Protection yeux",          20),
    ("Lunettes de protection teintées",  34,  "Protection yeux",          15),
    ("Lunettes panoramiques étanches",    8,  "Protection yeux",          10),
    ("Masque FFP2 sans valve",          145,  "Protection respiratoire",  30),
    ("Masque FFP3 avec valve",           62,  "Protection respiratoire",  20),
    ("Demi-masque filtrant A2P3",        17,  "Protection respiratoire",  10),
]

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

TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LogiStock — Gestion d'inventaire</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #f0f2f5;
            color: #2d3748;
            min-height: 100vh;
        }

        /* ===== HEADER ===== */
        header {
            background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
            color: white;
            padding: 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        .header-inner {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-logo {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .logo-icon {
            width: 48px;
            height: 48px;
            background: rgba(255,255,255,0.15);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
        }
        .header-logo h1 {
            font-size: 1.8rem;
            font-weight: 700;
            letter-spacing: -0.5px;
        }
        .header-logo span {
            font-size: 0.85rem;
            opacity: 0.75;
            display: block;
            font-weight: 400;
        }
        .header-meta {
            text-align: right;
            font-size: 0.82rem;
            opacity: 0.75;
        }

        /* ===== LAYOUT ===== */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 28px 24px;
        }

        /* ===== STATS CARDS ===== */
        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 28px;
        }
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            border-left: 4px solid #3182ce;
        }
        .stat-card.warning { border-left-color: #ed8936; }
        .stat-card.danger  { border-left-color: #e53e3e; }
        .stat-card.success { border-left-color: #38a169; }
        .stat-label {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #718096;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #1a202c;
        }
        .stat-sub {
            font-size: 0.78rem;
            color: #a0aec0;
            margin-top: 2px;
        }

        /* ===== PANELS ===== */
        .panel {
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            margin-bottom: 24px;
        }
        .panel-header {
            padding: 18px 24px;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .panel-header h2 {
            font-size: 1rem;
            font-weight: 600;
            color: #2d3748;
        }
        .panel-body { padding: 24px; }

        /* ===== FORM ===== */
        .form-grid {
            display: grid;
            grid-template-columns: 2fr 1fr 1.5fr 1fr auto;
            gap: 12px;
            align-items: end;
        }
        .form-group label {
            display: block;
            font-size: 0.78rem;
            font-weight: 600;
            color: #4a5568;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px 14px;
            border: 1.5px solid #e2e8f0;
            border-radius: 8px;
            font-size: 0.9rem;
            color: #2d3748;
            background: #f7fafc;
            transition: border-color 0.2s, box-shadow 0.2s;
            outline: none;
        }
        .form-group input:focus, .form-group select:focus {
            border-color: #3182ce;
            box-shadow: 0 0 0 3px rgba(49,130,206,0.15);
            background: white;
        }

        /* ===== BUTTONS ===== */
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
        }
        .btn-primary {
            background: #3182ce;
            color: white;
        }
        .btn-primary:hover { background: #2b6cb0; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(49,130,206,0.3); }
        .btn-danger {
            background: #fff5f5;
            color: #e53e3e;
            border: 1px solid #fed7d7;
            padding: 6px 12px;
            font-size: 0.8rem;
        }
        .btn-danger:hover { background: #e53e3e; color: white; }
        .btn-warning {
            background: #fffaf0;
            color: #c05621;
            border: 1px solid #fbd38d;
            padding: 6px 12px;
            font-size: 0.8rem;
        }
        .btn-warning:hover { background: #ed8936; color: white; }

        /* ===== FILTERS ===== */
        .filters {
            display: flex;
            gap: 12px;
            align-items: center;
            padding: 16px 24px;
            background: #f7fafc;
            border-bottom: 1px solid #e2e8f0;
            border-radius: 12px 12px 0 0;
        }
        .search-wrap {
            position: relative;
            flex: 1;
        }
        .search-wrap input {
            width: 100%;
            padding: 9px 14px 9px 36px;
            border: 1.5px solid #e2e8f0;
            border-radius: 8px;
            font-size: 0.88rem;
            background: white;
            outline: none;
            transition: border-color 0.2s;
        }
        .search-wrap input:focus { border-color: #3182ce; }
        .search-icon {
            position: absolute;
            left: 11px;
            top: 50%;
            transform: translateY(-50%);
            color: #a0aec0;
            font-size: 0.9rem;
        }
        .filter-select {
            padding: 9px 14px;
            border: 1.5px solid #e2e8f0;
            border-radius: 8px;
            font-size: 0.88rem;
            background: white;
            color: #2d3748;
            outline: none;
            cursor: pointer;
        }
        .filter-select:focus { border-color: #3182ce; }
        .filter-label {
            font-size: 0.8rem;
            color: #718096;
            font-weight: 600;
            white-space: nowrap;
        }

        /* ===== TABLE ===== */
        .table-wrap { overflow-x: auto; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        thead th {
            background: #f7fafc;
            padding: 12px 16px;
            text-align: left;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #718096;
            border-bottom: 2px solid #e2e8f0;
            white-space: nowrap;
        }
        tbody tr {
            border-bottom: 1px solid #f0f2f5;
            transition: background 0.15s;
        }
        tbody tr:hover { background: #f7fbff; }
        tbody tr.alerte-critique { background: #fff5f5; }
        tbody tr.alerte-critique:hover { background: #fed7d7; }
        tbody tr.alerte-warning { background: #fffaf0; }
        tbody tr.alerte-warning:hover { background: #fefcbf; }
        tbody td {
            padding: 13px 16px;
            font-size: 0.9rem;
            vertical-align: middle;
        }
        .td-id {
            color: #a0aec0;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .td-nom { font-weight: 500; }

        /* ===== BADGES ===== */
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.82rem;
            font-weight: 700;
        }
        .badge-ok      { background: #c6f6d5; color: #276749; }
        .badge-warning { background: #fefcbf; color: #744210; }
        .badge-danger  { background: #fed7d7; color: #9b2c2c; }
        .badge-cat {
            background: #ebf4ff;
            color: #2b6cb0;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 600;
        }

        /* ===== ACTIONS ===== */
        .actions { display: flex; gap: 6px; }

        /* ===== MODAL ===== */
        .modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal-overlay.open { display: flex; }
        .modal {
            background: white;
            border-radius: 16px;
            padding: 32px;
            width: 480px;
            max-width: 95vw;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .modal h3 {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 20px;
            color: #1a202c;
        }
        .modal-form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 20px;
        }
        .modal-form-grid .full { grid-column: 1 / -1; }
        .modal-footer { display: flex; gap: 10px; justify-content: flex-end; }
        .btn-secondary {
            background: #edf2f7;
            color: #4a5568;
            padding: 10px 20px;
        }
        .btn-secondary:hover { background: #e2e8f0; }

        /* ===== EMPTY STATE ===== */
        .empty {
            text-align: center;
            padding: 60px 20px;
            color: #a0aec0;
        }
        .empty-icon { font-size: 3rem; margin-bottom: 12px; }
        .empty p { font-size: 0.95rem; }

        /* ===== FOOTER ===== */
        footer {
            text-align: center;
            padding: 20px;
            font-size: 0.78rem;
            color: #a0aec0;
        }

        /* ===== RESPONSIVE ===== */
        @media (max-width: 900px) {
            .stats { grid-template-columns: repeat(2, 1fr); }
            .form-grid { grid-template-columns: 1fr 1fr; }
            .form-grid .btn-wrap { grid-column: 1 / -1; }
        }
    </style>
</head>
<body>

<header>
    <div class="header-inner">
        <div class="header-logo">
            <div class="logo-icon">🦺</div>
            <div>
                <h1>LogiStock</h1>
                <span>Gestion de matériel de sécurité</span>
            </div>
        </div>
        <div class="header-meta">
            Infrastructure DevSecOps — AWS EC2<br>
            Prometheus + Grafana
        </div>
    </div>
</header>

<div class="container">

    <!-- STATS -->
    <div class="stats">
        <div class="stat-card success">
            <div class="stat-label">Total articles</div>
            <div class="stat-value">{{ stats.total_articles }}</div>
            <div class="stat-sub">références en inventaire</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Stock total</div>
            <div class="stat-value">{{ stats.total_stock }}</div>
            <div class="stat-sub">unités disponibles</div>
        </div>
        <div class="stat-card warning">
            <div class="stat-label">Stocks faibles</div>
            <div class="stat-value">{{ stats.alerte_warning }}</div>
            <div class="stat-sub">sous 2× le seuil d'alerte</div>
        </div>
        <div class="stat-card danger">
            <div class="stat-label">Stocks critiques</div>
            <div class="stat-value">{{ stats.alerte_critique }}</div>
            <div class="stat-sub">sous le seuil d'alerte</div>
        </div>
    </div>

    <!-- ADD FORM -->
    <div class="panel">
        <div class="panel-header">
            <span>➕</span>
            <h2>Ajouter un article à l'inventaire</h2>
        </div>
        <div class="panel-body">
            <form method="POST" action="/ajouter">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Nom de l'article</label>
                        <input type="text" name="nom" placeholder="Ex : Casque de chantier blanc" required>
                    </div>
                    <div class="form-group">
                        <label>Quantité</label>
                        <input type="number" name="quantite" placeholder="0" min="0" required>
                    </div>
                    <div class="form-group">
                        <label>Catégorie</label>
                        <select name="categorie">
                            {% for cat in categories %}
                            <option value="{{ cat }}">{{ cat }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Seuil d'alerte</label>
                        <input type="number" name="seuil_alerte" placeholder="10" min="0" value="10">
                    </div>
                    <div class="form-group btn-wrap" style="display:flex;align-items:flex-end;">
                        <button type="submit" class="btn btn-primary" style="width:100%">
                            ➕ Ajouter
                        </button>
                    </div>
                </div>
            </form>
        </div>
    </div>

    <!-- INVENTORY TABLE -->
    <div class="panel">
        <div class="filters">
            <div class="search-wrap">
                <span class="search-icon">🔍</span>
                <input type="text" id="searchInput" placeholder="Rechercher un article…" oninput="filtrerTable()">
            </div>
            <span class="filter-label">Catégorie :</span>
            <select class="filter-select" id="catFilter" onchange="filtrerTable()">
                <option value="">Toutes</option>
                {% for cat in categories %}
                <option value="{{ cat }}">{{ cat }}</option>
                {% endfor %}
            </select>
            <select class="filter-select" id="alertFilter" onchange="filtrerTable()">
                <option value="">Tous les stocks</option>
                <option value="critique">⛔ Critiques</option>
                <option value="warning">⚠️ Faibles</option>
                <option value="ok">✅ OK</option>
            </select>
        </div>

        <div class="table-wrap">
            <table id="inventaireTable">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Article</th>
                        <th>Catégorie</th>
                        <th>Quantité</th>
                        <th>Seuil alerte</th>
                        <th>Statut</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                {% if articles %}
                    {% for a in articles %}
                    {% set statut = 'critique' if a[2] <= a[4] else ('warning' if a[2] <= a[4] * 2 else 'ok') %}
                    <tr class="alerte-{{ statut }}"
                        data-nom="{{ a[1]|lower }}"
                        data-cat="{{ a[3] }}"
                        data-statut="{{ statut }}">
                        <td class="td-id">#{{ a[0] }}</td>
                        <td class="td-nom">{{ a[1] }}</td>
                        <td><span class="badge-cat">{{ a[3] }}</span></td>
                        <td>
                            <strong>{{ a[2] }}</strong>
                        </td>
                        <td style="color:#a0aec0;font-size:0.85rem;">{{ a[4] }}</td>
                        <td>
                            {% if statut == 'critique' %}
                                <span class="badge badge-danger">⛔ Critique</span>
                            {% elif statut == 'warning' %}
                                <span class="badge badge-warning">⚠️ Faible</span>
                            {% else %}
                                <span class="badge badge-ok">✅ OK</span>
                            {% endif %}
                        </td>
                        <td>
                            <div class="actions">
                                <button class="btn btn-warning"
                                    onclick="ouvrirEditModal({{ a[0] }}, '{{ a[1]|replace("'", "\\'") }}', {{ a[2] }}, '{{ a[3] }}', {{ a[4] }})">
                                    ✏️ Modifier
                                </button>
                                <button class="btn btn-danger"
                                    onclick="supprimerArticle({{ a[0] }}, '{{ a[1]|replace("'", "\\'") }}')">
                                    🗑️ Supprimer
                                </button>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                {% else %}
                    <tr>
                        <td colspan="7">
                            <div class="empty">
                                <div class="empty-icon">📦</div>
                                <p>Aucun article dans l'inventaire.<br>Ajoutez votre premier article ci-dessus.</p>
                            </div>
                        </td>
                    </tr>
                {% endif %}
                </tbody>
            </table>
        </div>

        <div style="padding:14px 24px;border-top:1px solid #e2e8f0;font-size:0.8rem;color:#a0aec0;">
            <span id="countLabel">{{ articles|length }} article(s) affiché(s)</span>
        </div>
    </div>

</div>

<!-- MODAL MODIFICATION -->
<div class="modal-overlay" id="editModal">
    <div class="modal">
        <h3>✏️ Modifier l'article</h3>
        <div class="modal-form-grid">
            <div class="form-group full">
                <label>Nom de l'article</label>
                <input type="text" id="edit_nom">
            </div>
            <div class="form-group">
                <label>Quantité</label>
                <input type="number" id="edit_quantite" min="0">
            </div>
            <div class="form-group">
                <label>Seuil d'alerte</label>
                <input type="number" id="edit_seuil" min="0">
            </div>
            <div class="form-group full">
                <label>Catégorie</label>
                <select id="edit_categorie">
                    {% for cat in categories %}
                    <option value="{{ cat }}">{{ cat }}</option>
                    {% endfor %}
                </select>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="fermerModal()">Annuler</button>
            <button class="btn btn-primary" onclick="sauvegarderModif()">💾 Enregistrer</button>
        </div>
    </div>
</div>

<footer>
    LogiStock — Infrastructure DevSecOps sur AWS EC2 | Prometheus + Grafana | Pipeline CI/CD GitHub Actions
</footer>

<script>
let editId = null;

function filtrerTable() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const cat    = document.getElementById('catFilter').value;
    const alert  = document.getElementById('alertFilter').value;
    const rows   = document.querySelectorAll('#inventaireTable tbody tr[data-nom]');
    let count = 0;

    rows.forEach(row => {
        const nom    = row.dataset.nom || '';
        const rowCat = row.dataset.cat || '';
        const statut = row.dataset.statut || '';

        const matchSearch = nom.includes(search);
        const matchCat    = !cat   || rowCat === cat;
        const matchAlert  = !alert || statut === alert;

        if (matchSearch && matchCat && matchAlert) {
            row.style.display = '';
            count++;
        } else {
            row.style.display = 'none';
        }
    });

    document.getElementById('countLabel').textContent = count + ' article(s) affiché(s)';
}

function supprimerArticle(id, nom) {
    if (!confirm('Supprimer "' + nom + '" de l\'inventaire ?')) return;
    fetch('/api/articles/' + id, { method: 'DELETE' })
        .then(r => {
            if (r.ok) location.reload();
            else alert('Erreur lors de la suppression.');
        });
}

function ouvrirEditModal(id, nom, quantite, categorie, seuil) {
    editId = id;
    document.getElementById('edit_nom').value      = nom;
    document.getElementById('edit_quantite').value = quantite;
    document.getElementById('edit_seuil').value    = seuil;
    const sel = document.getElementById('edit_categorie');
    for (let i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === categorie) { sel.selectedIndex = i; break; }
    }
    document.getElementById('editModal').classList.add('open');
}

function fermerModal() {
    document.getElementById('editModal').classList.remove('open');
    editId = null;
}

function sauvegarderModif() {
    if (!editId) return;
    const body = {
        nom:         document.getElementById('edit_nom').value,
        quantite:    parseInt(document.getElementById('edit_quantite').value),
        categorie:   document.getElementById('edit_categorie').value,
        seuil_alerte: parseInt(document.getElementById('edit_seuil').value)
    };
    fetch('/api/articles/' + editId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(r => {
        if (r.ok) location.reload();
        else alert('Erreur lors de la modification.');
    });
}

// Fermer modal si clic en dehors
document.getElementById('editModal').addEventListener('click', function(e) {
    if (e.target === this) fermerModal();
});
</script>

</body>
</html>
"""


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS articles (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        nom          TEXT    NOT NULL,
        quantite     INTEGER DEFAULT 0,
        categorie    TEXT    DEFAULT 'Autre',
        seuil_alerte INTEGER DEFAULT 10
    )''')
    conn.commit()
    conn.close()


def seed_db_if_empty():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM articles")
    count = c.fetchone()[0]
    if count == 0:
        c.executemany(
            "INSERT INTO articles (nom, quantite, categorie, seuil_alerte) VALUES (?, ?, ?, ?)",
            ARTICLES_INITIAUX
        )
        conn.commit()
    conn.close()


def get_stats(articles):
    total_stock = sum(a[2] for a in articles)
    critique = sum(1 for a in articles if a[2] <= a[4])
    warning  = sum(1 for a in articles if a[4] < a[2] <= a[4] * 2)
    return {
        'total_articles': len(articles),
        'total_stock':    total_stock,
        'alerte_critique': critique,
        'alerte_warning':  warning
    }


# Route 1 : Interface web
@app.route('/', methods=['GET'])
def index():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nom, quantite, categorie, seuil_alerte FROM articles ORDER BY categorie, nom")
    articles = c.fetchall()
    conn.close()
    REQUETES_TOTALES.labels(methode='GET', route='/', statut='200').inc()
    return render_template_string(  # nosec B703 — template statique, aucune entree utilisateur injectee directement
        TEMPLATE_HTML,
        articles=articles,
        categories=CATEGORIES,
        stats=get_stats(articles)
    )


# Route 2 : Ajout via formulaire web
@app.route('/ajouter', methods=['POST'])
def ajouter():
    nom          = request.form.get('nom', '').strip()
    quantite     = int(request.form.get('quantite', 0))
    categorie    = request.form.get('categorie', 'Autre')
    seuil_alerte = int(request.form.get('seuil_alerte', 10))
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO articles (nom, quantite, categorie, seuil_alerte) VALUES (?, ?, ?, ?)",
        (nom, quantite, categorie, seuil_alerte)
    )
    conn.commit()
    conn.close()
    REQUETES_TOTALES.labels(methode='POST', route='/ajouter', statut='302').inc()
    return redirect('/')


# Route 3 : API REST — liste des articles
@app.route('/api/articles', methods=['GET'])
def get_articles():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nom, quantite, categorie, seuil_alerte FROM articles ORDER BY id")
    lignes = c.fetchall()
    conn.close()
    resultat = [
        {"id": r[0], "nom": r[1], "quantite": r[2], "categorie": r[3], "seuil_alerte": r[4]}
        for r in lignes
    ]
    REQUETES_TOTALES.labels(methode='GET', route='/api/articles', statut='200').inc()
    return jsonify(resultat)


# Route 4 : API REST — ajout article
@app.route('/api/articles', methods=['POST'])
def add_article():
    data = request.get_json()
    nom          = data.get('nom', '')
    quantite     = data.get('quantite', 0)
    categorie    = data.get('categorie', 'Autre')
    seuil_alerte = data.get('seuil_alerte', 10)
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO articles (nom, quantite, categorie, seuil_alerte) VALUES (?, ?, ?, ?)",
        (nom, int(quantite), categorie, int(seuil_alerte))
    )
    conn.commit()
    conn.close()
    REQUETES_TOTALES.labels(methode='POST', route='/api/articles', statut='201').inc()
    return jsonify({"message": "Article ajoute avec succes"}), 201


# Route 5 : API REST — modification article
@app.route('/api/articles/<int:article_id>', methods=['PUT'])
def update_article(article_id):
    data = request.get_json()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE articles SET nom=?, quantite=?, categorie=?, seuil_alerte=? WHERE id=?",
        (data.get('nom'), int(data.get('quantite', 0)),
         data.get('categorie', 'Autre'), int(data.get('seuil_alerte', 10)),
         article_id)
    )
    conn.commit()
    conn.close()
    REQUETES_TOTALES.labels(methode='PUT', route='/api/articles/<id>', statut='200').inc()
    return jsonify({"message": "Article modifie avec succes"}), 200


# Route 6 : API REST — suppression article
@app.route('/api/articles/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM articles WHERE id=?", (article_id,))
    conn.commit()
    conn.close()
    REQUETES_TOTALES.labels(methode='DELETE', route='/api/articles/<id>', statut='200').inc()
    return jsonify({"message": "Article supprime avec succes"}), 200


# Route 7 : Health Check
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"statut": "ok", "service": "logistock-api"}), 200


# Route 8 : Métriques Prometheus
@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == '__main__':
    init_db()
    seed_db_if_empty()
    app.run(host='0.0.0.0', port=5000)
