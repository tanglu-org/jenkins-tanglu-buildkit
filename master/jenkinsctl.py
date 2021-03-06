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
import json
import urllib2
import urllib
import base64
from ConfigParser import SafeConfigParser
from apt_pkg import version_compare
from xml.sax.saxutils import escape
from collections import Counter
from pkginfo import noEpoch

class JenkinsBridge:
    def __init__(self):
        parser = SafeConfigParser()
        parser.read(['/etc/jenkins/jenkins-dak.conf', 'jenkins-dak.conf'])
        url = parser.get('Jenkins', 'url')
        self._jenkinsUrl = url
        if parser.has_option('Jenkins', 'private_key'):
            keyfile = parser.get('Jenkins', 'private_key')
        self._authToken = parser.get('Jenkins', 'token')

        # check if we have a usable connection to Jenkins (authenticated as dak)
        self.jenkins_cmd = ["jenkins-cli", "-s", url]
        code, outputLines = self._run_simple_jenkins_command(["who-am-i"], False)
        if (code != 0) or (not outputLines.startswith("Authenticated as: dak")):
            raise Exception("Unable to authenticate against Jenkins!\nOutput: %s" % (outputLines))

        # load our job template now, so we can access it faster
        self._jobTemplateStr = open(os.path.dirname(os.path.realpath(__file__)) + '/templates/pkg-job-template.xml', 'r').read()

        # fetch all currently registered jobs and their versions (by using a small Groovy script - hackish, but it works)
        # this is only needed because the package-job name does not store an epoch
        scriptPath = os.path.dirname(os.path.realpath(__file__)) + "/list-jobversions.groovy"
        lines = self._run_simple_jenkins_command(["groovy", scriptPath])
        rawPkgJobLines = lines.splitlines ()

        # we use this to count how often a package is registered in the pool
        self.packagesDBCounter = Counter()

        self.currentJobs = []
        self.jobInfoDict = {}
        for jobln in rawPkgJobLines:
           pkgjob_parts = jobln.strip ().split (" ", 1)
           if len (pkgjob_parts) > 1:
               # map job name to package-name, version and arch
               pkgVersion = pkgjob_parts[1].strip ()
               jobName = pkgjob_parts[0].strip ()
               pkgName = self._get_pkgname_from_jobname(jobName)
               # add job to list of registered jobs
               self.currentJobs += [jobName]

               # replace it only if the version of the new item is higher (required to handle epoch bumps and new uploads)
               if pkgName in self.jobInfoDict:
                   regVersion = self.jobInfoDict[pkgName][0]
                   compare = version_compare(regVersion, pkgVersion)
                   if compare >= 0:
                       continue
               jobIdentifier = pkgName
               self.jobInfoDict[jobIdentifier] = [pkgVersion, jobName]

        self.queuedJobs = []
        self._refresh_jobqueue_info()

    def _run_simple_jenkins_command(self, options, failOnError=True):
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

    def _refresh_jobqueue_info(self):
        scriptPath = os.path.dirname(os.path.realpath(__file__)) + "/list-queued-jobs.groovy"
        lines = self._run_simple_jenkins_command(["groovy", scriptPath])
        rawPkgJobLines = lines.splitlines ()
        for jobln in rawPkgJobLines:
            if self.get_version_from_job_name(jobln) != "":
                self.queuedJobs.append(jobln)


    def _create_job_template(self, pkgname, pkgversion, component, distro, architectures, info=""):
        # Create the information html
        info_html = info.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        if component != "main":
            info_html = info_html + "<br/><br/><strong>This package is part of the <em>%s</em> department!</strong>" % (component)
        info_html = info_html + "<br/><br/>"

        archs_xml = ""
        for arch in architectures:
            archs_xml += "<string>arch-" + arch + "</string>\n"

        if archs_xml == "":
            raise Exception("Job for %s %s on %s has no architectures! This should never happen!" % (pkgname, pkgversion, distro))

        jobStr = self._jobTemplateStr.replace("{{architectures_xml}}", archs_xml)
        jobStr = jobStr.replace("{{distroname}}", escape(distro))
        jobStr = jobStr.replace("{{component}}", component)
        jobStr = jobStr.replace("{{pkgname}}", pkgname)
        jobStr = jobStr.replace("{{pkgversion}}", escape(pkgversion))
        jobStr = jobStr.replace("{{info}}", escape(info_html))

        return jobStr

    def get_job_name(self, pkgname, version):
        # generate generic job name
        return "pkg+%s_%s" % (pkgname, noEpoch(version))

    def get_version_from_job_name(self, jobName):
        s = jobName[::-1]
        s = s[:s.index("_")]

        return s[::-1]

    def _get_pkgname_from_jobname(self, jobName):
        s = jobName[jobName.index("+")+1:]
        s = s[:s.index("_")]

        return s

    def _get_last_build_status(self, jobName):
        try:
            jenkinsStream = urllib2.urlopen(self._jenkinsUrl + "/job/%s/lastBuild/api/json" % (jobName))
        except urllib2.HTTPError, e:
            if e.code == 404:
                # maybe the package has never been built?
                # return a fake build-id, so a build gets scheduled
                return False, "0#0"
            print("URL Error: " + str(e.code))
            print("Unable to get build status.")
            print("(job name [" + jobName + "] probably wrong)")
            sys.exit(2)
        try:
            buildStatusJson = json.load( jenkinsStream )
        except:
            print("Failed to parse json")
            sys.exit(3)

        if buildStatusJson.has_key("fullDisplayName"):
            displayName = buildStatusJson["fullDisplayName"]
            parts = displayName.split (" ", 1)
            buildVersion = parts[1].strip()
        else:
            return False, "0#0"

        if buildStatusJson.has_key("building"):
            return True, buildVersion
        if buildStatusJson.has_key("result"):
            if (buildStatusJson["result"] != "SUCCESS"):
                return False, buildVersion
            else:
                return True, buildVersion

    def _rename_job(self, currentName, newName):
        # TODO: We can't rename a job with a running build - fix that somehow by skipping that job until it was built,
        # or better abort the build, rename the job and restart it.
        qs = urllib.urlencode({'newName': newName})
        rename_job_url = self._jenkinsUrl + "/job/%s/doRename?%s" % (currentName, qs)

        request = urllib2.Request(url=rename_job_url, data='')
        base64string = base64.encodestring('%s:%s' % ("dak", self._authToken)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        try:
            result = urllib2.urlopen(request).read()
        except urllib2.HTTPError, e:
            print("Error post data %s" % rename_job_url)
            raise e

    def set_registered_packages_list(self, packagesList):
        self.packagesDBCounter = Counter(packagesList)

    def _create_job(self, jobName, jobXML):
        p = subprocess.Popen(self.jenkins_cmd + ["create-job", jobName], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = p.communicate(input=jobXML)
        if p.returncode is not 0:
            raise Exception("Failed adding %s:\n%s" % (jobName, output))

    def _update_job(self, jobName, jobXML):
        p = subprocess.Popen(self.jenkins_cmd + ["update-job", jobName], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = p.communicate(input=jobXML)
        if p.returncode is not 0:
            raise Exception("Failed updating %s:\n%s" % (jobName, output))

    def delete_job(self, jobName):
        code, outputLines = self._run_simple_jenkins_command(["delete-job", jobName], False)
        if (code != 0):
            raise Exception("Unable to delete job!\n%s" % (outputLines))

    def create_update_job(self, pkgname, pkgversion, component, distro, architectures, info="", alwaysRename=True):
        # get name of the job
        jobName = self.get_job_name(pkgname, noEpoch(pkgversion))

        jobXML = self._create_job_template(pkgname, pkgversion, component, distro, architectures, info)
        jobIdentifier = pkgname

        if not jobName in self.currentJobs:
            if ((alwaysRename) or (self.packagesDBCounter[pkgname] == 1)) and (jobIdentifier in self.jobInfoDict.keys()):
                compare = version_compare(self.jobInfoDict[jobIdentifier][0], pkgversion)
                if compare >= 0:
                    # the version already registered for build is higher or equal to the new one - no need for an update
                    return False

                # we get the old job name, rename it and update it - by doing this, we preserve the existing job statistics
                oldJobName = self.jobInfoDict[jobIdentifier][1]
                self._rename_job(oldJobName, jobName)
                self.currentJobs.remove(oldJobName)

                # NOTE: Ugly workaround to make the cannot-rename-job-while-building issue less annoying
                try:
                    self._update_job(jobName, jobXML)
                except:
                    print("*** Can not update job (maybe it is building?): %s ***" % (jobName))
                    return False

                self.currentJobs.append(jobName)
                self.jobInfoDict[jobIdentifier] = [pkgversion, jobName]
                print("*** Successfully updated job: %s ***" % (jobName))
            else:
                self._create_job(jobName, jobXML)

                self.currentJobs += [jobName]
                self.jobInfoDict[jobIdentifier] = [pkgversion, jobName]
                print("*** Successfully created new job: %s ***" % (jobName))
        else:
            # we might have an epoch bump!
            if (jobIdentifier in self.jobInfoDict.keys()):
                currentPkgVersion = self.jobInfoDict[jobIdentifier][0]
                compare = version_compare(currentPkgVersion, pkgversion)
                if compare >= 0:
                    # the version already registered for build is higher or equal to the new one - we skip this package
                    return False
                # check for epoch bump/higher version for some reason
                success, buildVersion = self._get_last_build_status(jobName)
                lastVersionBuilt = buildVersion[:buildVersion.index('#')]
                compare = version_compare(lastVersionBuilt, pkgversion)
                if compare >= 0:
                    # apparently no epoch bump
                    return False

                print("INFO: Updating existing job, epoch bump found: %s, %s -> %s" % (jobName, currentPkgVersion, pkgversion))
                self._update_job(jobName, jobXML)
                self.jobInfoDict[jobIdentifier] = [pkgversion, jobName]

        return True

    def schedule_build_if_not_failed(self, pkgname, pkgversion):
        versionNoEpoch = noEpoch(pkgversion)
        jobName = self.get_job_name(pkgname, versionNoEpoch)
        # if this job is already queued, we don't have to do anything
        if jobName in self.queuedJobs:
            return
        # if Jenkins doesn't know the job, skip it
        if not jobName in self.currentJobs:
            print("INFO: Skipping build request for %s" % (jobName))
            return

        success, buildVersion = self._get_last_build_status(jobName)

        # get the last version of the package which has been built (buildVersion without parts after the '#')
        lastVersionBuilt = buildVersion[:buildVersion.index('#')]
        compare = version_compare(lastVersionBuilt, pkgversion)

        if (compare < 0):
            print("*** Requesting build of %s ***" % (jobName))
            self._run_simple_jenkins_command(["build", jobName])
        # since lastBuildStatus returns success for builds in progress and returns the correct build number,
        # we are done here - if versions are equal, the last build was either successful or has failed.

    def checkbuild(self):
        scriptPath = os.path.dirname(os.path.realpath(__file__)) + "/checkbuild/checkbuild.groovy"

        p = subprocess.Popen(self.jenkins_cmd + ["groovy", scriptPath], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while(True):
          retcode = p.poll()
          sys.stdout.write(p.stdout.readline())
          if (retcode is not None):
              break
