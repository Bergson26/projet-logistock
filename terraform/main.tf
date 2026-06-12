# Auteur : Bergson Jean-Michel AQUEREBURU
# Role : Infrastructure as Code — Provisionnement AWS LogiStock
# Projet : LogiStock — Titre Professionnel ASD Niveau 6
# Equivalent Terraform du script provision.sh

# ============================================================
# PROVIDER — Connexion AWS region Paris
# ============================================================
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-3"
}

# ============================================================
# VARIABLE — IP administrateur (moindre privilege)
# Aucune valeur par defaut — force la specification explicite
# Usage : terraform apply -var admin_cidr="<TON_IP>/32"
# ============================================================
variable "admin_cidr" {
  description = "CIDR autorise pour SSH, preprod et Grafana (acces administrateur uniquement). Exemple : terraform apply -var admin_cidr=203.0.113.10/32"
  type        = string
  # Aucun default — si oublie, Terraform bloque et demande la valeur
}

# ============================================================
# VPC — Recuperation du VPC par defaut AWS
# ============================================================
data "aws_vpc" "default" {
  default = true
}

# ============================================================
# SECURITY GROUP — Pare-feu principe de moindre privilege
# ============================================================
resource "aws_security_group" "logistock" {
  name        = "logistock-sec-group"
  description = "Pare-feu restrictif pour API LogiStock et supervision"
  vpc_id      = data.aws_vpc.default.id

  # Port 22 : SSH restreint a l'administrateur uniquement (cle PEM obligatoire)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "SSH administrateur"
  }

  # Port 80 : HTTP public — nginx redirige vers HTTPS
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP public (redirection HTTPS via nginx)"
  }

  # Port 443 : HTTPS public — nginx reverse proxy (prod, preprod, grafana)
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS public (prod + preprod + grafana via nginx)"
  }

  # Port 3000 : Grafana restreint a l'administrateur
  # (acces public via https://logistock-grafana.duckdns.org)
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "Grafana supervision (acces direct admin)"
  }

  # NOTE : Ports 5000 (prod) et 8080 (preprod) non exposes publiquement.
  # L'acces logisticiens se fait via nginx/HTTPS sur les ports 80 et 443.

  # Trafic sortant : autorise tout (mises a jour, pull Docker Hub)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name   = "logistock-sec-group"
    Projet = "LogiStock"
  }
}

# ============================================================
# INSTANCE EC2 — Serveur de production LogiStock
# ============================================================
resource "aws_instance" "logistock" {
  ami                    = "ami-02ea01341a2884771"  # Amazon Linux 2023 — Region Paris
  instance_type          = "t3.micro"               # Free Tier eligible
  key_name               = "logistock-ssh-key"
  vpc_security_group_ids = [aws_security_group.logistock.id]

  tags = {
    Name   = "Serveur-LogiStock-Prod"
    Projet = "LogiStock"
  }
}

# ============================================================
# OUTPUT — Affiche l'IP publique apres creation
# ============================================================
output "ip_publique" {
  description = "Adresse IP publique de l'instance EC2 LogiStock"
  value       = aws_instance.logistock.public_ip
}
