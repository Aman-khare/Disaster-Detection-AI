<div align="center">
  <h1>🚨 Disaster Detection AI</h1>
  <p><strong>Autonomous Disaster Intelligence and Response System</strong></p>
</div>

Disaster Detection AI is an intelligent, autonomous, agent-based disaster prediction and response system. It analyzes real-time weather, geographic data, and live signals to predict hazards, assess risks, and generate comprehensive emergency response plans globally.

Powered by the **Model Context Protocol (MCP)** and advanced LLMs (like **Google Gemini**), the system operates via specialized agents that collaborate to ensure timely and actionable disaster intelligence.

---

## ✨ Key Features

- **Live Intelligence Ingestion:** Fetches real-time weather metrics (rainfall, wind speed, temperature, AQI) and geolocation data globally.
- **Autonomous Multi-Agent Pipeline:** Employs a sequence of specialized AI agents:
  - 🌦️ **Weather Intelligence Agent:** Builds a live hazard footprint.
  - 📉 **Disaster Prediction Agent:** Scores disaster probability, confidence, and alert states.
  - 🏙️ **Situation Assessment Agent:** Estimates the impact on the local population and infrastructure.
  - 🛡️ **Safe Zone Agent:** Ranks potential shelter locations based on safety buffers and capacity.
  - 🗺️ **Evacuation Planning Agent:** Computes hazard-aware evacuation routes.
  - 🆘 **Citizen Survival Assistant:** Prepares citizen instructions and emergency supply checklists.
  - 🚑 **Resource Allocation Agent:** Suggests field deployment strategies for rescue teams.
- **Dynamic Context Generation:** Automatically infers local emergency contacts, regional layout, and critical infrastructure based on the location.
- **Interactive Dashboard:** Sleek, responsive web dashboard with dynamic hazard maps, metrics, and automated PDF reporting.

---

## 🏗 Architecture

- **Backend:** Pure Python 3.11+ using the standard library `http.server`. No heavy web frameworks required.
- **Frontend:** Vanilla JS, HTML5, and CSS3 featuring a custom Glassmorphic design system and dynamic SVG maps.
- **AI & Data Protocols:** Utilizes the **Model Context Protocol (MCP)** to standardize tool execution. Agents are powered by LLMs to process signals and execute reasoning.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11** or higher
- **Git**
- **Gemini API Key:** Required for powering the reasoning capabilities of the autonomous AI agents via the MCP integration.

### 1. Clone the Repository

```bash
git clone https://github.com/Aman-khare/Disaster-Detection-AI.git
cd Disaster-Detection-AI
```

### 2. Configure the Gemini API Key

The system's agents utilize the Google Gemini API for their reasoning, decision-making, and natural language generation. 

Create a `.env` file in the root directory and add your API key, or set it as an environment variable in your terminal:

**On Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

**On macOS/Linux:**
```bash
export GEMINI_API_KEY="your_api_key_here"
```

> **Note:** The Gemini API key is queried by the engine's core logic whenever an agent needs to resolve ambiguities in live data, generate citizen survival instructions, or synthesize the final emergency report.

### 3. Install Dependencies

Install the necessary Python packages:

```bash
python -m pip install -r requirements.txt
```

### 4. Run the Application Locally

Start the local AI server:

```bash
python -B main.py
```

The server will initialize and start running on `http://127.0.0.1:8765`. 
Open your web browser and navigate to [http://127.0.0.1:8765](http://127.0.0.1:8765) to access the Disaster Detection Dashboard.

---

## 🧪 Testing Locally

The project includes an automated test suite to ensure the reliability of the agent pipelines and data ingestion tools. 

To run the unit tests locally, execute the following command from the project root directory:

```bash
python -B -m unittest discover -s tests -v
```

This will run tests against the engine logic, local server endpoints, and live weather ingestion mockups.

---

## 🔮 Future Scope

- **IoT Sensor Integration:** Direct ingestion from river sensors, seismographs, and live traffic cameras.
- **Social Listening Agents:** Reading live social media streams (e.g., X/Twitter) to gauge real-time public panic levels.
- **Automated Dispatch Integration:** Direct API pipelines with local emergency dispatch to route ambulances automatically.

---

## 🤝 Contributing

Contributions are welcome! If you'd like to improve the agents, add new data ingestion tools, or refine the UI, feel free to fork the repository, create a feature branch, and submit a pull request.
