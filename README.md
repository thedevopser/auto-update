# Docker Auto-Update

Script Python automatisé pour la mise à jour des images Docker locales avec interface graphique en terminal.

## Fonctionnalités

- **Liste automatique** de toutes les images Docker locales
- **Mise à jour intelligente** avec vérification des digests
- **Interface graphique** dans le terminal avec barres de progression
- **Résumé détaillé** des opérations effectuées
- **Nettoyage automatique** des images orphelines
- **Logs complets** de toutes les opérations
- **Mode dry-run** pour simulation sans modification
- **Exclusion de tags** spécifiques
- **Support du cron** pour automatisation complète

## Captures d'écran

Le script affiche :
- Tableau des images détectées
- Barre de progression en temps réel
- Résumé avec statistiques
- Liste des images mises à jour / échouées
- Temps d'exécution et logs

## Prérequis

- Python 3.6+
- Docker installé et accessible
- Permissions Docker (utilisateur dans le groupe `docker`)
- pip et python3-venv

## Installation rapide

```bash
# 1. Cloner ou télécharger le projet
cd /home/thedevopser/projects/auto-update

# 2. Lancer le script d'installation
chmod +x setup.sh
./setup.sh
```

Le script `setup.sh` va :
- Vérifier les prérequis (Python, Docker, pip)
- Créer un environnement virtuel Python
- Installer les dépendances nécessaires
- Configurer les permissions
- Créer les répertoires de logs
- Générer un script wrapper pour faciliter l'exécution

## Utilisation

### Exécution manuelle

```bash
# Exécution standard
./run-update.sh

# Mode simulation (aucune modification)
./run-update.sh --dry-run

# Exclure certains tags
./run-update.sh --exclude-tag latest --exclude-tag dev

# Afficher l'aide
./run-update.sh --help
```

### Exécution via cron

#### Configuration recommandée

1. Éditez votre crontab :
```bash
crontab -e
```

2. Ajoutez une des configurations suivantes :

```bash
# Mise à jour quotidienne à 2h du matin (recommandé)
0 2 * * * cd /home/thedevopser/projects/auto-update && ./run-update.sh >> ~/.docker-update/logs/cron.log 2>&1

# Mise à jour toutes les 6 heures
0 */6 * * * cd /home/thedevopser/projects/auto-update && ./run-update.sh >> ~/.docker-update/logs/cron.log 2>&1

# Mise à jour tous les dimanches à minuit
0 0 * * 0 cd /home/thedevopser/projects/auto-update && ./run-update.sh >> ~/.docker-update/logs/cron.log 2>&1
```

3. Vérifiez l'installation :
```bash
crontab -l
```

#### Voir les exemples de cron

Consultez le fichier [crontab.example](crontab.example) pour plus d'exemples de configuration.

## Structure du projet

```
auto-update/
├── docker-update.py       # Script principal Python
├── run-update.sh          # Wrapper pour exécution facile
├── setup.sh               # Script d'installation
├── requirements.txt       # Dépendances Python
├── config.example.json    # Exemple de configuration
├── crontab.example        # Exemples de configuration cron
├── README.md              # Cette documentation
└── venv/                  # Environnement virtuel Python (créé par setup.sh)
```

## Logs

Les logs sont stockés dans `~/.docker-update/logs/` :

```bash
# Voir les logs du jour
tail -f ~/.docker-update/logs/docker-update-$(date +%Y%m%d).log

# Voir tous les logs
ls -lh ~/.docker-update/logs/

# Logs du cron
tail -f ~/.docker-update/logs/cron.log
```

## Options de ligne de commande

```
Options:
  -h, --help            Afficher l'aide
  --dry-run             Mode simulation (aucune modification réelle)
  --exclude-tag TAG     Tags à exclure (peut être répété)
  --version             Afficher la version
```

## Fonctionnement détaillé

### 1. Listing des images

Le script liste toutes les images Docker locales :
```bash
docker images --format "{{json .}}"
```

### 2. Mise à jour

Pour chaque image :
- Récupération du digest actuel
- Pull de la nouvelle version
- Comparaison des digests
- Marquage comme "mise à jour" ou "déjà à jour"

### 3. Nettoyage

Suppression automatique des images orphelines :
```bash
docker image prune -f
```

### 4. Rapport

Affichage d'un résumé complet avec :
- Nombre total d'images
- Images mises à jour
- Images déjà à jour
- Images en échec
- Temps d'exécution
- Chemin des logs

## Exemples d'utilisation

### Test initial

```bash
# Premier test en mode dry-run
./run-update.sh --dry-run
```

### Mise à jour de production

```bash
# Exclure les images de développement
./run-update.sh --exclude-tag dev --exclude-tag test
```

### Monitoring

```bash
# Vérifier les images sans les modifier
./run-update.sh --dry-run >> ~/.docker-update/logs/check.log 2>&1
```

## Résolution de problèmes

### Problème : Permission denied avec Docker

**Solution :**
```bash
# Ajouter votre utilisateur au groupe docker
sudo usermod -aG docker $USER

# Se déconnecter et se reconnecter pour appliquer les changements
# Ou utiliser:
newgrp docker
```

### Problème : Python ou pip non trouvé

**Solution :**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip
```

### Problème : Le cron ne s'exécute pas

**Solution :**
1. Vérifier que le cron est actif :
```bash
sudo systemctl status cron
```

2. Vérifier les logs du cron :
```bash
grep CRON /var/log/syslog
```

3. Vérifier les chemins absolus dans le crontab

4. Tester manuellement le script :
```bash
cd /home/thedevopser/projects/auto-update && ./run-update.sh
```

### Problème : Images non mises à jour

**Vérifications :**
- L'image existe-t-elle sur le registry ?
- Avez-vous accès au registry (credentials) ?
- L'image est-elle exclue par un tag ?
- Consultez les logs pour plus de détails

## Sécurité

- Les logs peuvent contenir des informations sensibles (chemins, noms d'images)
- Assurez-vous que les permissions des fichiers de logs sont appropriées
- N'exposez pas les logs publiquement
- Utilisez `--exclude-tag` pour les images sensibles

## Performance

- Le script traite les images séquentiellement
- Le temps dépend du nombre d'images et de leur taille
- Planifiez les mises à jour pendant les heures creuses
- Le mode dry-run est beaucoup plus rapide (pas de download)

## Améliorations futures

- [ ] Support des registries privés avec authentification
- [ ] Notifications par email/webhook
- [ ] Parallélisation des pulls
- [ ] Filtrage par repository
- [ ] Export des rapports en JSON/HTML
- [ ] Dashboard web

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Signaler des bugs
- Proposer des améliorations
- Soumettre des pull requests

## Licence

Ce projet est fourni "tel quel" sans garantie d'aucune sorte.

## Support

Pour obtenir de l'aide :
1. Consultez les logs : `~/.docker-update/logs/`
2. Lancez en mode dry-run pour diagnostiquer
3. Vérifiez les prérequis (Docker, Python, permissions)

## Auteur

Projet créé pour automatiser la maintenance des images Docker en production.

---

**Version :** 1.0.0
**Date :** 2026-01-03
