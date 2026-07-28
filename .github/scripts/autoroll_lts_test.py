"""Tests for autoroll_lts.py."""

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

# Add the current directory to sys.path to import autoroll_lts
sys.path.append(os.path.dirname(__file__))
# pylint: disable=wrong-import-position
import autoroll_lts
from autoroll_lts import CommitStatus
# pylint: enable=wrong-import-position


class TestAutorollLts(unittest.TestCase):
  """Test cases for autoroll_lts helper functions."""

  @patch('autoroll_lts.get_out')
  def test_get_start_sha_normal(self, mock_get_out):
    mock_get_out.return_value = '  1234567890abcdef  \n'
    sha = autoroll_lts.get_start_sha('branch', 'file')
    self.assertEqual(sha, '1234567890abcdef')
    mock_get_out.assert_called_once_with(['git', 'show', 'branch:file'])

  @patch('autoroll_lts.get_out')
  def test_get_start_sha_conflicted(self, mock_get_out):
    mock_get_out.return_value = 'CONFLICTED:1234567890abcdef\n'
    sha = autoroll_lts.get_start_sha('branch', 'file')
    self.assertIsNone(sha)

  @patch('autoroll_lts.get_out')
  def test_get_commits(self, mock_get_out):
    mock_get_out.return_value = ('sha1 Commit Title 1 (#101)\n'
                                 'sha2 Commit Title 2\n'
                                 'sha3 Commit Title 3 (#102)\n')
    commits = autoroll_lts.get_commits('branch', 'start_sha')
    self.assertEqual(commits, [
        ('sha1', 'Commit Title 1', '101'),
        ('sha2', 'Commit Title 2', None),
        ('sha3', 'Commit Title 3', '102'),
    ])
    mock_get_out.assert_called_once_with([
        'git', 'rev-list', '--oneline', '--no-abbrev-commit', '--reverse',
        'start_sha..branch'
    ])

  @patch('autoroll_lts.get_out')
  def test_get_unmerged_files(self, mock_run):
    # Simulate output of 'git ls-files -u'
    mock_output = ('100644 123456 1\tfile1.txt\n'
                   '100644 123456 2\tfile1.txt\n'
                   '100644 123456 3\tfile1.txt\n'
                   '100644 abcdef 2\tfile2.txt\n')
    mock_run.return_value = mock_output
    unmerged = autoroll_lts.get_unmerged_files()
    self.assertEqual(unmerged, {
        'file1.txt': {'ancestor', 'ours', 'theirs'},
        'file2.txt': {'ours'}
    })

  @patch('autoroll_lts.run')
  @patch('autoroll_lts.get_out')
  def test_resolve_conflicts_submodule(self, mock_get_out, mock_run):
    unmerged = {'submodule_dir': {'ours', 'theirs'}}

    # ls-files output contains 160000 to indicate submodule
    mock_get_out.side_effect = [
        '160000 abcdef1234567890 3\tsubmodule_dir\n',  # check submodule
        '160000 abcdef1234567890 3\tsubmodule_dir\n',  # get theirs_sha
    ]

    resolved = autoroll_lts.resolve_conflicts(unmerged)
    self.assertTrue(resolved)
    mock_run.assert_called_once_with([
        'git', 'update-index', '--add', '--cacheinfo',
        '160000,abcdef1234567890,submodule_dir'
    ])

  @patch('autoroll_lts.run')
  @patch('autoroll_lts.get_out')
  def test_resolve_conflicts_deleted(self, mock_get_out, mock_run):
    unmerged = {'deleted_by_us': {'theirs'}, 'deleted_by_them': {'ours'}}
    mock_get_out.return_value = '100644 some_sha 2\tfile\n'  # Not submodule

    resolved = autoroll_lts.resolve_conflicts(unmerged)
    self.assertTrue(resolved)
    # Should call git rm for both
    self.assertEqual(mock_run.call_count, 2)
    mock_run.assert_any_call(
        ['git', 'rm', '--ignore-unmatch', '--', 'deleted_by_us'])
    mock_run.assert_any_call(
        ['git', 'rm', '--ignore-unmatch', '--', 'deleted_by_them'])

  @patch('autoroll_lts.get_out')
  def test_resolve_conflicts_unresolved(self, mock_get_out):
    unmerged = {'file.txt': {'ours', 'theirs'}}
    mock_get_out.return_value = '100644 some_sha 2\tfile.txt\n'  # Not submodule
    resolved = autoroll_lts.resolve_conflicts(unmerged)
    self.assertFalse(resolved)


