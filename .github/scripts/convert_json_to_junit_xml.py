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
"""Converts JSON test results (Chromium, Vega, YTS) to JUnit XML format."""

import argparse
import collections
import json
import sys
from typing import Any, Dict, List
from xml.dom import minidom


def _parse_chromium_format(
    data: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
  """Parses Chromium per_iteration_data test format."""
  suites = collections.defaultdict(list)
  for iteration in data.get('per_iteration_data', []):
    for test_key, results in iteration.items():
      for res in results:
        # Key format: ClassName#MethodName[Suffix]
        if '#' in test_key:
          classname, method_with_suffix = test_key.split('#', 1)
          method = method_with_suffix.split('[')[0]
        else:
          classname = 'UnknownClass'
          method = test_key.split('[')[0]

        status = res.get('status', 'SUCCESS')
        elapsed_ms = res.get('elapsed_time_ms', 0)
        elapsed_sec = elapsed_ms / 1000.0
        output_snippet = res.get('output_snippet', '')

        suites[classname].append({
            'name': method,
            'status': status,
            'time': elapsed_sec,
            'output': output_snippet,
            'message': f'Test {status}',
        })
  return suites


def _parse_vega_or_internal_format(
    data: Any,
) -> Dict[str, List[Dict[str, Any]]]:
  """Parses Vega, Maneki, or YTS JsonReport format."""
  suites = collections.defaultdict(list)
  if isinstance(data, dict):
    tests = data.get('tests', [])
  elif isinstance(data, list):
    tests = data
  else:
    tests = []

  for test in tests:
    if not isinstance(test, dict):
      continue
    method = (
        test.get('test_title')
        or test.get('name')
        or test.get('test_category')
        or 'UnknownTest'
    )
    classname = (
        test.get('class_name')
        or test.get('suite_name')
        or test.get('test_category')
        or 'VegaTest'
    )

    status_raw = str(test.get('result', test.get('status', 'PASSED'))).upper()
    if 'FAIL' in status_raw:
      status = 'FAILURE'
    elif any(s in status_raw for s in ('CRASH', 'TIMEOUT', 'ERROR')):
      status = 'ERROR'
    elif 'SKIP' in status_raw:
      status = 'SKIPPED'
    else:
      status = 'SUCCESS'

    if 'duration' in test:
      try:
        duration = float(test['duration'])
      except (ValueError, TypeError):
        duration = 0.0
    elif 'start_time' in test and 'end_time' in test:
      try:
        duration = max(0.0, (test['end_time'] - test['start_time']) / 1000.0)
      except (ValueError, TypeError):
        duration = 0.0
    else:
      duration = 0.0

    output_lines = []
    if test.get('output'):
      if isinstance(test['output'], list):
        output_lines.extend(str(x) for x in test['output'])
      else:
        output_lines.append(str(test['output']))
    if test.get('errors'):
      if isinstance(test['errors'], list):
        output_lines.extend(str(x) for x in test['errors'])
      else:
        output_lines.append(str(test['errors']))

    output_text = '\n'.join(output_lines)
    message = (
        output_lines[0]
        if output_lines
        else f'Test {status_raw}'
    )

    suites[classname].append({
        'name': method,
        'status': status,
        'time': duration,
        'output': output_text,
        'message': message,
    })

  return suites


def _append_safe_cdata(
    doc: minidom.Document, parent: minidom.Element, text: str
) -> None:
  """Appends CDATA sections safely handling any embedded ']]>' markers."""
  parts = text.split(']]>')
  for i, part in enumerate(parts):
    if i > 0:
      parent.appendChild(doc.createCDATASection(']]'))
      parent.appendChild(doc.createCDATASection('>'))
    if part:
      parent.appendChild(doc.createCDATASection(part))


def convert(json_path: str, xml_path: str) -> None:
  with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

  if isinstance(data, dict) and 'per_iteration_data' in data:
    suites = _parse_chromium_format(data)
  else:
    suites = _parse_vega_or_internal_format(data)

  total_tests = sum(len(cases) for cases in suites.values())
  total_failures = sum(
      1
      for cases in suites.values()
      for c in cases
      if c['status'] in ('FAILURE', 'FAIL')
  )
  total_errors = sum(
      1
      for cases in suites.values()
      for c in cases
      if c['status'] in ('CRASH', 'TIMEOUT', 'ERROR')
  )
  total_skipped = sum(
      1
      for cases in suites.values()
      for c in cases
      if c['status'] in ('SKIPPED', 'SKIP')
  )
  total_time = sum(c['time'] for cases in suites.values() for c in cases)

  doc = minidom.Document()
  testsuites = doc.createElement('testsuites')
  testsuites.setAttribute('tests', str(total_tests))
  testsuites.setAttribute('failures', str(total_failures))
  testsuites.setAttribute('errors', str(total_errors))
  testsuites.setAttribute('disabled', str(total_skipped))
  testsuites.setAttribute('time', f'{total_time:.3f}')
  testsuites.setAttribute('name', 'AllTests')

  for suite_name, cases in suites.items():
    suite_el = doc.createElement('testsuite')
    suite_el.setAttribute('name', suite_name)
    suite_el.setAttribute('tests', str(len(cases)))
    suite_el.setAttribute(
        'failures',
        str(sum(1 for c in cases if c['status'] in ('FAILURE', 'FAIL'))),
    )
    suite_el.setAttribute(
        'errors',
        str(
            sum(
                1
                for c in cases
                if c['status'] in ('CRASH', 'TIMEOUT', 'ERROR')
            )
        ),
    )
    suite_el.setAttribute(
        'disabled',
        str(sum(1 for c in cases if c['status'] in ('SKIPPED', 'SKIP'))),
    )
    suite_el.setAttribute('time', f"{sum(c['time'] for c in cases):.3f}")

    for case in cases:
      case_el = doc.createElement('testcase')
      case_el.setAttribute('name', case['name'])
      case_el.setAttribute('classname', suite_name)
      case_el.setAttribute('time', f"{case['time']:.3f}")

      if case['status'] in ('FAILURE', 'FAIL'):
        fail_el = doc.createElement('failure')
        fail_el.setAttribute('message', case['message'])
        if case['output']:
          # Use CDATA block safely split across any nested ]]> sequences.
          _append_safe_cdata(doc, fail_el, case['output'])
        case_el.appendChild(fail_el)
      elif case['status'] in ('CRASH', 'TIMEOUT', 'ERROR'):
        err_el = doc.createElement('error')
        err_el.setAttribute('message', case['message'])
        if case['output']:
          # Use CDATA block safely split across any nested ]]> sequences.
          _append_safe_cdata(doc, err_el, case['output'])
        case_el.appendChild(err_el)
      elif case['status'] in ('SKIPPED', 'SKIP'):
        skip_el = doc.createElement('skipped')
        case_el.appendChild(skip_el)

      suite_el.appendChild(case_el)

    testsuites.appendChild(suite_el)

  doc.appendChild(testsuites)

  with open(xml_path, 'w', encoding='utf-8') as f:
    f.write(doc.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8'))


def main(argv=None) -> int:
  """Entrypoint for convert_json_to_junit_xml CLI."""
  parser = argparse.ArgumentParser(
      description='Converts JSON test results to JUnit XML format.'
  )
  parser.add_argument('input_json', help='Input JSON file path.')
  parser.add_argument('output_xml', help='Output JUnit XML file path.')
  args = parser.parse_args(argv)

  convert(args.input_json, args.output_xml)
  return 0


if __name__ == '__main__':
  sys.exit(main())
