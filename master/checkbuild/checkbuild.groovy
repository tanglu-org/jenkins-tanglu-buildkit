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

NEEDSBUILD_EXPORT_DIR = '/srv/dak/export/needsbuild';
archList = ["all", "amd64", "i386"];

// load Java library to parse Yaml files
def classLoader = ClassLoader.systemClassLoader
while (classLoader.parent) {
	classLoader = classLoader.parent;

}
classLoader.addURL(new URL("file:///usr/share/java/snakeyaml.jar"))
Yaml = Class.forName("org.yaml.snakeyaml.Yaml").newInstance();
//

// get the build queue
queue = Hudson.getInstance().getQueue();
qitems = queue.getItems();
// we cache all currently running stuff, so nothing gets scheduled twice
scheduled_jobs = [];
for (qitem in qitems) {
	if (qitem.task.getClass().equals(matrix.MatrixConfiguration)) {
    		job = qitem.task;
      	 	scheduled_jobs.add(job.getParent().getName());
 	}
}

for (Computer computer : Hudson.getInstance().getComputers()) {
	for (Executor executor : computer.getExecutors()) {
		currentExecutable = executor.getCurrentExecutable();
		if (currentExecutable != null) {
			job = currentExecutable.getParent().getOwnerTask();
			if (job.getClass().equals(matrix.MatrixConfiguration))
				scheduled_jobs.add(job.getParent().getName());
		}
	}
}

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

	// check if package should be built using the exported Yaml data
	// check if package should be built using the exported XML data
	def ymlData = Yaml.load(new FileInputStream(new File("${NEEDSBUILD_EXPORT_DIR}/depwait-${dist}-${comp}_${arch}.yml")));
	if (ymlData['report'] == null) {
		println ("ERROR: Invalid Yaml input!");
		return false;
	}

	pkgNode = null;
	for (p in ymlData.report) {
		if (p.package == ('src%3a' + package_name)) {
			pkgNode = p;
		}
	}

	dependency_wait = false;
	build_possible = false;
	depends_hint = "";

	if (pkgNode == null) {
		//println ("Unable to find ${package_name} (${dist}, ${comp}, ${arch}) in exported depwait info. Scheduling build.");
		build_possible = true;
	} else {
		dependency_wait = true;
		depends_hint = Yaml.dump(pkgNode.reasons).replace(" ", "&nbsp;");
	}

	// prepare change of the project notes (in description of the matrix axes)
	desc = buildConfig.getDescription();
	if ((desc == null) || (desc.isEmpty()))
		desc = "Build configuration of ${package_name} on ${arch}<br/>";

	sep_idx = desc.indexOf('<br/>----');
	if (sep_idx > 0)
		desc = desc.substring(0, sep_idx);

	// prepare change of main project description
	pdesc = project.getDescription();
	pdesc_complete = pdesc;
	p_sep_idx = pdesc.indexOf('<br/>----');
	if (p_sep_idx > 0)
		pdesc = pdesc.substring(0, p_sep_idx);

	// check for the different return codes
	build_project = false;

	if (build_possible) {
		// we can build the project!
		desc = desc + '<br/>----<br/><br/>There are no notes about this build.'
		build_project = true;

		// reset the main description, if necessary (only reset it if no arch is in DEPWAIT anymore)
		if (pdesc_complete.indexOf("Status: DEPWAIT (${arch})") >= 0)
			pdesc = pdesc.replace("Status: DEPWAIT (${arch})", "");
 		if (pdesc_complete.indexOf("Status: DEPWAIT") <= 0)
			pdesc = pdesc + '<br/>----<br/><br>There are no notes about this package.';
		project.setDescription(pdesc);

	} else if (dependency_wait) {
		// we are waiting for depedencies
		desc = desc + "<br/>----<br/>" + depends_hint.replaceAll('\n', "<br/>");
		// add an information to the main project description too

		if (pdesc_complete.indexOf("Status: DEPWAIT") >= 0) {
			if (pdesc_complete.indexOf("Status: DEPWAIT (${arch})") < 0) {
				// apparently the other arch is in depwait too, so add ours now
				pdesc = pdesc_complete + "<br/>Status: DEPWAIT (${arch})";
			}
		} else {
			pdesc = pdesc + "<br/>----<br/><br/>Status: DEPWAIT (${arch})";
		}
		project.setDescription(pdesc);
		println("Job ${project.getName()} is in depwait on ${arch}.");

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
	//! println("Using project data: ${pieces}");

	dist = pieces[0];
	comp = pieces[1];
	pkg_name = pieces[2];

	projectArchs = [];
	buildArchs = [];

	for (arch in archList) {
		if (project.getItem("Architecture=arch-${arch}") == null)
			continue;
		projectArchs.add(arch);
		if (perform_buildcheck (dist, comp, pkg_name, arch)) {
			jobName = project.getName();
			if (jobName in scheduled_jobs) {
				println("Skipping ${pkg_name} (on ${arch}), a package job is already in queue.");
				continue;
			} else {

			}

			// add arch to to-be-built archlist
			buildArchs.add(arch);
		}
	}

	if (buildArchs.equals(projectArchs)) {
		// this means we can build the whole project!
		println("Going to build ${pkg_name} (complete rebuild)");
		//! queue.schedule(project, 8);
	} else {
		for (arch in buildArchs) {
			println("Going to build ${pkg_name} on ${arch}");
			//mbuild = new matrix.MatrixBuild(project);
			raction = new net.praqma.jenkins.plugin.reloaded.RebuildAction();
			//raction.setBaseBuildNumber(mbuild.getNumber());
			raction.addConfiguration( matrix.Combination.fromString("Architecture=arch-"+arch), true);

			//! queue.schedule(project, 8, raction);

			//buildConfig.scheduleBuild2(8,
			//                           new Cause.RemoteCause("archive-master", "New version of this package is buildable."),
			//                         raction);
		}
	}
}

//********//
// Main

allItems = jenkinsInstance.items;

nonbuilt_pkgs = [];
new File(NEEDSBUILD_EXPORT_DIR + '/needsbuild.list').eachLine { line ->
	pkgid = line;
	sep_idx = pkgid.indexOf(' ');
	if (sep_idx > 0)
		pkgid = pkgid.substring(0, sep_idx);
	nonbuilt_pkgs.add("pkg+" + pkgid);
}
new File(NEEDSBUILD_EXPORT_DIR + '/needsbuild-contrib.list').eachLine { line ->
	pkgid = line;
	sep_idx = pkgid.indexOf(' ');
	if (sep_idx > 0)
		pkgid = pkgid.substring(0, sep_idx);
	nonbuilt_pkgs.add("pkg+" + pkgid);
}
new File(NEEDSBUILD_EXPORT_DIR + '/needsbuild-non-free.list').eachLine { line ->
	pkgid = line;
	sep_idx = pkgid.indexOf(' ');
	if (sep_idx > 0)
		pkgid = pkgid.substring(0, sep_idx);
	nonbuilt_pkgs.add("pkg+" + pkgid);
}

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

	if (project.getName() in nonbuilt_pkgs)
		check_and_schedule_job(project);
}
