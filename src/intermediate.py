import glob
import os
import json
import util
import hashlib
import shutil
import version
from multiprocessing import Pool
import tqdm
from PIL import Image
import gzip
import numpy as np
import time
import unity
import UnityPy

def write_recursive(cur_path, cur_dict, overwrite=False):
    if "hash" not in cur_dict[list(cur_dict.keys())[0]]:
        for key, value in cur_dict.items():
            write_recursive(os.path.join(cur_path, str(key)), value, overwrite=overwrite)
    else:
        # The current dictionary is a leaf
        os.makedirs(os.path.dirname(cur_path), exist_ok=True)

        write_path = os.path.join(cur_path + ".json")

        if not overwrite:
            # Determine if the file already exists.
            # If it does, keep the original.
            # We keep the hash as well, so we can check if the file has changed later.
            # This script is not meant to overwrite existing translations.
            if os.path.exists(write_path):
                previous_dict = util.load_json(write_path)
            
                for key, value in cur_dict.items():
                    if key not in previous_dict:
                        previous_dict[key] = value
                
                cur_dict = previous_dict
        
        # Sort by key, the key needs to be converted to int first
        cur_dict = dict(sorted(cur_dict.items(), key=lambda x: int(x[0])))

        with open(write_path, "w", encoding="utf-8") as f:
            f.write(util.json.dumps(cur_dict, indent=4, ensure_ascii=False))

def load_table(table, keys):
    with util.MDBConnection() as (_, cursor):
        cursor.execute(
            f"""SELECT {','.join(keys)} FROM {table}"""
        )
        rows = cursor.fetchall()
    
    if not rows:
        raise ValueError(f"No rows found for table {table} with keys {keys}")

    return {tuple(row[:-1]): row[-1] for row in rows}


def mdb_to_intermediate(tmp_path=None):
    print("=== GENERATING EDITABLE FILES ===")

    index = util.load_json("src/index.json")

    os.makedirs(util.MDB_FOLDER_EDITING, exist_ok=True)

    # Search for any json files in the mdb folder and subfolders
    jsons = glob.glob(util.MDB_FOLDER + "/**/*.json", recursive=True)

    cached_translations = {}
    transformed_data = {}

    for path in jsons:
        tl_dict = util.load_json(path)

        rel_path = path[len(util.MDB_FOLDER):]

        path_segments = rel_path[:-5].split(os.sep)

        table_name = path_segments.pop(0)

        if table_name not in cached_translations:
            cached_translations[table_name] = {}

        if table_name not in index:
            raise ValueError(f"Table name {table_name} not found in index.json")

        for key, item_data in tl_dict.items():
            # Add the item to the transformed data
            tmp_dict = cached_translations[table_name]
            for seg in path_segments:
                if seg not in tmp_dict:
                    tmp_dict[seg] = {}
                tmp_dict = tmp_dict[seg]
            
            tmp_dict[key] = item_data
    
    for table, columns in index.items():
        table_data = load_table(table, columns)

        transformed_data[table] = {}

        for source_index, source_text in table_data.items():
            tl_item = {
                "version": version.VERSION,
                "keys": [],
                "source": source_text,
                "text": "",
                "prev_text": "",
                "hash": hashlib.sha256(source_text.encode('utf-8')).hexdigest(),
                "prev_hash": None,
                "new": True,
                "edited": False
            }

            category_id = source_index[0]

            if len(source_index) == 1:
                insert_dict = transformed_data[table]
            else:
                if category_id not in transformed_data[table]:
                    transformed_data[table][category_id] = {}
                insert_dict = transformed_data[table][category_id]

            if tl_item['hash'] in insert_dict:
                insert_dict[tl_item['hash']]['keys'].append(source_index)
                continue

            tl_item['keys'].append(source_index)

            def test_key_recursive(key, check_dict):
                key_str = str(key[0])

                if key_str not in check_dict:
                    return False

                next_key = key[1:]
                next_dict = check_dict[key_str]

                if len(next_key) == 0:
                    return next_dict

                return test_key_recursive(next_key, next_dict)

            old_item = test_key_recursive(source_index, cached_translations[table]) if table in cached_translations else None

            if old_item:
                tl_item['new'] = False

                if tl_item['hash'] != old_item['hash']:
                    tl_item['edited'] = True
                
                tl_item['prev_hash'] = old_item['hash']

                tl_item['text'] = old_item['text']
                tl_item['prev_text'] = old_item['text']

            insert_dict[tl_item['hash']] = tl_item
    
    for table, table_data in transformed_data.items():
        if not isinstance(list(table_data.keys())[0], int):
            write_dir = os.path.join(util.MDB_FOLDER_EDITING)
            category_dict = {table: table_data}
        else:
            write_dir = os.path.join(util.MDB_FOLDER_EDITING, table)
            category_dict = table_data
        os.makedirs(write_dir, exist_ok=True)

        for category_id, category_data in category_dict.items():

            write_path = os.path.join(write_dir, str(category_id) + ".json")

            write_data = []

            for item in category_data.values():
                # Hacky workaround to make the keys not take up a lot of space
                # Don't forget to convert it back to a list when loading the json!
                item['keys'] = json.dumps(item['keys'])
                write_data.append(item)

            write_str = json.dumps(write_data, indent=4, ensure_ascii=False)

            with open(write_path, "w", encoding="utf-8") as f:
                f.write(write_str)
    
    if tmp_path:
        shutil.rmtree(tmp_path)


