# Image Python allegee pour reduire la surface d'attaque et le temps de build
FROM python:3.13-slim

# Creation d'un repertoire de travail dedie dans le conteneur
WORKDIR /app

# Copie stricte du fichier des dependances avant le code pour optimiser le cache Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source de l'application
COPY . .

# Creation du dossier de donnees pour la base SQLite
RUN mkdir -p /app/data

# Exposition du port d'ecoute interne de l'API Flask
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["python", "app.py"]
