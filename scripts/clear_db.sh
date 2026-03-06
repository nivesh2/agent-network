#!/usr/bin/env bash

# Clear the Agent Network SQLite database

DB_FILE="board.db"

if [ -f "$DB_FILE" ]; then
    rm "$DB_FILE"
    rm -f "${DB_FILE}-wal" "${DB_FILE}-shm"
    echo "✅ Swarm board cleared ($DB_FILE)."
else
    echo "ℹ️ No board.db found. Already clean."
fi

echo "You can now run main.py or restart the Streamlit dashboard for a fresh start."
