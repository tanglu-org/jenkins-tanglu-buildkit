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
from apt_pkg import TagFile, TagSection, version_compare

def noEpoch(version):
    v = version
    if ":" in v:
        return v[v.index(":")+1:]
    else:
        return v

class PackageInfo():
    def __init__(self, pkgname, pkgversion, dist, component, archs):
        self.pkgname = pkgname
        self.version = pkgversion
        self.dist = dist
        self.component = component
        self.archs = archs
        self.info = ""
        self.build_depends = ""
        self.build_conflicts = ""
        self.installedArchs = []
        self.archs_str = ""

    def getVersionNoEpoch(self):
        return noEpoch(self.version)

    def __str__(self):
        return "PackageInfo_Obj: name: %s | version: %s | dist: %s | comp.: %s | archs: %s" % (self.pkgname, self.version, self.dist, self.component, self.archs)

class PackageInfoRetriever():
    def __init__(self):
        parser = SafeConfigParser()
        parser.read(['/etc/jenkins/jenkins-dak.conf', 'jenkins-dak.conf'])
        path = parser.get('Archive', 'path')
        self._archivePath = path
        self._archiveComponents = parser.get('Archive', 'components').split (" ")
        self._archiveDists = parser.get('Archive', 'dists').split (" ")
        self._supportedArchs = parser.get('Archive', 'archs').split (" ")
        self._supportedArchs += ["all"]

    def _set_pkg_installed_for_arch(self, dirname, pkg, binaryName):
        fileExt = "deb"
        if "-udeb" in binaryName:
            fileExt = "udeb"

        for arch in self._supportedArchs:
            if arch in pkg.installedArchs:
                continue
            binaryPkgName = "%s_%s_%s.%s" % (binaryName, pkg.getVersionNoEpoch(), arch, fileExt)
            expectedPackagePath = self._archivePath + "/%s/%s" % (dirname, binaryPkgName)

            if os.path.isfile(expectedPackagePath):
                pkg.installedArchs.append(arch)


    def get_packages_for(self, dist, component):
        source_path = self._archivePath + "/dists/%s/%s/source/Sources.gz" % (dist, component)
        f = gzip.open(source_path, 'rb')
        tagf = TagFile (f)
        packageList = []
        for section in tagf:
            # don't even try to build source-only packages
            if section.get('Extra-Source-Only', 'no') == 'yes':
                pass

            archs = section['Architecture']
            binaries = section['Binary']
            pkgversion = section['Version']
            pkgname = section['Package']
            pkg = PackageInfo(pkgname, pkgversion, dist, component, archs)

            pkg.info = ("Package: %s\nBinary Packages: %s\nMaintainer: %s\nCo-Maintainers: %s\nVCS-Browser: %s" %
                        (pkgname, binaries, section['Maintainer'], section.get('Uploaders', 'Nobody'), section.get('Vcs-Browser', 'None set')))

            # values needed for build-dependency solving
            pkg.build_depends = section.get['Build-Depends', '']
            pkg.build_conflicts = section.get['Build-Conflicts', '']
            pkg.archs_str = archs

            # we check if one of the arch-binaries exists. if it does, we consider the package built for this architecture
            # FIXME: This does not work well for binNMUed packages! Implement a possible solution later.
            # (at time, a version-check prevents packages from being built twice)
            if "," in binaries:
                binaryPkgs = binaries.split(', ')
            else:
                binaryPkgs = [binaries]
            for binaryName in binaryPkgs:
                self._set_pkg_installed_for_arch(section["Directory"], pkg, binaryName)
                #if (pkg.installedArchs != ["all"]) or (len(binaryPkgs) <= 0:

            packageList += [pkg]

        return packageList

    def get_all_packages(self):
        packageList = []
        for dist in self._archiveDists:
            for comp in self._archiveComponents:
                packageList += self.get_packages_for(dist, comp)
        return packageList

    def package_list_to_dict(self, pkg_list):
        pkg_dict = {}
        for pkg in pkg_list:
            # replace it only if the version of the new item is higher (required to handle epoch bumps and new uploads)
            if pkg.pkgname in pkg_dict:
                regVersion = pkg_dict[pkg.pkgname]
                compare = version_compare(regVersion, pkg.version)
                if compare >= 0:
                    continue
            pkg_dict[pkg.name] = pkg
        return pkg_dict
