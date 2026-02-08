"""Analyze command for extracting video features."""

from pathlib import Path
from typing import Optional

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..analyzer.embeddings import EmbeddingStore
from ..analyzer.feature_extractors import MultiModalExtractor
from ..analyzer.frame_extractor import FrameExtractor
from ..auth.oauth import OAuthManager
from ..auth.service import DriveServiceFactory
from ..common.exceptions import AuthenticationError
from ..common.logging import get_logger
from ..common.rate_limiter import TokenBucketRateLimiter
from ..config.settings import get_settings
from ..scanner.file_index import FileIndex
from .formatters import (
    create_progress,
    print_error,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger(__name__)

analyze_app = typer.Typer(help="Analyze videos to extract features")


@analyze_app.command()
def analyze(
    features: str = typer.Option(
        "face,body,pose,scene",
        "--features",
        "-f",
        help="Comma-separated list of features to extract (face, body, pose, scene)",
    ),
    fps: float = typer.Option(
        1.0, "--fps", help="Frames per second to extract (default: 1)"
    ),
    max_frames: Optional[int] = typer.Option(
        None, "--max-frames", help="Maximum frames to extract per video"
    ),
    mime_types: str = typer.Option(
        "video/mp4,video/quicktime,video/x-msvideo",
        "--mime-types",
        help="Comma-separated MIME types to analyze",
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Limit number of videos to analyze (for testing)"
    ),
    skip_analyzed: bool = typer.Option(
        True, "--skip-analyzed/--reanalyze", help="Skip already analyzed videos"
    ),
) -> None:
    """Analyze videos to extract multi-modal features.

    This command downloads videos from Google Drive, extracts keyframes,
    and computes face, body, pose, and scene embeddings for clustering.
    """
    settings = get_settings()

    try:
        # Parse features
        feature_list = [f.strip().lower() for f in features.split(",")]
        extract_faces = "face" in feature_list
        extract_body = "body" in feature_list
        extract_pose = "pose" in feature_list
        extract_scene = "scene" in feature_list

        print_info(f"Extracting features: {', '.join(feature_list)}")

        # Check authentication
        oauth_manager = OAuthManager(settings.token_path, settings.credentials_path)
        if not oauth_manager.is_authenticated():
            raise AuthenticationError(
                "Not authenticated. Run 'gdrive-dedup auth login' first."
            )

        # Initialize components
        service_factory = DriveServiceFactory(oauth_manager)
        rate_limiter = TokenBucketRateLimiter(settings.rate_limit)

        # Initialize extractors
        print_info("Initializing feature extractors...")
        extractor = MultiModalExtractor(
            extract_faces=extract_faces,
            extract_body=extract_body,
            extract_pose=extract_pose,
            extract_scene=extract_scene,
            device=None,  # Auto-detect
        )

        frame_extractor = FrameExtractor(service_factory, rate_limiter)

        # Initialize embedding store
        embeddings_db = settings.db_path.parent / "embeddings.db"
        embedding_store = EmbeddingStore(embeddings_db)

        print_success(f"Feature extractors ready (using {'GPU' if extractor.body_extractor and extractor.body_extractor.device != 'cpu' else 'CPU'})")

        # Get videos to analyze from file index
        with FileIndex(settings.db_path) as file_index:
            print_info("Loading videos from file index...")

            # Parse MIME types
            mime_type_list = [m.strip() for m in mime_types.split(",")]

            # Get all files matching MIME types
            all_files = file_index.get_all_files()
            video_files = [
                f
                for f in all_files
                if f.mime_type in mime_type_list and not f.trashed
            ]

            if not video_files:
                print_warning("No video files found in index. Run 'gdrive-dedup scan' first.")
                return

            # Filter already analyzed if requested
            if skip_analyzed:
                videos_to_analyze = [
                    f for f in video_files if not embedding_store.is_analyzed(f.file_id)
                ]
                already_analyzed = len(video_files) - len(videos_to_analyze)
                if already_analyzed > 0:
                    print_info(f"Skipping {already_analyzed} already analyzed videos")
            else:
                videos_to_analyze = video_files

            # Apply limit
            if limit:
                videos_to_analyze = videos_to_analyze[:limit]

            if not videos_to_analyze:
                print_success("All videos already analyzed!")
                return

            print_info(f"Analyzing {len(videos_to_analyze)} videos...")

            # Analyze videos
            progress = create_progress()
            successful = 0
            failed = 0

            with progress:
                task = progress.add_task(
                    "[cyan]Analyzing videos...",
                    total=len(videos_to_analyze),
                )

                for video_file in videos_to_analyze:
                    try:
                        # Store video metadata
                        embedding_store.store_video_metadata(
                            video_file.file_id,
                            video_file.name,
                            video_file.path,
                            video_file.size,
                            created_time=video_file.created_time.isoformat(),
                            modified_time=video_file.modified_time.isoformat(),
                        )

                        # Extract frames and features
                        frame_index = 0
                        for frame in frame_extractor.extract_frames(
                            video_file.file_id, fps=fps, max_frames=max_frames
                        ):
                            # Extract features
                            features_obj = extractor.extract_all(frame, frame_index)

                            # Store features
                            embedding_store.store_frame_features(
                                video_file.file_id, features_obj
                            )

                            frame_index += 1

                        logger.info(
                            f"Analyzed {video_file.name}: {frame_index} frames"
                        )
                        successful += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to analyze {video_file.name}: {e}"
                        )
                        failed += 1

                    progress.update(task, advance=1)

            # Summary
            print_success(f"\nAnalyzed {successful} videos successfully")
            if failed > 0:
                print_warning(f"Failed to analyze {failed} videos")

            print_info(f"Embeddings stored in: {embeddings_db}")

    except AuthenticationError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Analysis failed: {e}")
        logger.exception("Analysis error")
        raise typer.Exit(1)
