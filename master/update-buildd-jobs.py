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

import os
import sys
import apt_pkg
from optparse import OptionParser

from jenkinsctl import *
from pkginfo import *

class BuildJobUpdater:
    def __init__(self):
        self._jenkins = JenkinsBridge()
        self._pkginfo = PackageInfoRetriever()
        self.scheduleBuilds = True

        parser = SafeConfigParser()
        parser.read('jenkins-dak.conf')
        self._supportedArchs = parser.get('Archive', 'archs').split (" ")

    def syncPackages(self):
        pkgList = self._pkginfo.getAllPackages()
        for pkg in pkgList:
            # check if this is an arch:all package
            if pkg.archs == "all":
                 # our package is arch:all, schedule it on amd64 for build
                 self._jenkins.createUpdateJob(pkg.pkgname, pkg.version, pkg.component, pkg.dist, "all", False)
                 if not "all" in pkg.installedArchs:
                     if self.scheduleBuilds:
                         self._jenkins.scheduleBuildIfNotFailed(pkg.pkgname, pkg.version, pkg.component, pkg.dist, arch)
                 continue

            for arch in self._supportedArchs:
                if ("any" in pkg.archs) or ("linux-any" in pkg.archs) or (arch in pkg.archs):
                    # we add new packages for our binary architectures
                    self._jenkins.createUpdateJob(pkg.pkgname, pkg.version, pkg.component, pkg.dist, arch, False)
                    if not arch in pkg.installedArchs:
                        print("Package %s not built for %s!" % (pkg.pkgname, arch))
                        if self.scheduleBuilds:
                            self._jenkins.scheduleBuildIfNotFailed(pkg.pkgname, pkg.version, pkg.component, pkg.dist, arch)

def main():
    # init Apt, we need it later
    apt_pkg.init()

    parser = OptionParser()
    parser.add_option("-u", "--update",
                  action="store_true", dest="update", default=False,
                  help="syncronize Jenkins with archive contents")
    parser.add_option("--nobuild",
                  action="store_true", dest="no_build", default=False,
                  help="don't schedule any builds")

    (options, args) = parser.parse_args()

    if options.update:
        sync = BuildJobUpdater()
        sync.scheduleBuilds = not options.no_build
        sync.syncPackages()
    else:
        print("Run with -h for a list of available command-line options!")

if __name__ == "__main__":
    os.environ['LANG'] = 'C'
    os.environ['LC_ALL'] = 'C'
    main()
