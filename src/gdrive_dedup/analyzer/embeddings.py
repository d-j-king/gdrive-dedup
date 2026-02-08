"""Storage and retrieval of video feature embeddings."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ..common.logging import get_logger
from .feature_extractors import FrameFeatures

logger = get_logger(__name__)


class EmbeddingStore:
    """Store and retrieve video embeddings in SQLite."""

    def __init__(self, db_path: Path) -> None:
        """Initialize embedding store.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS video_metadata (
                    file_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    duration REAL,
                    created_time TEXT,
                    modified_time TEXT,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS frame_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    face_embeddings TEXT,  -- JSON array of embeddings
                    face_boxes TEXT,  -- JSON array of bounding boxes
                    body_embedding BLOB,  -- Numpy array
                    pose_keypoints BLOB,  -- Numpy array
                    scene_embedding BLOB,  -- Numpy array
                    FOREIGN KEY (file_id) REFERENCES video_metadata (file_id),
                    UNIQUE (file_id, frame_index)
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_file_id
                ON frame_features (file_id)
                """
            )

            logger.info(f"Embedding database initialized at {self.db_path}")

    def store_video_metadata(
        self,
        file_id: str,
        name: str,
        path: str,
        size: int,
        duration: Optional[float] = None,
        created_time: Optional[str] = None,
        modified_time: Optional[str] = None,
    ) -> None:
        """Store video metadata.

        Args:
            file_id: Google Drive file ID
            name: File name
            path: File path in Drive
            size: File size in bytes
            duration: Video duration in seconds
            created_time: ISO format creation timestamp
            modified_time: ISO format modification timestamp
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO video_metadata
                (file_id, name, path, size, duration, created_time, modified_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, name, path, size, duration, created_time, modified_time),
            )

    def store_frame_features(self, file_id: str, features: FrameFeatures) -> None:
        """Store features for a single frame.

        Args:
            file_id: Google Drive file ID
            features: Extracted features
        """
        # Serialize face embeddings as JSON
        face_embeddings_json = None
        if features.face_embeddings:
            face_embeddings_json = json.dumps(
                [emb.tolist() for emb in features.face_embeddings]
            )

        # Serialize face boxes as JSON
        face_boxes_json = None
        if features.face_boxes:
            face_boxes_json = json.dumps(features.face_boxes)

        # Serialize numpy arrays as blobs
        body_blob = (
            features.body_embedding.tobytes() if features.body_embedding is not None else None
        )
        pose_blob = (
            features.pose_keypoints.tobytes() if features.pose_keypoints is not None else None
        )
        scene_blob = (
            features.scene_embedding.tobytes() if features.scene_embedding is not None else None
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO frame_features
                (file_id, frame_index, face_embeddings, face_boxes,
                 body_embedding, pose_keypoints, scene_embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    features.frame_index,
                    face_embeddings_json,
                    face_boxes_json,
                    body_blob,
                    pose_blob,
                    scene_blob,
                ),
            )

    def get_video_features(self, file_id: str) -> list[FrameFeatures]:
        """Retrieve all frame features for a video.

        Args:
            file_id: Google Drive file ID

        Returns:
            List of frame features
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT frame_index, face_embeddings, face_boxes,
                       body_embedding, pose_keypoints, scene_embedding
                FROM frame_features
                WHERE file_id = ?
                ORDER BY frame_index
                """,
                (file_id,),
            )

            features_list = []
            for row in cursor:
                frame_index, face_emb_json, face_boxes_json, body_blob, pose_blob, scene_blob = (
                    row
                )

                # Deserialize face embeddings
                face_embeddings = []
                if face_emb_json:
                    face_emb_list = json.loads(face_emb_json)
                    face_embeddings = [np.array(emb, dtype=np.float32) for emb in face_emb_list]

                # Deserialize face boxes
                face_boxes = []
                if face_boxes_json:
                    face_boxes = json.loads(face_boxes_json)

                # Deserialize numpy arrays
                body_embedding = (
                    np.frombuffer(body_blob, dtype=np.float32) if body_blob else None
                )
                pose_keypoints = (
                    np.frombuffer(pose_blob, dtype=np.float32) if pose_blob else None
                )
                scene_embedding = (
                    np.frombuffer(scene_blob, dtype=np.float32) if scene_blob else None
                )

                features = FrameFeatures(
                    face_embeddings=face_embeddings,
                    face_boxes=face_boxes,
                    body_embedding=body_embedding,
                    pose_keypoints=pose_keypoints,
                    scene_embedding=scene_embedding,
                    frame_index=frame_index,
                )
                features_list.append(features)

            return features_list

    def get_all_videos(self) -> list[dict[str, Any]]:
        """Get metadata for all analyzed videos.

        Returns:
            List of video metadata dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT file_id, name, path, size, duration,
                       created_time, modified_time, analyzed_at
                FROM video_metadata
                ORDER BY analyzed_at DESC
                """
            )

            return [dict(row) for row in cursor]

    def get_video_metadata_for_clustering(self, file_id: str) -> Optional[dict[str, Any]]:
        """Get metadata for a specific video suitable for clustering.

        Args:
            file_id: Google Drive file ID

        Returns:
            Dict with file_id, name, created_time, modified_time, path
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT file_id, name, created_time, modified_time, path
                FROM video_metadata
                WHERE file_id = ?
                """,
                (file_id,),
            )

            row = cursor.fetchone()
            return dict(row) if row else None

    def is_analyzed(self, file_id: str) -> bool:
        """Check if a video has been analyzed.

        Args:
            file_id: Google Drive file ID

        Returns:
            True if video has features stored
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM frame_features WHERE file_id = ?", (file_id,)
            )
            count = cursor.fetchone()[0]
            return count > 0

    def delete_video(self, file_id: str) -> None:
        """Delete all data for a video.

        Args:
            file_id: Google Drive file ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM frame_features WHERE file_id = ?", (file_id,))
            conn.execute("DELETE FROM video_metadata WHERE file_id = ?", (file_id,))
            logger.info(f"Deleted embeddings for {file_id}")
