"""Cluster command for grouping similar videos."""

import json
from pathlib import Path
from typing import Optional

import typer

from ..analyzer.embeddings import EmbeddingStore
from ..clustering.clusterer import VideoClustering
from ..clustering.similarity import SimilarityScorer, VideoComparator
from ..common.logging import get_logger
from ..config.settings import get_settings
from .formatters import print_error, print_info, print_success, print_warning

logger = get_logger(__name__)

cluster_app = typer.Typer(help="Cluster similar videos")


@cluster_app.command()
def cluster(
    min_similarity: float = typer.Option(
        0.7, "--min-similarity", "-s", help="Minimum similarity threshold (0-1)"
    ),
    algorithm: str = typer.Option(
        "dbscan", "--algorithm", "-a", help="Clustering algorithm (dbscan, agglomerative)"
    ),
    face_weight: float = typer.Option(
        0.40, "--face-weight", help="Weight for face similarity"
    ),
    body_weight: float = typer.Option(
        0.25, "--body-weight", help="Weight for body similarity"
    ),
    pose_weight: float = typer.Option(
        0.20, "--pose-weight", help="Weight for pose similarity"
    ),
    scene_weight: float = typer.Option(
        0.15, "--scene-weight", help="Weight for scene similarity"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Save clusters to JSON file"
    ),
) -> None:
    """Cluster videos by similarity.

    Uses extracted features to group videos with similar actors, scenes, or content.
    """
    settings = get_settings()

    try:
        embeddings_db = settings.db_path.parent / "embeddings.db"

        if not embeddings_db.exists():
            print_error(
                f"Embeddings database not found: {embeddings_db}\n"
                "Run 'gdrive-dedup analyze' first."
            )
            raise typer.Exit(1)

        # Load embeddings
        print_info("Loading video embeddings...")
        embedding_store = EmbeddingStore(embeddings_db)

        videos = embedding_store.get_all_videos()
        if not videos:
            print_warning("No analyzed videos found. Run 'gdrive-dedup analyze' first.")
            return

        print_info(f"Loaded {len(videos)} analyzed videos")

        # Load features for all videos
        print_info("Loading features...")
        video_features = {}
        for video in videos:
            features = embedding_store.get_video_features(video["file_id"])
            if features:
                video_features[video["file_id"]] = features

        print_success(f"Loaded features for {len(video_features)} videos")

        # Compute similarity matrix
        print_info("Computing similarity matrix...")
        scorer = SimilarityScorer(
            face_weight=face_weight,
            body_weight=body_weight,
            pose_weight=pose_weight,
            scene_weight=scene_weight,
        )

        comparator = VideoComparator(scorer)
        file_ids, similarity_matrix = comparator.build_similarity_matrix(video_features)

        print_success("Similarity matrix computed")

        # Cluster videos
        print_info(f"Clustering with {algorithm} (min_similarity={min_similarity})...")
        clustering = VideoClustering(min_similarity=min_similarity, algorithm=algorithm)

        clusters = clustering.cluster_videos(file_ids, similarity_matrix)

        # Display results
        if not clusters:
            print_warning("No clusters found. Try lowering --min-similarity")
            return

        print_success(f"\nFound {len(clusters)} clusters:\n")

        # Create lookup for video names
        video_by_id = {v["file_id"]: v for v in videos}

        total_videos_clustered = 0
        for i, cluster in enumerate(clusters[:20]):  # Show top 20
            print_info(
                f"Cluster {cluster.cluster_id}: "
                f"{cluster.size} videos "
                f"(avg similarity: {cluster.avg_similarity:.2f})"
            )

            # Show first few files
            for file_id in cluster.file_ids[:3]:
                video = video_by_id.get(file_id)
                if video:
                    print(f"  - {video['name']}")

            if cluster.size > 3:
                print(f"  ... and {cluster.size - 3} more")

            print()
            total_videos_clustered += cluster.size

        if len(clusters) > 20:
            print_info(f"... and {len(clusters) - 20} more clusters")

        print_info(f"Total videos in clusters: {total_videos_clustered}/{len(videos)}")

        # Save to file if requested
        if output:
            print_info(f"Saving clusters to {output}...")

            clusters_data = []
            for cluster in clusters:
                cluster_dict = {
                    "cluster_id": cluster.cluster_id,
                    "size": cluster.size,
                    "avg_similarity": cluster.avg_similarity,
                    "files": [
                        {
                            "file_id": fid,
                            "name": video_by_id[fid]["name"],
                            "path": video_by_id[fid]["path"],
                        }
                        for fid in cluster.file_ids
                        if fid in video_by_id
                    ],
                }
                clusters_data.append(cluster_dict)

            with open(output, "w") as f:
                json.dump(clusters_data, f, indent=2)

            print_success(f"Clusters saved to {output}")

        print_info("\nNext step: Run 'gdrive-dedup organize' to create cluster folders")

    except Exception as e:
        print_error(f"Clustering failed: {e}")
        logger.exception("Clustering error")
        raise typer.Exit(1)


@cluster_app.command(name="find-similar")
def find_similar(
    file_id: str = typer.Argument(..., help="File ID to find similar videos for"),
    min_similarity: float = typer.Option(
        0.7, "--min-similarity", "-s", help="Minimum similarity threshold"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max number of results"),
) -> None:
    """Find videos similar to a specific video."""
    settings = get_settings()

    try:
        embeddings_db = settings.db_path.parent / "embeddings.db"
        embedding_store = EmbeddingStore(embeddings_db)

        videos = embedding_store.get_all_videos()
        video_features = {}
        for video in videos:
            features = embedding_store.get_video_features(video["file_id"])
            if features:
                video_features[video["file_id"]] = features

        # Compute similarity
        scorer = SimilarityScorer()
        comparator = VideoComparator(scorer)
        file_ids, similarity_matrix = comparator.build_similarity_matrix(video_features)

        # Find similar videos
        clustering = VideoClustering(min_similarity=min_similarity)
        similar_videos = clustering.find_similar_videos(
            file_id, file_ids, similarity_matrix
        )

        if not similar_videos:
            print_warning(f"No similar videos found for {file_id}")
            return

        # Display results
        video_by_id = {v["file_id"]: v for v in videos}

        print_success(f"Found {len(similar_videos)} similar videos:\n")

        for fid, sim in similar_videos[:limit]:
            video = video_by_id.get(fid)
            if video:
                print_info(f"{sim:.2f} - {video['name']}")
                print(f"        {video['path']}\n")

    except Exception as e:
        print_error(f"Search failed: {e}")
        raise typer.Exit(1)
