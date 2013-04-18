// small script to list all queued package jobs
import hudson.model.*

def q = Jenkins.instance.queue
q.items.findAll { it.task.name.startsWith('pkg+') }.each { print(it.task.name+"\n") }
