import os
import logging

logger = logging.getLogger("my_app")
logger.setLevel(logging.DEBUG)

current_file_path = __file__
current_directory = os.path.dirname(os.path.abspath(current_file_path))

file_handler = logging.FileHandler(current_directory+"/app.log")
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)