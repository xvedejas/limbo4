#!/usr/bin/bash

sqlite3 limbo4.db <<EOF
.timeout 20000
.backup limbo4-backup.db
EOF

# Add here routines to copy limbo4-backup.db to other machines.
