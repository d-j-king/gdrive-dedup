"""Similarity computation for multi-modal features."""

from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..analyzer.feature_extractors import FrameFeatures
from ..common.logging import get_logger
from .metadata_similarity import MetadataFeatures, MetadataSimilarityScorer

logger = get_logger(__name__)


class SimilarityScorer:
    """Compute similarity between video features (visual + metadata).

    Combines visual features (face, body, pose, scene) with metadata features
    (temporal, filename, path) for robust similarity scoring.

    Default weights (optimized for adult content clustering):
    - Visual features: 60% total
      - Face: 30% of visual (18% overall) - Strong when visible
      - Body: 35% of visual (21% overall) - Primary identifier
      - Scene: 20% of visual (12% overall) - Session identification
      - Pose: 15% of visual (9% overall) - Contextual info
    - Metadata features: 40% total
      - Temporal: 50% of metadata (20% overall) - Same session/date
      - Filename: 35% of metadata (14% overall) - User organization
      - Path: 15% of metadata (6% overall) - Folder organization
    """

    def __init__(
        self,
        # Overall visual vs metadata balance
        visual_weight: float = 0.60,
        metadata_weight: float = 0.40,
        # Visual feature weights (relative within visual features)
        face_weight: float = 0.30,
        body_weight: float = 0.35,
        scene_weight: float = 0.20,
        pose_weight: float = 0.15,
        # Metadata feature weights (relative within metadata features)
        temporal_weight: float = 0.50,
        filename_weight: float = 0.35,
        path_weight: float = 0.15,
    ) -> None:
        """Initialize similarity scorer with feature weights.

        Args:
            visual_weight: Overall weight for visual features
            metadata_weight: Overall weight for metadata features
            face_weight: Weight for face similarity (within visual)
            body_weight: Weight for body similarity (within visual)
            scene_weight: Weight for scene similarity (within visual)
            pose_weight: Weight for pose similarity (within visual)
            temporal_weight: Weight for temporal similarity (within metadata)
            filename_weight: Weight for filename similarity (within metadata)
            path_weight: Weight for path similarity (within metadata)
        """
        # Normalize overall weights
        total_overall = visual_weight + metadata_weight
        self.visual_weight = visual_weight / total_overall
        self.metadata_weight = metadata_weight / total_overall

        # Normalize visual feature weights
        total_visual = face_weight + body_weight + pose_weight + scene_weight
        self.face_weight = face_weight / total_visual
        self.body_weight = body_weight / total_visual
        self.pose_weight = pose_weight / total_visual
        self.scene_weight = scene_weight / total_visual

        # Initialize metadata scorer
        self.metadata_scorer = MetadataSimilarityScorer(
            temporal_weight=temporal_weight,
            filename_weight=filename_weight,
            path_weight=path_weight,
        )

        logger.info(
            f"Overall weights: visual={self.visual_weight:.2f}, "
            f"metadata={self.metadata_weight:.2f}"
        )
        logger.info(
            f"Visual weights: face={self.face_weight:.2f}, "
            f"body={self.body_weight:.2f}, scene={self.scene_weight:.2f}, "
            f"pose={self.pose_weight:.2f}"
        )

    def compute_similarity(
        self,
        features_a: list[FrameFeatures],
        features_b: list[FrameFeatures],
        metadata_a: Optional[MetadataFeatures] = None,
        metadata_b: Optional[MetadataFeatures] = None,
    ) -> float:
        """Compute similarity between two videos.

        Combines visual features (face, body, pose, scene) with metadata
        (temporal, filename, path) for comprehensive similarity scoring.

        Args:
            features_a: Visual features from video A
            features_b: Visual features from video B
            metadata_a: Metadata features from video A
            metadata_b: Metadata features from video B

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        # Compute visual similarity
        visual_sim = self._compute_visual_similarity(features_a, features_b)

        # Compute metadata similarity if available
        metadata_sim = 0.0
        if metadata_a and metadata_b:
            metadata_sim = self.metadata_scorer.compute_similarity(metadata_a, metadata_b)

        # Weighted combination
        total_similarity = (
            self.visual_weight * visual_sim + self.metadata_weight * metadata_sim
        )

        return total_similarity

    def _compute_visual_similarity(
        self, features_a: list[FrameFeatures], features_b: list[FrameFeatures]
    ) -> float:
        """Compute visual similarity between two videos.

        Args:
            features_a: Features from video A
            features_b: Features from video B

        Returns:
            Visual similarity score (0-1)
        """
        # Aggregate features across frames
        agg_a = self._aggregate_features(features_a)
        agg_b = self._aggregate_features(features_b)

        # Compute similarity for each modality
        face_sim = self._face_similarity(agg_a["faces"], agg_b["faces"])
        body_sim = self._embedding_similarity(agg_a["body"], agg_b["body"])
        pose_sim = self._embedding_similarity(agg_a["pose"], agg_b["pose"])
        scene_sim = self._embedding_similarity(agg_a["scene"], agg_b["scene"])

        # Weighted combination (weights already normalized)
        visual_similarity = (
            self.face_weight * face_sim
            + self.body_weight * body_sim
            + self.pose_weight * pose_sim
            + self.scene_weight * scene_sim
        )

        return visual_similarity

    def _aggregate_features(self, features_list: list[FrameFeatures]) -> dict:
        """Aggregate features across multiple frames.

        Args:
            features_list: List of frame features

        Returns:
            Aggregated features dict
        """
        # Collect all face embeddings
        all_faces = []
        for feat in features_list:
            all_faces.extend(feat.face_embeddings)

        # Average body embeddings
        body_embeddings = [f.body_embedding for f in features_list if f.body_embedding is not None]
        avg_body = np.mean(body_embeddings, axis=0) if body_embeddings else None

        # Average pose keypoints
        pose_keypoints = [f.pose_keypoints for f in features_list if f.pose_keypoints is not None]
        avg_pose = np.mean(pose_keypoints, axis=0) if pose_keypoints else None

        # Average scene embeddings
        scene_embeddings = [
            f.scene_embedding for f in features_list if f.scene_embedding is not None
        ]
        avg_scene = np.mean(scene_embeddings, axis=0) if scene_embeddings else None

        return {
            "faces": all_faces,
            "body": avg_body,
            "pose": avg_pose,
            "scene": avg_scene,
        }

    def _face_similarity(
        self, faces_a: list[np.ndarray], faces_b: list[np.ndarray]
    ) -> float:
        """Compute face similarity.

        Uses maximum similarity across all face pairs (handles multiple faces).

        Args:
            faces_a: Face embeddings from video A
            faces_b: Face embeddings from video B

        Returns:
            Face similarity score (0-1)
        """
        if not faces_a or not faces_b:
            return 0.0

        # Compute pairwise similarities
        max_sim = 0.0
        for face_a in faces_a:
            for face_b in faces_b:
                sim = self._cosine_similarity(face_a, face_b)
                max_sim = max(max_sim, sim)

        return max_sim

    def _embedding_similarity(
        self, emb_a: Optional[np.ndarray], emb_b: Optional[np.ndarray]
    ) -> float:
        """Compute cosine similarity between embeddings.

        Args:
            emb_a: Embedding A
            emb_b: Embedding B

        Returns:
            Cosine similarity (0-1)
        """
        if emb_a is None or emb_b is None:
            return 0.0

        return self._cosine_similarity(emb_a, emb_b)

    def _cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec_a: Vector A
            vec_b: Vector B

        Returns:
            Cosine similarity (0-1)
        """
        # Reshape to 2D for sklearn
        vec_a = vec_a.reshape(1, -1)
        vec_b = vec_b.reshape(1, -1)

        sim = cosine_similarity(vec_a, vec_b)[0][0]

        # Convert from [-1, 1] to [0, 1]
        return (sim + 1) / 2


