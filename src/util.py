import sqlite3
import os
import json
import requests
import numpy as np
from PIL import Image, ImageFilter

MDB_PATH = os.path.expandvars("%userprofile%\\appdata\\locallow\\Cygames\\umamusume\\master\\master.mdb")
META_PATH = os.path.expandvars("%userprofile%\\appdata\\locallow\\Cygames\\umamusume\\meta")

DATA_PATH = os.path.expandvars("%userprofile%\\appdata\\locallow\\Cygames\\umamusume\\dat")

TL_PREFIX = "translations\\"
INTERMEDIATE_PREFIX = "editing\\"

MDB_FOLDER = TL_PREFIX + "mdb\\"
MDB_FOLDER_EDITING = INTERMEDIATE_PREFIX + "mdb\\"

ASSETS_FOLDER = TL_PREFIX + "assets\\"
ASSETS_FOLDER_EDITING = INTERMEDIATE_PREFIX + "assets\\"

ASSEMBLY_FOLDER = TL_PREFIX + "assembly\\"
ASSEMBLY_FOLDER_EDITING = INTERMEDIATE_PREFIX + "assembly\\"

TABLE_BACKUP_PREFIX = "patch_backup_"

class Connection():
    DB_PATH = None

    def __init__(self):
        self.conn = sqlite3.connect(self.DB_PATH)
    def __enter__(self):
        return self.conn, self.conn.cursor()
    def __exit__(self, type, value, traceback):
        self.conn.close()

class MDBConnection(Connection):
    DB_PATH = MDB_PATH

class MetaConnection(Connection):
    DB_PATH = META_PATH


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding='utf-8') as f:
            return json.load(f)
    raise FileNotFoundError(f"Json not found: {path}")

def save_json(path, data):
    with open(path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def download_json(url):
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def xor_bytes(a, b):
    return (np.frombuffer(a, dtype='uint8') ^ np.frombuffer(b, dtype='uint8')).tobytes()

def fix_transparency(file_path, out_path=None):
    os.system(f"transparency-fix.exe {file_path}{f' {out_path}' if out_path else ''}")

def test_for_type(args):
    path, type = args
    data = load_json(path)
    if data.get('type', None) == type:
        return (True, data)
    return (False, None)

def get_asset_and_type(path):
    data = load_json(path)
    return (data.get('type'), data)

def get_asset_path(asset_hash):
    return os.path.join(DATA_PATH, asset_hash[:2], asset_hash)

def strings_numeric_key(item):
    if item.isnumeric():
        return int(item)
    return item


config = load_json("config.json") if os.path.exists("config.json") else load_json("src/config.json")