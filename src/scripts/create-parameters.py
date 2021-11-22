#!/usr/bin/env python3

import os
import re
import subprocess
import sys

output_path = os.environ.get('OUTPUT_PATH')
shared_files = os.environ.get('SHARED_FILES')
head = os.environ.get('CIRCLE_SHA1')
base = subprocess.run(
  ['git', 'merge-base', os.environ.get('BASE_REVISION'), head],
  check=True,
  capture_output=True
).stdout.decode('utf-8').strip()

if head == base:
  try:
    # If building on the same branch as BASE_REVISION, we will get the
    # current commit as merge base. In that case try to go back to the
    # first parent, i.e. the last state of this branch before the
    # merge, and use that as the base.
    base = subprocess.run(
      ['git', 'rev-parse', 'HEAD~1'], # FIXME this breaks on the first commit, fallback to something
      check=True,
      capture_output=True
    ).stdout.decode('utf-8').strip()
  except:
    # This can fail if this is the first commit of the repo, so that
    # HEAD~1 actually doesn't resolve. In this case we can compare
    # against this magic SHA below, which is the empty tree. The diff
    # to that is just the first commit as patch.
    base = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

print('Comparing {}...{}'.format(base, head))
changes = subprocess.run(
  ['git', 'diff', '--name-only', base, head],
  check=True,
  capture_output=True
).stdout.decode('utf-8').splitlines()

mappings = [
  m.split() for m in
  os.environ.get('MAPPING').splitlines()
]

def check_mapping(m):
  pattern, *paths = m
  regex = re.compile(r'^' + pattern + r'$')
  for change in changes:
    if regex.match(change):
      return True
  return False

def get_paths(m):
  return m[1:len(m)]

def flatten_paths(t):
    return [item for sublist in t for item in sublist]

mappings = filter(check_mapping, mappings)
paths = map(get_paths, mappings)
paths = flatten_paths(paths)

# Add shared files
if 0 < len(shared_files):
  paths += shared_files.split()

# Only unique files
paths = list(set(paths))

def non_present_files(path):
  return not os.path.exists(path)

# Log and halt when non present files
non_present_paths = list(filter(non_present_files, paths))
if 0 < len(non_present_paths):
  print('The following files are not present: ')
  print(*non_present_paths, sep='\n')
  sys.exit(-1)

if 0 == len(paths):
  print('No YAML files to merge')

  subprocess.run(["circleci-agent", "step",  "halt"])
else:
  print('YAML files to merge: ')
  print(*paths, sep='\n')

  merge_yaml_process = subprocess.run(
    ["xargs", "-L", "1", "yq", "-y", "-s", "reduce .[] as $item ({}; . * $item)"],
    input=' '.join(paths),
    text=True,
    capture_output=True)

  with open(output_path, 'w') as fp:
    fp.write(merge_yaml_process.stdout)