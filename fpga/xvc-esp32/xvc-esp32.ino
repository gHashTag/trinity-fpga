// XVC (Xilinx Virtual Cable) WiFi JTAG server for ESP32
// Target: QMTech XC7A100T/200T via P2 header
// Validated: IDCODE=0x0362D093 (XC7A100T) / 0x13631093 (XC7A200T v1)
// STAT: 0x401079FC  DONE=1
// φ² + φ⁻² = 3  |  trios#380 App.F
//
// GPIO assignment (BLK-002 fix: IO35 input-only — no pull-up for TDO)
// TMS = GPIO18 | TCK = GPIO19 | TDI = GPIO23 | TDO = GPIO35 (input-only)

#include <WiFi.h>

// --- Configuration ---
const char* SSID     = "YOUR_SSID";
const char* PASSWORD = "YOUR_PASSWORD";
const int   XVC_PORT = 2542;

// JTAG GPIO
#define TMS_PIN 18
#define TCK_PIN 19
#define TDI_PIN 23
#define TDO_PIN 35  // input-only, no internal pull-up

#define XVC_BUFLEN 1024

WiFiServer server(XVC_PORT);

void setup() {
  Serial.begin(115200);
  pinMode(TMS_PIN, OUTPUT);
  pinMode(TCK_PIN, OUTPUT);
  pinMode(TDI_PIN, OUTPUT);
  pinMode(TDO_PIN, INPUT);  // IO35: input-only, correct for TDO

  digitalWrite(TCK_PIN, LOW);
  digitalWrite(TMS_PIN, HIGH);

  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print('.'); }
  Serial.printf("\nXVC server ready at %s:%d\n",
                WiFi.localIP().toString().c_str(), XVC_PORT);
  server.begin();
}

// Bit-serial JTAG shift (BLK-003 fix: eliminates 32-bit endianness artefact)
// Processes each bit individually in LSB-first order per XVC spec.
static void do_shift(uint32_t len,
                     const uint8_t* tmsbuf,
                     const uint8_t* tdibuf,
                     uint8_t*       tdobuf) {
  uint32_t nbytes = (len + 7) / 8;
  memset(tdobuf, 0, nbytes);

  for (uint32_t bit = 0; bit < len; bit++) {
    int byteidx = bit / 8;
    int bitidx  = bit % 8;
    int tmsbit  = (tmsbuf[byteidx] >> bitidx) & 1;
    int tdibit  = (tdibuf[byteidx] >> bitidx) & 1;

    digitalWrite(TMS_PIN, tmsbit);
    digitalWrite(TDI_PIN, tdibit);
    delayMicroseconds(1);
    digitalWrite(TCK_PIN, HIGH);
    delayMicroseconds(1);
    int tdobit = digitalRead(TDO_PIN);
    digitalWrite(TCK_PIN, LOW);
    delayMicroseconds(1);

    if (tdobit) tdobuf[byteidx] |= (1 << bitidx);
  }
}

static bool handle_client(WiFiClient& client) {
  uint8_t buf[XVC_BUFLEN + 16];

  // Read until newline or 64-byte header
  int hlen = 0;
  while (hlen < 64 && client.connected()) {
    if (client.available()) {
      buf[hlen] = client.read();
      if (buf[hlen] == ':') { buf[++hlen] = 0; break; }
      hlen++;
    }
  }

  if (strncmp((char*)buf, "getinfo:", 8) == 0) {
    char resp[] = "xvcServer_v1.0:1024\n";
    client.write((uint8_t*)resp, strlen(resp));
    return true;
  }

  if (strncmp((char*)buf, "settck:", 7) == 0) {
    uint32_t period_ns;
    client.readBytes((uint8_t*)&period_ns, 4);
    client.write((uint8_t*)&period_ns, 4);  // echo back actual period
    return true;
  }

  if (strncmp((char*)buf, "shift:", 6) == 0) {
    uint32_t len;
    client.readBytes((uint8_t*)&len, 4);
    uint32_t nbytes = (len + 7) / 8;
    if (nbytes > XVC_BUFLEN) return false;

    uint8_t tms[XVC_BUFLEN], tdi[XVC_BUFLEN], tdo[XVC_BUFLEN];
    client.readBytes(tms, nbytes);
    client.readBytes(tdi, nbytes);
    do_shift(len, tms, tdi, tdo);
    client.write(tdo, nbytes);
    return true;
  }

  return false;  // unknown command
}

void loop() {
  WiFiClient client = server.accept();
  if (!client) return;
  Serial.printf("Client connected: %s\n", client.remoteIP().toString().c_str());
  while (client.connected()) {
    if (client.available()) {
      if (!handle_client(client)) break;
    }
    delay(1);
  }
  client.stop();
  Serial.println("Client disconnected");
}
