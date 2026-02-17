// Copyright 2024 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "base/functional/bind.h"
#include "base/test/launcher/unit_test_launcher.h"
#include "build/build_config.h"
#include "content/public/test/unittest_test_suite.h"
#include "content/test/content_test_suite.h"
#include "mojo/core/embedder/embedder.h"

#if BUILDFLAG(IS_COBALT_HERMETIC_BUILD)
#include "starboard/client_porting/wrap_main/wrap_main.h"
#endif  // BUILDFLAG(IS_COBALT_HERMETIC_BUILD)

namespace {

int RunTestSuite(int argc, char** argv) {
  content::UnitTestTestSuite test_suite(
      new content::ContentTestSuite(argc, argv),
      base::BindRepeating(content::UnitTestTestSuite::CreateTestContentClients),
      /*child_mojo_config=*/std::nullopt);

  mojo::core::Init();

  return base::LaunchUnitTests(argc, argv,
                               base::BindOnce(&content::UnitTestTestSuite::Run,
                                              base::Unretained(&test_suite)));
}

}  // namespace

#if BUILDFLAG(IS_COBALT_HERMETIC_BUILD)
SB_EXPORT STARBOARD_WRAP_SIMPLE_MAIN(RunTestSuite)
#else
int main(int argc, char** argv) {
  return RunTestSuite(argc, argv);
}
#endif  // BUILDFLAG(IS_COBALT_HERMETIC_BUILD)
