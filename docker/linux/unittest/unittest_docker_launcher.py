#!/usr/bin/env python3
# Copyright 2022 The Cobalt Authors. All Rights Reserved.
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
"""Entrypoint for running unit-tests shards in docker"""

import json
import logging
import os
import subprocess
import sys
import time

log = logging.getLogger(__name__)


def exc(cmd, check=False):
  log.info(cmd)
  with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
    for line in p.stdout:
      print(line)
  if check and p.returncode:
    raise subprocess.CalledProcessError(p.returncode, cmd)


def main(argv):
  shard_index = None
  if len(argv) >= 2:
    shard_index = int(argv[1])

  out_dir = '/out'
  coverage_dir = '/out/coverage'

  exc(['unzip', '-q', f'{out_dir}/app_launcher.zip', '-d', '/app_launcher_out'])

  xvfb_prefix = [
      'xvfb-run', '-a',
      '--server-args="-screen 0 1920x1080x24 +render +extension GLX -noreset"'
  ]
  env_platform = os.getenv('PLATFORM')
  env_config = os.getenv('CONFIG')
  test_command = [
      'python3', '/app_launcher_out/starboard/tools/testing/test_runner.py',
      '--run', '-o', out_dir, '-p', env_platform, '-c', env_config, '-l',
      '--coverage_dir', coverage_dir, '--coverage_report'
  ]

  if shard_index is not None:
    test_command.append('-s')
    test_command.append(str(shard_index))

  start_t = time.time()
  exc(xvfb_prefix + test_command)
  end_t = time.time()

  # Output shard timing information to file.
  duration_t = (end_t - start_t) / 60.0
  shard_timing_json = f'{out_dir}/shard_timing.json'
  try:
    with open(shard_timing_json, 'r', encoding='utf-8') as f:
      json_content = json.loads(f.read())
  except FileNotFoundError:
    json_content = {}
  json_content[str(shard_index)] = f'{duration_t:.2f}'
  with open(shard_timing_json, 'w+', encoding='utf-8') as f:
    json.dump(json_content, f, sort_keys=True, indent=2)


if __name__ == '__main__':
  logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
  main(sys.argv)
