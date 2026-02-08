"""Feature extraction for video frames using multiple modalities."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import cv2
import mediapipe as mp
import numpy as np
import torch
from insightface.app import FaceAnalysis
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from ..common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FrameFeatures:
    """Combined features extracted from a single frame."""

    face_embeddings: list[np.ndarray]  # Multiple faces possible
    face_boxes: list[tuple[int, int, int, int]]  # Bounding boxes for faces
    body_embedding: Optional[np.ndarray]  # Full body appearance
    pose_keypoints: Optional[np.ndarray]  # MediaPipe pose landmarks
    scene_embedding: Optional[np.ndarray]  # CLIP scene embedding
    frame_index: int


class FeatureExtractor(ABC):
    """Base class for feature extractors."""

    @abstractmethod
    def extract(self, frame: np.ndarray) -> Any:
        """Extract features from a frame."""
        pass


class FaceFeatureExtractor(FeatureExtractor):
    """Extract face embeddings using InsightFace."""

    def __init__(self, device: str = "cpu") -> None:
        """Initialize face extractor.

        Args:
            device: Device to run inference on ('cpu' or 'cuda')
        """
        logger.info("Initializing InsightFace...")
        self.app = FaceAnalysis(providers=["CPUExecutionProvider"])
        self.app.prepare(ctx_id=0 if device == "cpu" else -1, det_size=(640, 640))
        logger.info("InsightFace ready")

    def extract(self, frame: np.ndarray) -> tuple[list[np.ndarray], list[tuple]]:
        """Extract face embeddings from frame.

        Args:
            frame: Frame as numpy array (RGB)

        Returns:
            Tuple of (embeddings, bounding_boxes)
        """
        faces = self.app.get(frame)

        embeddings = []
        boxes = []

        for face in faces:
            embeddings.append(face.embedding)
            bbox = face.bbox.astype(int)
            boxes.append(tuple(bbox))

        return embeddings, boxes


class BodyFeatureExtractor(FeatureExtractor):
    """Extract full-body appearance features using CLIP."""

    def __init__(self, device: Optional[str] = None) -> None:
        """Initialize body feature extractor.

        Args:
            device: Device to run on (auto-detect if None)
        """
        if device is None:
            # Auto-detect best device
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"  # Apple Silicon
            else:
                device = "cpu"

        self.device = device
        logger.info(f"Initializing CLIP for body features on {device}...")

        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        self.model.to(device)
        self.model.eval()

        logger.info("CLIP ready for body features")

    def extract(self, frame: np.ndarray) -> np.ndarray:
        """Extract body appearance embedding.

        Args:
            frame: Frame as numpy array (RGB)

        Returns:
            Body embedding vector
        """
        # Convert to PIL Image
        image = Image.fromarray(frame)

        # Process and extract visual features
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)

        # Return as numpy array
        embedding = image_features.cpu().numpy().flatten()
        return embedding


class PoseFeatureExtractor(FeatureExtractor):
    """Extract body pose keypoints using MediaPipe."""

    def __init__(self) -> None:
        """Initialize pose extractor."""
        logger.info("Initializing MediaPipe Pose...")
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            enable_segmentation=False,
            min_detection_confidence=0.5,
        )
        logger.info("MediaPipe Pose ready")

    def extract(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Extract pose keypoints from frame.

        Args:
            frame: Frame as numpy array (RGB)

        Returns:
            Pose keypoints as flattened array, or None if no pose detected
        """
        results = self.pose.process(frame)

        if results.pose_landmarks:
            # Extract landmarks as array
            landmarks = []
            for landmark in results.pose_landmarks.landmark:
                landmarks.extend([landmark.x, landmark.y, landmark.z, landmark.visibility])

            return np.array(landmarks, dtype=np.float32)

        return None

    def __del__(self) -> None:
        """Clean up MediaPipe resources."""
        if hasattr(self, "pose"):
            self.pose.close()


class SceneFeatureExtractor(FeatureExtractor):
    """Extract scene/context features using CLIP."""

    def __init__(self, device: Optional[str] = None) -> None:
        """Initialize scene feature extractor.

        Args:
            device: Device to run on (auto-detect if None)
        """
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        self.device = device
        logger.info(f"Initializing CLIP for scene features on {device}...")

        self.model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
        self.model.to(device)
        self.model.eval()

        logger.info("CLIP ready for scene features")

    def extract(self, frame: np.ndarray) -> np.ndarray:
        """Extract scene embedding.

        Args:
            frame: Frame as numpy array (RGB)

        Returns:
            Scene embedding vector
        """
        image = Image.fromarray(frame)

        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)

        embedding = image_features.cpu().numpy().flatten()
        return embedding


class MultiModalExtractor:
    """Combine multiple feature extractors."""

    def __init__(
        self,
        extract_faces: bool = True,
        extract_body: bool = True,
        extract_pose: bool = True,
        extract_scene: bool = True,
        device: Optional[str] = None,
    ) -> None:
        """Initialize multi-modal extractor.

        Args:
            extract_faces: Enable face extraction
            extract_body: Enable body extraction
            extract_pose: Enable pose extraction
            extract_scene: Enable scene extraction
            device: Device for GPU models
        """
        self.face_extractor = FaceFeatureExtractor(device or "cpu") if extract_faces else None
        self.body_extractor = BodyFeatureExtractor(device) if extract_body else None
        self.pose_extractor = PoseFeatureExtractor() if extract_pose else None
        self.scene_extractor = SceneFeatureExtractor(device) if extract_scene else None

        logger.info(
            f"Multi-modal extractor initialized "
            f"(face={extract_faces}, body={extract_body}, "
            f"pose={extract_pose}, scene={extract_scene})"
        )

    def extract_all(self, frame: np.ndarray, frame_index: int = 0) -> FrameFeatures:
        """Extract all features from a frame.

        Args:
            frame: Frame as numpy array (RGB)
            frame_index: Index of frame in video

        Returns:
            Combined features
        """
        face_embeddings = []
        face_boxes = []
        if self.face_extractor:
            face_embeddings, face_boxes = self.face_extractor.extract(frame)

        body_embedding = None
        if self.body_extractor:
            body_embedding = self.body_extractor.extract(frame)

        pose_keypoints = None
        if self.pose_extractor:
            pose_keypoints = self.pose_extractor.extract(frame)

        scene_embedding = None
        if self.scene_extractor:
            scene_embedding = self.scene_extractor.extract(frame)

        return FrameFeatures(
            face_embeddings=face_embeddings,
            face_boxes=face_boxes,
            body_embedding=body_embedding,
            pose_keypoints=pose_keypoints,
            scene_embedding=scene_embedding,
            frame_index=frame_index,
        )
