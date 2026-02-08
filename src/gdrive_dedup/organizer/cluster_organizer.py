"""Smart organization of video clusters with minimal disruption."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..auth.service import DriveServiceFactory
from ..common.logging import get_logger
from ..common.rate_limiter import TokenBucketRateLimiter
from ..common.retry import exponential_backoff
from ..clustering.clusterer import VideoCluster

logger = get_logger(__name__)


@dataclass
class OrganizationPlan:
    """Plan for organizing a cluster."""

    cluster_id: int
    primary_folder: str  # Folder with most files
    cluster_folder_name: str  # Name of new cluster subfolder
    cluster_folder_id: Optional[str]  # Drive folder ID once created
    files_to_keep_in_place: list[str]  # File IDs already in primary folder
    files_to_duplicate: list[str]  # File IDs to copy from other folders
    total_files: int
    space_used_mb: float  # Estimated space for duplicates


class ClusterOrganizer:
    """Organize video clusters with smart folder selection."""

    def __init__(
        self,
        service_factory: DriveServiceFactory,
        rate_limiter: TokenBucketRateLimiter,
        file_metadata: dict[str, dict],  # file_id -> {name, path, size, etc}
    ) -> None:
        """Initialize cluster organizer.

        Args:
            service_factory: Factory for Drive API service
            rate_limiter: Rate limiter
            file_metadata: Metadata for all files
        """
        self.service_factory = service_factory
        self.rate_limiter = rate_limiter
        self.file_metadata = file_metadata

    def create_organization_plan(
        self, cluster: VideoCluster, cluster_name: Optional[str] = None
    ) -> OrganizationPlan:
        """Create organization plan for a cluster.

        Args:
            cluster: Video cluster
            cluster_name: Optional custom cluster name

        Returns:
            Organization plan
        """
        # Count files per folder
        folder_counts = Counter()
        file_to_folder = {}

        for file_id in cluster.file_ids:
            metadata = self.file_metadata.get(file_id)
            if not metadata:
                logger.warning(f"No metadata for {file_id}")
                continue

            folder = self._get_parent_folder(metadata["path"])
            folder_counts[folder] += 1
            file_to_folder[file_id] = folder

        # Find primary folder (most files)
        if not folder_counts:
            raise ValueError(f"No valid folders found for cluster {cluster.cluster_id}")

        primary_folder = folder_counts.most_common(1)[0][0]

        # Generate cluster folder name
        if cluster_name is None:
            cluster_name = f"Cluster_{cluster.cluster_id:03d}"

        # Separate files by location
        files_in_primary = []
        files_to_duplicate = []

        for file_id in cluster.file_ids:
            folder = file_to_folder.get(file_id)
            if folder == primary_folder:
                files_in_primary.append(file_id)
            else:
                files_to_duplicate.append(file_id)

        # Calculate space usage
        duplicate_size = sum(
            self.file_metadata[fid]["size"] for fid in files_to_duplicate if fid in self.file_metadata
        )
        space_used_mb = duplicate_size / (1024 * 1024)

        plan = OrganizationPlan(
            cluster_id=cluster.cluster_id,
            primary_folder=primary_folder,
            cluster_folder_name=cluster_name,
            cluster_folder_id=None,  # Will be set when created
            files_to_keep_in_place=files_in_primary,
            files_to_duplicate=files_to_duplicate,
            total_files=len(cluster.file_ids),
            space_used_mb=space_used_mb,
        )

        logger.info(
            f"Plan for cluster {cluster.cluster_id}: "
            f"{len(files_in_primary)} in place, "
            f"{len(files_to_duplicate)} to duplicate "
            f"(+{space_used_mb:.1f} MB)"
        )

        return plan

    def execute_plan(self, plan: OrganizationPlan, dry_run: bool = False) -> dict:
        """Execute organization plan.

        Args:
            plan: Organization plan
            dry_run: If True, don't actually create folders or copy files

        Returns:
            Result dict with statistics
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would organize cluster {plan.cluster_id}")
            return {
                "cluster_id": plan.cluster_id,
                "dry_run": True,
                "files_kept": len(plan.files_to_keep_in_place),
                "files_duplicated": 0,
                "space_used_mb": 0,
            }

        # Find or create cluster folder
        primary_folder_id = self._get_folder_id(plan.primary_folder)
        cluster_folder_id = self._create_cluster_folder(
            plan.cluster_folder_name, primary_folder_id
        )

        plan.cluster_folder_id = cluster_folder_id

        # Copy files from primary folder (symlink/shortcut)
        for file_id in plan.files_to_keep_in_place:
            self._create_shortcut(file_id, cluster_folder_id)

        # Duplicate files from other folders
        duplicated_count = 0
        for file_id in plan.files_to_duplicate:
            success = self._copy_file(file_id, cluster_folder_id)
            if success:
                duplicated_count += 1

        result = {
            "cluster_id": plan.cluster_id,
            "cluster_folder_id": cluster_folder_id,
            "files_kept": len(plan.files_to_keep_in_place),
            "files_duplicated": duplicated_count,
            "space_used_mb": plan.space_used_mb,
        }

        logger.info(
            f"Organized cluster {plan.cluster_id}: "
            f"{result['files_kept']} kept, {result['files_duplicated']} duplicated"
        )

        return result

    def _get_parent_folder(self, file_path: str) -> str:
        """Extract parent folder from file path.

        Args:
            file_path: Full file path

        Returns:
            Parent folder path
        """
        if "/" not in file_path:
            return "/"
        return file_path.rsplit("/", 1)[0]

    @exponential_backoff()
    def _get_folder_id(self, folder_path: str) -> str:
        """Get Google Drive folder ID from path.

        Args:
            folder_path: Folder path

        Returns:
            Folder ID
        """
        if folder_path == "/":
            return "root"

        # Search for folder by path
        # This is simplified - in production, you'd walk the path
        service = self.service_factory.create_service()
        self.rate_limiter.acquire()

        folder_name = folder_path.split("/")[-1]
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"

        response = service.files().list(q=query, fields="files(id, name)").execute()
        files = response.get("files", [])

        if files:
            return files[0]["id"]
        else:
            # Folder not found, return root
            logger.warning(f"Folder {folder_path} not found, using root")
            return "root"

    @exponential_backoff()
    def _create_cluster_folder(self, folder_name: str, parent_id: str) -> str:
        """Create cluster folder in Google Drive.

        Args:
            folder_name: Name of cluster folder
            parent_id: Parent folder ID

        Returns:
            Created folder ID
        """
        service = self.service_factory.create_service()
        self.rate_limiter.acquire()

        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }

        folder = service.files().create(body=file_metadata, fields="id").execute()
        folder_id = folder.get("id")

        logger.info(f"Created cluster folder: {folder_name} ({folder_id})")

        return folder_id

    @exponential_backoff()
    def _create_shortcut(self, file_id: str, target_folder_id: str) -> bool:
        """Create a shortcut to file in target folder.

        Args:
            file_id: File to create shortcut for
            target_folder_id: Folder to create shortcut in

        Returns:
            True if successful
        """
        service = self.service_factory.create_service()
        self.rate_limiter.acquire()

        # Get file metadata
        file_metadata = service.files().get(fileId=file_id, fields="name").execute()
        file_name = file_metadata.get("name")

        # Create shortcut
        shortcut_metadata = {
            "name": file_name,
            "mimeType": "application/vnd.google-apps.shortcut",
            "shortcutDetails": {"targetId": file_id},
            "parents": [target_folder_id],
        }

        service.files().create(body=shortcut_metadata, fields="id").execute()

        logger.debug(f"Created shortcut for {file_name}")
        return True

    @exponential_backoff()
    def _copy_file(self, file_id: str, target_folder_id: str) -> bool:
        """Copy file to target folder.

        Args:
            file_id: File to copy
            target_folder_id: Destination folder

        Returns:
            True if successful
        """
        service = self.service_factory.create_service()
        self.rate_limiter.acquire()

        # Get file metadata
        file_metadata = service.files().get(fileId=file_id, fields="name").execute()
        file_name = file_metadata.get("name")

        # Copy file
        copied_file = {"name": file_name, "parents": [target_folder_id]}

        service.files().copy(fileId=file_id, body=copied_file, fields="id").execute()

        logger.debug(f"Copied {file_name} to cluster folder")
        return True
