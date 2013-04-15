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

from ConfigParser import SafeConfigParser
import gzip
from apt_pkg import TagFile, TagSection

class PackageInfo():
    def __init__(self, pkgname, pkgversion, dist, component, archs):
        self._pkgname = pkgname
        self._version = pkgversion
        self._dist = dist
        self._component = component
        self._archs = archs

    @property
    def installed_arches(self):
        return self._installed_archs

    @installed_arches.setter
    def installed_arches(self, value):
        self._installed_archs = value

class PackageInfoRetriever():
    def __init__(self):
        parser = SafeConfigParser()
        parser.read('jenkins-dak.conf')
        path = parser.get('Archive', 'path')
        self._archive_path = path + "/dists"

    def _getPackagesFor(self, dist, component):
        source_path = self._archive_path + "/%s/%s/source/Sources.gz" % (dist, component)
        f = gzip.open(source_path, 'rb')
        tagf = TagFile (f)
        for section in tagf:
            print section['Package']
