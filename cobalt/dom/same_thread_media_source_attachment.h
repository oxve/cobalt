// Copyright 2024 The Cobalt Authors. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// Copyright 2020 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef COBALT_DOM_SAME_THREAD_MEDIA_SOURCE_ATTACHMENT_H_
#define COBALT_DOM_SAME_THREAD_MEDIA_SOURCE_ATTACHMENT_H_

#include "base/memory/weak_ptr.h"
#include "base/task/sequenced_task_runner.h"
#include "cobalt/dom/audio_track_list.h"
#include "cobalt/dom/media_source.h"
#include "cobalt/dom/media_source_attachment_supplement.h"
#include "cobalt/dom/media_source_ready_state.h"
#include "cobalt/dom/time_ranges.h"
#include "cobalt/dom/video_track_list.h"
#include "cobalt/script/environment_settings.h"
#include "cobalt/script/tracer.h"
#include "cobalt/web/url_registry.h"
#include "media/filters/chunk_demuxer.h"

namespace cobalt {
namespace dom {

class SameThreadMediaSourceAttachment : public MediaSourceAttachmentSupplement {
 public:
  explicit SameThreadMediaSourceAttachment(
      scoped_refptr<MediaSource> media_source);

  // Traceable
  void TraceMembers(script::Tracer* tracer) override;

  // MediaSourceAttachment
  bool StartAttachingToMediaElement(HTMLMediaElement* media_element) override;
  void CompleteAttachingToMediaElement(
      ::media::ChunkDemuxer* chunk_demuxer) override;
  void Close() override;
  scoped_refptr<TimeRanges> GetBufferedRange() const override;
  MediaSourceReadyState GetReadyState() const override;

  // MediaSourceAttachmentSupplement
  void NotifyDurationChanged(double duration) override;
  bool HasMaxVideoCapabilities() const override;
  double GetRecentMediaTime() override;
  bool GetElementError() override;
  scoped_refptr<AudioTrackList> CreateAudioTrackList(
      script::EnvironmentSettings* settings) override;
  scoped_refptr<VideoTrackList> CreateVideoTrackList(
      script::EnvironmentSettings* settings) override;

  // TODO(b/338425449): Remove media_source and media_element methods after
  // rollout. Reference to underlying objects is exposed for when the H5VCC
  // flag MediaElement.EnableUsingMediaSourceAttachmentMethods is disabled.
  scoped_refptr<MediaSource> media_source() const override {
    return media_source_;
  }
  base::WeakPtr<HTMLMediaElement> media_element() const override {
    return attached_element_;
  }

 private:
  ~SameThreadMediaSourceAttachment() = default;

  // Reference to the registered MediaSource.
  scoped_refptr<MediaSource> media_source_;

  // Reference to the HTMLMediaElement the associated MediaSource is attached
  // to. Only set after StartAttachingToMediaElement is called.
  base::WeakPtr<HTMLMediaElement> attached_element_ = nullptr;

  // Used to ensure all calls are made on the thread that created this object.
  base::SequencedTaskRunner* task_runner_;

  DISALLOW_COPY_AND_ASSIGN(SameThreadMediaSourceAttachment);
};

}  // namespace dom
}  // namespace cobalt

#endif  // COBALT_DOM_SAME_THREAD_MEDIA_SOURCE_ATTACHMENT_H_
