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
import logging
import time

class UploadService(dbus.service.Object):
    def __init__(self):
        bus_name = dbus.service.BusName('org.debian.PackageUpload', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/org/debian/packageupload')

        self._uploadQueue = deque()
        self._uploadRunning = False
        GLib.timeout_add_seconds(60, self._check_for_inactivity)
        self._last_action_timestamp = time.time()
        self._loop = GObject.MainLoop()
        self._loop.run()

    def _check_for_inactivity(self):
        logger.debug("Checking for inactivity")
        timestamp = self._last_action_timestamp
        if (not self._uploadRunning and
                not GLib.main_context_default().pending() and
                time.time() - timestamp > (4 * 60) and
                not self.queue):
            logger.info("Quitting due to inactivity")
            self._loop.quit()
            return False
        return True

    def _popenAndCall(self, popenArgs, onExit):
        def runInThread(popenArgs, onExit):
            self._uploadRunning = True
            proc = subprocess.Popen(popenArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.wait()
            self._uploadRunning = False
            if proc.returncode != 0:
                print("Upload failed!")
                logger.warning("Upload failed (cmd: %s): %s" % (popenArgs, proc.communicate()[0]))
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
        self._last_action_timestamp = time.time()
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
    logger = logging.getLogger('upload-service')
    hdlr = logging.FileHandler('/srv/buildd/logs/upload-service.log')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.WARNING)

    DBusGMainLoop(set_as_default=True)
    service = UploadService()
