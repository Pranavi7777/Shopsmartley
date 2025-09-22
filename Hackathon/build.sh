#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Create a temporary Python script to run create_tables
cat <<EOF > setup_db.py
from aplications import create_tables
print("Creating database tables...")
create_tables()
print("Database tables created successfully.")
EOF

# Run the script
python setup_db.py