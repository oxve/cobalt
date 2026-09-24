#!/usr/bin/env python3
# Copyright 2026 The Cobalt Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for synthesize_internal_test_failure.py."""

import pathlib
import tempfile
import unittest
import xml.etree.ElementTree as ET

from synthesize_internal_test_failure import synthesize_failure_xml


class TestSynthesizeInternalTestFailure(unittest.TestCase):

  def setUp(self):
    self.temp_dir = tempfile.TemporaryDirectory()
    self.dir_path = pathlib.Path(self.temp_dir.name)

  def tearDown(self):
    self.temp_dir.cleanup()

  def test_synthesize_with_log(self):
    log_file = self.dir_path / "test.log"
    log_file.write_text("line 1\nline 2\n[FATAL:cobalt.cc] Crash!\n", encoding="utf-8")

    xml_file = self.dir_path / "target_testoutput.xml"
    synthesize_failure_xml("my_internal_target", log_file, xml_file)

    self.assertTrue(xml_file.is_file())
    self.assertTrue(xml_file.with_suffix(".crash").is_file())

    tree = ET.parse(xml_file)
    root = tree.getroot()
    self.assertEqual(root.attrib["errors"], "1")
    error_el = root.find(".//error")
    self.assertIsNotNone(error_el)
    self.assertIn("Crash!", error_el.text)

  def test_synthesize_without_log(self):
    xml_file = self.dir_path / "target_testoutput.xml"
    synthesize_failure_xml("missing_log_target", None, xml_file)

    self.assertTrue(xml_file.is_file())
    self.assertTrue(xml_file.with_suffix(".crash").is_file())

    tree = ET.parse(xml_file)
    root = tree.getroot()
    error_el = root.find(".//error")
    self.assertIn("No test log output was found", error_el.text)

  def test_synthesize_with_cdata_split(self):
    xml_file = self.dir_path / "cdata_target_testoutput.xml"
    log_file = self.dir_path / "cdata_log.txt"
    log_file.write_text("Error occurred: ]]> in log output\n", encoding="utf-8")

    synthesize_failure_xml("cdata_target", log_file, xml_file)
    self.assertTrue(xml_file.is_file())

    tree = ET.parse(xml_file)
    root = tree.getroot()
    error_el = root.find(".//error")
    self.assertIn("]]> in log output", error_el.text)

  def test_synthesize_bounded_log_tail(self):
    xml_file = self.dir_path / "tail_target_testoutput.xml"
    log_file = self.dir_path / "tail_log.txt"
    log_file.write_text(
        "".join(f"line {i}\n" for i in range(200)), encoding="utf-8"
    )

    synthesize_failure_xml(
        "tail_target", log_file, xml_file, max_log_lines=10
    )
    tree = ET.parse(xml_file)
    root = tree.getroot()
    error_el = root.find(".//error")
    self.assertNotIn("line 0\n", error_el.text)
    self.assertIn("line 199\n", error_el.text)


if __name__ == "__main__":
  unittest.main()
