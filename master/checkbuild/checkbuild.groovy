// determine of a package should be built

jenkinsInstance = hudson.model.Hudson.instance

archList = ["amd64", "i386"];

def perform_buildcheck (dist, comp, package_name, arch) {
	// check if we should build this package
	def command = """package-buildcheck -c ${dist} ${comp} ${package_name} ${arch}""";
	def proc = command.execute();
	proc.waitFor();

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

	// prepare change of the project notes (in description)
	desc = buildConfig.getDescription();
	if ((desc == null) || (desc.isEmpty()))
		desc = "Build configuration of ${package_name} on ${arch}<br/>";

	sep_idx = desc.indexOf('<br/>----');
	if (sep_idx > 0)
		desc = desc.substring(0, sep_idx)

	// check for the different return codes
	build_project = false;
	code = proc.exitValue();
	if (code == 0) {
		println("Rebuild!");
		desc = desc + '<br/>----<br/><br/>No notes about this build exist.'
		build_project = true;
	} else if (code == 8) {
		// we are waiting for depedencies
		desc = desc + '<br/>----<br/>' + proc.in.text.replaceAll('\n', '<br/>');
		build_project = false;
	} else {
		desc = desc + '<br/>----<br/><br>No notes about this build exist.'
	}

	buildConfig.setDescription(desc);

	return build_project;
}

def check_and_schedule_job (project) {
	masterDesc = project.getDescription();
	def pattern = "Identifier:(.*)<br/>";
	if (masterDesc !=~ pattern) {
		println("ATTENTION: No data found for job ${project.getName()}! Skipping it.");
		return;
	}
	def match = masterDesc =~ pattern;
	projectData = match[0][1];
	pieces = projectData.stripMargin().split();
	println("Using project data: ${pieces}");

	dist = pieces[0];
	comp = pieces[1];
	pkg_name = pieces[2];

	projectData = masterDesc.substring(masterDesc.indexOf('Identifier:'), );

		for (arch in archList) {
			if (perform_buildcheck (dist, comp, pkg_name, arch)) {
				println("Going to build gnome-packagekit on ${arch}");

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
