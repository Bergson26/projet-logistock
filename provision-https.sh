#!/bin/bash
set -euo pipefail

# ============================================================
# provision-https.sh
# Role : Activation HTTPS via nginx + Let's Encrypt (Duck DNS)
# Usage   : bash provision-https.sh
# ============================================================

REGION="eu-west-3"
SG_NAME="logistock-sec-group"
EC2_IP="15.188.50.241"
SSH_KEY="logistock-ssh-key.pem"
DOMAIN="logistock.duckdns.org"
DOMAIN_PREPROD="logistock-preprod.duckdns.org"
DOMAIN_GRAFANA="logistock-grafana.duckdns.org"
EMAIL="bjmsaquereburu@gmail.com"

echo "=== [1/4] Ouverture des ports 80 et 443 dans le Security Group ==="

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
echo "=== [2/4] Installation nginx + certbot sur EC2 ==="

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
echo "=== [3/4] Configuration HTTPS Production (${DOMAIN}) ==="

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
  "sudo nginx -t && sudo systemctl reload nginx && echo '  nginx prod : OK'"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos --email ${EMAIL} --redirect"

echo ""
echo "=== [3b/4] Configuration HTTPS Pre-production (${DOMAIN_PREPROD}) ==="

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo tee /etc/nginx/conf.d/preprod.conf > /dev/null" << PREPRODEOF
server {
    listen 80;
    server_name ${DOMAIN_PREPROD};

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
PREPRODEOF

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo nginx -t && sudo systemctl reload nginx && echo '  nginx preprod : OK'"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo certbot --nginx -d ${DOMAIN_PREPROD} --non-interactive --agree-tos --email ${EMAIL} --redirect"

echo ""
echo "=== [4/4] Configuration HTTPS Grafana (${DOMAIN_GRAFANA}) ==="

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo tee /etc/nginx/conf.d/grafana.conf > /dev/null" << GRAFANAEOF
server {
    listen 80;
    server_name ${DOMAIN_GRAFANA};

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
GRAFANAEOF

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo nginx -t && sudo systemctl reload nginx && echo '  nginx grafana : OK'"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "ec2-user@$EC2_IP" \
  "sudo certbot --nginx -d ${DOMAIN_GRAFANA} --non-interactive --agree-tos --email ${EMAIL} --redirect"

echo ""
echo "============================================"
echo "HTTPS actif : https://${DOMAIN}"
echo "HTTPS actif : https://${DOMAIN_PREPROD}"
echo "HTTPS actif : https://${DOMAIN_GRAFANA}"
echo "============================================"
