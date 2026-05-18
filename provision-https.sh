#!/bin/bash
set -euo pipefail

# ============================================================
# provision-https.sh
# Role : Activation HTTPS via nginx + Let's Encrypt (Duck DNS)
# Domaine : logistock.duckdns.org -> 15.188.50.241
# Usage   : bash provision-https.sh
# ============================================================

REGION="eu-west-3"
SG_NAME="logistock-sec-group"
EC2_IP="15.188.50.241"
SSH_KEY="logistock-ssh-key.pem"
DOMAIN="logistock.duckdns.org"
EMAIL="bjmsaquereburu@gmail.com"

echo "=== [1/3] Ouverture des ports 80 et 443 dans le Security Group ==="

aws ec2 authorize-security-group-ingress \
  --group-name "$SG_NAME" \
  --protocol tcp --port 80 --cidr 0.0.0.0/0 \
  --region "$REGION" \
  && echo "  Port 80 : ouvert" \
  || echo "  Port 80 : deja ouvert (ignore)"

aws ec2 authorize-security-group-ingress \
  --group-name "$SG_NAME" \
  --protocol tcp --port 443 --cidr 0.0.0.0/0 \
  --region "$REGION" \
  && echo "  Port 443 : ouvert" \
  || echo "  Port 443 : deja ouvert (ignore)"

echo ""
echo "=== [2/3] Installation nginx + certbot sur EC2 ==="

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" bash -s << 'REMOTE'
set -e
echo "  Installation nginx..."
sudo dnf install -y nginx
sudo systemctl enable nginx --now

echo "  Installation pip + certbot..."
sudo dnf install -y python3-pip
sudo pip3 install certbot certbot-nginx

echo "  nginx + certbot : OK"
REMOTE

echo ""
echo "=== [2b/3] Configuration nginx pour ${DOMAIN} ==="

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo tee /etc/nginx/conf.d/logistock.conf > /dev/null" << NGINXEOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINXEOF

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo nginx -t && sudo systemctl reload nginx && echo '  nginx : OK'"

echo ""
echo "=== [3/3] Certificat Let's Encrypt pour ${DOMAIN} ==="

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos --email ${EMAIL} --redirect"

echo ""
echo "============================================"
echo "HTTPS actif : https://${DOMAIN}"
echo "============================================"
