# Projet LogiStock — ASD Niveau 6

Application de gestion d'inventaire pour la PME fictive LogiStock, réalisée dans le cadre de la certification RNCP ASD Niveau 6.

## Contexte

LogiStock est une PME qui gère ~500 références EPI (casques, gilets, harnais) pour ~10 logisticiens. L'objectif : déployer une infrastructure cloud complète avec une approche DevSecOps — automatisation du déploiement, sécurisation du pipeline, supervision temps réel et sauvegarde automatique.

---

## Architecture globale

![Architecture LogiStock — Infrastructure DevSecOps complète](architecture%20logistock.png)

**Flux de haut en bas :**
1. Le développeur fait un `git push main` → déclenche GitHub Actions (11 étapes DevSecOps)
2. Terraform provisionne le VPC + Security Group + EC2 ; Ansible installe Docker + Compose
3. nginx reçoit les requêtes HTTPS :443 (logistock.duckdns.org / Let's Encrypt) et reverse-proxie vers `api-prod :5000`
4. Prometheus scrape les 5 cibles toutes les 15s ; Grafana affiche 5 panneaux et envoie les alertes vers Slack

---

## Stack technique

| Composant        | Technologie                                  |
|------------------|----------------------------------------------|
| Application      | Python 3.13 / Flask / SQLite                 |
| Conteneurisation | Docker + Docker Compose v2.24.0              |
| Reverse proxy    | nginx + Let's Encrypt (HTTPS :443)           |
| CI/CD            | GitHub Actions — 11 étapes DevSecOps         |
| Sécurité SAST    | Bandit (-lll -iii) + Gitleaks                |
| Sécurité image   | Trivy (CVE CRITICAL/HIGH + secrets)          |
| IaC              | Terraform (VPC + SG + EC2) + Ansible         |
| Cloud            | AWS EC2 t3.micro Free Tier — eu-west-3       |
| OS serveur       | Amazon Linux 2023                            |
| Supervision      | Prometheus + Grafana + node-exporter + blackbox-exporter |
| Alertes          | Grafana → webhook Slack (#alertes-logistock) |
| Sauvegarde       | Script Bash + crontab 2h00 — rotation 7j     |

---

## Structure du projet

```
projet-logistock/
├── .github/
│   └── workflows/
│       └── main.yml              ← Pipeline CI/CD DevSecOps (11 étapes)
│
├── app.py                        ← API Flask (routes, métriques Prometheus)
├── test_app.py                   ← 15 tests automatisés (Pytest)
├── Dockerfile                    ← Image python:3.13-slim + HEALTHCHECK + apt-get upgrade
├── requirements.txt              ← Dépendances : flask, prometheus_client
│
├── docker-compose.yml            ← 6 services : prod, préprod, prometheus,
│                                    grafana, node-exporter, blackbox-exporter
├── prometheus.yml                ← Configuration scraping (5 jobs, 15s)
├── grafana/
│   └── provisioning/
│       ├── dashboards/
│       │   └── logistock.json    ← Dashboard exporté (5 panneaux)
│       ├── datasources/
│       │   └── prometheus.yml    ← Datasource Prometheus auto-provisionné
│       └── alerting/
│           ├── contact-points.yaml       ← Webhook Slack
│           └── notification-policies.yaml ← Règles d'envoi alertes
│
├── nginx/
│   └── logistock.conf            ← Configuration reverse proxy HTTPS
│
├── backup.sh                     ← Sauvegarde automatique SQLite (rotation 7j)
├── provision.sh                  ← Provisionnement AWS via Bash + AWS CLI
│
├── terraform/
│   └── main.tf                   ← IaC — VPC + Security Group + EC2
└── ansible/
    └── playbook.yml              ← Configuration serveur : Docker + Compose
```

---

## Prérequis

- Compte AWS avec AWS CLI configuré (`aws configure`)
- Git + compte GitHub
- Clé SSH générée localement (voir section déploiement)
- Docker installé sur la machine locale (pour les tests)

---

## Déploiement de l'infrastructure

Deux approches sont disponibles pour provisionner l'infrastructure :

| Approche | Fichier | Statut |
|---|---|---|
| Script Bash + AWS CLI | `provision.sh` | Utilisé en production pour ce projet |
| Infrastructure as Code | `terraform/main.tf` | Alternative IaC standard (recommandée en équipe) |

La configuration du serveur (Docker, docker-compose) est ensuite gérée par Ansible (`ansible/playbook.yml`).

---

### Option A — Bash (utilisé en production)

#### 1. Génération de la clé SSH

```bash
ssh-keygen -t rsa -b 2048 -f logistock-ssh-key.pem -N ""
aws ec2 import-key-pair \
  --key-name logistock-ssh-key \
  --region eu-west-3 \
  --public-key-material fileb://logistock-ssh-key.pem.pub
```

#### 2. Provisionnement via script

```bash
chmod +x provision.sh
./provision.sh
```

Le script crée un Security Group (port 443 public, ports 22/8080/3000 admin uniquement) et une instance EC2 t3.micro Amazon Linux 2023.

#### 3. Configuration du serveur via Ansible

```bash
ansible-playbook -i <IP_EC2>, -u ec2-user --private-key logistock-ssh-key.pem ansible/playbook.yml
```

---

### Option B — Terraform + Ansible (IaC standard)

```bash
cd terraform/
terraform init
terraform apply -var admin_cidr="<TON_IP>/32"

ansible-playbook -i <IP_EC2>, -u ec2-user --private-key ../logistock-ssh-key.pem ../ansible/playbook.yml
```

---

## Pipeline CI/CD — 11 étapes DevSecOps

Le pipeline se déclenche automatiquement à chaque push sur `main`. **Si une étape échoue, le déploiement est bloqué.**

| # | Étape | Outil | Bloquant |
|---|---|---|---|
| 1 | Checkout du code source | actions/checkout | — |
| 2 | Tests automatisés | Pytest (15 cas) | Oui |
| 3 | Analyse SAST Python | Bandit (-lll -iii) | Oui |
| 4 | Détection de secrets Git | Gitleaks | Oui |
| 5 | Build de l'image Docker | docker build | Oui |
| 6 | Scan CVE image | Trivy (CRITICAL/HIGH) | Oui |
| 7 | Scan secrets image | Trivy secrets | Oui |
| 8 | Déploiement préprod | SSH → port 8080 | Oui |
| 9 | Health check préprod | curl /health → HTTP 200 | Oui |
| 10 | Déploiement prod | SSH → port 5000 | Oui |
| 11 | Nettoyage images | docker image prune | Non |

**15 runs réalisés — dernier run vert ✅**

**Secrets GitHub requis :**
- `AWS_HOST_IP` : adresse IP publique de l'EC2
- `AWS_SSH_KEY` : contenu de la clé privée PEM
- `SLACK_WEBHOOK_URL` : webhook Grafana → Slack (ne jamais commiter en dur)

---

## Services Docker — 6 conteneurs

| Service | Port | Rôle |
|---|---|---|
| api-prod | :5000 | Flask Production — CRUD articles EPI |
| api-preprod | :8080 | Flask Préprod — validation CI/CD |
| prometheus | interne | Collecte métriques toutes les 15s |
| grafana | :3000 | Dashboard 5 panneaux + 2 alertes Slack |
| node-exporter | interne | Métriques système CPU / RAM / Disque |
| blackbox-exporter | interne | HTTP probe /health → probe_success |

---

## Supervision

### Prometheus — 5 cibles

- `logistock-prod` → métriques Flask production (:5000/metrics)
- `logistock-preprod` → métriques Flask préprod (:8080/metrics)
- `node-exporter` → métriques système (:9100)
- `prometheus` → auto-supervision
- `blackbox-exporter` → sondage HTTP /health → génère `probe_success`

### Grafana — 5 panneaux

| Panneau | Type | Valeur observée |
|---|---|---|
| CPU (%) | Gauge | 10,3 % |
| RAM (%) | Gauge | 76,0 % |
| Disque (%) | Gauge | 58,8 % |
| Requêtes HTTP total | Stat | 1 246 requêtes |
| Latence moyenne | Time series | Courbes api-prod + api-preprod |

### 2 alertes Slack automatiques

| Alerte | Condition | Délai | Canal |
|---|---|---|---|
| API LogiStock DOWN | `probe_success` < 1 | 2 min | #alertes-logistock |
| CPU critique | CPU > 85% | 5 min | #alertes-logistock |

---

## Sauvegarde automatique

```bash
# Vérifier le crontab
crontab -l
# → 0 2 * * * /home/ec2-user/backup.sh

# Tester manuellement
/home/ec2-user/backup.sh && cat /home/ec2-user/backups/backup.log
```

- Rotation : 7 dernières sauvegardes conservées
- Fenêtre de restauration : 7 jours

---

## API — Endpoints

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Interface web — tableau des articles avec filtres |
| GET | `/api/articles` | Liste tous les articles (JSON) |
| POST | `/api/articles` | Ajoute un article |
| PUT | `/api/articles/<id>` | Modifie un article |
| DELETE | `/api/articles/<id>` | Supprime un article |
| GET | `/health` | Health check (pipeline + Grafana) |
| GET | `/metrics` | Métriques Prometheus |

---

## Procédures opérationnelles

### Déploiement depuis zéro

**Prérequis**

| Prérequis | Vérification |
|---|---|
| AWS CLI installé et configuré | `aws sts get-caller-identity` → retourne un ARN |
| Clé SSH générée localement | `logistock-ssh-key.pem` + `.pem.pub` présents |
| Terraform ≥ 1.5 installé | `terraform -version` |
| Ansible ≥ 2.14 installé | `ansible --version` |
| Secrets GitHub configurés | `AWS_HOST_IP`, `AWS_SSH_KEY`, `SLACK_WEBHOOK_URL` |

**Étapes séquentielles**

```bash
# 1. Générer et importer la clé SSH
ssh-keygen -t rsa -b 2048 -f logistock-ssh-key.pem -N ""
aws ec2 import-key-pair --key-name logistock-ssh-key \
  --region eu-west-3 \
  --public-key-material fileb://logistock-ssh-key.pem.pub

# 2. Provisionner l'infrastructure AWS (Terraform)
cd terraform/
terraform init
terraform apply -var admin_cidr="<VOTRE_IP>/32"
# → noter l'IP publique affichée en output

# 3. Configurer le serveur (Ansible)
ansible-playbook -i <IP_EC2>, -u ec2-user \
  --private-key ../logistock-ssh-key.pem \
  ../ansible/playbook.yml
# → installe Docker, Docker Compose, clone le repo, lance les 6 services

# 4. Vérifier les services
ssh -i logistock-ssh-key.pem ec2-user@<IP_EC2>
docker ps
# → 6 conteneurs doivent être en statut "Up" ou "healthy"

# 5. Déclencher le premier pipeline
git push origin main
# → GitHub Actions lance les 11 étapes automatiquement
```

**Validation post-déploiement**

```bash
curl -I https://logistock.duckdns.org        # → HTTP/2 200
curl https://logistock.duckdns.org/health    # → {"status": "ok"}
curl https://logistock.duckdns.org/api/articles  # → JSON articles EPI
curl -I http://<IP_EC2>:3000                 # → HTTP/1.1 200 (Grafana)
```

---

### Procédure de rollback

**Cas 1 — Rollback via Git (recommandé)**

```bash
# Sur la machine locale
git revert HEAD
git push origin main
# → GitHub Actions redéploie automatiquement la version stable
```

**Cas 2 — Rollback manuel sur le serveur**

```bash
ssh -i logistock-ssh-key.pem ec2-user@15.188.50.241
cd /home/ec2-user/projet-logistock

# Revenir à l'image précédente
docker images | grep logistock
docker-compose stop api-prod
docker tag logistock-api:<VERSION_STABLE> logistock-api:latest
docker-compose up -d api-prod
curl http://localhost:5000/health
```

**Cas 3 — Déploiement d'urgence sans pipeline**

```bash
ssh -i logistock-ssh-key.pem ec2-user@15.188.50.241
cd /home/ec2-user/projet-logistock
git pull origin main
docker-compose pull && docker-compose up -d
curl http://localhost:5000/health
```

---

### Procédure d'incident — réponse aux alertes Grafana

**Alerte : API LogiStock DOWN (`probe_success` < 1)**

```bash
# Diagnostic
ssh -i logistock-ssh-key.pem ec2-user@15.188.50.241
docker ps                                    # vérifier statut conteneurs
docker logs logistock-prod --tail 50         # lire les erreurs
curl http://localhost:5000/health            # tester en local

# Résolution — conteneur arrêté
docker-compose up -d api-prod

# Résolution — crash loop
docker-compose logs api-prod | grep ERROR
docker-compose restart api-prod

# Résolution — instance EC2 injoignable
aws ec2 start-instances --instance-ids i-0e5e90fbf37eff269 --region eu-west-3
```

**Alerte : CPU critique (> 85% pendant 5 min)**

```bash
top -bn1 | head -20              # identifier le processus consommateur
docker stats --no-stream         # CPU par conteneur
docker-compose restart <service> # redémarrer le conteneur fautif
```

---

### Mode opératoire de supervision

**Accès aux outils**

| Outil | URL | Identifiants |
|---|---|---|
| Grafana | http://15.188.50.241:3000 | admin / admin |
| Application | https://logistock.duckdns.org | — (public) |

**Lecture des 5 panneaux Grafana**

| Panneau | Seuil normal | Seuil alerte | Action si dépassement |
|---|---|---|---|
| CPU (%) | < 50 % | > 85 % / 5 min | Identifier processus, redémarrer si nécessaire |
| RAM (%) | < 80 % | > 90 % | Redémarrer les conteneurs non critiques |
| Disque (%) | < 70 % | > 85 % | `docker image prune -a` |
| Requêtes HTTP total | Croissance normale | Pic anormal | Vérifier logs pour activité suspecte |
| Latence moyenne (s) | < 0,1 s | > 1 s | Vérifier charge CPU et requêtes DB |

**Vérification quotidienne (< 2 min)**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"  # conteneurs actifs ?
ls -lh /home/ec2-user/backups/ | tail -5             # dernière sauvegarde OK ?
df -h /                                              # espace disque suffisant ?
```

---

### Procédure de restauration testée

```bash
# 1. Lister les sauvegardes disponibles
ls -lh /home/ec2-user/backups/inventaire_*.db

# 2. Arrêter l'API
docker-compose stop api-prod

# 3. Restaurer la sauvegarde choisie
cp /home/ec2-user/backups/inventaire_YYYYMMDD_HHMMSS.db \
   /home/ec2-user/projet-logistock/data-prod/inventaire.db

# 4. Redémarrer l'API
docker-compose start api-prod

# 5. Vérifier l'intégrité
curl http://localhost:5000/api/articles | python3 -m json.tool | head -20
curl https://logistock.duckdns.org/health
# → {"status": "ok"} = restauration réussie
```

Fenêtre maximale de perte de données : **24h** (sauvegarde nightly à 2h00). Durée de restauration : **< 30 secondes**.

---

## Liens

- **Application** : https://logistock.duckdns.org
- **Grafana** : http://15.188.50.241:3000
- **GitHub** : github.com/Bergson26/projet-logistock
