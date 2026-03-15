from __future__ import annotations

import logging


def configure_logging(verbosity: int) -> None:
    """Configure root logging from the CLI verbosity flag.

    Args:
        verbosity: Count of `-v` flags supplied on the command line.

    Returns:
        None.
    """
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
