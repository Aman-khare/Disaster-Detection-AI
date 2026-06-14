# Disaster Detection AI

Disaster Detection AI is an autonomous, agent-based disaster intelligence and response system. It analyzes real-time weather and geographic data to predict hazards, assess risks, and generate comprehensive emergency response reports for any location globally.

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher

### Installation & Running Locally

1. **Navigate to the project directory:**
   ```bash
   cd path/to/crisismind-ai
   ```

2. **Install dependencies:**
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Start the application:**
   ```bash
   python -B main.py
   ```
   *The server will start on `http://127.0.0.1:8765`.*

4. **Access the Dashboard:**
   Open your web browser and navigate to [http://127.0.0.1:8765](http://127.0.0.1:8765).

---

## 🌍 Overview & Use Case

Disaster Detection AI is designed to assist emergency management authorities, city planners, and first responders by providing an automated, highly detailed analysis of impending natural disasters (such as floods, cyclones, and heatwaves).

When a user searches for a location or uses their live location, the system performs a multi-stage analysis:

1. **Live Data Ingestion:** Fetches real-time weather metrics (rainfall, wind speed, temperature, AQI) using Open-Meteo and geolocation data using Nominatim.
2. **Contextual Data Generation:** Dynamically generates location-aware contextual data. This includes plausible map regions, evacuation shelters, hospitals, schools, and emergency contact numbers mapped to the specific country/region being analyzed.
3. **Multi-Agent Pipeline:** A sequence of specialized logic agents processes the data:
   - **Weather Intelligence Agent:** Builds the live hazard footprint based on weather conditions.
   - **Disaster Prediction Agent:** Scores disaster probability, confidence, and alert states.
   - **Situation Assessment Agent:** Estimates the impact on the local population and critical infrastructure.
   - **Safe Zone Agent:** Ranks potential shelter locations based on safety buffers, distance, and capacity.
   - **Evacuation Planning Agent:** Computes hazard-aware evacuation routes and estimated travel times.
   - **Citizen Survival Assistant:** Prepares citizen instructions, emergency supply checklists, and contact guidance.
   - **Resource Allocation Agent:** Suggests field deployment strategies for ambulances, rescue teams, and drones.
   - **Emergency Report Agent:** Compiles all findings into an authority-facing incident recommendation report.
4. **Interactive Dashboard & Reporting:** The results are presented in a sleek, responsive web dashboard featuring dynamic hazard maps, critical risk metrics, safe zone directories, and the ability to download the full intelligence report as a PDF.

## 🏗 Architecture

The system is built as a self-contained web application:
- **Backend:** Pure Python 3.11+ using the standard library `http.server`. It requires zero external backend frameworks (like Django/FastAPI) to run.
- **Frontend:** Vanilla JavaScript, HTML5, and CSS3. The UI uses a modern design system with dynamic SVG maps and animated metrics.
- **Data Protocols:** The architecture supports the Model Context Protocol (MCP) for tool and data integration. The engine leverages an internal `LocalDatasetRegistry` to dynamically generate region-specific data, ensuring the application remains fully functional globally even without external data providers.

## 🧪 Testing

To run the automated test suite, execute the following command from the project root:

```bash
python -B -m unittest discover -s tests -v
```
