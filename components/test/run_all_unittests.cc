// Copyright 2012 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "components/test/components_test_suite.h"

#if BUILDFLAG(IS_COBALT_HERMETIC_BUILD)
#include "starboard/client_porting/wrap_main/wrap_main.h"
#endif  // BUILDFLAG(IS_COBALT_HERMETIC_BUILD)

int RunTestSuite(int argc, char** argv) {
  return base::LaunchUnitTests(argc, argv, GetLaunchCallback(argc, argv));
}

#if BUILDFLAG(IS_COBALT_HERMETIC_BUILD)
SB_EXPORT STARBOARD_WRAP_SIMPLE_MAIN(RunTestSuite)
#else
int main(int argc, char** argv) {
  return RunTestSuite(argc, argv);
}
#endif  // BUILDFLAG(IS_COBALT_HERMETIC_BUILD)
