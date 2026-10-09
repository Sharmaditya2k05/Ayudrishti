/*
 * AyuDrishti wearable firmware -- ESP32
 *
 * Streams heart rate, SpO2, galvanic skin response and motion over Bluetooth
 * Low Energy to the AyuDrishti app, which forwards the readings to the
 * backend for physiological context during a session.
 *
 * This device is OPTIONAL. AyuDrishti's camera-based assessment loop is fully
 * functional with no wearable connected, and nothing in the app blocks on
 * these readings.
 *
 * IMPORTANT: This is a wellness accessory built from hobbyist sensors. It is
 * not a medical device, it is not certified, and its readings must never be
 * used for diagnosis or clinical decisions.
 *
 * Hardware
 *   ESP32 dev board (ESP32-WROOM-32 or similar)
 *   MAX30102  pulse oximeter / heart rate  -> I2C  (SDA 21, SCL 22)
 *   MPU6050   6-axis accelerometer + gyro  -> I2C  (same bus, addr 0x68)
 *   SSD1306   128x64 OLED (live display)    -> I2C  (same bus, addr 0x3C)
 *   GSR sensor (Grove or equivalent)       -> ADC1 channel (GPIO 34)
 *
 * Libraries (Arduino Library Manager)
 *   "SparkFun MAX3010x Pulse and Proximity Sensor Library"
 *   "Adafruit MPU6050" + "Adafruit Unified Sensor"
 *   "Adafruit SSD1306" + "Adafruit GFX Library"
 *   ESP32 BLE Arduino (bundled with the ESP32 board package)
 *
 * BLE contract
 *   Service          6e400001-b5a3-f393-e0a9-e50e24dcca9e
 *   Telemetry (TX)   6e400003-b5a3-f393-e0a9-e50e24dcca9e  notify, JSON
 *   Command  (RX)    6e400002-b5a3-f393-e0a9-e50e24dcca9e  write
 *
 * Telemetry payload (one JSON object per notification, ~1 Hz):
 *   {"hr":72.4,"spo2":97.1,"gsr":8.42,"motion":1.02,"t":123456,"ok":true}
 *
 *   hr      beats per minute, -1 when no stable pulse is detected
 *   spo2    percent, -1 when unavailable
 *   gsr     microsiemens
 *   motion  acceleration magnitude in g (1.0 at rest)
 *   t       milliseconds since boot
 *   ok      false when the finger is off the sensor, so the app can discard
 *           the sample rather than treating noise as a physiological event
 */

#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#include "MAX30105.h"
#include "heartRate.h"
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

#define DEVICE_NAME        "AyuDrishti-Band"
#define SERVICE_UUID       "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define CHAR_TELEMETRY_UUID "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
#define CHAR_COMMAND_UUID   "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

#define GSR_PIN            34      // ADC1_CH6; ADC2 is unusable while WiFi/BLE is active
#define SAMPLE_INTERVAL_MS 1000    // telemetry cadence
#define FINGER_THRESHOLD   50000   // MAX30102 IR reading below this = no finger

#define OLED_WIDTH         128
#define OLED_HEIGHT        64
#define OLED_ADDR          0x3C    // common SSD1306 I2C address (some are 0x3D)

// Heart rate is averaged over this many beats. Optical sensors are noisy and
// a single inter-beat interval is not a usable reading.
#define HR_AVG_SIZE        8

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

MAX30105 particleSensor;
Adafruit_MPU6050 mpu;
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);

BLEServer*         bleServer     = nullptr;
BLECharacteristic* telemetryChar = nullptr;
bool deviceConnected     = false;
bool lastConnectedState  = false;
bool haveMax30102        = false;
bool haveMpu6050         = false;
bool haveOled            = false;

byte  hrRates[HR_AVG_SIZE];
byte  hrIndex     = 0;
long  lastBeatMs  = 0;
float beatsPerMin = 0;
int   beatAverage = 0;
bool  hrBufferFilled = false;

unsigned long lastSampleMs = 0;

// ---------------------------------------------------------------------------
// BLE callbacks
// ---------------------------------------------------------------------------

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* server) override {
    deviceConnected = true;
    Serial.println("[BLE] Central connected");
  }

  void onDisconnect(BLEServer* server) override {
    deviceConnected = false;
    Serial.println("[BLE] Central disconnected");
  }
};

class CommandCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* characteristic) override {
    String value = characteristic->getValue().c_str();
    value.trim();
    if (value.length() == 0) return;

    Serial.print("[BLE] Command: ");
    Serial.println(value);

