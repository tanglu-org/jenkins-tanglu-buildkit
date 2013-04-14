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

class JenkinsBridge:
    def __init__(self):
        parser = SafeConfigParser()
        parser.read('jenkins-dak.conf')
        url = parser.get('Jenkins', 'url')
        if parser.has_option('Jenkins', 'private_key'):
            keyfile = parser.get('Jenkins', 'private_key')
        
        self.jenkins_cmd = ["jenkins-cli", "-s", url]
        code, outputLines = self.runSimpleJenkinsCommand(["who-am-i"], False)
        if (code != 0) or (not outputLines.startswith("Authenticated as: dak")):
            raise Exception("Unable to authenticate against Jenkins!\nOutput: %s" % (outputLines))
        
        self.currentJobs = []
        lines = self.runSimpleJenkinsCommand(["list-jobs"])
        for jobName in lines:
            if jobName.startswith("pkg+"):
                self.currentJobs += [jobName]
        
        
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
        templateStr = open('templates/pkg-job-template.xml', 'r').read()
        
        jobStr = templateStr.replace("{{architecture}}", architecture)
        jobStr = jobStr.replace("{{distroname}}", distro)
        jobStr = jobStr.replace("{{component}}", component)
        jobStr = jobStr.replace("{{pkgname}}", pkgname)
        jobStr = jobStr.replace("{{pkgversion}}", pkgversion)
        
        return jobStr
    
    def createUpdateJob(self, pkgname, pkgversion, component, distro, architecture):
        # generate generic job name
        jobName = "pkg+%s_%s" % (pkgname, architecture)
        
        if jobName in self.currentJobs:
            print("TODO: Update job")
        else:
            jobXML = self._createJobTemplate(pkgname, pkgversion, component, distro, architecture)
            p = Popen(self.jenkins_cmd + ["create-job", jobName], stdout=PIPE, stdin=PIPE, stderr=STDOUT)
            output = p.communicate(input=jobXML)
            if p.returncode is not 0:
                raise Exception(output)
            
            self.currentJobs += [jobName]
            print("*** Successfully created new job: %s ***" % (jobName))

          