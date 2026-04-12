# Projet LogiStock — ASD Niveau 6

Application de gestion d'inventaire pour la PME fictive LogiStock, réalisée dans le cadre de la certification RNCP ASD Niveau 6.

## Contexte

LogiStock est une PME qui a besoin de gérer son inventaire de manière fiable. L'objectif du projet est de concevoir et déployer une infrastructure cloud complète avec une approche DevSecOps : automatisation du déploiement, sécurisation du pipeline, supervision en temps réel et sauvegarde des données.

---

## Architecture globale

```
GitHub (code source)
        |
        | push sur main
        v
GitHub Actions (CI/CD)
        |
        |-- docker build
        |-- trivy scan (CRITICAL/HIGH bloquant)
        |-- déploiement SSH préprod (port 8080)
        |-- health check préprod
        |-- déploiement SSH prod (port 5000)
        v
AWS EC2 t3.micro — eu-west-3 (Paris)
        |
        |-- api-prod        (Flask + SQLite, port 5000)
        |-- api-preprod     (Flask + SQLite, port 8080)
        |-- prometheus      (collecte métriques, interne)
        |-- grafana         (tableaux de bord, port 3000)
        |-- node-exporter   (métriques système, interne)
```

---

## Stack technique

| Composant        | Technologie                        |
|------------------|------------------------------------|
| Application      | Python / Flask / SQLite            |
| Conteneurisation | Docker + Docker Compose v2.24.0    |
| CI/CD            | GitHub Actions                     |
| Sécurité image   | Trivy (scan CVE)                   |
| Cloud            | AWS EC2 t3.micro (Free Tier)       |
| OS serveur       | Amazon Linux 2023                  |
| Supervision      | Prometheus + Grafana + node_exporter |
| Sauvegarde       | Script Bash + crontab              |

---

## Structure du projet

```
projet-logistock/
├── app.py                  # API Flask (articles, health, metrics)
├── requirements.txt        # Dépendances Python
├── Dockerfile              # Image python:3.13-slim
├── docker-compose.yml      # 5 services : prod, préprod, prometheus, grafana, node-exporter
├── prometheus.yml          # Configuration des jobs de scraping
├── grafana-dashboard.json  # Dashboard exporté (5 panneaux + 2 alertes)
├── backup.sh               # Script de sauvegarde automatique SQLite
├── provision.sh            # Script de provisionnement AWS (EC2 + Security Group)
└── .github/
    └── workflows/
        └── main.yml        # Pipeline CI/CD GitHub Actions
```

---

## Prérequis

- Compte AWS avec AWS CLI configuré (`aws configure`)
- Git + compte GitHub
- Clé SSH générée localement (voir section déploiement)
- Docker installé sur la machine locale (pour les tests)

---

## Déploiement de l'infrastructure

### 1. Génération de la clé SSH

La clé SSH est générée localement pour éviter les problèmes de format (CRLF) liés à AWS CLI sur Windows :

```bash
ssh-keygen -t rsa -b 2048 -f logistock-ssh-key.pem -N ""
aws ec2 import-key-pair \
  --key-name logistock-ssh-key \
  --region eu-west-3 \
  --public-key-material fileb://logistock-ssh-key.pem.pub
```

### 2. Provisionnement automatique

```bash
chmod +x provision.sh
./provision.sh
```

Le script crée :
- Un Security Group avec les ports 22, 5000, 8080, 3000 ouverts
- Une instance EC2 t3.micro Amazon Linux 2023

### 3. Installation des dépendances sur l'EC2

```bash
ssh -i logistock-ssh-key.pem ec2-user@<IP_PUBLIQUE>

# Docker
sudo dnf install -y docker
sudo systemctl enable docker --now
sudo usermod -aG docker ec2-user

# Docker Compose (plugin non disponible sur AL2023)
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# cronie pour le crontab
sudo dnf install -y cronie
sudo systemctl enable crond --now
```

### 4. Déploiement de l'application

```bash
git clone https://github.com/Bergson26/projet-logistock.git
cd projet-logistock
docker-compose up -d
```

---

## Pipeline CI/CD

Le pipeline se déclenche automatiquement à chaque push sur la branche `main`.

**Étapes :**
1. Checkout du code
2. Build de l'image Docker
3. Scan de sécurité Trivy — bloque sur toute CVE CRITICAL ou HIGH
4. Déploiement en pré-production (port 8080) via SSH
5. Health check automatique de la préprod (`/health`)
6. Déploiement en production (port 5000) uniquement si le health check passe

**Secrets GitHub requis :**
- `AWS_HOST_IP` : adresse IP publique de l'EC2
- `AWS_SSH_KEY` : contenu de la clé privée PEM

---

## Supervision

### Prometheus

Scraping toutes les 15 secondes sur 4 jobs :
- `logistock-prod` → métriques applicatives Flask (port 5000)
- `logistock-preprod` → métriques applicatives Flask (port 5000)
- `node-exporter` → métriques système CPU/RAM/disque
- `prometheus` → auto-supervision

Accès : `http://<IP>:9090` (interne uniquement via réseau Docker)

### Grafana

