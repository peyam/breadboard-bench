/*
  PC-2 EEPROM programmer
  For a Nano-compatible board (compatible with Arduino(R); 5 V, ATmega328P) and two 74HC595 shift registers.

  Derived from Ben Eater's EEPROM programmer, https://github.com/beneater/eeprom-programmer
  Copyright 2017 Ben Eater, MIT licence:

    Permission is hereby granted, free of charge, to any person obtaining a copy of this
    software and associated documentation files (the "Software"), to deal in the Software
    without restriction, including without limitation the rights to use, copy, modify,
    merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be included in all copies
    or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
    INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
    PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
    CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
    OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

  Changes for PC-2 (also MIT licence; see LICENSE): the PC-2 ROM images, WE on A0,
  data polling, verify and report, skip bytes already right, the unlock routine.

  Wiring (see the book, Chapter 7, Lesson 21):
    Nano D2  -> 74HC595 #1 pin 14 (SER)
    Nano D3  -> both 74HC595 pin 11 (SRCLK)
    Nano D4  -> both 74HC595 pin 12 (RCLK)
    74HC595 #1 pin 9 (QH') -> 74HC595 #2 pin 14 (SER)
    74HC595 #1 QA..QH -> EEPROM A0..A7
    74HC595 #2 QA..QG -> EEPROM A8..A14
    74HC595 #2 QH     -> EEPROM OE (pin 22)        (0 = outputs on)
    Nano D5..D12 -> EEPROM I/O0..I/O7 (pins 11, 12, 13, 15, 16, 17, 18, 19)
    Nano A0 (D14) -> EEPROM WE (pin 27)
    EEPROM CE (pin 20) -> GND
    10 kOhm from EEPROM WE (pin 27) to 5 V: while the Nano starts up all its pins are inputs,
    and the pull-up holds WE high (no write). WE is NOT on D13: D13 carries the Nano's "L" LED
    (through about 1 kOhm to GND, which would drag WE down to about 2 V) and the bootloader
    drives D13 to flash that LED on every reset, which would write a stray byte.
    Insert or remove the EEPROM only with the USB cable unplugged.
    Both 74HC595: pin 10 (SRCLR) -> 5 V, pin 13 (OE) -> GND, pin 16 -> 5 V, pin 8 -> GND.

  Open the Serial Monitor at 57600 baud, line ending "Newline", and type:
    0, 1 or 2  write and verify microcode ROM 0, 1 or 2
    D          write and verify the display ROM
    R          read and print the first 512 bytes of the chip in the socket
    U          turn off software data protection (only needed for chips that have it on)
  Label each chip as you take it out.
*/
#include <Arduino.h>
#include <avr/pgmspace.h>
#include "pc2_roms.h"

const int SHIFT_DATA = 2;
const int SHIFT_CLK = 3;
const int SHIFT_LATCH = 4;
const int EEPROM_D0 = 5;    // D5..D12 carry I/O0..I/O7
const int WRITE_EN = A0;   // = D14, PORTC bit 0 (never D13: see above)

// Put a 15-bit address on the shift registers. outputEnable = true turns the
// EEPROM's outputs on (so we can read); false keeps them off (so we can write).
void setAddress(unsigned int address, bool outputEnable) {
  shiftOut(SHIFT_DATA, SHIFT_CLK, MSBFIRST, (address >> 8) | (outputEnable ? 0x00 : 0x80));
  shiftOut(SHIFT_DATA, SHIFT_CLK, MSBFIRST, address & 0xFF);
  digitalWrite(SHIFT_LATCH, LOW);
  digitalWrite(SHIFT_LATCH, HIGH);
  digitalWrite(SHIFT_LATCH, LOW);
}

void dataPinsMode(int mode) {
  for (int pin = EEPROM_D0; pin < EEPROM_D0 + 8; pin++) {
    pinMode(pin, mode);
  }
}

byte readEEPROM(unsigned int address) {
  dataPinsMode(INPUT);
  setAddress(address, true);
  delayMicroseconds(1);                 // access time is 150 ns; 1 us is plenty
  byte data = 0;
  for (int pin = EEPROM_D0 + 7; pin >= EEPROM_D0; pin--) {
    data = (data << 1) | digitalRead(pin);
  }
  return data;
}

// Write one byte, then wait until the chip reports the write is finished
// ("data polling": while it is busy it shows the opposite of bit 7).
bool writeEEPROM(unsigned int address, byte data) {
  byte want = data;
  setAddress(address, false);
  dataPinsMode(OUTPUT);
  for (int pin = EEPROM_D0; pin < EEPROM_D0 + 8; pin++) {
    digitalWrite(pin, data & 1);
    data = data >> 1;
  }
  digitalWrite(WRITE_EN, LOW);
  delayMicroseconds(1);
  digitalWrite(WRITE_EN, HIGH);
  unsigned long start = millis();
  while ((readEEPROM(address) & 0x80) != (want & 0x80)) {
    if (millis() - start > 20) {        // a write takes at most 10 ms
      return false;
    }
  }
  return true;
}