def add_to_dict(parent_dict, values_list):
    if len(values_list) == 2:
        parent_dict[str(values_list[0])] = values_list[1]
    else:
        if values_list[0] not in parent_dict:
            parent_dict[values_list[0]] = {}
        add_to_dict(parent_dict[values_list[0]], values_list[1:])

def mdb_from_intermediate():
    print("=== CREATING TL FILES FOR MDB ===")

    index = util.load_json("src/index.json")

    os.makedirs(util.MDB_FOLDER, exist_ok=True)

    # Search for any json files in the mdb folder and subfolders
    jsons = glob.glob(util.MDB_FOLDER_EDITING + "/**/*.json", recursive=True)

    transformed_data = {}

    for path in jsons:
        tl_dict = util.load_json(path)

        rel_path = path[len(util.MDB_FOLDER_EDITING):]

        path_segments = rel_path[:-5].split(os.sep)

        table_name = path_segments.pop(0)

        if table_name not in index:
            raise ValueError(f"Table name {table_name} not found in index.json")

        for item_data in tl_dict:
            if not item_data['text']:
                continue

            if table_name not in transformed_data:
                transformed_data[table_name] = {}

            keys = json.loads(item_data['keys'])
            text = item_data['text']
            hash = item_data['hash']
            tl_item = {
                "text": text,
                "hash": hash
            }
            for key_list in keys:
                add_to_dict(transformed_data[table_name], key_list + [tl_item])
    
    for table, data in transformed_data.items():
        if not data:
            continue
        write_recursive(os.path.join(util.MDB_FOLDER, table), data, overwrite=True)
    
    print("Done")


def process_asset(path):
    interm_data = util.load_json(path)
    new_chapter_data = {
        "row_index": interm_data['row_index'],
        "file_name": interm_data['file_name'],
        "hash": interm_data['hash'],
        "data": []
    }
    empty_count = 0
    for item in interm_data['data']:
        if interm_data['file_name'].startswith("race/"):
            if not item['text']:
                empty_count += 1
            new_chapter_data['data'].append(item['text'])
            continue

        if not item['text'] and not item['name']:
            empty_count += 1

        new_item = {
            "text": item['text'],
            "name": item['name'],
        }
        if 'clip_length' in item:
            new_item['clip_length'] = item['clip_length']
        if 'choices' in item:
            new_item['choices'] = item['choices']
        if 'anim_data' in item:
            new_item['anim_data'] = item['anim_data']
        if 'color_info' in item:
            new_item['color_info'] = item['color_info']
        new_chapter_data['data'].append(new_item)
    
    base_path = path[len(util.ASSETS_FOLDER_EDITING):]
    write_path = os.path.join(util.ASSETS_FOLDER, base_path)

    if empty_count == len(interm_data['data']):
        # Skip empty files
        return

    os.makedirs(os.path.dirname(write_path), exist_ok=True)
    with open(write_path, "w", encoding="utf-8") as f:
        f.write(util.json.dumps(new_chapter_data, indent=4, ensure_ascii=False))