Accès : `http://<IP>:3000` (admin / admin par défaut)

**Dashboard LogiStock - Supervision :**

| Panneau              | Type        | Requête PromQL                                                                 |
|----------------------|-------------|--------------------------------------------------------------------------------|
| CPU (%)              | Gauge       | `100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`            |
| RAM (%)              | Gauge       | `100 - ((node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100)` |
| Disque (%)           | Gauge       | `100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)` |
| Requêtes HTTP (total)| Stat        | `sum(logistock_requetes_total)`                                                 |
| Latence moyenne (s)  | Time series | `rate(logistock_latence_secondes_sum[5m]) / rate(logistock_latence_secondes_count[5m])` |

**Alertes configurées :**

| Alerte                     | Condition              | Délai  |
|----------------------------|------------------------|--------|
| API LogiStock - Health DOWN | `probe_success` < 1   | 2 min  |
| CPU critique - LogiStock   | CPU > 85%              | 5 min  |

Notifications envoyées vers le contact point `logistock-alerts` (email).

---

## Sauvegarde automatique

Le script `backup.sh` copie la base SQLite avec un horodatage dans `/home/ec2-user/backups/`.

- Rotation : 7 dernières sauvegardes conservées
- Logs dans `/home/ec2-user/backups/backup.log`
- Planification via crontab : tous les jours à 2h du matin

```bash
# Vérifier le crontab
crontab -l

# Tester manuellement
/home/ec2-user/backup.sh && cat /home/ec2-user/backups/backup.log
```

---

## API — Endpoints

| Méthode | Route            | Description                          |
|---------|------------------|--------------------------------------|
| GET     | `/api/articles`  | Liste tous les articles              |
| POST    | `/api/articles`  | Ajoute un article `{nom, quantite}`  |
| GET     | `/health`        | Health check (utilisé par le CI/CD)  |
| GET     | `/metrics`       | Métriques Prometheus                 |

**Exemple :**
```bash
curl -X POST http://<IP>:5000/api/articles \
  -H "Content-Type: application/json" \
  -d '{"nom": "Casque LogiStock", "quantite": 50}'
```

---

## Difficultés rencontrées et solutions

### 1. Clé SSH corrompue (CRLF) sous Windows

**Problème** : AWS CLI sur Windows génère les fichiers PEM avec des fins de ligne CRLF au lieu de LF. La clé privée était donc invalide pour OpenSSH, rendant toute connexion SSH impossible malgré une instance EC2 fonctionnelle.

**Solution** : Abandon de la génération de clé via AWS CLI. La clé RSA est désormais générée localement avec `ssh-keygen`, puis la clé publique est importée dans AWS avec `aws ec2 import-key-pair --public-key-material fileb://`. Cette approche garantit des fins de ligne correctes et reste reproductible sur tout OS.

---

### 2. Mauvais utilisateur SSH (ubuntu vs ec2-user)

**Problème** : Tentatives de connexion SSH avec l'utilisateur `ubuntu`, qui est l'utilisateur par défaut des AMI Ubuntu. L'AMI utilisée (`ami-02ea01341a2884771`) est Amazon Linux 2023, dont l'utilisateur par défaut est `ec2-user`.

**Solution** : Correction de l'utilisateur dans tous les scripts et dans la configuration GitHub Actions (`ec2-user@...`). Documentation de ce point dans le script `provision.sh` avec un commentaire explicite sur l'AMI et l'utilisateur associé.

---

### 3. CVE bloquantes sur l'image python:3.9-slim

**Problème** : Le scan Trivy a bloqué le pipeline en détectant des vulnérabilités de sévérité HIGH et CRITICAL dans l'image `python:3.9-slim`. C'est le comportement attendu du DevSecOps, mais il fallait corriger l'image.

**Solution** : Migration vers `python:3.13-slim`, qui ne présente aucune CVE critique ou haute au moment du déploiement. Le pipeline est repassé au vert. Ce changement illustre concrètement l'intérêt du scan automatisé dans la chaîne CI/CD.

---

### 4. docker compose non disponible sur Amazon Linux 2023

**Problème** : La commande `docker compose` (plugin intégré) n'est pas disponible sur la version de Docker fournie par les dépôts Amazon Linux 2023. La commande retournait une erreur `unknown command`.

**Solution** : Installation manuelle de `docker-compose` v2.24.0 (binaire standalone) depuis les releases GitHub dans `/usr/local/bin/`. Tous les scripts et le pipeline utilisent la commande avec tiret (`docker-compose`).

---

### 5. crontab non disponible sur Amazon Linux 2023

**Problème** : La commande `crontab` retournait `command not found` car le démon `crond` n'est pas installé par défaut sur Amazon Linux 2023.

**Solution** : Installation du paquet `cronie` via `sudo dnf install -y cronie` et activation du service avec `sudo systemctl enable crond --now`. Le crontab fonctionne ensuite normalement.

---

## Infrastructure

- Provisionnement : 2026-04-10 - Instance t3.micro, region eu-west-3, AMI ami-02ea01341a2884771
- Instance active : i-0e5e90fbf37eff269 — IP : 15.188.50.241
