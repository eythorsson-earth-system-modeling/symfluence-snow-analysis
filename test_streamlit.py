import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
from streamlit_folium import st_folium

st.set_page_config(page_title="Snow Cover Analysis", layout="wide")

@st.cache_resource
def initialize_ee():
    try:
        ee.Initialize()
        return True
    except:
        try:
            ee.Authenticate()
            ee.Initialize()
            return True
        except:
            return False

def get_modis_snow(start_date, end_date, geometry=None):
    """Get MODIS snow cover data"""
    collection = ee.ImageCollection('MODIS/061/MOD10A1') \
        .filterDate(start_date, end_date) \
        .select('NDSI_Snow_Cover')
    
    if geometry:
        collection = collection.filterBounds(geometry)
    
    return collection

def analyze_snow_time_series(geometry, start_date, end_date):
    """Analyze snow cover time series for a geometry"""
    snow_collection = get_modis_snow(start_date, end_date, geometry)
    
    def calculate_snow_stats(image):
        snow_mask = image.select('NDSI_Snow_Cover').gte(10)
        snow_area = snow_mask.multiply(ee.Image.pixelArea()).divide(1e6)
        
        stats = snow_area.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geometry,
            scale=500,
            maxPixels=1e9
        )
        
        return ee.Feature(None, {
            'date': image.date().format('YYYY-MM-dd'),
            'snow_area_km2': stats.get('NDSI_Snow_Cover')
        })
    
    time_series = snow_collection.map(calculate_snow_stats)
    return time_series.getInfo()

def create_interactive_map():
    """Create interactive map with Earth Engine layers"""
    Map = geemap.Map(center=[45, -110], zoom=4)
    
    # Add base snow cover layer
    snow_vis = {
        'min': 0,
        'max': 100,
        'palette': ['black', 'blue', 'cyan', 'yellow', 'red']
    }
    
    # Recent snow cover
    recent_snow = ee.ImageCollection('MODIS/061/MOD10A1') \
        .filterDate('2023-01-01', '2023-12-31') \
        .select('NDSI_Snow_Cover') \
        .mean()
    
    Map.addLayer(recent_snow, snow_vis, 'Mean Snow Cover 2023')
    
    # Add drawing tools
    Map.add_basemap('SATELLITE')
    
    return Map

def plot_time_series(data, title):
    """Plot time series data"""
    if not data['features']:
        return None
    
    dates = []
    values = []
    
    for feature in data['features']:
        props = feature['properties']
        if props['snow_area_km2'] is not None:
            dates.append(props['date'])
            values.append(props['snow_area_km2'])
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        mode='lines+markers',
        name='Snow Area',
        line=dict(color='#2E86AB', width=2)
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='Snow Area (km²)',
        height=400,
        showlegend=False
    )
    
    return fig

def main():
    st.title("Snow Cover Analysis")
    st.write("Interactive analysis of MODIS snow cover data")
    
    if not initialize_ee():
        st.error("Earth Engine authentication required")
        st.stop()
    
    # Sidebar controls
    with st.sidebar:
        st.header("Analysis Parameters")
        
        start_date = st.date_input(
            "Start Date",
            value=date(2023, 1, 1),
            min_value=date(2000, 1, 1)
        )
        
        end_date = st.date_input(
            "End Date", 
            value=date(2023, 12, 31),
            min_value=date(2000, 1, 1)
        )
        
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Interactive Map", "Time Series Analysis", "Regional Statistics"]
        )
    
    if analysis_type == "Interactive Map":
        st.subheader("Interactive Snow Cover Map")
        st.write("Draw a polygon or click points to analyze snow cover")
        
        # Create and display map
        Map = create_interactive_map()
        map_data = st_folium(Map, width=700, height=500)
        
        # Process map interactions
        if map_data['last_object_clicked_popup']:
            coords = map_data['last_object_clicked_popup']
            st.write(f"Clicked coordinates: {coords}")
        
        if map_data['all_drawings']:
            st.write("Drawn geometries:")
            for drawing in map_data['all_drawings']:
                st.json(drawing)
    
    elif analysis_type == "Time Series Analysis":
        st.subheader("Snow Cover Time Series")
        
        # Coordinate input for point analysis
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Latitude", value=45.0, format="%.4f")
        with col2:
            lon = st.number_input("Longitude", value=-110.0, format="%.4f")
        
        buffer_km = st.slider("Buffer radius (km)", 1, 50, 10)
        
        if st.button("Analyze Time Series"):
            # Create point geometry with buffer
            point = ee.Geometry.Point([lon, lat]).buffer(buffer_km * 1000)
            
            with st.spinner("Processing time series..."):
                data = analyze_snow_time_series(
                    point, 
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
            
            if data:
                fig = plot_time_series(data, f"Snow Cover at ({lat:.3f}, {lon:.3f})")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Show data table
                if st.checkbox("Show raw data"):
                    df_data = []
                    for feature in data['features']:
                        props = feature['properties']
                        if props['snow_area_km2'] is not None:
                            df_data.append({
                                'Date': props['date'],
                                'Snow Area (km²)': props['snow_area_km2']
                            })
                    
                    if df_data:
                        df = pd.DataFrame(df_data)
                        st.dataframe(df)
                        
                        # Download option
                        csv = df.to_csv(index=False)
                        st.download_button(
                            "Download CSV",
                            csv,
                            f"snow_analysis_{lat}_{lon}.csv",
                            "text/csv"
                        )
    
    elif analysis_type == "Regional Statistics":
        st.subheader("Regional Snow Statistics")
        st.write("Upload a shapefile or define a region for analysis")
        
        # Predefined regions
        regions = {
            "Rocky Mountains": ee.Geometry.Rectangle([-115, 45, -105, 50]),
            "Sierra Nevada": ee.Geometry.Rectangle([-122, 36, -118, 40]),
            "Cascades": ee.Geometry.Rectangle([-122, 45, -120, 49])
        }
        
        selected_region = st.selectbox("Select Region", list(regions.keys()))
        
        if st.button("Analyze Region"):
            geometry = regions[selected_region]
            
            with st.spinner(f"Analyzing {selected_region}..."):
                data = analyze_snow_time_series(
                    geometry,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
            
            if data:
                fig = plot_time_series(data, f"Snow Cover - {selected_region}")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