    if (value == "RESET") {
      resetHeartRate();
    }
  }
};

void resetHeartRate() {
  hrIndex = 0;
  beatAverage = 0;
  beatsPerMin = 0;
  hrBufferFilled = false;
  for (byte i = 0; i < HR_AVG_SIZE; i++) hrRates[i] = 0;
}

// ---------------------------------------------------------------------------
// Sensors
// ---------------------------------------------------------------------------

bool setupMax30102() {
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("[MAX30102] Not found. Heart rate and SpO2 disabled.");
    return false;
  }
  // Conservative settings: enough LED power for a reliable finger reading
  // without cooking the sensor or draining the battery.
  particleSensor.setup(60, 4, 2, 100, 411, 4096);
  particleSensor.setPulseAmplitudeRed(0x0A);
  particleSensor.setPulseAmplitudeGreen(0);
  Serial.println("[MAX30102] Ready.");
  return true;
}

bool setupOled() {
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("[OLED] Not found. Live display disabled.");
    return false;
  }
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("AyuDrishti Band");
  display.println("starting...");
  display.display();
  Serial.println("[OLED] Ready.");
  return true;
}

/*
 * Render the current readings to the OLED, so the band is useful on its own
 * (and debuggable) even with no phone connected. Mirrors the telemetry values.
 */
void updateOled(float hr, float spo2, float gsr, float motion, bool contact) {
  if (!haveOled) return;

  display.clearDisplay();

  // Header with BLE connection state.
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("AyuDrishti ");
  display.println(deviceConnected ? "[BLE]" : "[---]");
  display.drawLine(0, 10, OLED_WIDTH - 1, 10, SSD1306_WHITE);

  // Heart rate, large, most glanceable metric.
  display.setTextSize(2);
  display.setCursor(0, 16);
  if (contact && hr > 0) display.print((int) hr);
  else display.print("--");
  display.setTextSize(1);
  display.print(" bpm");

  // SpO2, GSR, motion on the lower rows.
  display.setTextSize(1);
  display.setCursor(0, 40);
  display.print("SpO2 ");
  if (contact && spo2 > 0) { display.print(spo2, 0); display.print('%'); }
  else display.print("--");

  display.setCursor(0, 52);
  display.print("GSR ");
  display.print(gsr, 1);
  display.print("uS  M");
  display.print(motion, 1);

  display.display();
}

