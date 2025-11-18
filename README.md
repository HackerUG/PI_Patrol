# 🛡️ Pi-Patrol Smart Security System
A Raspberry Pi–based intelligent security system featuring **face recognition**, **PIR motion detection**, **gas sensing**, **camera capture**, **event logging**, and a **web dashboard**.

---

## 📌 Overview
Pi-Patrol is a modular, real-time security system built on Raspberry Pi.  
It captures motion, recognizes faces using **LBPH + CLAHE**, detects gas levels, records unknown events, and provides a **Flask-based web dashboard** for monitoring.

The system:
- Detects humans via **PIR sensor**
- Recognizes faces from a local dataset
- Records images/videos of unknown visitors
- Logs all events in `patrol.db`
- Provides live preview (`live.jpg`)
- Shows gas alerts & system status
- Runs a real-time dashboard

---

## 🧰 Hardware Requirements
- Raspberry Pi 3B / 3B+ / 4B  
- Raspberry Pi Camera Module (V2 / HQ) or USB camera  
- PIR Motion Sensor  
- Gas Sensor (MQ-x)  
- Optional: HDMI display, keyboard, mouse

---

<p align="center">
  <img src="https://img.shields.io/badge/Raspberry%20Pi-Pi%20Patrol-red?logo=raspberrypi&style=for-the-badge" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python" />
</p>

<h1 align="center">🛡️ Pi-Patrol Smart Security System</h1>
<p align="center">An advanced Raspberry Pi–based security system with AI-powered <b>Face Recognition</b>, <b>PIR Motion Detection</b>, <b>Gas Sensing</b>, <b>Event Logging</b>, and a <b>Web Dashboard</b>.</p>

---

## 🚀 Features

- 🎯 **PIR Motion Detection** – Detects movement and wakes the camera  
- 🧠 **Face Recognition (LBPH + CLAHE)** – Recognizes known faces with improved accuracy  
- 👤 **Unknown Visitor Capture** – Stores snapshots & short video clips  
- 🧪 **Gas Sensor Monitoring (MQ)** – Triggers real-time gas alerts  
- 💾 **SQLite Event Logging** – Logs all events with timestamps  
- 🖼️ **Live Preview (live.jpg)** – Updated in near real-time  
- 🌐 **Flask-based Web Dashboard** – View logs, live feed, and status  
- 🔌 **Modular Sensor Design** – Easily extendable  

---

## 🛠️ Software Requirements

### Install system packages:
```bash
sudo apt update
sudo apt install python3-opencv python3-pip git
