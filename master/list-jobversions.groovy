// we need this script to gerenate a jobname:package-version matching very fast
// if there is a better way to do this, please implement it! :)

hudsonInstance = hudson.model.Hudson.instance

allItems = hudsonInstance.items
pkgJobs = allItems.findAll{job -> job.name.contains("pkg+")}

for (job in pkgJobs) {
  lastBuild = job.getLastBuild();
  if (lastBuild == null)
    // catch case when job has never been built so far
    println job.name + " 0.0#0"
  else
    println lastBuild
}
