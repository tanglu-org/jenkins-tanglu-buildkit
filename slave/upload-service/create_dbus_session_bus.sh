# Search processes for the dbus-daemon session bus PID

PID=$(ps | grep "dbus-daemon" | grep "session" | grep "user" | cut -d' ' -f3)

# Figure out who is logging in

WHOAMI=$(whoami)

# If there is no PID for a session bus then start a session bus
# and grab the resulting pid

if [[ "${PID}" == "" ]]; then
    echo "No existing dbus session bus... Starting one now."
    eval $(dbus-launch --sh-syntax)
    export DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS
    export DBUS_SESSION_BUS_PID=$DBUS_SESSION_BUS_PID
    if [[ "${WHOAMI}" == "user" ]]; then
        echo "user user logging in.. creating ~/.dbus-session-bus-address"
        echo ${DBUS_SESSION_BUS_ADDRESS} > $HOME/.dbus-session-bus-address
        chmod 777 ~/.dbus-session-bus-address
    else
        # If the root user logs in don't attempt to read the dbus
        echo "Root user logging in.. not exporting DBus SessionBus environment"
    fi
    PID=$DBUS_SESSION_BUS_PID
else
    # We only care about user user loggin in with regard to the session bus
    if [[ "${WHOAMI}" == "user" ]]; then
        echo "Existing DBUS session bus found..."
        echo "Reading ~/dbus-session-bus-address file:"
        export DBUS_SESSION_BUS_ADDRESS=$(cat $HOME/.dbus-session-bus-address)
    else
        # If the root user logs in don't attempt to read the dbus
        echo "Root user logging in.. not exporting DBus SessionBus environment"
    fi
fi
