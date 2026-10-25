#include "Arduino.h"
#include <vector>
#include <cassert>
SerialT Serial;
static int pinv[20], pinm[20];
static const int WE_PIN = 14;            // A0
static uint8_t sr1, sr2, lat1, lat2;           // 595 #1 (low address byte), #2 (high byte + OE)
static std::vector<uint8_t> rom(32768, 0xFF);
static unsigned long now_us = 0;
static int busy_reads = 0; static unsigned busy_addr; static uint8_t last_written;
static unsigned we_addr; static bool sdp_seen = false; static std::vector<std::pair<unsigned,int>> seq;
static int writes = 0, bad_timing = 0; static unsigned long last_we_fall = 0;
static unsigned addr() { return lat1 | ((lat2 & 0x7F) << 8); }
static bool oe_low() { return (lat2 & 0x80) == 0; }
static uint8_t data_from_pins() { uint8_t d = 0; for (int i = 0; i < 8; i++) d |= (pinv[5 + i] & 1) << i; return d; }
static void on_change(int p, int old, int v) {
  if (p == 3 && old == 0 && v == 1) { uint8_t carry = (sr1 >> 7) & 1; sr1 = (sr1 << 1) | (pinv[2] & 1); sr2 = (sr2 << 1) | carry; }
  if (p == 4 && old == 0 && v == 1) { lat1 = sr1; lat2 = sr2; }
  if (p == WE_PIN && old == 1 && v == 0) { we_addr = addr(); if (now_us - last_we_fall > 150 && !seq.empty() && seq.size() < 6) bad_timing++; now_us += 1; last_we_fall = now_us; }
  if (p == WE_PIN && old == 0 && v == 1) {          // data latched on WE rising edge
    assert(!oe_low() && "outputs on during a write");
    uint8_t d = data_from_pins();
    seq.push_back({we_addr, d}); if (seq.size() > 6) seq.erase(seq.begin());
    if (seq.size() == 6 && seq[0] == std::make_pair(0x5555u, 0xAA) && seq[5] == std::make_pair(0x5555u, 0x20)) sdp_seen = true;
    rom[we_addr] = d; busy_reads = 3; busy_addr = we_addr; last_written = d; writes++;
  }
}
void pinMode(int p, int m) { pinm[p] = m; }
void digitalWrite(int p, int v) { int o = pinv[p]; pinv[p] = v ? 1 : 0; now_us += 4; if (o != pinv[p]) on_change(p, o, pinv[p]); }
int digitalRead(int p) {
  now_us += 4;
  if (p >= 5 && p <= 12 && pinm[p] == INPUT) {
    if (!oe_low() || pinv[WE_PIN] == 0) return 1;     // outputs off: floating, read as 1
    unsigned a = addr();
    if (busy_reads > 0 && a == busy_addr) { busy_reads--; uint8_t v = (~last_written) & 0x80; return p == 12 ? (v >> 7) : 0; }
    return (rom[a] >> (p - 5)) & 1;
  }
  return pinv[p];
}
void shiftOut(int dp, int cp, int, byte v) { for (int i = 7; i >= 0; i--) { digitalWrite(dp, (v >> i) & 1); digitalWrite(cp, 1); digitalWrite(cp, 0); } }
void delayMicroseconds(unsigned us) { now_us += us; }
void delay(unsigned ms) { now_us += ms * 1000; }
unsigned long millis() { return now_us / 1000; }
Port::operator byte() const { byte v = 0; for (int i = 0; i < bits; i++) v |= (pinv[base + i] & 1) << i; return v; }
Port &Port::operator=(byte v) {
  for (int i = 0; i < bits; i++) { int p = base + i; int nv = (v >> i) & 1; int o = pinv[p]; pinv[p] = nv; if (o != nv) on_change(p, o, nv); }
  now_us += 0; return *this;
}
Port PORTD{0, 8}, PORTB{8, 6}, PORTC{14, 6};
#include "../PC2_EEPROM_Programmer/PC2_EEPROM_Programmer.ino"
int main() {
  pinv[WE_PIN] = 1;   // 10k pull-up on WE
  // the bootloader flashes the "L" LED on D13 at every reset: that must not touch the EEPROM
  for (int i = 0; i < 6; i++) { pinMode(13, OUTPUT); digitalWrite(13, i & 1 ? LOW : HIGH); }
  digitalWrite(13, LOW); pinMode(13, INPUT);
  int boot_writes = writes;
  setup();
  printf("writes during bootloader LED flashes: %d\n", boot_writes);
  if (boot_writes) return 1;
  const uint8_t *imgs[4] = {MICROCODE_ROM0, MICROCODE_ROM1, MICROCODE_ROM2, DISPLAY_ROM};
  unsigned lens[4] = {sizeof(MICROCODE_ROM0), sizeof(MICROCODE_ROM1), sizeof(MICROCODE_ROM2), sizeof(DISPLAY_ROM)};
  const char keys[4] = {'0', '1', '2', 'D'};
  int fails = 0;
  for (int k = 0; k < 4; k++) {
    std::fill(rom.begin(), rom.end(), 0xFF);
    Serial.out.clear(); Serial.pending = keys[k]; loop();
    for (unsigned a = 0; a < lens[k]; a++) if (rom[a] != imgs[k][a]) { fails++; break; }
    bool ok = Serial.out.find("OK:") != std::string::npos;
    printf("ROM %c: %s, chip %s\n", keys[k], ok ? "programmer says OK" : "programmer says FAIL", fails ? "WRONG" : "matches image");
  }
  // a chip that is already right is not rewritten
  int before = writes; Serial.pending = 'D'; loop(); printf("rewrite of identical chip: %d writes\n", writes - before);
  seq.clear(); bad_timing = 0; last_we_fall = now_us; Serial.out.clear(); Serial.pending = 'U'; loop(); printf("unlock sequence seen: %s, slow gaps: %d\n", sdp_seen ? "yes" : "no", bad_timing);
  Serial.out.clear(); Serial.pending = 'R'; loop(); printf("dump first line: %s\n", Serial.out.substr(0, 60).c_str());
  printf("total failures: %d\n", fails);
  return fails;
}
