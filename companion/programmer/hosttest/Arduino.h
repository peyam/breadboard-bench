// Host-side stand-in for the Arduino core, wired to models of two 74HC595s and an AT28C256.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
typedef uint8_t byte;
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define MSBFIRST 1
#define HEX 16
#define A0 14
void pinMode(int p, int m);
void digitalWrite(int p, int v);
int digitalRead(int p);
void shiftOut(int dp, int cp, int order, byte v);
void delayMicroseconds(unsigned us);
void delay(unsigned ms);
unsigned long millis();
inline void noInterrupts() {}
inline void interrupts() {}
struct SerialT {
  std::string out; int pending = -1;
  void begin(long) {}
  int available() { return pending >= 0; }
  int read() { int c = pending; pending = -1; return c; }
  void print(const char *s) { out += s; } void print(char c) { out += c; }
  void print(unsigned v) { out += std::to_string(v); } void print(int v) { out += std::to_string(v); }
  void print(unsigned long v) { out += std::to_string(v); }
  void print(byte v, int) { char b[8]; snprintf(b, 8, "%X", v); out += b; }
  void println() { out += "\n"; } void println(const char *s) { out += s; out += "\n"; }
  void println(byte v, int b) { print(v, b); println(); }
  void println(unsigned v) { print(v); println(); } void println(int v) { print(v); println(); }
};
extern SerialT Serial;
struct Port {
  int base; // pin number of bit 0
  int bits;
  operator byte() const;
  Port &operator=(byte v);
  Port &operator|=(byte v) { return *this = (byte)(byte(*this) | v); }
  Port &operator&=(byte v) { return *this = (byte)(byte(*this) & v); }
};
extern Port PORTD, PORTB, PORTC;
