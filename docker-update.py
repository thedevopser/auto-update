#!/usr/bin/env python3
"""
Docker Image Auto-Update Script
Automatise la mise à jour des images Docker locales avec interface de progression
"""

import subprocess
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import argparse
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich import box

# Configuration du logging
LOG_DIR = Path.home() / ".docker-update" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"docker-update-{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
    ]
)

logger = logging.getLogger(__name__)
console = Console()


class DockerImageUpdater:
    """Gestionnaire de mise à jour des images Docker"""

    def __init__(self, dry_run: bool = False, exclude_tags: Optional[List[str]] = None,
                 skip_local_builds: bool = True):
        self.dry_run = dry_run
        self.exclude_tags = exclude_tags or ['<none>']
        self.skip_local_builds = skip_local_builds
        self.updated_images = []
        self.failed_images = []
        self.unchanged_images = []
        self.skipped_local_images = []
        self.stats = {
            'total': 0,
            'updated': 0,
            'failed': 0,
            'unchanged': 0,
            'skipped_local': 0,
            'start_time': datetime.now()
        }

    def run_command(self, cmd: List[str]) -> Optional[str]:
        """Exécute une commande shell et retourne le résultat"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur lors de l'exécution de {' '.join(cmd)}: {e.stderr}")
            return None

    def is_local_build(self, repository: str, tag: str) -> bool:
        """
        Détecte si une image est buildée localement (pas de registry).

        Stratégie:
        1. Si pas de RepoDigests, c'est local
        2. Si repository commence par localhost, c'est local
        3. Si RepoDigest ne contient pas de nom de domaine (avec '.'), c'est local
        4. Images Docker Hub officielles: repository sans '/' OU avec format 'user/image' qui existe sur Docker Hub
        """
        image_name = f"{repository}:{tag}"

        # Vérifier si l'image a un RepoDigests
        cmd = ["docker", "inspect", "--format={{.RepoDigests}}", image_name]
        digests = self.run_command(cmd)

        # Si pas de digests ou digests vide [], c'est une image locale
        if not digests or digests == "[]":
            logger.info(f"Image {image_name} détectée comme build local (pas de RepoDigests)")
            return True

        # Si repository commence par localhost ou 127.0.0.1, c'est local
        if repository.startswith('localhost') or repository.startswith('127.0.0.1'):
            logger.info(f"Image {image_name} détectée comme build local (localhost registry)")
            return True

        # Analyser le RepoDigest pour voir s'il contient un nom de domaine
        # Format attendu pour registry: "registry.com/path/image@sha256:..."
        # Format local: "image-name@sha256:..." ou "user/image@sha256:..." (sans domaine)
        if digests and digests != "[]":
            # Extraire le premier digest (format: [image@sha256:...])
            digest_content = digests.strip('[]').strip()

            if '@sha256:' in digest_content:
                # Récupérer la partie avant @sha256
                digest_prefix = digest_content.split('@sha256:')[0]

                # Vérifier si le prefix contient un '.' (indique un nom de domaine)
                # Images locales: "docker-wowplanet", "project/app"
                # Images registry: "docker.io/library/postgres", "ghcr.io/user/app", "index.docker.io/postgres"
                if '.' not in digest_prefix:
                    # Pas de domaine, probablement local
                    # MAIS attention aux images Docker Hub qui n'ont pas de domaine dans le digest

                    # Règle 1: Si le repository contient un '/', c'est probablement Docker Hub (user/image)
                    # Ex: "portainer/portainer-ce", "axllent/mailpit", "jakzal/phpqa"
                    if '/' in repository:
                        logger.debug(f"Image {image_name} considérée comme Docker Hub (format user/image)")
                        return False

                    # Règle 2: Liste blanche d'images officielles communes (sans domaine mais sur Docker Hub)
                    common_official_images = [
                        'nginx', 'postgres', 'redis', 'mysql', 'mongo', 'ubuntu', 'debian',
                        'alpine', 'python', 'node', 'golang', 'java', 'openjdk', 'httpd',
                        'memcached', 'rabbitmq', 'elasticsearch', 'mariadb', 'traefik',
                        'caddy', 'registry', 'vault', 'consul', 'jenkins', 'sonarqube'
                    ]

                    # Si c'est une image officielle connue, on ne la considère pas comme locale
                    if repository in common_official_images:
                        logger.debug(f"Image {image_name} reconnue comme image officielle Docker Hub")
                        return False

                    # Sinon, c'est probablement une image locale
                    # Ex: "docker-wowplanet", "mon-projet", "app"
                    logger.info(f"Image {image_name} détectée comme build local (RepoDigest sans domaine ni /: {digest_prefix})")
                    return True

        # Par défaut, on considère que l'image vient d'un registry
        return False

    def get_local_images(self) -> List[Dict[str, str]]:
        """Récupère la liste des images Docker locales"""
        logger.info("Récupération de la liste des images Docker locales...")

        cmd = ["docker", "images", "--format", "{{json .}}"]
        output = self.run_command(cmd)

        if not output:
            logger.warning("Aucune image Docker trouvée")
            return []

        images = []
        for line in output.split('\n'):
            if line.strip():
                try:
                    image_data = json.loads(line)
                    # Exclure les images avec tags spécifiques
                    if image_data['Tag'] not in self.exclude_tags:
                        images.append({
                            'repository': image_data['Repository'],
                            'tag': image_data['Tag'],
                            'id': image_data['ID'],
                            'size': image_data['Size'],
                            'created': image_data.get('CreatedAt', 'N/A')
                        })
                except json.JSONDecodeError:
                    logger.warning(f"Impossible de parser la ligne: {line}")

        logger.info(f"{len(images)} image(s) trouvée(s)")
        return images

    def pull_image(self, repository: str, tag: str) -> bool:
        """Pull une image Docker depuis le registry"""
        image_name = f"{repository}:{tag}"
        logger.info(f"Pull de l'image {image_name}...")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Simulation du pull de {image_name}")
            return True

        cmd = ["docker", "pull", image_name]
        result = self.run_command(cmd)

        return result is not None

    def get_image_digest(self, repository: str, tag: str) -> Optional[str]:
        """Récupère le digest d'une image"""
        image_name = f"{repository}:{tag}"
        cmd = ["docker", "inspect", "--format={{index .RepoDigests 0}}", image_name]
        return self.run_command(cmd)

    def update_image(self, image: Dict[str, str]) -> Dict[str, any]:
        """Met à jour une image Docker"""
        repository = image['repository']
        tag = image['tag']
        old_id = image['id']

        logger.info(f"Traitement de {repository}:{tag} (ID: {old_id})")

        # Récupérer le digest avant le pull
        old_digest = self.get_image_digest(repository, tag)

        # Pull la nouvelle version
        if not self.pull_image(repository, tag):
            logger.error(f"Échec du pull pour {repository}:{tag}")
            return {'status': 'failed', 'image': f"{repository}:{tag}"}

        # Récupérer le nouveau digest
        new_digest = self.get_image_digest(repository, tag)

        # Vérifier si l'image a été mise à jour
        if old_digest == new_digest:
            logger.info(f"✓ {repository}:{tag} est déjà à jour")
            return {'status': 'unchanged', 'image': f"{repository}:{tag}"}
        else:
            logger.info(f"✓ {repository}:{tag} a été mise à jour")
            return {'status': 'updated', 'image': f"{repository}:{tag}"}

    def cleanup_dangling_images(self):
        """Supprime les images orphelines (dangling)"""
        logger.info("Nettoyage des images orphelines...")

        if self.dry_run:
            logger.info("[DRY-RUN] Simulation du nettoyage")
            return "Simulation"

        cmd = ["docker", "image", "prune", "-f"]
        result = self.run_command(cmd)

        if result:
            logger.info(f"Nettoyage effectué: {result}")
            return result
        return "Aucune image à nettoyer"

    def update_all_images(self):
        """Met à jour toutes les images locales avec interface graphique"""
        console.print(Panel.fit(
            "[bold cyan]Docker Image Auto-Update[/bold cyan]\n"
            f"[dim]Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            box=box.DOUBLE
        ))

        images = self.get_local_images()
        self.stats['total'] = len(images)

        if not images:
            console.print("[yellow]Aucune image à mettre à jour[/yellow]")
            return

        # Table des images trouvées
        table = Table(title="Images Docker locales détectées", box=box.ROUNDED)
        table.add_column("Repository", style="cyan")
        table.add_column("Tag", style="magenta")
        table.add_column("ID", style="green")
        table.add_column("Size", style="yellow")

        for image in images[:10]:  # Limiter l'affichage à 10
            table.add_row(
                image['repository'],
                image['tag'],
                image['id'][:12],
                image['size']
            )

        if len(images) > 10:
            table.add_row("[dim]...[/dim]", f"[dim]+{len(images)-10} autres[/dim]", "", "")

        console.print(table)
        console.print()

        # Mise à jour avec barre de progression
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:

            task = progress.add_task(
                "[cyan]Mise à jour des images...",
                total=len(images)
            )

            for image in images:
                image_name = f"{image['repository']}:{image['tag']}"
                progress.update(task, description=f"[cyan]Traitement: {image_name[:50]}")

                try:
                    # Vérifier si c'est une image buildée localement
                    if self.skip_local_builds and self.is_local_build(image['repository'], image['tag']):
                        logger.info(f"Image {image_name} ignorée (build local)")
                        self.skipped_local_images.append(image_name)
                        self.stats['skipped_local'] += 1
                        progress.advance(task)
                        continue

                    result = self.update_image(image)

                    if result['status'] == 'updated':
                        self.updated_images.append(result['image'])
                        self.stats['updated'] += 1
                    elif result['status'] == 'unchanged':
                        self.unchanged_images.append(result['image'])
                        self.stats['unchanged'] += 1
                    else:
                        self.failed_images.append(result['image'])
                        self.stats['failed'] += 1

                except Exception as e:
                    logger.error(f"Erreur lors de la mise à jour de {image_name}: {e}")
                    self.failed_images.append(image_name)
                    self.stats['failed'] += 1

                progress.advance(task)

        console.print()

        # Nettoyage
        with console.status("[bold green]Nettoyage des images orphelines..."):
            cleanup_result = self.cleanup_dangling_images()

        console.print(f"[dim]Nettoyage: {cleanup_result}[/dim]\n")

        # Afficher le résumé
        self.print_summary()

    def print_summary(self):
        """Affiche un résumé détaillé de la mise à jour"""
        elapsed = datetime.now() - self.stats['start_time']

        # Tableau récapitulatif
        summary_table = Table(title="Résumé de la mise à jour", box=box.DOUBLE_EDGE, show_header=False)
        summary_table.add_column("Métrique", style="bold cyan")
        summary_table.add_column("Valeur", style="bold white")

        summary_table.add_row("Images totales", str(self.stats['total']))
        summary_table.add_row(
            "Images mises à jour",
            f"[green]{self.stats['updated']}[/green]"
        )
        summary_table.add_row(
            "Images déjà à jour",
            f"[blue]{self.stats['unchanged']}[/blue]"
        )
        summary_table.add_row(
            "Images locales ignorées",
            f"[yellow]{self.stats['skipped_local']}[/yellow]"
        )
        summary_table.add_row(
            "Images en échec",
            f"[red]{self.stats['failed']}[/red]"
        )
        summary_table.add_row(
            "Temps d'exécution",
            f"{elapsed.total_seconds():.2f}s"
        )
        summary_table.add_row(
            "Fichier log",
            f"[dim]{LOG_FILE}[/dim]"
        )

        console.print(summary_table)

        # Détails des échecs
        if self.failed_images:
            console.print()
            error_table = Table(title="Images ayant échoué", box=box.ROUNDED, style="red")
            error_table.add_column("Image", style="red")

            for img in self.failed_images:
                error_table.add_row(img)

            console.print(error_table)

        # Détails des mises à jour
        if self.updated_images:
            console.print()
            update_table = Table(title="Images mises à jour", box=box.ROUNDED, style="green")
            update_table.add_column("Image", style="green")

            for img in self.updated_images:
                update_table.add_row(img)

            console.print(update_table)

        # Détails des images locales ignorées
        if self.skipped_local_images:
            console.print()
            skipped_table = Table(title="Images locales ignorées (builds locaux)", box=box.ROUNDED, style="yellow")
            skipped_table.add_column("Image", style="yellow")

            for img in self.skipped_local_images:
                skipped_table.add_row(img)

            console.print(skipped_table)

        console.print()

        # Message de fin
        if self.stats['failed'] > 0:
            status_msg = f"[yellow]Terminé avec {self.stats['failed']} erreur(s)[/yellow]"
        else:
            status_msg = "[green]Terminé avec succès ![/green]"

        console.print(Panel(status_msg, box=box.ROUNDED))


