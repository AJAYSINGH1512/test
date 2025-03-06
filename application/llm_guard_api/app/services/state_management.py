import uuid
import json
from datetime import datetime

STATE_FILE = "state.json"

def load_state():
    try:
        with open(STATE_FILE, "r+") as file:
            return json.loads(file.read())
    except FileNotFoundError:
        return {}
    
def save_state(state):
    with open(STATE_FILE, "w") as file:
        file.write(json.dumps(state))

def generate_unique_job_id(existing_uuids):
    while True:
        new_job_id = str(uuid.uuid4())
        if new_job_id not in existing_uuids:
            return new_job_id