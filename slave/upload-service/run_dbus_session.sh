#!/bin/bash
if test -z "$DBUS_SESSION_BUS_ADDRESS" ; then
        eval `dbus-launch --sh-syntax`
        echo "D-Bus per-session daemon address is:"
        echo "$DBUS_SESSION_BUS_ADDRESS"
fi
