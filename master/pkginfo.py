#!/usr/bin/python
# Copyright (C) 2013 Matthias Klumpp <mak@debian.org>
#
# Licensed under the GNU General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gzip
import os.path
from ConfigParser import SafeConfigParser
from apt_pkg import TagFile, TagSection

class PackageInfo():
    def __init__(self, pkgname, pkgversion, dist, component, archs):
        self._pkgname = pkgname
        self._version = pkgversion
        self._dist = dist
        self._component = component
        self._archs = archs

    @property
    def installedArchs(self):
        return self._installedArchs

    @installedArchs.setter
    def installedArchs(self, value):
        self._installedArchs = value

class PackageInfoRetriever():
    def __init__(self):
        parser = SafeConfigParser()
        parser.read('jenkins-dak.conf')
        path = parser.get('Archive', 'path')
        self._archivePath = path
        self._supportedArchs = parser.get('Archive', 'archs').split (" ")
        self._supportedArchs += ["all"]

    def _getPackagesFor(self, dist, component):
        source_path = self._archivePath + "dists/%s/%s/source/Sources.gz" % (dist, component)
        f = gzip.open(source_path, 'rb')
        tagf = TagFile (f)
        packageList = []
        for section in tagf:
            # don't even try to build source-only packages
            if section['Extra-Source-Only'] == 'yes':
                pass

            archs = section['Architecture']
            binaries = section['Binary']
            pkgversion = section['Version']
            pkg = PackageInfo(section['Package'], pkgversion, dist, component, archs)

            # we check if one of the arch-binaries exists. if it does, we consider the package built for this architecture
            if binaries.index(',') > 0:
                binaryName = binaries[:binaries.index(',')]
            else:
                binaryName = binaries
            for arch in self._supportedArchs:
                fileExt = "deb"
                if binaryName.index('udeb') > 0:
                    fileExt = "udeb"
                binaryPkgName = "%s_%s_%s.%s" % (binaryName, pkgversion, arch, fileExt)
                expectedPackagePath = self._archivePath + "/%s/%s" % (section["Directory"], binaryPkgName)

                if os.path.isfile(expectedPackagePath):
                    pkg.installedArchs += arch
                else:
                    print("INFO: Binary package %s not found in the archive." % (expectedPackagePath))

           # print pkg
