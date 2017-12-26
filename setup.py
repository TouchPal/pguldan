#!/usr/bin/env python

try:
  from setuptools import setup, Extension
  from setuptools.command import install_lib as _install_lib
except ImportError:
  from distutils.core import setup, Extension
  from distutils.command import install_lib as _install_lib
import sys, imp, os, glob

def version():
  module = imp.load_source("pguldan.version", "pguldan/version.py")
  return module.__version__


# Patch "install_lib" command to run build_clib before build_ext
# to properly work with easy_install.
# See: http://bugs.python.org/issue5243
class install_lib(_install_lib.install_lib):
  def build(self):
    if not self.skip_build:
      if self.distribution.has_pure_modules():
        self.run_command('build_py')
        if self.distribution.has_c_libraries():
          self.run_command('build_clib')
        if self.distribution.has_ext_modules():
          self.run_command('build_ext')

setup(name='pguldan',
      version=version(),
      description='guldan pure python client',
      url='https://gitlab.corp.cootek.com/livexmm.xu/pguldan',
      author='livexmm',
      author_email='livexmm.xu@cootek.cn',
      packages=['pguldan'],
      cmdclass={ "install_lib": install_lib })

