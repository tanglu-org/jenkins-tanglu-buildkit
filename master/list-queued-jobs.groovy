// small script to list all queued package jobs

def q = hudson.model.Hudson.instance.queue
buildItem = q.items.findAll{it.task.name.startsWith('pkg+')}

for (item in buildItem) {
    println(item.task.name)
}
