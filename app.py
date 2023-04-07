# stdlib
import argparse
import subprocess
from argparse import RawTextHelpFormatter
from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel

# project
from panel_extractor import PanelExtractor

app = FastAPI()


# logging_example.py

import logging

# Create a custom logger
logger = logging.getLogger(__name__)

# Create handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler('file.log')
c_handler.setLevel(logging.WARNING)
f_handler.setLevel(logging.ERROR)

# Create formatters and add it to handlers
c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)

panel_extractor = PanelExtractor(just_contours=True, keep_text=True, min_pct_panel=2, max_pct_panel=90)


class Data(BaseModel):
    chapter_url: str


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post("/chapter")
def post_chapter(data: Data):
    logger.info("post_chapter")
    chapter_url = data.chapter_url

    output = subprocess.check_output(['./get_images.sh',str(chapter_url)])
    # print(output)

    # potentially we want the shell script to generate a uuid each time, save the result in a folder named as the uuid
    # and return the uuid as output, and use the autput uuid as input for the method extract
    final = panel_extractor.extract("./images/")

    return {"data": final}