/* Copyright (C) 2013 Matthias Klumpp <mak@debian.org>
*
* Licensed under the GNU General Public License Version 3
*
* This program is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* This program is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

// determine which packages should be built amd issue build requests

import jenkins.*
import jenkins.model.*
import hudson.*
import hudson.model.*
jenkinsInstance = hudson.model.Hudson.instance

archList = ["all", "amd64", "i386"];

def perform_buildcheck (dist, comp, package_name, arch) {
	buildConfig = project.getItem("Architecture=arch-${arch}");
	if (buildConfig == null) {
		println("ERROR: Build configuration for architecture ${arch} was NULL!");
		return false;
	}

	// check current job version
	jobVersion = "0";
	project.getBuildWrappersList().each() {
		cl -> if (cl.getClass().equals(org.jenkinsci.plugins.buildnamesetter.BuildNameSetter))
		jobVersion = cl.template.replace('#${BUILD_NUMBER}', "");
	}
	lastVersionBuilt = "Unknown";
	build = buildConfig.getLastBuild()
	if (build != null) {
		lastVersionBuilt = build.getDisplayName();
		lastVersionBuilt = lastVersionBuilt.substring(0, lastVersionBuilt.indexOf('#'));
	}

	// we only need to run a build-check if we haven't already built the current version
	if (jobVersion == lastVersionBuilt)
		return false;

	// check if we should build this package (if all dependencies are in place)
	def command = """package-buildcheck -c ${dist} ${comp} ${package_name} ${arch}""";
	def proc = command.execute();
	proc.waitFor();

	// prepare change of the project notes (in description of the matrix axes)
	desc = buildConfig.getDescription();
	if ((desc == null) || (desc.isEmpty()))
		desc = "Build configuration of ${package_name} on ${arch}<br/>";

	sep_idx = desc.indexOf('<br/>----');
	if (sep_idx > 0)
		desc = desc.substring(0, sep_idx);

	// prepare change of main project description
	pdesc = project.getDescription();
	p_sep_idx = pdesc.indexOf('<br/>----');
	if (p_sep_idx > 0)
		pdesc = pdesc.substring(0, p_sep_idx);

	// check for the different return codes
	build_project = false;
	code = proc.exitValue();
	if (code == 0) {
		desc = desc + '<br/>----<br/><br/>There are no notes about this build.'
		build_project = true;

		// reset the main description, if necessary (only reset it if no arch is in DEPWAIT anymore)
		if ((pdesc.indexOf("Status: DEPWAIT (${arch})") >= 0) || (pdesc.indexOf("Status: DEPWAIT") <= 0)) {
			pdesc = pdesc + '<br/>----<br/><br>There are no notes about this package.';
			project.setDescription(pdesc);
		}
	} else if (code == 8) {
		// we are waiting for depedencies
		desc = desc + '<br/>----<br/>' + proc.in.text.replaceAll('\n', '<br/>');
		// add an information to the main project description too

		pdesc = pdesc + '<br/>----<br/><br/>Status: DEPWAIT (${arch})';
		project.setDescription(pdesc);

		build_project = false;
	} else {
		desc = desc + '<br/>----<br/><br>There are no notes about this build.';
	}

	buildConfig.setDescription(desc);

	return build_project;
}

def check_and_schedule_job (project) {
	masterDesc = project.getDescription();

	def match = masterDesc =~ "Identifier:(.*)<br/>";
	if (!match.find()) {
		println("ATTENTION: No data found for job ${project.getName()}! Skipping it.");
		return;
	}

	projectData = match[0][1];
	pieces = projectData.stripMargin().split();
	println("Using project data: ${pieces}");

	dist = pieces[0];
	comp = pieces[1];
	pkg_name = pieces[2];

	projectData = masterDesc.substring(masterDesc.indexOf('Identifier:'), );

	for (arch in archList) {
		if (project.getItem("Architecture=arch-${arch}") == null)
			continue;
		if (perform_buildcheck (dist, comp, pkg_name, arch)) {
			println("Going to build ${pkg_name} on ${arch}");

			//mbuild = new matrix.MatrixBuild(project);
			raction = new net.praqma.jenkins.plugin.reloaded.RebuildAction();
			//raction.setBaseBuildNumber(mbuild.getNumber());
			raction.addConfiguration( matrix.Combination.fromString("Architecture=arch-"+arch), true);

			Hudson.getInstance().getQueue().schedule(project,
									8,
									raction);

			//buildConfig.scheduleBuild2(8,
			//                           new Cause.RemoteCause("archive-master", "New version of this package is buildable."),
			//                         raction);
		}
	}
}

//********//
// Main

allItems = jenkinsInstance.items;

for (item in allItems) {
	project = null;
	if (item.getName().startsWith("pkg+"))
		project = item;
	else
		continue;

	if (!project.getClass().equals(matrix.MatrixProject)) {
		println("ATTENTION!!! Detected project ${project.getName()} which is no matrix project! We cannot continue.");
		continue;
	}

	check_and_schedule_job(project);
}
