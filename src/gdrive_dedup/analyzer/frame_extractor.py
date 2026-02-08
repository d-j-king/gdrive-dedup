"""Extract keyframes from videos for analysis."""

import io
import tempfile
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np
from PIL import Image

from ..auth.service import DriveServiceFactory
from ..common.logging import get_logger
from ..common.rate_limiter import TokenBucketRateLimiter

logger = get_logger(__name__)


class FrameExtractor:
    """Extract keyframes from videos stored in Google Drive."""

    def __init__(
        self,
        service_factory: DriveServiceFactory,
        rate_limiter: TokenBucketRateLimiter,
    ) -> None:
        """Initialize frame extractor.

        Args:
            service_factory: Factory for creating Drive API service
            rate_limiter: Rate limiter for API requests
        """
        self.service_factory = service_factory
        self.rate_limiter = rate_limiter

    def extract_frames(
        self,
        file_id: str,
        fps: float = 1.0,
        max_frames: Optional[int] = None,
        scene_detection: bool = False,
    ) -> Iterator[np.ndarray]:
        """Extract frames from a video file.

        Args:
            file_id: Google Drive file ID
            fps: Frames per second to extract (default: 1 frame/second)
            max_frames: Maximum number of frames to extract
            scene_detection: If True, only extract frames at scene changes

        Yields:
            Frames as numpy arrays (RGB format)
        """
        logger.info(f"Extracting frames from video {file_id} (fps={fps})")

        # Download video to temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            try:
                self._download_video(file_id, tmp_path)

                # Extract frames
                yield from self._extract_frames_from_file(
                    tmp_path, fps, max_frames, scene_detection
                )
            finally:
                # Clean up temp file
                Path(tmp_path).unlink(missing_ok=True)

    def _download_video(self, file_id: str, output_path: str) -> None:
        """Download video from Google Drive.

        Args:
            file_id: Google Drive file ID
            output_path: Local path to save video
        """
        service = self.service_factory.create_service()
        self.rate_limiter.acquire()

        request = service.files().get_media(fileId=file_id)

        with open(output_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download {int(status.progress() * 100)}%")

    def _extract_frames_from_file(
        self,
        video_path: str,
        fps: float,
        max_frames: Optional[int],
        scene_detection: bool,
    ) -> Iterator[np.ndarray]:
        """Extract frames from a local video file.

        Args:
            video_path: Path to video file
            fps: Frames per second to extract
            max_frames: Maximum frames to extract
            scene_detection: Use scene detection

        Yields:
            Frames as numpy arrays (RGB)
        """
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            logger.error(f"Failed to open video: {video_path}")
            return

        try:
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            if video_fps == 0:
                video_fps = 30.0  # Fallback

            # Calculate frame interval
            frame_interval = int(video_fps / fps)
            if frame_interval < 1:
                frame_interval = 1

            frame_count = 0
            extracted_count = 0
            prev_frame = None

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Extract at intervals
                if frame_count % frame_interval == 0:
                    if scene_detection and prev_frame is not None:
                        # Check if scene changed significantly
                        if not self._is_scene_change(prev_frame, frame):
                            frame_count += 1
                            continue

                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                    yield frame_rgb
                    extracted_count += 1
                    prev_frame = frame

                    if max_frames and extracted_count >= max_frames:
                        break

                frame_count += 1

            logger.info(f"Extracted {extracted_count} frames from {frame_count} total frames")

        finally:
            cap.release()

    def _is_scene_change(
        self, prev_frame: np.ndarray, curr_frame: np.ndarray, threshold: float = 30.0
    ) -> bool:
        """Detect if there's a scene change between frames.

        Args:
            prev_frame: Previous frame (BGR)
            curr_frame: Current frame (BGR)
            threshold: Difference threshold for scene change

        Returns:
            True if scene changed
        """
        # Calculate mean absolute difference
        diff = cv2.absdiff(prev_frame, curr_frame)
        mean_diff = np.mean(diff)

        return mean_diff > threshold


# Import for video download
from googleapiclient.http import MediaIoBaseDownload
