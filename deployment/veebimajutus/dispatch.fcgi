#!/usr/bin/env python3.9

import os
import sys

DOMAIN = "tammets.ee"
APP_NAME = "tammets"
PYTHON_VERSION = "python3.9"
PREFIX = f"/www/apache/domains/www.{DOMAIN}"
PROJECT_DIR = os.path.join(PREFIX, APP_NAME)
SITE_PACKAGES = os.path.join(PREFIX, f".virtualenvs/website/lib/{PYTHON_VERSION}/site-packages")

sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, SITE_PACKAGES)
os.chdir(PROJECT_DIR)

from flup.server.fcgi import WSGIServer
from app import application


WSGIServer(application).run()
