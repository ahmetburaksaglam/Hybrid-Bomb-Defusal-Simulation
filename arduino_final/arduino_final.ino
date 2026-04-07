/*
 * ============================================================================
 * PROJECT      : Hybrid Bomb Defusal Simulation (Firmware)
 * PLATFORM     : Arduino Uno
 * COURSE       : CSE 101 - Introduction to Computer Engineering
 * TERM         : Fall 2025
 * INSTITUTION  : Gebze Technical University
 * DATE         : January 14, 2026
 * 
 * * DESCRIPTION  :
 * This firmware acts as the Slave Node for the defusal simulation. It handles
 * real-time interrupt-based inputs from wires and buttons, manages the 
 * TM1637 display driver for countdown timing, and executes the "Simon Says"
 * memory game logic. It communicates with the Python host via Serial UART.
 * ============================================================================
 */

#include <Arduino.h>
#include <TM1637Display.h>

// --- PIN CONFIGURATION ---

// Display Module (TM1637)
#define CLK 2
#define DIO 3
TM1637Display display(CLK, DIO);

// Defusal Wires (Cut to trigger logic)
const int pinsWire[] = {4, 5, 6, 7}; //ben guncelledım
const int NUM_WIRE = 4; //ben guncelledım

// Simon Says Game Module
const int pinsSimonLED[] = {11, 10, 12, 9};  
const int pinsSimonBTN[] = {A0, A1, A2, A3}; 
const int NUM_SIMON = 4;

// Status & Feedback Actuators
#define PIN_WIN_LED   13    // Visual indicator for success
#define PIN_PENALTY   A4    // Manual time reduction input
#define PIN_ALARM     A5    // Audio/Visual stress effector (Buzzer + LED)

// --- SYSTEM VARIABLES ---

unsigned long previousMillis = 0;   // Timer tracking
unsigned long stressMillis = 0;     // Stress effect timing
int gameTimer = 300;                // Default: 300 Seconds (5 Minutes)
bool gameActive = false;            // System state flag
bool simonMode = false;             // Sub-game state flag
int targetWireIndex = -1;           // Target wire ID received from PC

// Tracks the state of wires to prevent duplicate triggering
bool wireSolved[5] = {false, false, false, false, false}; 

// Simon Game Variables
int simonLevel = 1;
const int MAX_LEVEL = 5;
int simonSequence[10];

void setup() {
  // Initialize Serial Communication for PC Sync
  Serial.begin(9600);
  
  // Configure Display
  display.setBrightness(0x0f);
  
  // Initialize Input Pins (Internal Pull-up Resistors enabled)
  for (int i = 0; i < NUM_WIRE; i++) pinMode(pinsWire[i], INPUT_PULLUP);
  for (int i = 0; i < NUM_SIMON; i++) {
    pinMode(pinsSimonLED[i], OUTPUT);
    pinMode(pinsSimonBTN[i], INPUT_PULLUP);
  }
  
  // Initialize Output Pins
  pinMode(PIN_WIN_LED, OUTPUT);
  pinMode(PIN_PENALTY, INPUT_PULLUP);
  pinMode(PIN_ALARM, OUTPUT);

  // Boot-up Sequence Test
  display.showNumberDec(8888);
  delay(500);
  display.clear();
  Serial.println("SYSTEM READY. WAITING FOR COMMAND...");
}

void loop() {
  // 1. Poll Serial Buffer for incoming commands from PC
  listenSerial(); 

  // 2. Main Game Logic Loop
  if (gameActive) {
    manageTimer();          
    checkPenaltyButton();
    
    // Check active game mode
    if (!simonMode) {
      manageStressEffect(false); // Audible stress active
      checkWires();
    } else {
      playSimonGame();
    }
  }
}

/**
 * Handles incoming Serial commands from the Python Host.
 * Command Protocol:
 * 'S' -> Start Game
 * 'P' -> Panic (Explosion)
 * 'W' -> Activate Simon Mode
 * '0'-'4' -> Set Target Wire Index
 */
