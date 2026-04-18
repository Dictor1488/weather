# -*- coding: utf-8 -*-
"""
build.py — збирає .wotmod з сирців.

v2: без AS3 (використовуємо modsSettingsApi від izeberg, який сам малює UI).
Треба тільки скомпілювати Python у .pyc і спакувати в zip.

Запуск:
    python2 build.py                   # збирає версію з meta.xml
    python2 build.py --version 0.1.2   # форсує версію (для CI на тегах)
    python2 build.py --skip-pyc        # покласти .py замість .pyc (для тестів)
"""

from __future__ import print_function
import argparse
import os
import py_compile
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


def compile_python(src_dir, dst_dir, as_pyc=True):
    """Рекурсивно кладе .py або .pyc у dst_dir зі збереженням структури."""
    if as_pyc and sys.version_info[0] != 2:
        log("WARNING: running on Python {}.{} — WoT needs .pyc from Python 2.7!"
            .format(sys.version_info[0], sys.version_info[1]))
        log("         Скомпільовані .pyc, найімовірніше, не завантажаться у грі.")

    count = 0
    for dirpath, _, filenames in os.walk(src_dir):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            src_file = os.path.join(dirpath, fn)
            rel = os.path.relpath(src_file, src_dir)
            if as_pyc:
                dst_file = os.path.join(dst_dir, rel + "c")
            else:
                dst_file = os.path.join(dst_dir, rel)

            dst_parent = os.path.dirname(dst_file)
            if not os.path.exists(dst_parent):
                os.makedirs(dst_parent)

            if as_pyc:
                py_compile.compile(src_file, dst_file, doraise=True)
            else:
                shutil.copyfile(src_file, dst_file)
            count += 1
    log("Processed {} Python files ({})".format(count, "pyc" if as_pyc else "py"))


def build_wotmod(staging_dir, version):
    """
    .wotmod = zip такої структури:
        meta.xml                        <- у корені
        res/
            scripts/client/gui/mods/    <- наш Python
            mods/<author>.<mod>/        <- наші ресурси (конфіги)
    """
    if not os.path.exists(DIST):
        os.makedirs(DIST)

    out_name = "{}_{}.wotmod".format(MOD_ID_DIR, version)
    out_path = os.path.join(DIST, out_name)

    log("Packing .wotmod -> {}".format(out_path))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
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
    ap.add_argument("--skip-pyc", action="store_true",
                    help="ship .py instead of .pyc (for local testing)")
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
        shutil.move(os.path.join(staging, "res", "mods", MOD_ID_DIR, "meta.xml"),
                    os.path.join(staging, "meta.xml"))
        patch_meta_version(staging, version)

        # 2. Python → .pyc
        pyc_out_dir = os.path.join(staging, "res", "scripts", "client", "gui", "mods")
        compile_python(
            os.path.join(PY_SRC, "gui", "mods"),
            pyc_out_dir,
            as_pyc=not args.skip_pyc,
        )

        # 3. Zip → .wotmod
        out = build_wotmod(staging, version)
        log("SUCCESS: {}".format(out))

    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
