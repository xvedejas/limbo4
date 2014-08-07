#!/usr/bin/bash
# Get today's date
DATE=${date -I}

# Set a timeout (in ms) for sql operations to finish, then safely backup the
# database to a new file.
sqlite3 limbo4.db <<EOF
.timeout 20000
.backup limbo4-${DATE}.db
EOF

# Routines to copy limbo4-backup.db to other machines.
USER=undef
HOST=undef
DIR=under

scp limbo4-backup.db ${USER}@${HOST}:${DIR}