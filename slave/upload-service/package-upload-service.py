#!/usr/bin/python
# Copyright (C) 2013 Matthias Klumpp <mak@debian.org>
#
# Licensed under the GNU General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GObject, GLib
from collections import deque
import subprocess
import multiprocessing

class UploadService(dbus.service.Object):
    def __init__(self):
        bus_name = dbus.service.BusName('org.debian.PackageUpload', bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, '/org/debian/packageupload')

        self._uploadQueue = deque()
        self._uploadRunning = False
        #self._timer = GLib.Timer()

    def _popenAndCall(self, popenArgs, onExit):
        def runInThread(popenArgs, onExit):
            self._uploadRunning = True
            print("OPEN")
            proc = subprocess.Popen(popenArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.wait()
            self._uploadRunning = False
            print(proc.communicate())
            onExit()
            return
        thread = multiprocessing.Process(target=runInThread, args=(popenArgs, onExit))
        thread.start()
        # returns immediately after the thread starts
        return thread

    def _run_package_upload(self):
        if self._uploadRunning:
            print("One upload running at time.")
            return
        if len(self._uploadQueue) <= 0:
            return
        item = self._uploadQueue.popleft()
        print("Doing upload of: %s" % (item[1]))
        self._popenAndCall(['dput', item[0], item[1]], self._run_package_upload)


    @dbus.service.method('org.debian.PackageUpload')
    def get_description(self):
        return "Debian package upload service"

    @dbus.service.method('org.debian.PackageUpload')
    def trigger_upload (self, location, changes_path):
        self._uploadQueue.append([location, changes_path])
        print("Upload to %s triggered: %s" % (location, changes_path))
        self._run_package_upload()


if __name__ == "__main__":
    DBusGMainLoop(set_as_default=True)
    service = UploadService()
    loop = GObject.MainLoop()
    loop.run()
