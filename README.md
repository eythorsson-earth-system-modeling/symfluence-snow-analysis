# SYMFLUENCE Snow Cover Analysis Tool

🌨️ **Advanced snow cover analysis using Google Earth Engine and MODIS satellite data**

Built by **Darri Eythorsson**, University of Calgary  
Contact: darri@symfluence.org

## 🚀 Features

- **📊 Watershed Analysis**: Complete basin-scale snow cover analysis
- **📍 Point Analysis**: Detailed location-specific analysis with SWE time series  
- **🎬 Animation Support**: Snow evolution visualization over time
- **📈 Advanced Statistics**: Peak timing, persistence, seasonal patterns
- **💾 Multiple Export Formats**: CSV, JSON, comprehensive summaries
- **🗺️ Interactive Maps**: Click-to-analyze functionality with folium integration

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/eythorsson-earth-system-modeling/symfluence-snow-analysis.git
cd symfluence-snow-analysis

# Install dependencies
pip install -r requirements.txt

# Set up Google Earth Engine authentication
earthengine authenticate
```

## 🎯 Usage

```bash
# Run the Streamlit app
streamlit run test_streamlit.py
```

The app will open in your browser at `http://localhost:8501`

## 📊 Data Sources

- **MODIS/061/MOD10A1**: Daily snow cover data
- **USGS/GTOPO30**: Digital elevation model
- **Custom watersheds**: User-defined analysis boundaries
- **Time Range**: 2000-present (daily resolution)

## 🌟 Analysis Modes

### Watershed Analysis
- Complete basin-scale snow cover statistics
- Seasonal snow patterns and trends
- Elevation-dependent analysis
- Multi-year comparisons

### Point Analysis  
- Location-specific snow cover time series
- SWE (Snow Water Equivalent) analysis
- Interactive map selection
- Detailed statistical summaries

## 📈 Outputs

- **Time Series Charts**: Interactive plotly visualizations
- **Statistical Summaries**: Peak timing, duration, persistence
- **Animation Frames**: Snow evolution over time
- **Export Options**: CSV, JSON, summary reports

## 🔬 Technical Details

- **Platform**: Google Earth Engine + Streamlit
- **Language**: Python 3.8+
- **Visualization**: Plotly, Folium
- **Data Processing**: Earth Engine API
- **UI Framework**: Streamlit with custom CSS

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## 📧 Contact

**Darri Eythorsson**  
University of Calgary  
Email: darri@symfluence.org  
Website: https://eythorsson-earth-system-modeling.github.io
