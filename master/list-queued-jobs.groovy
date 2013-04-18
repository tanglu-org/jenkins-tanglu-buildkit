// small script to list all queued package jobs
import hudson.model.*

def q = hudson.model.Hudson.instance.queue
q.items.findAll { it.task.name.startsWith('pkg+') }.each { print(it.task.name+"\n") }
