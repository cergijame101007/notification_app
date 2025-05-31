from models import SessionLocal, Temperature
import json
from pathlib import Path

DATA_FILE = Path("temperature_data.json")

try:
    raw_data = json.loads(DATA_FILE.read_text())
except Exception as e:
    print(f"JSON reading error: {e}")
    exit(1)

session = SessionLocal()

data_count = 0
for entry in raw_data:
    try:
        temp = Temperature(            
            timestamp=entry["timestamp"],
            temperature=entry["temperature"]
        )
        session.add(temp)
        data_count += 1
    except Exception as e:
        print(f"Data registration error: {entry} → {e}")

try:
    session.commit()
    print(f"{data_count} data imported into the database")
except Exception as e:
    print(f"Commit error: {e}")
    session.rollback()
finally:
    session.close()