void listenSerial() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    
    if (command == 'S') { 
      randomSeed(micros()); // Seed RNG for Simon sequence
      gameActive = true;
      
      // Reset wire states
      for(int i=0; i<NUM_WIRE; i++) wireSolved[i] = false;
      
      resetExplosion(); 
      Serial.println("GAME STARTED");
    }
    else if (command == 'P') { 
      gameOver(false); // Trigger failure state
    } 
    else if (command == 'W') { 
      gameActive = true;
      simonMode = true; 
      simonLevel = 1; 
      generateSimonSequence(); 
      resetExplosion();
      
      // Simon Initialization Animation
      for(int k=0; k<3; k++){ 
        for(int i=0; i<4; i++) digitalWrite(pinsSimonLED[i], HIGH);
        delay(100); 
        for(int i=0; i<4; i++) digitalWrite(pinsSimonLED[i], LOW);
        delay(100);
      }
    }
    else if (command >= '0' && command <= '4') { 
      targetWireIndex = command - '0';
      Serial.print("TARGET RECEIVED: ");
      Serial.println(targetWireIndex);
    }
  }
}

/**
 * Generates dynamic audio-visual stress based on remaining time.
 * Frequency of effects increases as timer approaches zero.
 */
void manageStressEffect(bool silentMode) {
  unsigned long currentMillis = millis();
  int interval = 2000;

  // Dynamic interval adjustment
  if (gameTimer < 60) interval = 1000;
  if (gameTimer < 30) interval = 500;
  if (gameTimer < 10) interval = 250;
  if (gameTimer < 5)  interval = 100;

  if (currentMillis - stressMillis >= interval) {
    stressMillis = currentMillis;
    digitalWrite(PIN_ALARM, HIGH); 
    
    if (!silentMode) tone(PIN_ALARM, 2000); 
    
    delay(50);
    
    digitalWrite(PIN_ALARM, LOW);
    if (!silentMode) noTone(PIN_ALARM);
  }
}

/**
 * Core logic for the Simon Says memory sub-game.
 * Handles sequence display and user input validation.
 */
void playSimonGame() {
  delay(500);
  
  // Phase 1: Display Sequence
  for (int i = 0; i < simonLevel; i++) {
    int ledIndex = simonSequence[i];
    unsigned long noteStart = millis();
    
    digitalWrite(pinsSimonLED[ledIndex], HIGH); 
    tone(PIN_ALARM, 500 + (ledIndex * 200));
    
    // Non-blocking stress effect (Visual only)
    while(millis() - noteStart < 400) {
      manageStressEffect(true);
    }
    
    noTone(PIN_ALARM);
    digitalWrite(pinsSimonLED[ledIndex], LOW);
    delay(100);
  }

  // Phase 2: Await User Input
  for (int i = 0; i < simonLevel; i++) {
    int pressedIndex = -1;
    
    while (pressedIndex == -1) {
      manageTimer();          
      manageStressEffect(false); 
      if (!gameActive) return;

      for (int j = 0; j < NUM_SIMON; j++) {
        if (digitalRead(pinsSimonBTN[j]) == LOW) { 
          pressedIndex = j;
          // Input Feedback
          digitalWrite(pinsSimonLED[j], HIGH); 
          tone(PIN_ALARM, 500 + (j * 200)); 
          while(digitalRead(pinsSimonBTN[j]) == LOW); // Debounce
          delay(50); 
          noTone(PIN_ALARM);
          digitalWrite(pinsSimonLED[j], LOW);
        }
      }
    }

    if (pressedIndex != simonSequence[i]) {
      gameOver(false); // Wrong input
      return;
    }
  }

  delay(500);
  simonLevel++; 
  if (simonLevel > MAX_LEVEL) gameOver(true); // Victory condition
}

/**
 * Monitors the state of defusal wires.
 * Triggers success or failure based on target wire index.
 */
