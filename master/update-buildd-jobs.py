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
        self.debugMode = False

        parser = SafeConfigParser()
        parser.read(['/etc/jenkins/jenkins-dak.conf', 'jenkins-dak.conf'])
        self._supportedArchs = parser.get('Archive', 'archs').split (" ")

    def sync_packages(self):
        pkgList = self._pkginfo.get_all_packages()
        # generate list of all package names, to make the Jenkins job builder
        # smarter in determining if a package was replaced or is still valid
        pkgNameList = []
        for pkg in pkgList:
            pkgNameList.append(pkg.pkgname)
        self._jenkins.set_registered_packages_list(pkgNameList)

        for pkg in pkgList:
            # check if this is an arch:all package
            # TODO: Wilter out not-built architectures (armel, kfreebsd-*, etc. to determine arch:all build)
            if pkg.archs == "all":
                 # our package is arch:all, schedule it on amd64 for build
                 self._jenkins.create_update_job(pkg.pkgname, pkg.version, pkg.component, pkg.dist, "all", pkg.info)
                 if not 'all' in pkg.installedArchs:
                     if self.scheduleBuilds:
                         self._jenkins.schedule_build_if_not_failed(pkg.pkgname, pkg.version, "all")
                 continue

            for arch in self._supportedArchs:
                # TODO Handle i386-any version ID's ;-)
                if ('any' in pkg.archs) or ('linux-any' in pkg.archs) or (arch in pkg.archs):
                    # we add new packages for our binary architectures
                    self._jenkins.create_update_job(pkg.pkgname, pkg.version, pkg.component, pkg.dist, arch, pkg.info)
                    if not arch in pkg.installedArchs:
                        if self.debugMode:
                            print("Package %s not built for %s!" % (pkg.pkgname, arch))
                        if self.scheduleBuilds:
                            self._jenkins.schedule_build_if_not_failed(pkg.pkgname, pkg.version, arch)

    def _get_cruft_jobs(self):
        pkgList = self._pkginfo.get_all_packages()
        jobList = self._jenkins.currentJobs

        for pkg in pkgList:
            if ' ' in pkg.archs:
                archs = pkg.archs.split(' ')
            else:
                archs = [pkg.archs]

            # TODO: Wilter out not-built architectures (armel, kfreebsd-*, etc. to determine arch:all build)
            if pkg.archs == "all":
                jobName = self._jenkins.get_job_name(pkg.pkgname, pkg.version, "all")
                if jobName in jobList:
                    jobList.remove(jobName)
            for arch in self._supportedArchs:
                if ('any' in pkg.archs) or ('linux-any' in pkg.archs) or (arch in pkg.archs):
                    jobName = self._jenkins.get_job_name(pkg.pkgname, pkg.version, arch)
                    if jobName in jobList:
                        jobList.remove(jobName)
        return jobList

    def cruft_report(self):
        jobList = self._get_cruft_jobs()
        for job in jobList:
            print("Cruft: %s" % (job))

def main():
    # init Apt, we need it later
    apt_pkg.init()

    parser = OptionParser()
    parser.add_option("-u", "--update",
                  action="store_true", dest="update", default=False,
                  help="syncronize Jenkins with archive contents")
    parser.add_option("--cruft-report",
                  action="store_true", dest="cruft_report", default=False,
                  help="report jobs without matching package")
    parser.add_option("--nobuild",
                  action="store_true", dest="no_build", default=False,
                  help="don't schedule any builds")

    (options, args) = parser.parse_args()

    if options.update:
        sync = BuildJobUpdater()
        sync.scheduleBuilds = not options.no_build
        sync.sync_packages()
    elif options.cruft_report:
        sync = BuildJobUpdater()
        sync.cruft_report()
    else:
        print("Run with -h for a list of available command-line options!")

if __name__ == "__main__":
    os.environ['LANG'] = 'C'
    os.environ['LC_ALL'] = 'C'
    main()
