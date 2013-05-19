hudsonInstance = hudson.model.Hudson.instance

allItems = hudsonInstance.items
pkgJobs = allItems.findAll{job -> job.name.contains("pkg+")}

for (job in pkgJobs) {
	build = job.getLastBuild()
	if (build != null) {
		if (build.result != Result.SUCCESS)
			job.delete()
	}
}