void checkWires() {
  if (targetWireIndex == -1) return; 
  
  for (int i = 0; i < NUM_WIRE; i++) {
    // Skip already solved/cut wires
    if (wireSolved[i] == true) continue;

    // Detect wire cut (Input goes HIGH due to internal pull-up)
    if (digitalRead(pinsWire[i]) == HIGH) { 
       if (i == targetWireIndex) {
         Serial.println("WIRE_CORRECT");
         wireSolved[i] = true;

         // Visual/Audio confirmation
         for(int k=0; k<2; k++) { 
           digitalWrite(PIN_WIN_LED, HIGH);
           tone(PIN_ALARM, 1500, 100); 
           delay(100); 
           digitalWrite(PIN_WIN_LED, LOW); 
           delay(100); 
         }
         targetWireIndex = -1;
       } else { 
         gameOver(false); // Wrong wire cut
       }
    }
  }
}

/**
 * Checks the penalty button status.
 * Reduces timer by 20 seconds upon activation.
 */
void checkPenaltyButton() {
  if (digitalRead(PIN_PENALTY) == LOW) {
    if (gameTimer > 20) gameTimer -= 20;
    else gameTimer = 0;
    
    tone(PIN_ALARM, 100, 200); 
    display.showNumberDec(gameTimer); 
    
    Serial.print("TIME: ");
    Serial.println(gameTimer);
    
    delay(300); // Simple debounce
  }
}

/**
 * Manages the countdown timer.
 * Synchronizes time with PC every second.
 */
void manageTimer() {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= 1000) {
    previousMillis = currentMillis;
    
    if (gameTimer > 0) {
      gameTimer--;
      
      // Sync with PC
      Serial.print("TIME: ");
      Serial.println(gameTimer);
      
      int min = gameTimer / 60;
      int sec = gameTimer % 60;
      display.showNumberDecEx(min * 100 + sec, 0b01000000, true);
    } else { 
      gameOver(false); // Time expired
    }
  }
}

void generateSimonSequence() { 
  for (int i = 0; i < 10; i++) simonSequence[i] = random(0, 4);
}

void resetExplosion() { 
  digitalWrite(PIN_ALARM, LOW); 
  digitalWrite(PIN_WIN_LED, LOW); 
  noTone(PIN_ALARM); 
  display.clear(); 
}

/**
 * Handles Game Over state (Win or Loss).
 * Executes final animations and sound effects.
 */
void gameOver(bool win) {
  gameActive = false;
  simonMode = false;
  
  if (win) {
    digitalWrite(PIN_WIN_LED, HIGH); 
    display.showNumberDec(9999); 
    Serial.println("YOU WON!");
    
    int melody[] = {659, 659, 659, 523, 659, 784, 392};
    int duration[] = {150, 150, 150, 150, 150, 300, 300};
    
    for(int i=0; i<7; i++) { 
      tone(PIN_ALARM, melody[i]); 
      delay(duration[i]); 
      noTone(PIN_ALARM); 
      delay(50);
    }
  } else {
    Serial.println("BOOM!");
    display.showNumberDec(0000);
    
    // Explosion Animation Phase 1
    for(int i=0; i<3; i++) {
      for(int j=0; j<4; j++) digitalWrite(pinsSimonLED[j], HIGH); 
      digitalWrite(PIN_ALARM, HIGH); 
      digitalWrite(PIN_WIN_LED, HIGH);
      
      tone(PIN_ALARM, 200); 
      delay(100);
      
      for(int j=0; j<4; j++) digitalWrite(pinsSimonLED[j], LOW); 
      digitalWrite(PIN_ALARM, LOW); 
      digitalWrite(PIN_WIN_LED, LOW); 
      noTone(PIN_ALARM); 
      delay(100);
    }
    
    // Explosion Animation Phase 2 (Sound Drop)
    for(int j=0; j<4; j++) digitalWrite(pinsSimonLED[j], HIGH); 
    digitalWrite(PIN_ALARM, HIGH);
    
    for(int freq = 1000; freq > 50; freq -= 10) { 
      tone(PIN_ALARM, freq); 
      delay(5);
    }
    
    tone(PIN_ALARM, 50); delay(2000);
    noTone(PIN_ALARM); 
    
    // Reset indicators
    for(int j=0; j<4; j++) digitalWrite(pinsSimonLED[j], LOW); 
    digitalWrite(PIN_ALARM, LOW);
    digitalWrite(PIN_WIN_LED, LOW); 
    display.clear();
  }
}