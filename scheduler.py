import os,time
from astronomy import create_app
from astronomy.tasks import fetch_and_store_astronomy
app=create_app()
if __name__=="__main__":
    location=os.environ.get("CURRENT_LOCATION")
    print(f"Starting astronomy scheduler for {location or 'configured location'}")
    while True:
        with app.app_context():
            if fetch_and_store_astronomy(): print("Astronomy data collected")
        time.sleep(int(os.environ.get("ASTRONOMY_INTERVAL_SECONDS","3600")))
