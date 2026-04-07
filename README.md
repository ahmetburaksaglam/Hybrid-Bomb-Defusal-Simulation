# 💣 Defuse the Bomb: Hybrid Hardware-Software Simulation

## Project Overview
"Defuse the Bomb" is a hybrid simulation game that combines physical hardware interaction with digital software puzzles. Developed as a term project for the CSE 101 course at Gebze Technical University (Fall 2025), this system bridges the gap between software programming and hardware engineering. 

The player acts as a bomb disposal expert, multitasking between solving logic puzzles on a PC monitor and physically manipulating a custom-built bomb circuit (cutting specific wires, pressing buttons) before the hardware countdown timer reaches zero.

## System Architecture
The project operates on a custom "PC-Arduino" architecture, utilizing serial communication protocols.

* **Master PC (Python):** Runs the main game GUI, physics engine, and computer vision modules. It utilizes a multi-threaded approach to simultaneously communicate with two separate independent Arduino units.
* **Main Control Unit (Arduino Uno 1):** Manages the physical bomb interface, including the TM1637 countdown display, the 5-wire defusal mechanism, and the "Simon Says" hardware module. It communicates with the PC via 9600 Baud Serial.
* **Sensor Unit (Arduino Uno 2):** Dedicated entirely to processing MPU6050 Accelerometer data. It sends X/Y tilt values to the PC at a high speed (115200 Baud) to ensure smooth, real-time control for the physics-based minigame.

## My Contribution
As a core member of the **Hardware & Circuit Design Team**, my primary responsibilities were focused on the **Main Control Unit**:
* Designed the core circuit architecture and assembled the physical hardware components into the final model.
* Developed the `arduino_final.ino` firmware.
* Programmed the interrupt-based wire-cutting logic, the synchronized countdown timer, and the interactive 'Simon Says' memory game.

## Gameplay Modules
The simulation requires completing 4 digital levels to unlock physical wires on the bomb:
1. **Laser Mirrors:** A Pygame-based logic puzzle focusing on algorithmic pathfinding.
2. **Tilt Arena:** A ball physics game controlled physically by tilting the MPU6050 Sensor Unit.
3. **Energy Stabilizer:** A dynamic resource management minigame.
4. **Red Light Green Light:** Uses OpenCV for real-time player motion detection via the computer camera.
5. **Final Stage (Simon Says):** A physical memory game activated on the Arduino hardware once all digital tasks are completed.

## Project Demonstration
Watch the full system in action: [Demo Video on YouTube](https://www.youtube.com/watch?v=pYHDOQSZFzM)
