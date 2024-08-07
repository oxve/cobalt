#!/usr/bin/python

# Copyright 2017 The Cobalt Authors. All Rights Reserved.
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
"""Cobalt specific configuration for XB1 packages."""

from starboard.tools import config

_PACKAGE_CONFIGURATIONS = [
    config.Config.QA,
    config.Config.GOLD,
]


def DefaultPackageParameters(_, product):
  """Default parameters to be passed to XB1's Package constructor."""
  return {'publisher': None, 'product': product}


def NightlyPackageParametersList(product):
  """Yield a (config, package_parameters, install_targets) tuple."""
  for configuration in _PACKAGE_CONFIGURATIONS:
    package_parameters = DefaultPackageParameters(configuration, product)
    yield (configuration, package_parameters, None)
