"""Organize command for creating cluster folders."""

import json
from pathlib import Path
from typing import Optional

import typer
from humanize import naturalsize

from ..analyzer.embeddings import EmbeddingStore
from ..auth.oauth import OAuthManager
from ..auth.service import DriveServiceFactory
from ..clustering.clusterer import VideoCluster, VideoClustering
from ..clustering.similarity import SimilarityScorer, VideoComparator
from ..common.exceptions import AuthenticationError
from ..common.logging import get_logger
from ..common.rate_limiter import TokenBucketRateLimiter
from ..config.settings import get_settings
from ..organizer.cluster_organizer import ClusterOrganizer
from .formatters import (
    create_progress,
    print_error,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger(__name__)

organize_app = typer.Typer(help="Organize videos into cluster folders")


@organize_app.command()
def organize(
    clusters_file: Optional[Path] = typer.Option(
        None, "--clusters", "-c", help="JSON file with clusters (from 'cluster' command)"
    ),
    min_similarity: float = typer.Option(
        0.7, "--min-similarity", "-s", help="Minimum similarity (if recomputing clusters)"
    ),
    min_cluster_size: int = typer.Option(
        2, "--min-size", help="Minimum cluster size to organize"
    ),
    cluster_prefix: str = typer.Option(
        "Actor", "--prefix", "-p", help="Prefix for cluster folder names"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without doing it"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """Organize videos into cluster folders.

    Creates cluster folders in the location with most files,
    duplicating (not moving) files from other locations.
    """
    settings = get_settings()

    try:
        # Check authentication
        oauth_manager = OAuthManager(settings.token_path, settings.credentials_path)
        if not oauth_manager.is_authenticated():
            raise AuthenticationError(
                "Not authenticated. Run 'gdrive-dedup auth login' first."
            )

        embeddings_db = settings.db_path.parent / "embeddings.db"
        embedding_store = EmbeddingStore(embeddings_db)

        videos = embedding_store.get_all_videos()
        if not videos:
            print_error("No analyzed videos found. Run 'gdrive-dedup analyze' first.")
            raise typer.Exit(1)

        # Load or compute clusters
        if clusters_file and clusters_file.exists():
            print_info(f"Loading clusters from {clusters_file}...")
            with open(clusters_file) as f:
                clusters_data = json.load(f)

            # Reconstruct VideoCluster objects
            clusters = []
            for c in clusters_data:
                if c["size"] >= min_cluster_size:
                    cluster = VideoCluster(
                        cluster_id=c["cluster_id"],
                        file_ids=[f["file_id"] for f in c["files"]],
                        avg_similarity=c["avg_similarity"],
                        size=c["size"],
                    )
                    clusters.append(cluster)

        else:
            print_info("Computing clusters...")

            # Load features
            video_features = {}
            for video in videos:
                features = embedding_store.get_video_features(video["file_id"])
                if features:
                    video_features[video["file_id"]] = features

            # Compute similarity and cluster
            scorer = SimilarityScorer()
            comparator = VideoComparator(scorer)
            file_ids, similarity_matrix = comparator.build_similarity_matrix(video_features)

            clustering = VideoClustering(min_similarity=min_similarity)
            all_clusters = clustering.cluster_videos(file_ids, similarity_matrix)

            # Filter by size
            clusters = [c for c in all_clusters if c.size >= min_cluster_size]

        if not clusters:
            print_warning("No clusters found to organize.")
            return

        print_success(f"Found {len(clusters)} clusters to organize")

        # Prepare file metadata
        file_metadata = {v["file_id"]: v for v in videos}

        # Initialize organizer
        service_factory = DriveServiceFactory(oauth_manager)
        rate_limiter = TokenBucketRateLimiter(settings.rate_limit)
        organizer = ClusterOrganizer(service_factory, rate_limiter, file_metadata)

        # Create organization plans
        print_info("\nCreating organization plans...")
        plans = []
        total_space_mb = 0.0

        for cluster in clusters:
            cluster_name = f"{cluster_prefix}_{cluster.cluster_id:03d}"
            try:
                plan = organizer.create_organization_plan(cluster, cluster_name)
                plans.append(plan)
                total_space_mb += plan.space_used_mb
            except Exception as e:
                logger.warning(f"Failed to plan cluster {cluster.cluster_id}: {e}")

        # Display plans
        print_info(f"\nOrganization summary:")
        print_info(f"  Clusters: {len(plans)}")
        print_info(f"  Total files: {sum(p.total_files for p in plans)}")
        print_info(f"  Files to keep in place: {sum(len(p.files_to_keep_in_place) for p in plans)}")
        print_info(f"  Files to duplicate: {sum(len(p.files_to_duplicate) for p in plans)}")
        print_info(f"  Additional space used: {naturalsize(total_space_mb * 1024 * 1024)}")

        if dry_run:
            print_warning("\n[DRY RUN] No changes will be made\n")
        else:
            print_warning("\nWARNING: This will create cluster folders and duplicate files")

        # Show first few plans
        print_info("\nSample organization plans:\n")
        for plan in plans[:5]:
            print(f"  Cluster {plan.cluster_id}: {plan.cluster_folder_name}")
            print(f"    Primary folder: {plan.primary_folder}")
            print(f"    Files in place: {len(plan.files_to_keep_in_place)}")
            print(f"    Files to duplicate: {len(plan.files_to_duplicate)} (+{plan.space_used_mb:.1f} MB)")
            print()

        if len(plans) > 5:
            print_info(f"  ... and {len(plans) - 5} more clusters\n")

        # Confirm
        if not yes and not dry_run:
            confirm = typer.confirm(
                f"\nOrganize {len(plans)} clusters?",
                default=False,
            )
            if not confirm:
                print_info("Cancelled.")
                return

        # Execute plans
        print_info("\nOrganizing clusters...")
        progress = create_progress()

        results = []
        with progress:
            task = progress.add_task(
                "[cyan]Creating cluster folders...",
                total=len(plans),
            )

            for plan in plans:
                try:
                    result = organizer.execute_plan(plan, dry_run=dry_run)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to organize cluster {plan.cluster_id}: {e}")

                progress.update(task, advance=1)

        # Summary
        total_kept = sum(r["files_kept"] for r in results)
        total_duplicated = sum(r["files_duplicated"] for r in results)
        total_space = sum(r["space_used_mb"] for r in results)

        if dry_run:
            print_success(f"\n[DRY RUN] Would organize {len(results)} clusters")
        else:
            print_success(f"\nOrganized {len(results)} clusters:")
            print_info(f"  Files kept in place: {total_kept}")
            print_info(f"  Files duplicated: {total_duplicated}")
            print_info(f"  Space used: {naturalsize(total_space * 1024 * 1024)}")

    except AuthenticationError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Organization failed: {e}")
        logger.exception("Organization error")
        raise typer.Exit(1)
