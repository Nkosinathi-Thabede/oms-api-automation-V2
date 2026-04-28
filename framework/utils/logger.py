"""
Logger — Centralised Logging Configuration
===========================================
Sets up logging for the entire test session.
Writes to both the terminal and a log file in reports/
so there is a persistent record of each test run.
"""

import logging
import os


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger for the test session.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR)
    """
    # Ensure the reports directory exists before writing to it
    os.makedirs("reports", exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(),                                    # Terminal output
            logging.FileHandler("reports/test_run.log", mode="w")      # File output
        ]
    )