bool program(const uint8_t *image, unsigned int length, const char *name) {
  Serial.print("Writing ");
  Serial.print(name);
  Serial.print(" (");
  Serial.print(length);
  Serial.println(" bytes)...");
  for (unsigned int a = 0; a < length; a++) {
    byte b = pgm_read_byte(image + a);
    if (readEEPROM(a) != b) {           // skip bytes that are already right
      if (!writeEEPROM(a, b)) {
        Serial.print("  write timed out at address ");
        Serial.println(a);
        return false;
      }
    }
    if (a % 64 == 63) {
      Serial.print('.');
    }
  }
  Serial.println();
  Serial.println("Verifying...");
  unsigned int errors = 0;
  for (unsigned int a = 0; a < length; a++) {
    byte b = pgm_read_byte(image + a);
    byte r = readEEPROM(a);
    if (r != b) {
      if (errors < 10) {
        Serial.print("  address ");
        Serial.print(a);
        Serial.print(": wanted ");
        Serial.print(b, HEX);
        Serial.print(", read ");
        Serial.println(r, HEX);
      }
      errors++;
    }
  }
  if (errors == 0) {
    Serial.print("OK: ");
    Serial.print(name);
    Serial.println(" written and verified. Label the chip now.");
    return true;
  }
  Serial.print("FAILED: ");
  Serial.print(errors);
  Serial.println(" bytes wrong. Check the wiring and try again.");
  return false;
}

void printContents(unsigned int length) {
  for (unsigned int base = 0; base < length; base += 16) {
    char line[80];
    byte d[16];
    for (int i = 0; i < 16; i++) {
      d[i] = readEEPROM(base + i);
    }
    sprintf(line, "%03x:  %02x %02x %02x %02x %02x %02x %02x %02x   %02x %02x %02x %02x %02x %02x %02x %02x",
            base, d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7],
            d[8], d[9], d[10], d[11], d[12], d[13], d[14], d[15]);
    Serial.println(line);
  }
}

// The unlock sequence must be written quickly (each byte within 150 us of the last),
// faster than digitalWrite allows, so this routine drives the ports directly.
// Nano: D2-D7 are PORTD bits 2-7, D8-D13 are PORTB bits 0-5, A0-A5 (D14-D19) are PORTC bits 0-5.
void fastSetAddress(unsigned int address) {
  byte hi = (address >> 8) | 0x80;      // outputs off while writing
  byte lo = address & 0xFF;
  for (int k = 0; k < 2; k++) {
    byte v = (k == 0) ? hi : lo;
    for (int i = 7; i >= 0; i--) {
      if (v & (1 << i)) PORTD |= (1 << 2); else PORTD &= ~(1 << 2);   // SER  (D2)
      PORTD |= (1 << 3);                                              // SRCLK (D3) high
      PORTD &= ~(1 << 3);                                             // SRCLK low
    }
  }
  PORTD |= (1 << 4);                                                  // RCLK (D4) pulse
  PORTD &= ~(1 << 4);
}

void fastWrite(unsigned int address, byte data) {
  fastSetAddress(address);
  // data bits 0-2 on D5-D7 (PORTD 5-7), bits 3-7 on D8-D12 (PORTB 0-4)
  PORTD = (PORTD & 0x1F) | ((data & 0x07) << 5);
  PORTB = (PORTB & 0xE0) | ((data >> 3) & 0x1F);
  PORTC &= ~(1 << 0);                                                 // WE (A0) low
  PORTC |= (1 << 0);                                                  // WE high
}

void disableProtection() {
  dataPinsMode(OUTPUT);
  noInterrupts();
  fastWrite(0x5555, 0xAA);
  fastWrite(0x2AAA, 0x55);
  fastWrite(0x5555, 0x80);
  fastWrite(0x5555, 0xAA);
  fastWrite(0x2AAA, 0x55);
  fastWrite(0x5555, 0x20);
  interrupts();
  delay(10);
  Serial.println("Software data protection turned off.");
}

void menu() {
  Serial.println();
  Serial.println("PC-2 EEPROM programmer. Type 0, 1, 2 (microcode), D (display), R (read) or U (unlock).");
}

void setup() {
  pinMode(SHIFT_DATA, OUTPUT);
  pinMode(SHIFT_CLK, OUTPUT);
  pinMode(SHIFT_LATCH, OUTPUT);
  digitalWrite(WRITE_EN, HIGH);         // set high before making it an output: no stray write
  pinMode(WRITE_EN, OUTPUT);
  Serial.begin(57600);
  menu();
}

void loop() {
  if (!Serial.available()) {
    return;
  }
  char c = Serial.read();
  switch (c) {
    case '0': program(MICROCODE_ROM0, sizeof(MICROCODE_ROM0), "microcode ROM 0"); menu(); break;
    case '1': program(MICROCODE_ROM1, sizeof(MICROCODE_ROM1), "microcode ROM 1"); menu(); break;
    case '2': program(MICROCODE_ROM2, sizeof(MICROCODE_ROM2), "microcode ROM 2"); menu(); break;
    case 'D': case 'd': program(DISPLAY_ROM, sizeof(DISPLAY_ROM), "display ROM"); menu(); break;
    case 'R': case 'r': printContents(512); menu(); break;
    case 'U': case 'u': disableProtection(); menu(); break;
    default: break;                     // ignore newlines and anything else
  }
}
