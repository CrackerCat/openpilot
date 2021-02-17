#!/usr/bin/env python3
from panda.python import serial
from panda import Panda, PandaDFU, build_st
import unittest
import time
import os
import requests
import zipfile
from io import BytesIO
import subprocess

from panda import BASEDIR as PANDA_BASEDIR

SIGNED_FW_FN = os.path.join(os.path.abspath(PANDA_BASEDIR), "board", "obj", "panda.bin.signed")
SIGNED_FIRMWARE_URL = "https://github.com/commaai/openpilot/blob/release2/panda/board/obj/panda.bin.signed?raw=true"


def build_dev_fw():
  fn = "obj/panda.bin"
  build_st(fn, clean=False)
  return os.path.abspath(os.path.join(PANDA_BASEDIR, "board", fn))


def get_expected_signature(fn):
  try:
    return Panda.get_signature_from_firmware(fn)
  except Exception:
    return b""


def download_file(url):
  r = requests.get(url, allow_redirects=True)
  return r.content


class TestPandaFlashing(unittest.TestCase):
  def wait_for(self, cls, serial):
    for _ in range(10):
      pandas = cls.list()
      if serial in pandas:
        return

      time.sleep(0.5)
    self.assertTrue(False)

  def ensure_dfu(self):
    """Ensures the connected panda is running in DFU mode"""
    dfu_list = PandaDFU.list()
    if self.dfu_serial in dfu_list:
      return

    # Move to DFU mode
    panda = Panda(self.serial)
    panda.reset(enter_bootstub=True)
    panda.reset(enter_bootloader=True)
    panda.close()

    self.wait_for(PandaDFU, self.dfu_serial)

  def check_panda_running(self, expected_signature=None):
    self.wait_for(Panda, self.serial)

    panda = Panda(self.serial)
    self.assertFalse(panda.bootstub)

    # TODO: check signature
    # self.assertNotEqual(panda.get_signature(), comma_sig)
    panda.close()

  def flash_release_bootloader_and_fw(self):
    self.ensure_dfu()

    fp = BytesIO(download_file("https://github.com/commaai/panda-artifacts/blob/master/panda-v1.7.3-DEV-d034f3e9-RELEASE.zip?raw=true"))

    with zipfile.ZipFile(fp) as zip_file:
      bootstub_code = zip_file.open('bootstub.panda.bin').read()
      PandaDFU(self.dfu_serial).program_bootstub(bootstub_code)

      self.wait_for(Panda, self.serial)

      firmware_code = zip_file.open('panda.bin').read()
      panda = Panda(self.serial)
      panda.flash(code=firmware_code)
      panda.close()

  def run_flasher(self):
    subprocess.check_call("./flash_panda")

  def claim_panda(self):
    # TODO: handle starting test with a panda in DFU mode

    panda_list = Panda.list()
    self.assertTrue(len(panda_list) > 0)

    self.serial = panda_list[0]
    self.dfu_serial = PandaDFU.st_serial_to_dfu_serial(self.serial)
    print("Got panda", self.serial, self.dfu_serial)

  def setUp(self):
    if not hasattr(self, 'serial'):
      self.claim_panda()

    try:
      os.unlink(SIGNED_FW_FN)
    except FileNotFoundError:
      pass

    self.flash_release_bootloader_and_fw()
    self.wait_for(Panda, self.serial)

  def test_flash_from_dfu(self):
    self.ensure_dfu()

    self.run_flasher()
    self.check_panda_running()

  def test_dev_firmware(self):
    self.run_flasher()

    # TODO: check for development signature
    self.check_panda_running()

  def test_signed_firmware(self):
    with open(SIGNED_FW_FN, 'wb') as f:
      f.write(download_file(SIGNED_FIRMWARE_URL))

    try:
      os.system("./flash_panda")
    finally:
      os.unlink(SIGNED_FW_FN)

    # TODO: check for signed signature
    self.check_panda_running()


if __name__ == '__main__':
    unittest.main()
