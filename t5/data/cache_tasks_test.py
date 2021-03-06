# Copyright 2020 The T5 Authors.
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

"""Tests for t5.data.cache_tasks_main."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from absl.testing import absltest
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that
from apache_beam.testing.util import equal_to
import t5
from t5.data import cache_tasks_main
import tensorflow.compat.v1 as tf


test_utils = t5.data.test_utils
TaskRegistry = t5.data.TaskRegistry


class ProcessTaskBeamTest(test_utils.FakeTaskTest):

  def test_get_info(self):
    input_examples = [{"targets": range(10), "inputs": "test"}]

    with TestPipeline() as p:
      pcoll = (p
               | beam.Create(input_examples)
               | cache_tasks_main.GetInfo(num_shards=3))

    assert_that(pcoll, equal_to(
        {
            "num_shards": 3,
            "features_dict": {
                "targets": {"dtype": "int32", "shape": [10]},
                "inputs": {"dtype": "string", "shape": []},
            }
        }))

  def test_pipeline(self):
    self.assertTrue(TaskRegistry.get("cached_task").cache_dir)
    self.assertFalse(TaskRegistry.get("uncached_task").cache_dir)

    with TestPipeline() as p:
      output_dirs = cache_tasks_main.run_pipeline(
          p, ["cached_task", "uncached_task"], cache_dir=self.test_data_dir)

    actual_task_dir = os.path.join(self.test_data_dir, "uncached_task")
    expected_task_dir = os.path.join(test_utils.TEST_DATA_DIR, "cached_task")
    expected_tfrecord_files = [
        "train.tfrecord-00000-of-00002",
        "train.tfrecord-00001-of-00002",
        "validation.tfrecord-00000-of-00001"]
    expected_auxiliary_files = [
        "stats.train.json", "stats.validation.json",
        "info.train.json", "info.validation.json"]

    self.assertEqual([actual_task_dir], output_dirs)
    self.assertCountEqual(
        expected_tfrecord_files + expected_auxiliary_files,
        tf.io.gfile.listdir(actual_task_dir))

    for fname in expected_auxiliary_files:
      self.assertEqual(
          tf.io.gfile.GFile(os.path.join(expected_task_dir, fname)).read(),
          tf.io.gfile.GFile(
              os.path.join(actual_task_dir, fname)).read().replace(", ", ","))

    # Add COMPLETED file so that we can load `uncached_task`.
    test_utils.mark_completed(self.test_data_dir, "uncached_task")

    # Load task.
    uncached_task = TaskRegistry.get("uncached_task")

    # Check datasets.
    test_utils.verify_task_matches_fake_datasets(uncached_task, use_cached=True)


if __name__ == "__main__":
  tf.disable_v2_behavior()
  tf.enable_eager_execution()
  absltest.main()
