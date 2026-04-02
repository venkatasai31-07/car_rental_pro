import sys
import os

# Ensure Vercel can find the 'backend' package
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "backend"))

# Import the Flask app
from backend.app import app

# Vercel looks for a callable named "app" by default.
