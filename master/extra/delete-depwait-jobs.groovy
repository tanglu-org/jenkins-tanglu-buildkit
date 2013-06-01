hudsonInstance = hudson.model.Hudson.instance

allItems = hudsonInstance.items
pkgJobs = allItems.findAll{job -> job.name.contains("pkg+")}

depwait_jobs_count = 0;
for (job in pkgJobs) {
	pdesc = job.getDescription();
	if (pdesc.indexOf("Status: DEPWAIT") >= 0) {
		depwait_jobs_count++;
		println("Delete: ${job.getDisplayName()}");
		job.delete();
	}
}

println ("Number of deleted jobs in depwait: ${depwait_jobs_count}");
