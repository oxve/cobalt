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
"""Synthesizes a JUnit XML failure report for internal tests when results are missing."""

import argparse
import collections
import html
import pathlib
import sys
from typing import Optional


def _format_cdata(text: str) -> str:
  """Formats text as CDATA, splitting any embedded ']]>' sequences."""
  safe_text = text.replace("]]>", "]]]]><![CDATA[>")
  return f"<![CDATA[{safe_text}]]>"


def synthesize_failure_xml(
    target_name: str,
    log_path: Optional[pathlib.Path],
    xml_path: pathlib.Path,
    max_log_lines: int = 100,
) -> None:
  """Generates a JUnit XML error report encapsulating the log tail in CDATA.

  Args:
    target_name: Name of the test target.
    log_path: Path to the test log file if available, or None.
    xml_path: Destination path for the generated JUnit XML file.
    max_log_lines: Maximum number of log lines from the tail to include.
  """
  log_tail = ""
  if log_path and log_path.is_file():
    try:
      with log_path.open("r", encoding="utf-8", errors="replace") as f:
        # Bounded streaming read via collections.deque to avoid OOM on huge logs
        tail_lines = collections.deque(f, maxlen=max_log_lines)
        log_tail = "".join(tail_lines)
    except Exception as e:
      log_tail = f"Failed to read log file {log_path}: {e}"
  else:
    log_tail = "No test log output was found for this target."

  xml_path.parent.mkdir(parents=True, exist_ok=True)
  escaped_target = html.escape(target_name)
  cdata_block = _format_cdata(log_tail)

  # Note: Use CDATA block for the raw log text so special characters and
  # ANSI escape sequences do not break XML parsing.
  content = f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuites tests="1" failures="0" disabled="0" errors="1" time="0">
  <testsuite name="{escaped_target}" tests="1" failures="0" disabled="0" errors="1" time="0">
    <testcase name="{escaped_target}" classname="{escaped_target}" time="0">
      <error message="Test target produced no structured results (crashed, timed out, or lab failure)">
        {cdata_block}
      </error>
    </testcase>
  </testsuite>
</testsuites>
"""
  xml_path.write_text(content, encoding="utf-8")

  # Create companion .crash marker file so downstream retry filter generation
  # treats this target as crashed and does not write a filter to skip it.
  marker_path = xml_path.with_suffix(".crash")
  marker_path.write_text(f"{target_name}\n", encoding="utf-8")


def main(argv=None) -> int:
  """Main entrypoint for synthesize_internal_test_failure CLI."""
  parser = argparse.ArgumentParser(
      description=(
          "Synthesizes JUnit XML error report for internal test runs without"
          " results."
      )
  )
  parser.add_argument("--target", required=True, help="Test target name.")
  parser.add_argument(
      "--log-path",
      "--log-file",
      dest="log_path",
      type=pathlib.Path,
      default=None,
      help="Path to test log or cobalt.log file if available.",
  )
  parser.add_argument(
      "--xml-path",
      "--output-xml",
      dest="xml_path",
      type=pathlib.Path,
      required=True,
      help="Output JUnit XML path.",
  )
  args = parser.parse_args(argv)

  synthesize_failure_xml(args.target, args.log_path, args.xml_path)
  return 0


if __name__ == "__main__":
  sys.exit(main())