def main():
    """Point d'entrée principal du script"""
    parser = argparse.ArgumentParser(
        description="Mise à jour automatique des images Docker locales",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  %(prog)s                             # Mise à jour de toutes les images registry
  %(prog)s --dry-run                   # Mode simulation
  %(prog)s --exclude-tag latest        # Exclure les images avec tag 'latest'
  %(prog)s --include-local-builds      # Inclure aussi les images buildées localement
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Mode simulation (aucune modification réelle)"
    )
    parser.add_argument(
        '--exclude-tag',
        action='append',
        help="Tags à exclure de la mise à jour (peut être répété)"
    )
    parser.add_argument(
        '--include-local-builds',
        action='store_true',
        help="Inclure les images buildées localement (par défaut: exclues)"
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )

    args = parser.parse_args()

    # Vérifier que Docker est installé et accessible
    try:
        subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[bold red]Erreur: Docker n'est pas installé ou n'est pas accessible[/bold red]")
        sys.exit(1)

    # Vérifier les permissions Docker
    try:
        subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError:
        console.print("[bold red]Erreur: Permissions insuffisantes pour accéder à Docker[/bold red]")
        console.print("[yellow]Assurez-vous que votre utilisateur fait partie du groupe 'docker'[/yellow]")
        sys.exit(1)

    if args.dry_run:
        console.print("[bold yellow]Mode DRY-RUN activé - Aucune modification ne sera effectuée[/bold yellow]\n")

    # Créer l'updater et lancer la mise à jour
    updater = DockerImageUpdater(
        dry_run=args.dry_run,
        exclude_tags=args.exclude_tag,
        skip_local_builds=not args.include_local_builds
    )

    try:
        updater.update_all_images()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interruption par l'utilisateur[/yellow]")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)
        console.print(f"[bold red]Erreur fatale: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
