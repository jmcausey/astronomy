#!/usr/bin/env python3
import time

from astronomy import create_app
from astronomy.tasks import run_due_astronomy_jobs

app = create_app()

if __name__ == "__main__":
    print("Starting astronomy scheduler")
    while True:
        with app.app_context():
            results = run_due_astronomy_jobs()
            if results:
                print(f"Ran astronomy jobs: {results}")
        time.sleep(30)
