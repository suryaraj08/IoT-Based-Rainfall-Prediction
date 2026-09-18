# AERIS AI — Rainfall Prediction & Weather Intelligence System

AI-based environmental monitoring and rainfall prediction system using ESP32 IoT sensors and a supervised Random Forest classifier.

## Objective

AERIS AI receives weather measurements from an ESP32-based sensor system, validates and processes the data, feeds features into a trained Random Forest model, and presents live sensor readings, rainfall probability, historical trends, and analytics in a premium web dashboard.

## System Architecture

```
Sensors (DHT22 / BMP280 / Rain Sensor)
  -> ESP32 Microcontroller
  -> Serial / USB (115200 baud)
  -> Python Backend (Flask)
  -> Data Validation & Preprocessing
  -> Random Forest ML Model
  -> Rainfall Classification / Probability
  -> Web Dashboard (HTML / CSS / JS)
```

## Hardware

| Component | Purpose |
|-----------|---------|
| ESP32 | Microcontroller, serial communication |
| DHT22 | Temperature and humidity |
| BMP280 / BME280 | Atmospheric pressure |
| Rain Sensor Module | Rain detection (analog) |
| OLED Display | Local display (optional) |

### Wiring Overview

- DHT22 DATA -> GPIO4
- BMP280 SDA -> GPIO21, SCL -> GPIO22
- Rain Sensor AOUT -> GPIO34
- OLED SDA -> GPIO21, SCL -> GPIO22 (shared I2C bus)

## Software Requirements

- Python 3.9+
- Arduino IDE (for ESP32 firmware)

## Installation

```bash
# Clone or download the project
cd AERIS-AI

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Generate sample dataset (optional, for demo)
python generate_sample_data.py

# Train the model
python model/train_model.py

# Start the application
python app.py
```

Open browser: `http://localhost:5000`

## Simulation Mode (No Hardware)

The application starts in **Simulation Mode** by default. All sensor values are generated with realistic smooth drift. Every simulated value is clearly labeled `SIMULATED`.

## Live ESP32 Mode

1. Flash `hardware/esp32/firmware.ino` to your ESP32
2. Connect ESP32 via USB
3. Close Arduino Serial Monitor (only one program can use the COM port)
4. In the dashboard, go to Settings and switch to **Live ESP32** mode
5. Set the correct COM port (e.g., `COM3`, `COM5`, etc.)
6. Default baud rate: 115200

### Serial Data Format

CSV: `temperature,humidity,pressure,rain_sensor`

Example: `31.40,79.20,1005.80,420`

## Dataset Format

CSV with columns:

| Column | Description |
|--------|-------------|
| temperature | Celsius |
| humidity | Percentage |
| pressure | hPa |
| rain_sensor | Raw or normalized sensor value |
| rain | Target: `RAIN` or `NO_RAIN` |

## ML Training

```bash
python model/train_model.py --dataset data/raw/dataset.csv
```

Or use the **Train Model** button in the dashboard Model section.

### Training Outputs

- `model/rain_model.pkl` — trained model
- `model/metadata.json` — metrics, feature list, hyperparameters

## Evaluation

```bash
python model/evaluate.py
```

## Model Details

- **Algorithm**: RandomForestClassifier
- **Trees**: 200 (configurable)
- **Features**: temperature, humidity, pressure, rain_sensor
- **Target**: RAIN / NO_RAIN
- **Class handling**: balanced weights for imbalanced datasets

## Configuration

### config.py

Key settings:

- `SERIAL_PORT` — default `COM9` (override via `AERIS_SERIAL_PORT` env var)
- `BAUD_RATE` — default `115200`
- `UPDATE_INTERVAL` — 1.5 seconds
- `RAIN_CALIBRATION` — dry/wet values, normalize toggle
- `RF_PARAMS` — RandomForest hyperparameters

### Environment Variables

```bash
set AERIS_SERIAL_PORT=COM5
set AERIS_BAUD_RATE=115200
```

### JSON Config (Optional)

Create `aeris_config.json` in the project root:

```json
{
  "serial_port": "COM5",
  "baud_rate": 115200,
  "update_interval": 2.0
}
```

## API Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Dashboard |
| GET | `/api/status` | System status |
| GET | `/api/sensors` | Current sensor readings |
| GET | `/api/prediction` | Latest prediction |
| GET | `/api/history` | Observation history |
| GET | `/api/history/download` | Download CSV |
| GET | `/api/model` | Model info and metadata |
| GET | `/api/model/metrics` | Training metrics |
| GET | `/api/model/feature_importance` | Feature importance |
| POST | `/api/mode` | Set mode (simulation/live) |
| POST | `/api/calibration` | Update rain calibration |
| POST | `/api/train` | Train model |
| POST | `/api/settings` | Update settings |

## Troubleshooting

**ESP32 not detected:**
- Check USB connection
- Verify correct COM port in Settings
- Close Arduino Serial Monitor
- Install ESP32 USB drivers if needed

**Model not training:**
- Ensure dataset CSV exists at specified path
- Check column names match: temperature, humidity, pressure, rain_sensor, rain
- Check for missing or invalid values

**Simulation shows NaN:**
- Refresh the page
- Check browser console for API errors

## Future Improvements

- Wind speed / direction sensors
- UV and light sensors
- Calibrated rain gauge (mm)
- External weather API integration
- Multi-location monitoring
- Alerts and notifications
- Mobile-responsive PWA
- Automated retraining jobs
- Anomaly detection
- Time-series forecasting

## Limitations

- Prototype system for academic demonstration
- Model accuracy depends on training dataset quality
- Geographic relevance: trained on specific regional data
- Sensor calibration affects prediction quality
- Weather is inherently variable
- Predictions are probabilistic, not certainties
- Not a replacement for professional meteorological services

## License

Academic project. For educational use.
