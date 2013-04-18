// we need this script to gerenate a jobname:package-version matching very fast
// (relatively ugly, but fast - better ideas for version-handling are welcome!)

hudsonInstance = hudson.model.Hudson.instance

allItems = hudsonInstance.items
pkgJobs = allItems.findAll{job -> job.name.contains("pkg+")}

for (job in pkgJobs) {
  jobName = job.name;
  jobVersion = "0";
  job.getBuildWrappersList().each() {
    cl -> if (cl.getClass().equals(org.jenkinsci.plugins.buildnamesetter.BuildNameSetter))
      jobVersion = cl.template.replace('#${BUILD_NUMBER}', "");
  }
  println(jobName + " " + jobVersion);
}
