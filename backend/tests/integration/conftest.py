import os
import shutil
import tempfile
import pytest

@pytest.fixture
def real_repo_fixture():
    """
    Creates a real temporary repository on disk with actual legacy python code
    for the migration engine to parse, read, and write to.
    """
    temp_dir = tempfile.mkdtemp(prefix="codemigration_integration_")
    
    # Create a legacy Flask application file
    main_py_path = os.path.join(temp_dir, "main.py")
    legacy_code = """
from flask import Flask, jsonify
import requests

app = Flask(__name__)

@app.route("/users")
def get_users():
    # Synchronous blocking call
    response = requests.get("https://jsonplaceholder.typicode.com/users")
    return jsonify(response.json())

if __name__ == "__main__":
    app.run(port=5000)
"""
    with open(main_py_path, "w") as f:
        f.write(legacy_code)
        
    yield temp_dir
    
    # Teardown
    shutil.rmtree(temp_dir, ignore_errors=True)
