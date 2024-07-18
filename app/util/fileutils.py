# importing the zipfile module
import os
from zipfile import ZipFile
from semconstmining.config import Config
from sentence_transformers import SentenceTransformer


def check_data_directories_on_start(conf: Config):
    """
    Check if the data directories are available and create them if not.
    """
    if not os.path.exists(conf.DATA_ROOT):
        os.makedirs(conf.DATA_ROOT)
    if not os.path.exists(conf.DATA_LOGS):
        os.makedirs(conf.DATA_LOGS)
    if not os.path.exists(conf.DATA_INTERIM):
        os.makedirs(conf.DATA_INTERIM)
    if not os.path.exists(conf.DATA_RAW):
        os.makedirs(conf.DATA_RAW)
    if not os.path.exists(conf.DATA_DATASET):
        os.makedirs(conf.DATA_DATASET)

    check files in the logs directory and unzip if necessary
    for file in os.listdir(conf.DATA_LOGS):
        if file.endswith(".zip"):
            with ZipFile(conf.DATA_LOGS / file, 'r') as zip_ref:
                zip_ref.extractall(conf.DATA_LOGS)
            os.remove(conf.DATA_LOGS / file)

    # check the interim directory and unzip files in place if necessary
    for file in os.listdir(conf.DATA_INTERIM):
        if file.endswith(".zip"):
            with ZipFile(conf.DATA_INTERIM / file, 'r') as zip_ref:
                zip_ref.extractall(conf.DATA_INTERIM)
            os.remove(conf.DATA_INTERIM / file)

    # check the model directory and unzip files in place if necessary
    for file in os.listdir(conf.DATA_DATASET):
        if file.endswith(".zip"):
            with ZipFile(conf.DATA_DATASET / file, 'r') as zip_ref:
                zip_ref.extractall(conf.DATA_DATASET)
            os.remove(conf.DATA_DATASET / file)



