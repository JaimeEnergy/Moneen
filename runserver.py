"""
This script runs the FlaskWebProject1 application using a development server.
"""

# important note
import os
from os import environ
from moneen import app

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5555))
    app.secret_key = os.urandom(24)
    app.run(host='0.0.0.0', port=port)
