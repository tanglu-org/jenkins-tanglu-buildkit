#!/bin/sh
set -e
script_dir=`dirname $0`

# Run the maintenance script in our Jenkins instance
jenkins-cli -s http://localhost:8094 groovy $script_dir/checkbuild.groovy