class TestAutorollLtsApplyAndCommit(unittest.TestCase):
  """Test cases for apply_and_commit."""

  def setUp(self):
    super().setUp()
    self.metadata = ('date', 'author', 'msg')

  @patch('autoroll_lts.run')
  @patch('autoroll_lts.get_out')
  def test_apply_and_commit_success(self, mock_get_out, mock_run):
    # Simulate git diff showing changes to commit
    mock_get_out.side_effect = [
        'file.txt\n',  # git diff --cached
    ]

    with patch('builtins.open', unittest.mock.mock_open()):
      status, unmerged = autoroll_lts.apply_and_commit(
          'cherry-pick',
          'sha',
          self.metadata,
          first_commit=True,
          autoroll_file='AUTOROLL')

    self.assertEqual(status, CommitStatus.SUCCESS)
    self.assertIsNone(unmerged)
    mock_run.assert_any_call(['git', 'cherry-pick', '--no-commit', 'sha'])
    mock_run.assert_any_call(['git', 'add', '--', 'AUTOROLL'])
    mock_run.assert_any_call([
        'git', 'commit', '--no-verify', '--date=date', '--author=author', '-m',
        'msg'
    ])

  @patch('autoroll_lts.run')
  @patch('autoroll_lts.get_out')
  def test_apply_and_commit_skipped(self, mock_get_out, mock_run):
    # Simulate git diff showing NO changes
    mock_get_out.return_value = ''

    status, unmerged = autoroll_lts.apply_and_commit(
        'cherry-pick',
        'sha',
        self.metadata,
        first_commit=True,
        autoroll_file='AUTOROLL')

    self.assertEqual(status, CommitStatus.SKIPPED)
    self.assertIsNone(unmerged)
    mock_run.assert_called_once_with(
        ['git', 'cherry-pick', '--no-commit', 'sha'])

  @patch('autoroll_lts.run')
  @patch('autoroll_lts.get_unmerged_files')
  @patch('autoroll_lts.resolve_conflicts')
  @patch('autoroll_lts.get_out')
  def test_apply_and_commit_conflict_resolved(self, mock_get_out, mock_resolve,
                                              mock_get_unmerged, mock_run):
    # Simulate cherry-pick failure, but conflicts resolved
    mock_run.side_effect = [
        subprocess.CalledProcessError(1, 'cherry-pick'),  # run cherry-pick
        None,  # git add
        None,  # git commit
    ]
    mock_get_unmerged.return_value = {'file.txt': {'ours', 'theirs'}}
    mock_resolve.return_value = True  # Resolved!
    mock_get_out.return_value = 'file.txt\n'  # git diff shows changes

    with patch('builtins.open', unittest.mock.mock_open()):
      status, unmerged = autoroll_lts.apply_and_commit(
          'cherry-pick',
          'sha',
          self.metadata,
          first_commit=True,
          autoroll_file='AUTOROLL')

    self.assertEqual(status, CommitStatus.SUCCESS)
    self.assertIsNone(unmerged)

  @patch('autoroll_lts.run')
  @patch('autoroll_lts.get_unmerged_files')
  @patch('autoroll_lts.resolve_conflicts')
  @patch('autoroll_lts.get_out')
  def test_apply_and_commit_conflict_unresolved_first_commit(
      self, mock_get_out, mock_resolve, mock_get_unmerged, mock_run):
    # Simulate cherry-pick failure, conflicts unresolved, first commit
    mock_run.side_effect = [
        subprocess.CalledProcessError(1, 'cherry-pick'),  # run cherry-pick
        None,  # git add unmerged
        None,  # git add autoroll
        None,  # git commit
    ]
    mock_get_unmerged.return_value = {'file.txt': {'ours', 'theirs'}}
    mock_resolve.return_value = False  # Unresolved!
    mock_get_out.return_value = 'file.txt\n'  # git diff shows changes

    with patch('builtins.open', unittest.mock.mock_open()):
      status, unmerged = autoroll_lts.apply_and_commit(
          'cherry-pick',
          'sha',
          self.metadata,
          first_commit=True,
          autoroll_file='AUTOROLL')

    self.assertEqual(status, CommitStatus.CONFLICTED)
    self.assertEqual(unmerged, ['file.txt'])
    mock_run.assert_any_call(['git', 'add', '--', 'file.txt'])
    mock_run.assert_any_call([
        'git', 'commit', '--no-verify', '--date=date', '--author=author', '-m',
        'CONFLICTED msg'
    ])

  @patch('autoroll_lts.run')
  @patch('autoroll_lts.get_unmerged_files')
  @patch('autoroll_lts.resolve_conflicts')
  def test_apply_and_commit_conflict_unresolved_not_first_commit(
      self, mock_resolve, mock_get_unmerged, mock_run):
    # Simulate cherry-pick failure, conflicts unresolved, NOT first commit
    mock_run.side_effect = [
        subprocess.CalledProcessError(1, 'cherry-pick'),  # run cherry-pick
        None,  # git reset --hard
    ]
    mock_get_unmerged.return_value = {'file.txt': {'ours', 'theirs'}}
    mock_resolve.return_value = False  # Unresolved!

    status, unmerged = autoroll_lts.apply_and_commit(
        'cherry-pick',
        'sha',
        self.metadata,
        first_commit=False,
        autoroll_file='AUTOROLL')

    self.assertEqual(status, CommitStatus.FAILED)
    self.assertEqual(unmerged, ['file.txt'])
    mock_run.assert_any_call(['git', 'reset', '--hard', 'HEAD'])


