"""Generate a sample demonstration dataset for AERIS AI."""
import os
import csv
import random
import math

ROWS = 500
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw", "dataset.csv")

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

random.seed(42)

rows = []
for i in range(ROWS):
    hour = (i * 2) % 24
    diurnal = math.sin((hour - 6) * math.pi / 12)

    temp = 28.0 + 4.0 * diurnal + random.gauss(0, 1.2)
    temp = round(max(22, min(38, temp)), 2)

    hum = 72.0 - 12.0 * diurnal + random.gauss(0, 3.0)
    hum = round(max(35, min(98, hum)), 2)

    pres = 1010.0 + 3.0 * math.sin(i * 0.02) + random.gauss(0, 1.5)
    pres = round(max(995, min(1025, pres)), 2)

    # ~40% of samples should be RAIN
    if random.random() < 0.4:
        # Rain scenario: higher humidity, lower pressure, higher rain sensor
        hum = round(min(98, hum + random.uniform(10, 20)), 2)
        pres = round(max(995, pres - random.uniform(2, 8)), 2)
        rain_raw = round(random.uniform(50, 100), 2)
        rain = "RAIN"
    else:
        # No rain scenario
        hum = round(max(35, hum - random.uniform(0, 10)), 2)
        rain_raw = round(random.uniform(0, 40), 2)
        rain = "NO_RAIN"

    rows.append([temp, hum, pres, rain_raw, rain])

with open(OUTPUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["temperature", "humidity", "pressure", "rain_sensor", "rain"])
    w.writerows(rows)

print(f"Generated {ROWS} rows -> {OUTPUT}")
