import streamlit as st
import ee
import pandas as pd
import plotly.graph_objects as go
from datetime import date

st.set_page_config(page_title="Snow Analysis", layout="wide")

@st.cache_resource
def init_ee():
    try:
        ee.Initialize()
        return True
    except:
        return False

@st.cache_data(ttl=3600)
def get_snow_data(lat, lon, start_date, end_date, buffer_km):
    """Cached snow data retrieval"""
    point = ee.Geometry.Point([lon, lat]).buffer(buffer_km * 1000)
    
    collection = ee.ImageCollection('MODIS/061/MOD10A1') \
        .filterDate(start_date, end_date) \
        .filterBounds(point) \
        .select('NDSI_Snow_Cover')
    
    def extract_snow(image):
        snow_mask = image.select('NDSI_Snow_Cover').gte(10)
        snow_area = snow_mask.multiply(ee.Image.pixelArea()).divide(1e6)
        
        stats = snow_area.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=point,
            scale=500,
            maxPixels=1e8
        )
        
        return ee.Feature(None, {
            'date': image.date().format('YYYY-MM-dd'),
            'snow_area': stats.get('NDSI_Snow_Cover')
        })
    
    return collection.map(extract_snow).getInfo()

def plot_snow_series(data, location):
    """Fast plotting with minimal overhead"""
    dates, values = [], []
    
    for feature in data.get('features', []):
        props = feature['properties']
        if props.get('snow_area') is not None:
            dates.append(props['date'])
            values.append(props['snow_area'])
    
    if not dates:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values,
        mode='lines',
        name='Snow Area (km²)',
        line=dict(color='#1f77b4', width=2)
    ))
    
    fig.update_layout(
        title=f'Snow Cover - {location}',
        xaxis_title='Date',
        yaxis_title='Snow Area (km²)',
        height=400,
        showlegend=False,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    return fig

def main():
    st.title("Snow Cover Analysis")
    
    if not init_ee():
        st.error("Earth Engine authentication required")
        st.stop()
    
    # Streamlined interface
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        lat = st.number_input("Latitude", value=45.0, format="%.3f")
    with col2:
        lon = st.number_input("Longitude", value=-110.0, format="%.3f")
    with col3:
        buffer_km = st.selectbox("Buffer (km)", [5, 10, 25, 50], index=1)
    with col4:
        days_back = st.selectbox("Period", [30, 90, 365], index=1)
    
    # Auto-calculate date range
    end_date = date.today()
    start_date = date.fromordinal(end_date.toordinal() - days_back)
    
    # Auto-run analysis on parameter change
    if st.button("Analyze", type="primary") or True:  # Auto-run
        with st.spinner("Processing..."):
            try:
                data = get_snow_data(
                    lat, lon, 
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    buffer_km
                )
                
                if data and data.get('features'):
                    fig = plot_snow_series(data, f"({lat:.2f}, {lon:.2f})")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Quick stats
                    values = [f['properties']['snow_area'] for f in data['features'] 
                             if f['properties'].get('snow_area') is not None]
                    
                    if values:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Max Snow Area", f"{max(values):.1f} km²")
                        with col2:
                            st.metric("Mean Snow Area", f"{sum(values)/len(values):.1f} km²")
                        with col3:
                            st.metric("Data Points", len(values))
                else:
                    st.warning("No snow data found for this location and period")
                    
            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    main()