class TestAutorollLtsMain(unittest.TestCase):
  """Test cases for main() function flow."""

  @patch('autoroll_lts.get_start_sha')
  @patch('autoroll_lts.get_commits')
  @patch('autoroll_lts.get_cherry_pick_metadata')
  @patch('autoroll_lts.cherry_pick')
  @patch('sys.argv', [
      'autoroll_lts.py', '--source-branch', 'main', '--target-branch', '27.lts',
      '--autoroll-file', 'AUTOROLL', '--max-commits', '5', '--existing-pr-sha',
      ''
  ])
  def test_main_flow_success(self, mock_cherry_pick, mock_metadata,
                             mock_get_commits, mock_get_start_sha):
    mock_get_start_sha.side_effect = [
        'target_start_sha',  # target_branch
        'autoroll_start_sha',  # HEAD
    ]
    # Commits to target: C1, C2, C3
    mock_get_commits.side_effect = [
        [('sha1', 'T1', '1'), ('sha2', 'T2', '2'),
         ('sha3', 'T3', '3')],  # commits_to_target
        [('sha2', 'T2', '2'), ('sha3', 'T3', '3')
        ],  # commits_to_autoroll (C1 is already in autoroll)
    ]
    mock_metadata.return_value = ('date', 'author', 'msg')
    mock_cherry_pick.return_value = (CommitStatus.SUCCESS, None)

    with patch('builtins.print') as mock_print:
      autoroll_lts.main()

    # C1 should be skipped (not in shas_to_autoroll)
    # C2 and C3 should be cherry-picked
    self.assertEqual(mock_cherry_pick.call_count, 2)
    mock_cherry_pick.assert_any_call('sha2', ('date', 'author', 'msg'), False,
                                     'AUTOROLL')
    mock_cherry_pick.assert_any_call('sha3', ('date', 'author', 'msg'), False,
                                     'AUTOROLL')

    # Verify stdout output (printed links)
    printed_calls = mock_print.call_args_list
    stdout_calls = [call for call in printed_calls if 'file' not in call[1]]
    self.assertEqual(len(stdout_calls), 1)
    # C1 is added as skipped, C2 and C3 as success
    self.assertEqual(stdout_calls[0][0][0], '- #1\n- #2\n- #3')

  @patch('autoroll_lts.get_start_sha')
  @patch('autoroll_lts.get_commits')
  @patch('sys.argv', [
      'autoroll_lts.py', '--source-branch', 'main', '--target-branch', '27.lts',
      '--autoroll-file', 'AUTOROLL', '--max-commits', '5', '--existing-pr-sha',
      ''
  ])
  def test_main_flow_unresolved_conflicted_start(self, mock_get_commits,
                                                 mock_get_start_sha):
    mock_get_start_sha.side_effect = [
        'target_start_sha',  # target_branch
        None,  # HEAD has unresolved conflict (returns None)
    ]

    with patch('autoroll_lts.log') as mock_log:
      autoroll_lts.main()

    mock_log.assert_called_once_with(
        'Autoroll branch has an unresolved CONFLICTED commit.')
    mock_get_commits.assert_not_called()


if __name__ == '__main__':
  unittest.main()
