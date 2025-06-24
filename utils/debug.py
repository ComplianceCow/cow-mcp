import os
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE_PATH ="/app.log"
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024


current_file_path = __file__
current_directory = os.path.dirname(os.path.abspath(current_file_path))

file_handler = RotatingFileHandler(
    current_directory+LOG_FILE_PATH,
    maxBytes=MAX_LOG_FILE_SIZE,
    backupCount=1
)

logger = logging.getLogger("my_app")
logger.setLevel(logging.DEBUG)

logger.addHandler(file_handler)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
