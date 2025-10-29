import logging

from logging.handlers import RotatingFileHandler

LOGGER_NAME = "lookout_mra_client"


def init_lookout_logger(
    file: str, level: int = logging.DEBUG, maxMegabytes: int = 10, backupCount: int = 5
) -> logging.Logger:
    """
    Initialize and return a logger for lookout_mra_client code

    Args:
        file (str): Log file location
        level (int, optional): Python logging level. Defaults to logging.DEBUG.
        maxMegabytes (int, optional): Log file max size in Megabytes. Defaults to 10.
        backupCount (int, optional): Number of log file backups. Defaults to 5.

    Returns:
        logging.Logger: Logger object
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if len(logger.handlers) == 0:
        formatter = logging.Formatter("%(asctime)s [%(name)s] [%(levelname)s] %(message)s")

        maxBytes = maxMegabytes * 1e6
        file_handler = RotatingFileHandler(file, maxBytes=maxBytes, backupCount=backupCount)
        file_handler.formatter = formatter

        logger.addHandler(file_handler)

    return logger
