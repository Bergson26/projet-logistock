#!/bin/bash
# Auteur : Bergson Jean-Michel AQUEREBURU
# Role : Sauvegarde automatique de la base de donnees LogiStock
# Projet : LogiStock
# Strategie : sauvegarde locale (rotation 7 jours) + envoi vers serveur externe

# --- CONFIGURATION ---
BACKUP_DIR="/home/ec2-user/backups"
BACKUP_FILE="$BACKUP_DIR/inventaire_$(date '+%Y%m%d_%H%M%S').db"
SOURCE="/home/ec2-user/projet-logistock/data-prod/inventaire.db"
MAX_BACKUPS=7

# Serveur externe de sauvegarde (a configurer selon l'environnement cible)
REMOTE_USER="backup-user"
REMOTE_HOST="backup.logistock.internal"
REMOTE_DIR="/backups/logistock"

# --- SAUVEGARDE LOCALE ---
mkdir -p $BACKUP_DIR

if [ ! -f "$SOURCE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERREUR : base de donnees source introuvable ($SOURCE)" >> $BACKUP_DIR/backup.log
    exit 1
fi

cp "$SOURCE" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Sauvegarde locale reussie : $BACKUP_FILE" >> $BACKUP_DIR/backup.log
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERREUR : echec de la sauvegarde locale" >> $BACKUP_DIR/backup.log
    exit 1
fi

# --- ENVOI VERS SERVEUR EXTERNE ---
# Transfert via SCP vers un serveur distant dedie aux sauvegardes
# En production : remplacer REMOTE_HOST par l'IP/nom du serveur de sauvegarde
# et s'assurer que la cle SSH ec2-user -> backup-server est configuree
if ssh -o ConnectTimeout=10 -o BatchMode=yes "$REMOTE_USER@$REMOTE_HOST" exit 2>/dev/null; then
    scp "$BACKUP_FILE" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"
    if [ $? -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Envoi externe reussi : $REMOTE_HOST:$REMOTE_DIR" >> $BACKUP_DIR/backup.log
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - AVERTISSEMENT : echec de l envoi externe" >> $BACKUP_DIR/backup.log
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - AVERTISSEMENT : serveur externe inaccessible - sauvegarde locale uniquement" >> $BACKUP_DIR/backup.log
fi

# --- ROTATION LOCALE : conservation des 7 derniers fichiers ---
NB_FICHIERS=$(ls -1 $BACKUP_DIR/inventaire_*.db 2>/dev/null | wc -l)
if [ $NB_FICHIERS -gt $MAX_BACKUPS ]; then
    ls -1t $BACKUP_DIR/inventaire_*.db | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Rotation : anciennes sauvegardes supprimees" >> $BACKUP_DIR/backup.log
fi
