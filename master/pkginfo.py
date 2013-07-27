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
import re
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
        self.pkgname = pkgname.strip()
        self.version = pkgversion.strip()
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
        export_path = parser.get('Archive', 'export_dir')
        self._archivePath = path
        self._archiveComponents = parser.get('Archive', 'components').split (" ")
        self._archiveDists = parser.get('Archive', 'dists').split (" ")
        self._supportedArchs = parser.get('Archive', 'archs').split (" ")
        self._supportedArchs.append("all")
        self._installedPkgs = {}

        # to speed up source-fetching and to kill packages without maintainer immediately, we include the pkg-maintainer
        # mapping, to find out active source/binary packages (currently, only source packages are filtered)
        self._activePackages = []
        for line in open(export_path + "/SourceMaintainers"):
           pkg_m = line.strip ().split (" ", 1)
           if len (pkg_m) > 1:
               self._activePackages.append(pkg_m[0].strip())

    def _set_pkg_installed_for_arch(self, dirname, pkg, binaryName):
        fileExt = "deb"
        for arch in self._supportedArchs:
            if arch in pkg.installedArchs:
                continue

            # check if package file is in the archive (faster than checking the caches)
            binaryExists = False
            for fileExt in ["deb", "udeb"]:
                binaryPkgName = "%s_%s_%s.%s" % (binaryName, pkg.getVersionNoEpoch(), arch, fileExt)
                expectedPackagePath = self._archivePath + "/%s/%s" % (dirname, binaryPkgName)

                if os.path.isfile(expectedPackagePath):
                    binaryExists = True
                    break

            if binaryExists:
                pkg.installedArchs.append(arch)
                continue

            # if package file was not found, ensure that it is missing by checking the caches
            # (this also catches binNMUs and other weird things)
            pkg_id = "%s_%s" % (binaryName, arch)
            if pkg_id in self._installedPkgs:
                existing_pkgversion = self._installedPkgs[pkg_id]
                if pkg.version == existing_pkgversion:
                    pkg.installedArchs.append(arch)
                    continue
                # try to catch binNMUed packages from Debian
                if re.match(re.escape(pkg.version) + "\+b\d$", existing_pkgversion):
                    pkg.installedArchs.append(arch)
                    continue


    def get_packages_for(self, dist, component):
        # create a cache of all installed packages on the different architectures
        self._build_installed_pkgs_cache(dist, component)
        source_path = self._archivePath + "/dists/%s/%s/source/Sources.gz" % (dist, component)
        f = gzip.open(source_path, 'rb')
        tagf = TagFile (f)
        packageList = []
        for section in tagf:
            # don't even try to build source-only packages
            if section.get('Extra-Source-Only', 'no') == 'yes':
                continue

            pkgname = section['Package']
            if not pkgname in self._activePackages:
                continue
            archs_str = section['Architecture']
            binaries = section['Binary']
            pkgversion = section['Version']

            if ' ' in archs_str:
                archs = archs_str.split(' ')
            else:
                archs = [archs_str]
            # remove duplicate archs from list
            # this is very important, because we otherwise will add duplicate build requests in Jenkins
            archs = list(set(archs))

            pkg = PackageInfo(pkgname, pkgversion, dist, component, archs)

            pkg.info = ("Package: %s\nBinary Packages: %s\nMaintainer: %s\nCo-Maintainers: %s\nVCS-Browser: %s" %
                        (pkgname, binaries, section['Maintainer'], section.get('Uploaders', 'Nobody'), section.get('Vcs-Browser', 'None set')))

            # values needed for build-dependency solving
            pkg.build_depends = section.get('Build-Depends', '')
            pkg.build_conflicts = section.get('Build-Conflicts', '')
            pkg.archs_str = archs_str

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

    def _build_installed_pkgs_cache(self, dist, component):
        for arch in self._supportedArchs:
            source_path = self._archivePath + "/dists/%s/%s/binary-%s/Packages.gz" % (dist, component, arch)
            f = gzip.open(source_path, 'rb')
            tagf = TagFile (f)
            for section in tagf:
                # make sure we have the right arch (closes bug in installed-detection)
                if section['Architecture'] != arch:
                    continue
                pkgversion = section['Version']
                pkgname = section['Package']
                pkid = "%s_%s" % (pkgname, arch)
                if pkid in self._installedPkgs:
                   regVersion = self._installedPkgs[pkid]
                   compare = version_compare(regVersion, pkgversion)
                   if compare >= 0:
                       continue
                self._installedPkgs[pkid] = pkgversion

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
                regVersion = pkg_dict[pkg.pkgname].version
                compare = version_compare(regVersion, pkg.version)
                if compare >= 0:
                    continue
            pkg_dict[pkg.pkgname] = pkg
        return pkg_dict
