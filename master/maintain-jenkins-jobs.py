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
import apt_pkg
from optparse import OptionParser

from jenkinsctl import *
from pkginfo import *
from package_buildcheck import *

NEEDSBUILD_EXPORT_DIR = "/srv/dak/export/needsbuild"

class BuildJobUpdater:
    def __init__(self):
        self._jenkins = JenkinsBridge()
        self._pkginfo = PackageInfoRetriever()
        self.scheduleBuilds = False
        self.debugMode = False

        parser = SafeConfigParser()
        parser.read(['/etc/jenkins/jenkins-dak.conf', 'jenkins-dak.conf'])
        self._archiveComponents = parser.get('Archive', 'components').split (" ")
        self._archiveDists = parser.get('Archive', 'dists').split (" ")

        self._supportedArchs = parser.get('Archive', 'archs').split (" ")
        self._unsupportedArchs = parser.get('Archive', 'archs_all').split (" ")
        for arch in self._supportedArchs:
            self._unsupportedArchs.remove(arch)

    def _filterUnsupportedArchs(self, pkgArchs):
        for uarch in self._unsupportedArchs:
            if uarch in pkgArchs:
                pkgArchs.remove(uarch)
        return pkgArchs

    def sync_packages(self, dist, component, needsbuild_list):
        pkgList = self._pkginfo.get_packages_for(dist, component)
        # generate list of all package names, to make the Jenkins job builder
        # smarter in determining if a package was replaced or is still valid
        pkgNameList = []
        for pkg in pkgList:
            pkgNameList.append(pkg.pkgname)
        self._jenkins.set_registered_packages_list(pkgNameList)

        for pkg in pkgList:
            archs = self._filterUnsupportedArchs(pkg.archs)
            # remove duplicates
            archs = list(set(archs))

            # check if this is an arch:all package
            if archs == ["all"]:
                 # our package is arch:all, schedule it on amd64 for build
                 ret = self._jenkins.create_update_job(pkg.pkgname, pkg.version, pkg.component, pkg.dist, ["all"], pkg.info)
                 if not ret:
                        if self.debugMode:
                            print("INFO: Skipping %s, package not created/updated (higher version available?)" % (pkg.pkgname))
                 if not 'all' in pkg.installedArchs:
                     needsbuild_list.write("%s_%s [%s]\n" % (pkg.pkgname, pkg.getVersionNoEpoch(), "all"))
                     if self.scheduleBuilds:
                         self._jenkins.schedule_build_if_not_failed(pkg.pkgname, pkg.version, "all")
                 continue

            pkgArchs = []
            for arch in self._supportedArchs:
                if ('any' in archs) or ('linux-any' in archs) or (("any-"+arch) in archs) or (arch in archs):
                    pkgArchs.append(arch)
            if ("all" in archs):
                    pkgArchs.append("all")

            if len(pkgArchs) <= 0:
                print("Skipping job %s %s on %s, no architectures found!" % (pkg.pkgname, pkg.version, pkg.dist))
                continue

            # packages for arch:all are built on amd64, we don't need an extra build slot for them if it is present
            # we need to eliminate possible duplicate arch enties first, so we don't add duplicate archs (or amd64 and all together in one package)
            buildArchs = list(set(pkgArchs))
            if ("amd64" in buildArchs) and ("all" in buildArchs):
                buildArchs.remove("all")

            ret = self._jenkins.create_update_job(pkg.pkgname, pkg.version, pkg.component, pkg.dist, buildArchs, pkg.info)
            if not ret:
                if self.debugMode:
                        print("INFO: Skipping %s, package not created/updated (higher version available?)" % (pkg.pkgname))

            for arch in buildArchs:
                if not arch in pkg.installedArchs:
                    # safety check, to not build stuff twice
                    if (arch == "amd64") and ("all" in pkg.installedArchs):
                        continue
                    if self.debugMode:
                        print("Package %s not built for %s!" % (pkg.pkgname, arch))
                    needsbuild_list.write("%s_%s [%s]\n" % (pkg.pkgname, pkg.getVersionNoEpoch(), arch))
                    #if self.scheduleBuilds:
                    #    self._jenkins.schedule_build_if_not_failed(pkg.pkgname, pkg.version, arch)

        bcheck = BuildCheck()
        for arch in self._supportedArchs:
            yaml_data = bcheck.get_package_states_yaml(dist, component, arch)
            yaml_file = open("%s/depwait-%s-%s_%s.yml" % (NEEDSBUILD_EXPORT_DIR, dist, component, arch), "w")
            yaml_file.write(yaml_data)
            yaml_file.close()

    def sync_packages_all(self):
        for comp in self._archiveComponents:
            # we need the extra list as temporary hack for Jenkins to know if it should investigate building a package
            # (will later be replaced by the XML generated by edos-debcheck)
            if comp == "main":
                needsbuild_list = open("%s/needsbuild.list" % (NEEDSBUILD_EXPORT_DIR), "w")
            else:
                needsbuild_list = open("%s/needsbuild-%s.list" % (NEEDSBUILD_EXPORT_DIR, comp), "w")

            for dist in self._archiveDists:
                self.sync_packages(dist, comp, needsbuild_list)
            needsbuild_list.close()

    def _get_cruft_jobs(self):
        pkgList = self._pkginfo.get_all_packages()
        jobList = self._jenkins.currentJobs

        for pkg in pkgList:
            # check if this is an arch:all package
            jobName = self._jenkins.get_job_name(pkg.pkgname, pkg.version)
            if jobName in jobList:
                jobList.remove(jobName)

        return jobList

    def cruft_report(self):
        jobList = self._get_cruft_jobs()
        for job in jobList:
            print("Cruft: %s" % (job))

    def cruft_remove(self):
        jobList = self._get_cruft_jobs()
        for job in jobList:
            print("Deleting cruft job: %s" % (job))
            self._jenkins.delete_job(job)
            print("Done.")

    def checkbuild(self):
        self._jenkins.checkbuild()

def main():
    # init Apt, we need it later
    apt_pkg.init()

    parser = OptionParser()
    parser.add_option("-u", "--update",
                  action="store_true", dest="update", default=False,
                  help="syncronize Jenkins with archive contents")
    parser.add_option("--checkbuild",
                  action="store_true", dest="checkbuild", default=False,
                  help="check if packages need to be build and schedule builds if possible")
  #  parser.add_option("--build",
  #                action="store_true", dest="build", default=False,
  #                help="schedule builds for not-built packages")
    parser.add_option("--cruft-report",
                  action="store_true", dest="cruft_report", default=False,
                  help="report jobs without matching package")
    parser.add_option("--cruft-remove",
                  action="store_true", dest="cruft_remove", default=False,
                  help="delete jobs without matching source package.")

    (options, args) = parser.parse_args()

    if options.update:
        sync = BuildJobUpdater()
        #sync.scheduleBuilds = options.build
        sync.sync_packages_all()
    elif options.checkbuild:
        sync = BuildJobUpdater()
        sync.checkbuild()
    elif options.cruft_report:
        sync = BuildJobUpdater()
        sync.cruft_report()
    elif options.cruft_remove:
        sync = BuildJobUpdater()
        sync.cruft_remove()
    else:
        print("Run with -h for a list of available command-line options!")

if __name__ == "__main__":
    os.environ['LANG'] = 'C'
    os.environ['LC_ALL'] = 'C'
    main()
