#!/bin/bash
# Double-click launcher for macOS: runs start.sh from this folder.
exec /bin/bash "$(dirname "$0")/start.sh"
