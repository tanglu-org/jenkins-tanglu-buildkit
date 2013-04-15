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
from daklib.dbconn import Component, DBConn, OverrideType, Suite

def getPackages(suite):
    session = DBConn().session()

    q = session.execute("""
SELECT b.package, b.version, a.arch_string, su.suite_name, c.name, m.name
  FROM binaries b, architecture a, suite su, bin_associations ba,
       files f, files_archive_map af, component c, maintainer m
 WHERE b.package = :package AND a.id = b.architecture AND su.id = ba.suite
   AND b.id = ba.bin AND b.file = f.id AND af.file_id = f.id AND su.archive_id = af.archive_id
   AND af.component_id = c.id AND b.maintainer = m.id %s %s %s
""" % (con_suites, con_architectures, con_bintype), {'package': package})
        ql = q.fetchall()
        if check_source:
            q = session.execute("""
SELECT s.source, s.version, 'source', su.suite_name, c.name, m.name
  FROM source s, suite su, src_associations sa, files f, files_archive_map af,
       component c, maintainer m
 WHERE s.source = :package AND su.id = sa.suite AND s.id = sa.source
   AND s.file = f.id AND af.file_id = f.id AND af.archive_id = su.archive_id AND af.component_id = c.id
   AND s.maintainer = m.id %s
""" % (con_suites), {'package': package})
            if not Options["Architecture"] or con_architectures:
                ql.extend(q.fetchall())
            else:
                ql = q.fetchall()
        d = {}
        highver = {}
        for i in ql:
            results += 1
            (pkg, version, architecture, suite, component, maintainer) = i
            if component != "main":
                suite = "%s/%s" % (suite, component)
            if not d.has_key(pkg):
                d[pkg] = {}
            highver.setdefault(pkg,"")
            if not d[pkg].has_key(version):
                d[pkg][version] = {}
                if apt_pkg.version_compare(version, highver[pkg]) > 0:
                    highver[pkg] = version
            if not d[pkg][version].has_key(suite):
                d[pkg][version][suite] = []
            d[pkg][version][suite].append(architecture)

        packages = d.keys()
        packages.sort()
        for pkg in packages:
            versions = d[pkg].keys()
            versions.sort(apt_pkg.version_compare)
            for version in versions:
                suites = d[pkg][version].keys()
                suites.sort()
                for suite in suites:
                    arches = d[pkg][version][suite]
                    arches.sort(utils.arch_compare_sw)
                    if Options["Format"] == "": #normal
                        sys.stdout.write("%10s | %10s | %13s | " % (pkg, version, suite))
                        sys.stdout.write(", ".join(arches))
                        sys.stdout.write('\n')
                    elif Options["Format"] in [ "control-suite", "heidi" ]:
                        for arch in arches:
                            sys.stdout.write("%s %s %s\n" % (pkg, version, arch))
            if Options["GreaterOrEqual"]:
                print "\n%s (>= %s)" % (pkg, highver[pkg])
            if Options["GreaterThan"]:
                print "\n%s (>> %s)" % (pkg, highver[pkg])

