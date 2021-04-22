import logging

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)
fileHandle = logging.FileHandler("out.log")
logger.addHandler(fileHandle)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fileHandle.setFormatter(formatter)