def convert_stories():
    print("=== STORIES ===")

    asset_jsons = []
    asset_jsons += glob.glob(util.ASSETS_FOLDER_EDITING + "story/**/*.json", recursive=True)
    asset_jsons += glob.glob(util.ASSETS_FOLDER_EDITING + "home/**/*.json", recursive=True)
    asset_jsons += glob.glob(util.ASSETS_FOLDER_EDITING + "race/**/*.json", recursive=True)

    with Pool() as pool:
        _ = list(tqdm.tqdm(pool.imap_unordered(process_asset, asset_jsons, chunksize=128), total=len(asset_jsons)))


def convert_lyrics():
    print("=== LYRICS ===")

    lyric_jsons = glob.glob(util.ASSETS_FOLDER_EDITING + "lyrics/**/*.json", recursive=True)

    for path in lyric_jsons:
        base_path = path[len(util.ASSETS_FOLDER_EDITING):]
        write_path = os.path.join(util.ASSETS_FOLDER, base_path)

        data = util.load_json(path)

        new_data = {
            "row_index": data['row_index'],
            "file_name": data['file_name'],
            "hash": data['hash'],
            "data": []
        }

        empty_count = 0
        for item in data['data']:

            if not item['text']:
                empty_count += 1

            new_item = {
                "text": item['text'],
                "hash": item['hash']
            }

            new_data['data'].append(new_item)
        
        if empty_count == len(data['data']):
            # Skip empty files
            continue
        
        os.makedirs(os.path.dirname(write_path), exist_ok=True)
        with open(write_path, "w", encoding="utf-8") as f:
            f.write(util.json.dumps(new_data, indent=4, ensure_ascii=False))


def test_atlas():
    edited_path = r"editing\assets\atlas\single\single_tex.png"
    preprocess_path = r"editing\assets\atlas\single\single_tex.preprocess.png"
    source_path = r"editing\assets\atlas\single\single_tex.org.png"

    diff_path = r"editing\assets\atlas\single\single_tex.diff"
    new_path = r"editing\assets\atlas\single\single_tex.new.png"


    # Pre-processing
    util.fix_transparency(edited_path, preprocess_path)

    with open(preprocess_path, "rb") as f:
        edited_bytes = f.read()

    with open(source_path, "rb") as f:
        source_bytes = f.read()
    
    max_len = max(len(edited_bytes), len(source_bytes))

    edited_bytes += np.random.bytes(max_len - len(edited_bytes))
    source_bytes = source_bytes.ljust(max_len, b'\x00')

    diff = util.xor_bytes(edited_bytes, source_bytes)

    with open(diff_path, "wb") as f:
        f.write(diff)


    # =============================================================


    with open(diff_path, "rb") as f:
        diff_bytes = f.read()

    with open(source_path, "rb") as f:
        source_bytes = f.read()
    
    max_len = max(len(edited_bytes), len(source_bytes))
    
    diff_bytes = diff_bytes.ljust(max_len, b'\x00')
    source_bytes = source_bytes.ljust(max_len, b'\x00')

    new_bytes = util.xor_bytes(diff_bytes, source_bytes)

    with open(new_path, "wb") as f:
        f.write(new_bytes)
    

    # Replace the asset
    json_path = r"editing\assets\atlas\single\single_tex.json"
    json_data = util.load_json(json_path)

    file_hash = json_data['hash']

    file_path = os.path.join(util.DATA_PATH, file_hash[:2], file_hash)

    print(file_path)

    shutil.copy(file_path, f"{file_path}_{round(time.time())}")

    asset_bundle = UnityPy.load(file_path)

    with Image.open(new_path) as img:
        for asset in asset_bundle.objects:
            data = asset.read()
            # if data.m_Name == "utx_btn_healthroom_main_00":
            #     tree = asset.read_typetree()
            #     tree['m_Rect']['x'] = 100
            #     tree['m_Rect']['y'] = 100
            #     asset.save_typetree(tree)


            if asset.type.name == "Texture2D":
                data.image = img.convert("RGBA")
                data.save()
                break

        with open(file_path, "wb") as f:
            f.write(asset_bundle.file.save())


def assets_from_intermediate():
    print("=== CREATING TL FILES FOR ASSET TEXT ===")

    convert_lyrics()
    convert_stories()
    # convert_atlas()

    print("Done")

def main():
    test_atlas()

if __name__ == "__main__":
    main()