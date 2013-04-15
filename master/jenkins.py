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
import subprocess
from ConfigParser import SafeConfigParser
from apt_pkg import version_compare

class JenkinsBridge:
    def __init__(self):
        parser = SafeConfigParser()
        parser.read('jenkins-dak.conf')
        url = parser.get('Jenkins', 'url')
        if parser.has_option('Jenkins', 'private_key'):
            keyfile = parser.get('Jenkins', 'private_key')

        # check if we have a usable connection to Jenkins (authenticated as dak)
        self.jenkins_cmd = ["jenkins-cli", "-s", url]
        code, outputLines = self.runSimpleJenkinsCommand(["who-am-i"], False)
        if (code != 0) or (not outputLines.startswith("Authenticated as: dak")):
            raise Exception("Unable to authenticate against Jenkins!\nOutput: %s" % (outputLines))
        
        # load our job template now, so we can access it faster
        self._jobTemplateStr = open('templates/pkg-job-template.xml', 'r').read()

        # fetch all currently registered jobs and their versions (by using a small Groovy script - hackish, but it works)
        scriptPath = os.path.dirname(os.path.realpath(__file__)) + "/list-jobversions.groovy" 
        lines = self.runSimpleJenkinsCommand(["groovy", scriptPath])
        rawPkgJobLines = lines.splitlines ()
        
        self.currentJobs = {}
        for jobln in rawPkgJobLines:
           pkgjob_parts = jobln.strip ().split (" ", 1)
           if len (pkgjob_parts) > 1:
               # map package-job name to version
               self.currentJobs[pkgjob_parts[0].strip ()] = pkgjob_parts[1].strip ()

    def runSimpleJenkinsCommand(self, options, failOnError=True):
        p = subprocess.Popen(self.jenkins_cmd + options, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        resLines = ""
        while(True):
          retcode = p.poll()
          line = p.stdout.readline()
          resLines += line
          if (retcode is not None):
              break
        if failOnError:
            if p.returncode is not 0:
                raise Exception(resLines)
            return resLines

        return p.returncode, resLines

    def _createJobTemplate(self, pkgname, pkgversion, component, distro, architecture):
        jobStr = self._jobTemplateStr.replace("{{architecture}}", architecture)
        jobStr = jobStr.replace("{{distroname}}", distro)
        jobStr = jobStr.replace("{{component}}", component)
        jobStr = jobStr.replace("{{pkgname}}", pkgname)
        jobStr = jobStr.replace("{{pkgversion}}", pkgversion)

        return jobStr

    def createUpdateJob(self, pkgname, pkgversion, component, distro, architecture, scheduleBuild=True):
        # generate generic job name
        jobName = "pkg+%s_%s" % (pkgname, architecture)
        jobXML = self._createJobTemplate(pkgname, pkgversion, component, distro, architecture)

        if jobName in self.currentJobs.keys():
            compare = version_compare(self.currentJobs[jobName], pkgversion)
            if compare >= 0:
                # the version already registered for build is higher or equal to the new one - we skip this package
                return
                
            p = subprocess.Popen(self.jenkins_cmd + ["update-job", jobName], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = p.communicate(input=jobXML)
            if p.returncode is not 0:
                raise Exception("Failed updating %s:\n%s" % (jobName, output))

            print("*** Successfully updated job: %s ***" % (jobName))
            # shedule build of changed package
            if scheduleBuild:
                self._runSimpleJenkinsCommand(["build", jobName])
        else:
            p = subprocess.Popen(self.jenkins_cmd + ["create-job", jobName], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = p.communicate(input=jobXML)
            if p.returncode is not 0:
                raise Exception("Failed adding %s:\n%s" % (jobName, output))

            self.currentJobs[jobName] = pkgversion
            print("*** Successfully created new job: %s ***" % (jobName))
            # shedule build of the new package
            if scheduleBuild:
                self._runSimpleJenkinsCommand(["build", jobName])
