// --- ARDUINO 2: TILT CONTROLLER (MPU6050) ---
// Bu kodu "Kumanda" olarak kullanacağın Arduino'ya yükle.
// Baud Rate: 115200

#include <Wire.h>
#include <MPU6050.h>

MPU6050 mpu;

int16_t ax, ay, az, gx, gy, gz;

void setup() {
  Serial.begin(115200); // HIZLI VERİ AKIŞI İÇİN YÜKSEK HIZ
  Wire.begin();
  mpu.initialize();

  if (!mpu.testConnection()) {
    // Bağlantı yoksa bile devam et, belki sonra gelir
  }
}

void loop() {
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

  // İvme verilerini açıya (roll/pitch) çevir
  float fax = (float)ax;
  float fay = (float)ay;
  float faz = (float)az;

  // Basit trigonometri ile açı hesabı
  float roll  = atan2(fay, faz) * 180.0 / PI;
  float pitch = atan2(-fax, sqrt(fay*fay + faz*faz)) * 180.0 / PI;

  // Python'a gönder: "roll,pitch" formatında
  Serial.print(roll, 2);
  Serial.print(",");
  Serial.println(pitch, 2);

  delay(20); // Saniyede ~50 veri paketi gönderir
}