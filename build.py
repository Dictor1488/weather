# -*- coding: utf-8 -*-
"""
build.py — збирає .wotmod з сирців.

WoT завантажує як .pyc так і .py файли, тому Python 2.7 не потрібен.
Просто пакуємо .py напряму — ZIP_STORED (без компресії, обов'язково для WoT).

Запуск:
    python3 build.py                  # бере версію з meta.xml
    python3 build.py --version 0.1.2  # форсує версію
"""

from __future__ import print_function
import argparse
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile


ROOT         = os.path.dirname(os.path.abspath(__file__))
PY_SRC       = os.path.join(ROOT, "python")
RES_TEMPLATE = os.path.join(ROOT, "resources", "in", "mods")
DIST         = os.path.join(ROOT, "dist")
MOD_ID_DIR   = "com.example.weather"


def log(msg):
    print("[build] {}".format(msg))


def get_version_from_meta():
    meta_path = os.path.join(RES_TEMPLATE, MOD_ID_DIR, "meta.xml")
    tree = ET.parse(meta_path)
    return tree.getroot().findtext("version", "0.0.1")


def patch_meta_version(staging_dir, version):
    meta_path = os.path.join(staging_dir, "meta.xml")
    tree = ET.parse(meta_path)
    tree.getroot().find("version").text = version
    tree.write(meta_path, encoding="UTF-8", xml_declaration=True)


def copy_python_files(src_dir, dst_dir):
    """Копіює .py файли — WoT підтримує як .py так і .pyc."""
    count = 0
    for dirpath, _, filenames in os.walk(src_dir):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            src_file = os.path.join(dirpath, fn)
            rel = os.path.relpath(src_file, src_dir)
            dst_file = os.path.join(dst_dir, rel)

            if not os.path.exists(os.path.dirname(dst_file)):
                os.makedirs(os.path.dirname(dst_file))
            shutil.copyfile(src_file, dst_file)
            count += 1
    log("Copied {} .py files".format(count))


def build_wotmod(staging_dir, version):
    """
    .wotmod = zip без компресії (ZIP_STORED) такої структури:
        meta.xml
        res/
            scripts/client/gui/mods/mod_*.py
            mods/<author>.<mod>/
    """
    if not os.path.exists(DIST):
        os.makedirs(DIST)

    out_name = "{}_{}.wotmod".format(MOD_ID_DIR, version)
    out_path = os.path.join(DIST, out_name)

    log("Packing .wotmod -> {}".format(out_path))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as zf:
        for dirpath, _, filenames in os.walk(staging_dir):
            for fn in filenames:
                abs_path = os.path.join(dirpath, fn)
                rel_path = os.path.relpath(abs_path, staging_dir)
                zf.write(abs_path, rel_path.replace(os.sep, "/"))

    log("DONE. File size: {} bytes".format(os.path.getsize(out_path)))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="override version from meta.xml")
    args = ap.parse_args()

    version = args.version or get_version_from_meta()
    if version.startswith("v"):
        version = version[1:]
    log("Building version: {}".format(version))

    staging = tempfile.mkdtemp(prefix="wotmod_build_")
    log("Staging dir: {}".format(staging))

    try:
        # 1. Ресурси
        shutil.copytree(os.path.join(RES_TEMPLATE, MOD_ID_DIR),
                        os.path.join(staging, "res", "mods", MOD_ID_DIR))
        # meta.xml — у корінь архіву
        shutil.move(os.path.join(staging, "res", "mods", MOD_ID_DIR, "meta.xml"),
                    os.path.join(staging, "meta.xml"))
        patch_meta_version(staging, version)

        # 2. Python → копіюємо .py (без компіляції)
        py_out_dir = os.path.join(staging, "res", "scripts", "client", "gui", "mods")
        copy_python_files(
            os.path.join(PY_SRC, "gui", "mods"),
            py_out_dir,
        )

        # 3. Zip → .wotmod
        out = build_wotmod(staging, version)
        log("SUCCESS: {}".format(out))

    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
