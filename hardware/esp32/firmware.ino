/*
 * AERIS AI — ESP32 Firmware Template
 * 
 * Reads: DHT22 (temp/humidity), BMP280 (pressure), Rain Sensor (analog)
 * Output: CSV via Serial at 115200 baud
 * Format: temperature,humidity,pressure,rain_sensor
 * 
 * Libraries required:
 *   - DHT sensor library (Adafruit)
 *   - Adafruit BMP280 Library
 *   - Wire (built-in)
 * 
 * Wiring:
 *   DHT22  -> GPIO4
 *   BMP280 -> I2C (SDA=GPIO21, SCL=GPIO22)
 *   Rain   -> GPIO34 (analog input)
 *   OLED   -> I2C (optional, same bus as BMP280)
 */

#include <Wire.h>
#include <DHT.h>
#include <Adafruit_BMP280.h>

// ---- Pin Config ----
#define DHT_PIN        4
#define DHT_TYPE       DHT22
#define RAIN_PIN       34
#define SERIAL_BAUD    115200
#define READ_INTERVAL  2000  // ms

// ---- Objects ----
DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_BMP280 bmp;

// ---- Rain Sensor Calibration ----
// Adjust based on your module:
//   Dry air value (no water) -> e.g. 4095 (ADC max on ESP32)
//   Wet value (water on sensor) -> e.g. 1500
const int RAIN_DRY = 4095;
const int RAIN_WET = 1500;

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(1000);

  // DHT22
  dht.begin();

  // BMP280
  if (!bmp.begin(0x76)) {
    // Try alternate address
    if (!bmp.begin(0x77)) {
      Serial.println("BMP280 not found");
    }
  }

  // Rain sensor
  pinMode(RAIN_PIN, INPUT);

  // ADC config for ESP32
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
}

void loop() {
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  float pressure = bmp.readPressure() / 100.0F;  // hPa
  int rainRaw = analogRead(RAIN_PIN);

  // Handle DHT failure
  if (isnan(temperature)) temperature = -999.0;
  if (isnan(humidity)) humidity = -999.0;

  // Handle BMP failure
  if (pressure < 0) pressure = -999.0;

  // Output CSV
  Serial.print(temperature, 2);
  Serial.print(",");
  Serial.print(humidity, 2);
  Serial.print(",");
  Serial.print(pressure, 2);
  Serial.print(",");
  Serial.println(rainRaw);

  delay(READ_INTERVAL);
}
