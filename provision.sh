#!/bin/bash
# Auteur : Bergson Jean-Michel AQUEREBURU
# Role : Creation automatisee de l'infrastructure reseau et calcul sur AWS
# Projet : LogiStock

# Definition des variables pour faciliter la maintenance et l'evolution du script
REGION="eu-west-3"
AMI_AL2023="ami-02ea01341a2884771"  # Image Amazon Linux 2023 (Region Paris) - utilisateur : ec2-user
TYPE_INSTANCE="t3.micro"            # Instance eligible au Free Tier (budget 0)
NOM_CLE="logistock-ssh-key"
GROUPE_SECU="logistock-sec-group"

echo "Demarrage du provisionnement de l'infrastructure..."

# 1. Creation de la cle SSH pour l'administration distante
# Suppression de l'ancienne cle si elle existe deja
aws ec2 delete-key-pair --key-name $NOM_CLE --region $REGION 2>/dev/null
rm -f $NOM_CLE.pem

# La cle est extraite au format texte et ses droits sont verrouilles immediatement
aws ec2 create-key-pair \
    --key-name $NOM_CLE \
    --region $REGION \
    --query 'KeyMaterial' \
    --output text > $NOM_CLE.pem

chmod 400 $NOM_CLE.pem
echo "Cle SSH generee et securisee localement."

# 2. Creation du pare-feu (Security Group)
# Note : description sans apostrophe (contrainte AWS)
SG_ID=$(aws ec2 create-security-group \
    --group-name $GROUPE_SECU \
    --region $REGION \
    --description "Pare-feu restrictif pour API LogiStock et supervision" \
    --query 'GroupId' \
    --output text)
echo "Groupe de securite cree : $SG_ID"

# 3. Configuration des regles reseau (Principe de moindre privilege)

# Port 22 pour mon acces administrateur et celui de l'agent GitHub Actions
aws ec2 authorize-security-group-ingress --group-id $SG_ID \
    --region $REGION \
    --protocol tcp --port 22 --cidr 0.0.0.0/0

# Port 5000 pour l'acces des logisticiens a l'environnement de Production
aws ec2 authorize-security-group-ingress --group-id $SG_ID \
    --region $REGION \
    --protocol tcp --port 5000 --cidr 0.0.0.0/0

# Port 8080 dedie a l'environnement de Pre-production (tests automatises)
aws ec2 authorize-security-group-ingress --group-id $SG_ID \
    --region $REGION \
    --protocol tcp --port 8080 --cidr 0.0.0.0/0

# Port 3000 pour l'acces a l'interface de supervision Grafana
aws ec2 authorize-security-group-ingress --group-id $SG_ID \
    --region $REGION \
    --protocol tcp --port 3000 --cidr 0.0.0.0/0

echo "Regles reseau configurees."

# 4. Lancement de la machine virtuelle
aws ec2 run-instances \
    --image-id $AMI_AL2023 \
    --count 1 \
    --instance-type $TYPE_INSTANCE \
    --key-name $NOM_CLE \
    --security-group-ids $SG_ID \
    --region $REGION \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Serveur-LogiStock-Prod}]'

echo "L'instance EC2 demarre sur AWS."

# 5. Mise a jour de la documentation technique
echo "" >> README.md
echo "- Provisionnement : $(date '+%Y-%m-%d') - Instance $TYPE_INSTANCE, region $REGION, AMI $AMI_AL2023" >> README.md
echo "Documentation mise a jour dans README.md."
