"""Clustering algorithms for grouping similar videos."""

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.cluster import DBSCAN, AgglomerativeClustering

from ..common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VideoCluster:
    """A cluster of similar videos."""

    cluster_id: int
    file_ids: list[str]
    avg_similarity: float  # Average intra-cluster similarity
    size: int

    @property
    def primary_folder(self) -> Optional[str]:
        """Folder containing most files in this cluster."""
        # Will be set by organizer
        return None


class VideoClustering:
    """Cluster videos based on similarity."""

    def __init__(
        self,
        min_similarity: float = 0.7,
        algorithm: str = "dbscan",
    ) -> None:
        """Initialize clustering.

        Args:
            min_similarity: Minimum similarity threshold for clustering
            algorithm: Clustering algorithm ('dbscan' or 'agglomerative')
        """
        self.min_similarity = min_similarity
        self.algorithm = algorithm

        logger.info(f"Clustering with {algorithm}, min_similarity={min_similarity}")

    def cluster_videos(
        self, file_ids: list[str], similarity_matrix: np.ndarray
    ) -> list[VideoCluster]:
        """Cluster videos based on similarity matrix.

        Args:
            file_ids: List of file IDs
            similarity_matrix: Pairwise similarity matrix

        Returns:
            List of video clusters
        """
        logger.info(f"Clustering {len(file_ids)} videos...")

        # Convert similarity to distance
        distance_matrix = 1 - similarity_matrix

        # Run clustering algorithm
        if self.algorithm == "dbscan":
            labels = self._dbscan_clustering(distance_matrix)
        elif self.algorithm == "agglomerative":
            labels = self._agglomerative_clustering(distance_matrix)
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

        # Build clusters
        clusters = self._build_clusters(file_ids, labels, similarity_matrix)

        logger.info(f"Found {len(clusters)} clusters")

        return clusters

    def _dbscan_clustering(self, distance_matrix: np.ndarray) -> np.ndarray:
        """DBSCAN clustering.

        Args:
            distance_matrix: Pairwise distance matrix

        Returns:
            Cluster labels for each video
        """
        # eps = maximum distance between two samples in same cluster
        # We use (1 - min_similarity) as the threshold
        eps = 1 - self.min_similarity

        clustering = DBSCAN(
            eps=eps,
            min_samples=2,  # Minimum 2 videos per cluster
            metric="precomputed",
        )

        labels = clustering.fit_predict(distance_matrix)

        return labels

    def _agglomerative_clustering(self, distance_matrix: np.ndarray) -> np.ndarray:
        """Agglomerative (hierarchical) clustering.

        Args:
            distance_matrix: Pairwise distance matrix

        Returns:
            Cluster labels for each video
        """
        # distance_threshold sets the minimum distance for merging
        distance_threshold = 1 - self.min_similarity

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric="precomputed",
            linkage="average",
        )

        labels = clustering.fit_predict(distance_matrix)

        return labels

    def _build_clusters(
        self, file_ids: list[str], labels: np.ndarray, similarity_matrix: np.ndarray
    ) -> list[VideoCluster]:
        """Build VideoCluster objects from labels.

        Args:
            file_ids: List of file IDs
            labels: Cluster labels
            similarity_matrix: Similarity matrix

        Returns:
            List of clusters
        """
        clusters = []

        # Group by cluster label
        unique_labels = set(labels)

        for label in unique_labels:
            # Skip noise cluster (-1 from DBSCAN)
            if label == -1:
                continue

            # Get files in this cluster
            indices = np.where(labels == label)[0]
            cluster_file_ids = [file_ids[i] for i in indices]

            # Calculate average intra-cluster similarity
            if len(indices) > 1:
                cluster_similarities = []
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        sim = similarity_matrix[indices[i]][indices[j]]
                        cluster_similarities.append(sim)
                avg_sim = np.mean(cluster_similarities)
            else:
                avg_sim = 1.0

            cluster = VideoCluster(
                cluster_id=int(label),
                file_ids=cluster_file_ids,
                avg_similarity=float(avg_sim),
                size=len(cluster_file_ids),
            )

            clusters.append(cluster)

        # Sort by cluster size (largest first)
        clusters.sort(key=lambda c: c.size, reverse=True)

        return clusters

    def find_similar_videos(
        self,
        target_file_id: str,
        file_ids: list[str],
        similarity_matrix: np.ndarray,
        min_similarity: Optional[float] = None,
    ) -> list[tuple[str, float]]:
        """Find videos similar to a target video.

        Args:
            target_file_id: File ID to find similar videos for
            file_ids: All file IDs
            similarity_matrix: Similarity matrix
            min_similarity: Minimum similarity (uses self.min_similarity if None)

        Returns:
            List of (file_id, similarity) tuples, sorted by similarity
        """
        if min_similarity is None:
            min_similarity = self.min_similarity

        # Find target index
        try:
            target_idx = file_ids.index(target_file_id)
        except ValueError:
            logger.warning(f"File {target_file_id} not found")
            return []

        # Get similarities to target
        similarities = similarity_matrix[target_idx]

        # Find similar videos
        similar_videos = []
        for i, sim in enumerate(similarities):
            if i != target_idx and sim >= min_similarity:
                similar_videos.append((file_ids[i], float(sim)))

        # Sort by similarity (highest first)
        similar_videos.sort(key=lambda x: x[1], reverse=True)

        return similar_videos
