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
import sys
import subprocess
import yaml
from optparse import OptionParser
from ConfigParser import SafeConfigParser

from pkginfo import *

class BuildCheck:
    def __init__(self):
        self._pkginfo = PackageInfoRetriever()
        parser = SafeConfigParser()
        parser.read(['/etc/jenkins/jenkins-dak.conf', 'jenkins-dak.conf'])
        path = parser.get('Archive', 'path')
        self._archive_path = path

    def _run_dose_builddebcheck(self, dist, comp, arch):
        archive_indices = []
        archive_binary_index_path = self._archive_path + "/dists/%s/%s/binary-%s/Packages.gz" % (dist, comp, arch)
        archive_indices.append(archive_binary_index_path)
        if arch == "all":
            # if arch is all, we feed the solver with a binary architecture as example, to solve dependencies on arch-specific stuff
            archive_binary_index_path_arch = self._archive_path + "/dists/%s/%s/binary-amd64/Packages.gz" % (dist, comp)
            archive_indices.append(archive_binary_index_path_arch)
        else:
            # any architecture canb also depend on arch:all stuff, so we add it to the loop
            archive_binary_index_path_all = self._archive_path + "/dists/%s/%s/binary-all/Packages.gz" % (dist, comp)
            archive_indices.append(archive_binary_index_path_all)
        # append the corresponding sources information
        archive_source_index_path = self._archive_path + "/dists/%s/%s/source/Sources.gz" % (dist, comp)
        archive_indices.append(archive_source_index_path)

        dose_cmd = ["dose-builddebcheck", "--quiet", "-e", "-f", "--summary", "--deb-native-arch=%s" % (arch)]
        # add the archive index files
        dose_cmd.extend(archive_indices)

        proc = subprocess.Popen(dose_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        output = stdout
        if (proc.returncode != 0):
            return False, output
        return True, output

    def check_build(self, dist, component, package_name, arch):
        pkgList = self._pkginfo.get_packages_for(dist, component)
        pkg_dict = self._pkginfo.package_list_to_dict(pkgList)
        # NOTE: The dictionary always contains the most recent pkg version
        # This means there is no need for any additional version checks :)

        if package_name not in pkg_dict:
            print("Package %s was not found in %s!" % (package_name, dist))
            return 1
        src_pkg = pkg_dict[package_name]

        if not arch in src_pkg.installedArchs:
            ret, info = self._run_dose_builddebcheck(dist, component, arch)
            doc = yaml.load(info)
            if doc['report'] is not None:
                for p in doc['report']:
                    if p['package'] == ('src%3a' + package_name):
                        print("Package '%s (%s)' has unsatisfiable dependencies on %s:\n%s" % (package_name, p['version'], arch, yaml.dump(p['reasons'])))
                        # return code 8, which means dependency-wait
                        return 8

                # yay, we can build the package!
                return 0

        # apparently, we don't need to build the package
        return 1

    def get_package_states_yaml(self, dist, component, arch):
        ret, info = self._run_dose_builddebcheck(dist, component, arch)

        return info

def main():
    # init Apt, we need it later
    apt_pkg.init()

    parser = OptionParser()
    parser.add_option("-c", "--check",
                  action="store_true", dest="check", default=False,
                  help="check if the given package name can be built (returns 1 if not, 8 if dep-wait, 0 if build should be scheduled)")

    (options, args) = parser.parse_args()

    if options.check:
        if len(args) != 4:
            print("Invalid number of arguments (need dist, component, package-name, arch)")
            sys.exit(6)
        dist = args[0]
        comp = args[1]
        package_name = args[2]
        arch = args[3]
        bc = BuildCheck()
        code = bc.check_build(dist, comp, package_name, arch)
        if code == 1:
            print("There is no need to build this package.")
        if code == 0:
            print("We should (re)build this package.")
        sys.exit(code)
    else:
        print("Run with -h for a list of available command-line options!")

if __name__ == "__main__":
    os.environ['LANG'] = 'C'
    os.environ['LC_ALL'] = 'C'
    main()