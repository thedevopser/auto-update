#!/bin/bash
###############################################################################
# Script d'installation et de configuration de Docker Auto-Update
# Ce script configure l'environnement virtuel Python et installe les dépendances
###############################################################################

set -e  # Arrêter en cas d'erreur

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="${SCRIPT_DIR}/venv"
PYTHON_CMD="python3"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Bannière
echo "========================================"
echo "  Docker Auto-Update - Installation"
echo "========================================"
echo ""

# Vérifier que Python3 est installé
print_info "Vérification de Python3..."
if ! command -v ${PYTHON_CMD} &> /dev/null; then
    print_error "Python3 n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

PYTHON_VERSION=$(${PYTHON_CMD} --version 2>&1 | awk '{print $2}')
print_success "Python ${PYTHON_VERSION} détecté"

# Vérifier que Docker est installé
print_info "Vérification de Docker..."
if ! command -v docker &> /dev/null; then
    print_error "Docker n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
print_success "Docker ${DOCKER_VERSION} détecté"

# Vérifier les permissions Docker
print_info "Vérification des permissions Docker..."
if ! docker ps &> /dev/null; then
    print_warning "Permissions Docker insuffisantes"
    print_info "Ajout de l'utilisateur au groupe docker..."
    sudo usermod -aG docker ${USER}
    print_warning "Vous devrez vous déconnecter et vous reconnecter pour que les permissions prennent effet"
fi

# Vérifier si pip est installé
print_info "Vérification de pip..."
if ! ${PYTHON_CMD} -m pip --version &> /dev/null; then
    print_error "pip n'est pas installé. Installation..."
    sudo apt-get update
    sudo apt-get install -y python3-pip
fi

# Vérifier si python3-venv est installé
print_info "Vérification de python3-venv..."
if ! ${PYTHON_CMD} -m venv --help &> /dev/null; then
    print_info "Installation de python3-venv..."
    sudo apt-get update
    sudo apt-get install -y python3-venv
fi

# Créer le virtual environment
if [ -d "${VENV_DIR}" ]; then
    print_warning "Un environnement virtuel existe déjà"
    read -p "Voulez-vous le recréer ? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Suppression de l'ancien environnement..."
        rm -rf "${VENV_DIR}"
    else
        print_info "Conservation de l'environnement existant"
    fi
fi

if [ ! -d "${VENV_DIR}" ]; then
    print_info "Création de l'environnement virtuel..."
    ${PYTHON_CMD} -m venv "${VENV_DIR}"
    print_success "Environnement virtuel créé"
fi

# Activer le virtual environment
print_info "Activation de l'environnement virtuel..."
source "${VENV_DIR}/bin/activate"

# Mettre à jour pip
print_info "Mise à jour de pip..."
pip install --upgrade pip --quiet

# Installer les dépendances
print_info "Installation des dépendances..."
pip install -r "${SCRIPT_DIR}/requirements.txt" --quiet
print_success "Dépendances installées"

# Rendre le script principal exécutable
print_info "Configuration des permissions..."
chmod +x "${SCRIPT_DIR}/docker-update.py"

# Créer le répertoire de logs
LOG_DIR="${HOME}/.docker-update/logs"
mkdir -p "${LOG_DIR}"
print_success "Répertoire de logs créé: ${LOG_DIR}"

# Créer un script wrapper pour faciliter l'exécution
WRAPPER_SCRIPT="${SCRIPT_DIR}/run-update.sh"
cat > "${WRAPPER_SCRIPT}" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${SCRIPT_DIR}/venv/bin/activate"
python "${SCRIPT_DIR}/docker-update.py" "$@"
EOF

chmod +x "${WRAPPER_SCRIPT}"
print_success "Script wrapper créé: ${WRAPPER_SCRIPT}"

echo ""
echo "========================================"
print_success "Installation terminée avec succès!"
echo "========================================"
echo ""
print_info "Pour exécuter le script:"
echo "  ${WRAPPER_SCRIPT}"
echo ""
print_info "Pour un test en mode dry-run:"
echo "  ${WRAPPER_SCRIPT} --dry-run"
echo ""
print_info "Pour configurer le cron:"
echo "  Consultez le fichier crontab.example"
echo ""
print_info "Logs disponibles dans:"
echo "  ${LOG_DIR}"
echo ""
