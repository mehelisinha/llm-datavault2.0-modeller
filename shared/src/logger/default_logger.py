import logging

from shared.src.logger.logger_manager import EDHLogger

# Set up the logger only once
dbfs_logger = EDHLogger(log_level=logging.DEBUG, logger_source="stdout")
default_logger = dbfs_logger.get_logger()
