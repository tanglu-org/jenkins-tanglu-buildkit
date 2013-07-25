hudsonInstance = hudson.model.Hudson.instance

allItems = hudsonInstance.items
pkgJobs = allItems.findAll{job -> job.name.contains("pkg+")}

for (job in pkgJobs) {
	build = job.getLastBuild()
	if (build != null) {
		if ((job.isBuildable() == true) && (build.result != Result.SUCCESS)) {
			println("Delete: ${job.getName()}");
			job.delete();
		}
	}
}
