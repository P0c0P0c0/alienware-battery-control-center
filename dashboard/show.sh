#!/bin/sh
if systemctl --user is-active --quiet bat07-widget.service; then
    exec /usr/bin/python3 -B "$(dirname -- "$0")/widget.py" show
fi
exec systemctl --user start bat07-widget.service
