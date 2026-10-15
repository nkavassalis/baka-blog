#!/usr/bin/env bash
# Start the blog editor in the background if it is not already running.
# Safe to call from anywhere, any number of times: an flock guard prevents
# two concurrent starts, and a pgrep guard prevents duplicate live servers.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"

exec 9>/tmp/baka-editor-start.lock
flock -n 9 || exit 0            # another starter holds the lock; not our turn

if pgrep -f "^$DIR/.venv/bin/python $DIR/app.py$" >/dev/null 2>&1; then
  exit 0                        # editor already running
fi

cd "$DIR"
setsid nohup "$DIR/.venv/bin/python" "$DIR/app.py" >> /tmp/baka-editor.log 2>&1 &
echo "blog editor started (log: /tmp/baka-editor.log)"
