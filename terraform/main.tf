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
# Remplacer par l'IP fixe de l'admin ou le CIDR de l'ecole
# ============================================================
variable "admin_cidr" {
  description = "CIDR autorise pour SSH, preprod et Grafana (acces administrateur uniquement)"
  type        = string
  default     = "0.0.0.0/0"
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

  # Port 22 : SSH restreint a l'administrateur uniquement
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "SSH administrateur"
  }

  # Port 5000 : Production accessible aux logisticiens (monde entier)
  ingress {
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "API Flask production"
  }

  # Port 8080 : Pre-production restreinte a l'administrateur
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "API Flask pre-production"
  }

  # Port 3000 : Grafana restreint a l'administrateur
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "Grafana supervision"
  }

  # Trafic sortant : autorise tout (mises a jour, pull Docker Hub)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "logistock-sec-group"
    Projet  = "LogiStock"
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
