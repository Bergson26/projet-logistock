#!/bin/bash
# Auteur : Bergson Jean-Michel AQUEREBURU
# Role : Sauvegarde automatique de la base de donnees LogiStock
# Projet : LogiStock

# Dossier de destination des sauvegardes
BACKUP_DIR="/home/ec2-user/backups"
# Nom du fichier avec horodatage
BACKUP_FILE="$BACKUP_DIR/inventaire_$(date '+%Y%m%d_%H%M%S').db"
# Source : base SQLite dans le volume Docker
SOURCE="/home/ec2-user/projet-logistock/data-prod/inventaire.db"
# Nombre de sauvegardes a conserver (rotation)
MAX_BACKUPS=7

# Creation du dossier de sauvegarde s'il n'existe pas
mkdir -p $BACKUP_DIR

# Verification que la source existe
if [ ! -f "$SOURCE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERREUR : base de donnees source introuvable ($SOURCE)" >> $BACKUP_DIR/backup.log
    exit 1
fi

# Copie de la base de donnees
cp "$SOURCE" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Sauvegarde reussie : $BACKUP_FILE" >> $BACKUP_DIR/backup.log
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERREUR : echec de la sauvegarde" >> $BACKUP_DIR/backup.log
    exit 1
fi

# Rotation : suppression des sauvegardes les plus anciennes
NB_FICHIERS=$(ls -1 $BACKUP_DIR/inventaire_*.db 2>/dev/null | wc -l)
if [ $NB_FICHIERS -gt $MAX_BACKUPS ]; then
    ls -1t $BACKUP_DIR/inventaire_*.db | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Rotation : anciennes sauvegardes supprimees" >> $BACKUP_DIR/backup.log
fi
