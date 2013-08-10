# Copyright [2013] Jesse Sipprell <jessesipprell@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os,sys

from ez_setup import use_setuptools
use_setuptools(download_delay=0)
from setuptools import setup,find_packages

try:
  here = os.path.abspath(os.path.dirname(__file__))
except:
  here = os.path.abspath(os.path.normpath(os.path.dirname(__file__)))

version_txt = os.path.join(here,'version.txt')
supervisor_restarter_version = open(version_txt).read().strip()
requires = ['setuptools','supervisor >= 3.0a']

if __name__ == '__main__':
  setup(name='supervisor-restarter',
        version=supervisor_restarter_version,
        author='Jesse Sipprell',
        author_email='jessesipprell@gmail.com',
        license='BSD',
        description='Fast process group restarting for supervisord',
        long_description=
'''Provides a plugin for python-supervisor which can restart process groups rapidly.
Standard supervisor has a design flaw which makes restarting process groups with large
numbers of processes VERY slow.
''',
        packages=find_packages(),
        namespace_packages=['supervisor','supervisor.plugins'],
        install_requires=requires,
        zip_safe=False
      )
