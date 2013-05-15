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
from apt_pkg import TagFile
from optparse import OptionParser
import tempfile
from ConfigParser import SafeConfigParser

from pkginfo import *

class BuildCheck:
    def __init__(self):
        self._pkginfo = PackageInfoRetriever()
        parser = SafeConfigParser()
        parser.read(['/etc/jenkins/jenkins-dak.conf', 'jenkins-dak.conf'])
        path = parser.get('Archive', 'path')
        self._archive_path = path

    def _run_edos_builddebcheck(self, dist, comp, pkg, arch):
        # write fake package-info for edos-builddebcheck
        f = tempfile.NamedTemporaryFile(mode ='w+t', prefix="edos-bdc-pkg")
        f.write('Package: %s\n' % (pkg.pkgname))
        f.write('Version: %s\n' % (pkg.version))
        f.write('Depends: %s\n' % (pkg.build_depends))
        f.write('Conflicts: %s\n' % (pkg.build_conflicts))
        f.write('Architecture: %s\n' % (pkg.arch))
        f.flush()

        archive_binary_index_path = self._archive_path + "/dists/%s/%s/binary-%s/Packages.gz" % (dist, comp, arch)
        print("DEBUG: using %s and %s" % (f.name, archive_binary_index_path))

        proc = subprocess.Popen(["edos-builddebcheck", archive_binary_index_path, f.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.wait()
        stdout, stderr = proc.communicate()
        output = "%s\n%s" % (stdout, stderr)
        if (proc.returncode != 0) or ("FAILED" in output):
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
        src_pkg = pkg[package_name]

        if not arch in src_pkg.installedArchs:
            ret, info = _run_edos_builddebcheck(dist, component, src_pkg, arch)
            if not ret:
                print("Package '%s' has unsatisfiable dependencies:\n%s" % (package_name, info))
                # return code 8, which means dependency-wait
                return 8
            else:
                # yay, we can build the package!
                return 0

        # apparently, we don't need to build the package
        return 1

def main():
    # init Apt, we need it later
    apt_pkg.init()

    parser = OptionParser()
    parser.add_option("-c", "--check",
                  action="store_true", dest="check", default=False,
                  help="check if the given package name can be built (returns 1 if not, 8 if dep-wait, 0 if build should be scheduled)")

    (options, args) = parser.parse_args()

    if options.check:
        if len(args) != 2:
            print("Invalid number of arguments (need dist, component, package-name, arch)")
            sys.exit(6)
        dist = args[0]
        comp = args[1]
        package_name = args[2]
        arch = args[3]
        bc = BuildCheck()
        code = bc.check_build(dist, comp, package_name, arch)
        sys.exit(code)
    else:
        print("Run with -h for a list of available command-line options!")

if __name__ == "__main__":
    os.environ['LANG'] = 'C'
    os.environ['LC_ALL'] = 'C'
    main()
