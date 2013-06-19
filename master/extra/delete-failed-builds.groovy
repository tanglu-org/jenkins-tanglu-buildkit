hudsonInstance = hudson.model.Hudson.instance

allItems = hudsonInstance.items;
pkgJobs = allItems.findAll{job -> job.name.contains("pkg+")}

for (job in pkgJobs) {
	builds = job.getBuilds();
	for (build in builds) {
		if (build != null) {
			if ((build.result != Result.SUCCESS) && (build.result != null)) {
				println("Delete: ${job.getName()} >> ${build.getDisplayName()}");
				build.delete();
			}
		}
	}
}
