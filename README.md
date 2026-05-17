# 🥾 Pathfinder — The AI Smart Trail & Travel Companion

**Developed for the Deloitte Makeathon 2026 by Team MAURAETOI.**

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B.svg)
![AI](https://img.shields.io/badge/AI-Groq_Llama_3.1-000000.svg)
![Sustainability](https://img.shields.io/badge/Focus-Sustainability_%26_Eco--Tourism-4CAF50.svg)

---

## 🌍 The Problem: Over-tourism & Generic Travel
Greece is one of the top tourist destinations globally, but this often leads to **over-tourism** in specific hotspots (e.g., Santorini, Mykonos, central Athens). This creates severe environmental strain, overcrowding, and a generic, non-personalized experience for travelers. Current travel apps offer static suggestions, ignoring the user's micro-interests and completely bypassing the environmental impact or local biodiversity.

## 💡 Our Solution: Pathfinder
**Pathfinder** is an intelligent, dynamic, and eco-conscious AI travel companion built to decentralize tourism and promote sustainable exploration across Greece. 

Instead of forcing users into generic tourist traps, Pathfinder uses advanced Generative AI to understand the user's exact preferences—whether they are looking for a moderate mountain hike, local seafood gastronomy, ancient history, or even specific sports culture (like tennis or basketball). It then suggests highly targeted, alternative Greek destinations.

Once a destination is chosen, Pathfinder transforms into a **Live Environmental Dashboard**, empowering the user with real-time data to plan safely and sustainably.

---

## ✨ Core Features & The User Journey

### 1. Adaptive AI Planner (Zero-Click Context)
- Powered by the blazing-fast **Groq API (`Llama-3.1-8b-instant`)**.
- The AI acts as a conversational agent. Users can answer 3 simple hiking questions (Difficulty, Time, Landscape) OR simply state an interest (e.g., "I love basketball and culture").
- The AI instantly adapts, skipping rigid flows, and outputs highly personalized location recommendations in beautiful HTML/CSS rendered cards.

### 2. Interactive & Dynamic UI
- Built entirely in **Streamlit** with a custom premium UI/UX (dark-green "forest" theme).
- **Auto-generated Interactive Buttons:** The app parses the AI's suggestions and dynamically creates clickable buttons for the recommended destinations. Zero typing required from the user.

### 3. Real-Time Environmental Dashboard
Upon selecting a location, the app automatically fetches and displays:
- **Live Weather & Topography:** Uses the *OpenWeatherMap API* and *Open-Elevation API* to display real-time temperature, humidity, wind speed, and altitude.
- **Biodiversity Tracking:** Integrates with the *iNaturalist API* to list the exact species of flora and fauna (plants, insects, birds) recently observed in that specific area, bringing the user closer to nature.

### 4. Regional Sustainability Score
- A dynamic scoring engine that calculates a **Sustainability & Crowd Avoidance Score (0-100)**.
- It rewards locations that are away from massive tourist hotspots and provides actionable **Eco-Tips** (e.g., "Leave No Trace", "Respect local wildlife") to guide user behavior.

---

## 🛠️ Technical Architecture & Stack

- **Frontend & Routing:** Streamlit (Python) with injected HTML5/CSS3 for premium card styling and layout management.
- **LLM Engine:** Groq Cloud API utilizing the `llama-3.1-8b-instant` model for near-zero latency conversational generation and strict output formatting.
- **External APIs & Microservices:**
  - `OpenWeatherMap API` (Live meteorological data)
  - `iNaturalist API` (Real-time biological observations)
  - `Open-Elevation API` (Topographical altitude data)
  - `Geocoding Services` (Translating city/island names to accurate Lat/Lon coordinates)

---

## 🚀 Installation & Local Setup

### Prerequisites
- Python 3.9 or higher.
- Git installed on your machine.

### Step-by-Step Guide

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/geoeleu13/makeathon-2026-mauraetoi-pathfinder-deloitte.git](https://github.com/geoeleu13/makeathon-2026-mauraetoi-pathfinder-deloitte.git)
   cd makeathon-2026-mauraetoi-pathfinder-deloitte

   
2. **install the required dependencies:**

pip install -r requirements.txt
3. **Configure Environment Variables:**

Create a .env file in the root directory. Add your secure API keys as follows:
GROQ_API_KEY=your_groq_api_key_here
OPENWEATHER_API_KEY=your_openweather_key_here
(Note: The .env file is excluded via .gitignore to ensure security).
4. **Laucnh application:**
streamlit run app.py