bool setupMpu6050() {
  if (!mpu.begin()) {
    Serial.println("[MPU6050] Not found. Motion disabled.");
    return false;
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  Serial.println("[MPU6050] Ready.");
  return true;
}

/*
 * Poll the pulse sensor. Called as often as possible from loop() because beat
 * detection needs a continuous sample stream -- sampling only once per
 * telemetry interval would miss most beats entirely.
 */
void pollHeartRate() {
  if (!haveMax30102) return;

  long irValue = particleSensor.getIR();
  if (irValue < FINGER_THRESHOLD) {
    // Finger removed: drop the running average rather than reporting a stale
    // heart rate that no longer describes anything.
    if (beatAverage != 0) resetHeartRate();
    return;
  }

  if (checkForBeat(irValue)) {
    long now = millis();
    long delta = now - lastBeatMs;
    lastBeatMs = now;

    float bpm = 60.0f / (delta / 1000.0f);
    if (bpm > 20 && bpm < 220) {
      hrRates[hrIndex++] = (byte) bpm;
      if (hrIndex >= HR_AVG_SIZE) { hrIndex = 0; hrBufferFilled = true; }

      byte count = hrBufferFilled ? HR_AVG_SIZE : hrIndex;
      if (count > 0) {
        long total = 0;
        for (byte i = 0; i < count; i++) total += hrRates[i];
        beatAverage = total / count;
      }
      beatsPerMin = bpm;
    }
  }
}

/*
 * Estimate SpO2 from the ratio of red to infrared absorption.
 *
 * This is a simplified empirical approximation, adequate for showing a
 * trend during a yoga session. It is NOT calibrated against a reference
 * oximeter and must not be read as a clinical measurement.
 */
float readSpo2() {
  if (!haveMax30102) return -1.0f;

  long ir = particleSensor.getIR();
  long red = particleSensor.getRed();
  if (ir < FINGER_THRESHOLD || red <= 0) return -1.0f;

  float ratio = (float) red / (float) ir;
  float spo2 = 110.0f - 25.0f * ratio;
  if (spo2 > 100.0f) spo2 = 100.0f;
  if (spo2 < 70.0f) return -1.0f;  // outside the range this approximation supports
  return spo2;
}

/*
 * Convert the GSR analog reading to an approximate conductance in
 * microsiemens. Absolute values vary enormously between people and with
 * electrode contact, so the backend baselines each session per user rather
 * than thresholding this number directly.
 */
float readGsr() {
  // Average several samples: the ESP32 ADC is noisy and a single read
  // fluctuates more than the physiological signal being measured.
  long total = 0;
  const int samples = 16;
  for (int i = 0; i < samples; i++) {
    total += analogRead(GSR_PIN);
    delayMicroseconds(200);
  }
  float raw = (float) total / samples;         // 0..4095
  float voltage = raw * (3.3f / 4095.0f);
  if (voltage < 0.01f) return 0.0f;

  // Series divider with a 10k reference resistor.
  float resistance = (3.3f - voltage) * 10000.0f / voltage;
  if (resistance <= 0) return 0.0f;
  return 1000000.0f / resistance;              // microsiemens
}

/* Acceleration magnitude in g; ~1.0 when still. */
float readMotion() {
  if (!haveMpu6050) return -1.0f;

  sensors_event_t accel, gyro, temp;
  mpu.getEvent(&accel, &gyro, &temp);

  float x = accel.acceleration.x;
  float y = accel.acceleration.y;
  float z = accel.acceleration.z;
  float magnitude = sqrt(x * x + y * y + z * z);
  return magnitude / 9.80665f;
}

// ---------------------------------------------------------------------------
// Telemetry
// ---------------------------------------------------------------------------

void sendTelemetry() {
  if (!deviceConnected || telemetryChar == nullptr) return;

  float spo2 = readSpo2();
  float gsr = readGsr();
  float motion = readMotion();
  bool contact = haveMax30102 && particleSensor.getIR() >= FINGER_THRESHOLD;
  float hr = beatAverage > 0 ? (float) beatAverage : -1.0f;

  // Keep the on-band display in step with what we transmit.
  updateOled(hr, spo2, gsr, motion, contact);

  // Hand-built JSON: a full JSON library is overkill for six fixed fields and
  // costs flash we would rather leave for the sensor drivers.
  char payload[160];
  snprintf(
    payload, sizeof(payload),
    "{\"hr\":%.1f,\"spo2\":%.1f,\"gsr\":%.2f,\"motion\":%.2f,\"t\":%lu,\"ok\":%s}",
    hr,
    spo2,
    gsr,
    motion,
    millis(),
    contact ? "true" : "false"
  );

  telemetryChar->setValue((uint8_t*) payload, strlen(payload));
  telemetryChar->notify();

  Serial.println(payload);
}

// ---------------------------------------------------------------------------
// Arduino lifecycle
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nAyuDrishti wearable starting...");
  Serial.println("Wellness accessory only - not a medical device.");

  Wire.begin();
  analogReadResolution(12);

  haveOled = setupOled();
  haveMax30102 = setupMax30102();
  haveMpu6050 = setupMpu6050();
  resetHeartRate();

  BLEDevice::init(DEVICE_NAME);
  bleServer = BLEDevice::createServer();
  bleServer->setCallbacks(new ServerCallbacks());

  BLEService* service = bleServer->createService(SERVICE_UUID);

  telemetryChar = service->createCharacteristic(
    CHAR_TELEMETRY_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
  );
  telemetryChar->addDescriptor(new BLE2902());

  BLECharacteristic* commandChar = service->createCharacteristic(
    CHAR_COMMAND_UUID,
    BLECharacteristic::PROPERTY_WRITE
  );
  commandChar->setCallbacks(new CommandCallbacks());

  service->start();

  BLEAdvertising* advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setScanResponse(true);
  // Helps iOS central devices discover the peripheral reliably.
  advertising->setMinPreferred(0x06);
  advertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();

  Serial.print("Advertising as ");
  Serial.println(DEVICE_NAME);
}

void loop() {
  // Beat detection needs continuous sampling, so this runs every iteration
  // while telemetry is emitted on a slower fixed cadence.
  pollHeartRate();

  unsigned long now = millis();
  if (now - lastSampleMs >= SAMPLE_INTERVAL_MS) {
    lastSampleMs = now;
    sendTelemetry();
  }

  // Restart advertising once a central disconnects, otherwise the band
  // becomes invisible until it is power-cycled.
  if (!deviceConnected && lastConnectedState) {
    delay(500);
    bleServer->startAdvertising();
    Serial.println("[BLE] Advertising restarted");
  }
  lastConnectedState = deviceConnected;
}
