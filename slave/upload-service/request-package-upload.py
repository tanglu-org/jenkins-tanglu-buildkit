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
import sys

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("ERROR: RequestPackageUpload: Invalid numer of arguments received!")
        exit(1)
    u_location = sys.argv[1]
    u_changesfile = sys.argv[2]
    print (u_location + " ## " + u_changesfile)
    bus = dbus.SessionBus()
    uploadservice = bus.get_object('org.debian.PackageUpload', '/org/debian/packageupload')
    trigger_upload = uploadservice.get_dbus_method('trigger_upload', 'org.debian.PackageUpload')
    trigger_upload(u_location, u_changesfile)
