"""Batch API request helper."""

from typing import Any, Callable

from ..common.logging import get_logger

logger = get_logger(__name__)


class BatchProcessor:
    """Helper for processing items in batches."""

    def __init__(self, batch_size: int = 100) -> None:
        """Initialize batch processor.

        Args:
            batch_size: Number of items per batch
        """
        self.batch_size = batch_size

    def process_batches(
        self,
        items: list[Any],
        processor: Callable[[list[Any]], dict[Any, bool]],
    ) -> dict[Any, bool]:
        """Process items in batches.

        Args:
            items: Items to process
            processor: Function that processes a batch and returns results

        Returns:
            Combined results dictionary
        """
        all_results = {}

        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            logger.debug(f"Processing batch {i // self.batch_size + 1}")
            results = processor(batch)
            all_results.update(results)

        return all_results