class VideoComparator:
    """Compare videos and build similarity matrix."""

    def __init__(self, scorer: SimilarityScorer) -> None:
        """Initialize video comparator.

        Args:
            scorer: Similarity scorer
        """
        self.scorer = scorer

    def build_similarity_matrix(
        self,
        video_features: dict[str, list[FrameFeatures]],
        video_metadata: Optional[dict[str, MetadataFeatures]] = None,
    ) -> tuple[list[str], np.ndarray]:
        """Build pairwise similarity matrix for all videos.

        Args:
            video_features: Dict mapping file_id to list of FrameFeatures
            video_metadata: Optional dict mapping file_id to MetadataFeatures

        Returns:
            Tuple of (file_ids, similarity_matrix)
        """
        file_ids = list(video_features.keys())
        n = len(file_ids)

        logger.info(f"Building similarity matrix for {n} videos...")

        # Initialize matrix
        similarity_matrix = np.zeros((n, n), dtype=np.float32)

        # Compute pairwise similarities
        for i in range(n):
            for j in range(i, n):
                if i == j:
                    similarity_matrix[i][j] = 1.0
                else:
                    # Get metadata if available
                    meta_i = video_metadata.get(file_ids[i]) if video_metadata else None
                    meta_j = video_metadata.get(file_ids[j]) if video_metadata else None

                    sim = self.scorer.compute_similarity(
                        video_features[file_ids[i]],
                        video_features[file_ids[j]],
                        meta_i,
                        meta_j,
                    )
                    similarity_matrix[i][j] = sim
                    similarity_matrix[j][i] = sim  # Symmetric

            if (i + 1) % 10 == 0:
                logger.info(f"Processed {i + 1}/{n} videos")

        logger.info("Similarity matrix complete")

        return file_ids, similarity_matrix
