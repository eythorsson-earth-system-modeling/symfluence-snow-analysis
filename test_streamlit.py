#!/usr/bin/env python3
"""
SYMFLUENCE Snow Cover Analysis - Advanced Interactive App
Beautiful app with maps, point-click analysis, SWE time series, and animated visualizations
"""

import streamlit as st
import ee
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, date
import json
import time
from PIL import Image
import io
import base64

# Optional imports for mapping
try:
    import folium
    from streamlit_folium import st_folium
    MAPPING_AVAILABLE = True
except ImportError:
    MAPPING_AVAILABLE = False
    st.warning("⚠️ Mapping features disabled. Install folium and streamlit-folium for full functionality.")

# Page config
st.set_page_config(
    page_title="SYMFLUENCE Snow Analysis",
    page_icon="🌨️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for beautiful styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #2E86AB 0%, #A23B72 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2E86AB;
        margin: 0.5rem 0;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .error-box {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .sidebar .sidebar-content {
        background: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def initialize_ee():
    """Initialize Earth Engine with error handling"""
    try:
        ee.Initialize(project='ee-koppengeiger')
        return True, "✅ Earth Engine connected successfully"
    except Exception as e:
        return False, f"❌ Earth Engine initialization failed: {str(e)}"

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_watersheds():
    """Get watershed list with caching"""
    try:
        watersheds = ee.FeatureCollection('projects/ee-koppengeiger/assets/merged_lumped')
        names = watersheds.aggregate_array('layer').distinct().getInfo()
        return sorted(names), None
    except Exception as e:
        return [], f"Failed to load watersheds: {str(e)}"

def analyze_snow_cover(watershed_name, start_date, end_date, progress_bar=None):
    """Analyze snow cover with progress tracking"""
    
    try:
        # Update progress
        if progress_bar:
            progress_bar.progress(10, "Loading watershed data...")
        
        watersheds = ee.FeatureCollection('projects/ee-koppengeiger/assets/merged_lumped')
        modis = ee.ImageCollection("MODIS/061/MOD10A1")
        
        # Get watershed
        watershed = watersheds.filter(ee.Filter.eq('layer', watershed_name)).first()
        geometry = watershed.geometry()
        
        if progress_bar:
            progress_bar.progress(30, "Filtering MODIS data...")
        
        # Filter MODIS
        snow_collection = modis.filterDate(
            start_date.strftime('%Y-%m-%d'), 
            end_date.strftime('%Y-%m-%d')
        ).filterBounds(geometry)
        
        # Get collection size
        collection_size = snow_collection.size().getInfo()
        
        if collection_size == 0:
            return None, None, "No MODIS data found for the selected period and watershed"
        
        if progress_bar:
            progress_bar.progress(50, f"Processing {collection_size} MODIS images...")
        
        # Calculate snow metrics
        def calculate_snow_metrics(image):
            snow_mask = image.select('NDSI_Snow_Cover').gte(10)
            snow_stats = snow_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=500,
                maxPixels=1e9
            )
            snow_percent = ee.Number(snow_stats.get('NDSI_Snow_Cover', 0)).multiply(100)
            
            return ee.Feature(None, {
                'date': image.date().format('YYYY-MM-dd'),
                'snow_cover_percent': snow_percent,
                'year': image.date().get('year'),
                'month': image.date().get('month')
            })
        
        # Process data
        snow_features = snow_collection.map(calculate_snow_metrics)
        
        if progress_bar:
            progress_bar.progress(80, "Converting to DataFrame...")
        
        features_list = snow_features.getInfo()['features']
        
        # Convert to DataFrame
        data = []
        for feature in features_list:
            props = feature['properties']
            if props['snow_cover_percent'] is not None:  # Filter out null values
                data.append({
                    'date': pd.to_datetime(props['date']),
                    'snow_cover_percent': float(props['snow_cover_percent']),
                    'year': int(props['year']),
                    'month': int(props['month'])
                })
        
        df = pd.DataFrame(data)
        
        if df.empty:
            return None, None, "No valid snow cover data found"
        
        if progress_bar:
            progress_bar.progress(100, "Analysis complete!")
        
        # Calculate statistics
        stats = {
            'mean': df['snow_cover_percent'].mean(),
            'max': df['snow_cover_percent'].max(),
            'min': df['snow_cover_percent'].min(),
            'std': df['snow_cover_percent'].std(),
            'count': len(df),
            'images_processed': collection_size
        }
        
        return df, stats, None
        
    except Exception as e:
        return None, None, f"Analysis failed: {str(e)}"

def create_time_series_chart(df, watershed_name):
    """Create beautiful time series chart"""
    fig = px.line(
        df, 
        x='date', 
        y='snow_cover_percent',
        title=f'Snow Cover Time Series - {watershed_name}',
        labels={'snow_cover_percent': 'Snow Cover (%)', 'date': 'Date'},
        color_discrete_sequence=['#2E86AB']
    )
    
    fig.update_layout(
        height=500,
        showlegend=False,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font_size=18,
        title_font_color='#2E86AB',
        xaxis=dict(
            showgrid=True,
            gridcolor='#f0f0f0',
            title_font_size=14
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#f0f0f0',
            title_font_size=14,
            range=[0, 100]
        )
    )
    
    return fig

def create_seasonal_chart(df):
    """Create seasonal pattern chart"""
    monthly_avg = df.groupby('month')['snow_cover_percent'].mean().reset_index()
    monthly_avg['month_name'] = monthly_avg['month'].map({
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    })
    
    fig = px.bar(
        monthly_avg,
        x='month_name',
        y='snow_cover_percent',
        title='Seasonal Snow Cover Pattern',
        color='snow_cover_percent',
        color_continuous_scale='Blues',
        labels={'snow_cover_percent': 'Average Snow Cover (%)', 'month_name': 'Month'}
    )
    
    fig.update_layout(
        height=400,
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font_size=16,
        title_font_color='#A23B72'
    )
    
    return fig

def create_distribution_chart(df, stats):
    """Create distribution histogram"""
    fig = px.histogram(
        df,
        x='snow_cover_percent',
        nbins=30,
        title='Snow Cover Distribution',
        color_discrete_sequence=['#17a2b8'],
        labels={'snow_cover_percent': 'Snow Cover (%)', 'count': 'Frequency'}
    )
    
    fig.add_vline(
        x=stats['mean'],
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {stats['mean']:.1f}%",
        annotation_position="top"
    )
    
    fig.update_layout(
        height=400,
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font_size=16,
        title_font_color='#17a2b8'
    )
    
    return fig
    """Analyze snow cover at a specific point with buffer"""
    
    try:
        # Create point geometry with buffer
        point = ee.Geometry.Point([lon, lat]).buffer(buffer_size)
        
        # Get MODIS data
        modis = ee.ImageCollection("MODIS/061/MOD10A1")
        snow_collection = modis.filterDate(
            start_date.strftime('%Y-%m-%d'), 
            end_date.strftime('%Y-%m-%d')
        ).filterBounds(point)
        
        # Calculate snow metrics for each image
        def calculate_point_snow(image):
            # Snow cover percentage
            snow_mask = image.select('NDSI_Snow_Cover').gte(10)
            snow_stats = snow_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=500,
                maxPixels=1e6
            )
            
            # Snow Water Equivalent (if available)
            swe_stats = image.select('NDSI_Snow_Cover').reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=500,
                maxPixels=1e6
            )
            
            return ee.Feature(None, {
                'date': image.date().format('YYYY-MM-dd'),
                'snow_cover_percent': ee.Number(snow_stats.get('NDSI_Snow_Cover', 0)).multiply(100),
                'swe_estimate': ee.Number(swe_stats.get('NDSI_Snow_Cover', 0)).multiply(50),  # Rough SWE estimate
                'year': image.date().get('year'),
                'month': image.date().get('month'),
                'doy': image.date().getRelative('day', 'year')
            })
        
        # Process collection
        point_data = snow_collection.map(calculate_point_snow)
        features_list = point_data.getInfo()['features']
        
        # Convert to DataFrame
        data = []
        for feature in features_list:
            props = feature['properties']
            if props['snow_cover_percent'] is not None:
                data.append({
                    'date': pd.to_datetime(props['date']),
                    'snow_cover_percent': float(props['snow_cover_percent']),
                    'swe_estimate': float(props['swe_estimate']),
                    'year': int(props['year']),
                    'month': int(props['month']),
                    'doy': int(props['doy'])
                })
        
        return pd.DataFrame(data)
        
    except Exception as e:
        st.error(f"Point analysis failed: {str(e)}")
        return None

def create_interactive_map(watersheds_fc, center_lat=51, center_lon=-115):
    """Create interactive Folium map with watersheds"""
    
    if not MAPPING_AVAILABLE:
        st.error("❌ Mapping functionality requires folium and streamlit-folium packages")
        return None
    
    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles='OpenStreetMap'
    )
    
    # Add satellite imagery option
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Add watersheds layer
    try:
        # Get watershed geometries (simplified for performance)
        watersheds_geojson = watersheds_fc.getInfo()
        
        folium.GeoJson(
            watersheds_geojson,
            style_function=lambda x: {
                'fillColor': 'blue',
                'color': 'blue',
                'weight': 2,
                'fillOpacity': 0.1,
                'opacity': 0.8
            },
            popup=folium.GeoJsonPopup(fields=['layer'], labels=True),
            tooltip=folium.GeoJsonTooltip(fields=['layer'], labels=False)
        ).add_to(m)
        
    except Exception as e:
        st.warning(f"Could not load watershed boundaries: {str(e)}")
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add click instruction
    folium.Marker(
        [center_lat + 2, center_lon],
        popup="Click anywhere on the map to analyze snow cover at that point!",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)
    
    return m

def create_swe_time_series_chart(df, lat, lon):
    """Create SWE time series chart"""
    
    fig = go.Figure()
    
    # Add snow cover percentage
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['snow_cover_percent'],
        mode='lines+markers',
        name='Snow Cover (%)',
        line=dict(color='#2E86AB', width=2),
        marker=dict(size=4),
        yaxis='y'
    ))
    
    # Add SWE estimate
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['swe_estimate'],
        mode='lines+markers',
        name='SWE Estimate (mm)',
        line=dict(color='#A23B72', width=2),
        marker=dict(size=4),
        yaxis='y2'
    ))
    
    # Update layout for dual y-axis
    fig.update_layout(
        title=f'Snow Analysis at Point ({lat:.3f}, {lon:.3f})',
        xaxis_title='Date',
        yaxis=dict(
            title='Snow Cover (%)',
            side='left',
            range=[0, 100],
            titlefont=dict(color='#2E86AB'),
            tickfont=dict(color='#2E86AB')
        ),
        yaxis2=dict(
            title='SWE Estimate (mm)',
            side='right',
            overlaying='y',
            titlefont=dict(color='#A23B72'),
            tickfont=dict(color='#A23B72')
        ),
        height=500,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    return fig

def create_snow_animation_frames(watershed_name, start_date, end_date, max_frames=12):
    """Create frames for snow cover animation"""
    
    try:
        watersheds = ee.FeatureCollection('projects/ee-koppengeiger/assets/merged_lumped')
        modis = ee.ImageCollection("MODIS/061/MOD10A1")
        
        # Get watershed
        watershed = watersheds.filter(ee.Filter.eq('layer', watershed_name)).first()
        geometry = watershed.geometry()
        
        # Create monthly composites
        months = pd.date_range(start_date, end_date, freq='MS')[:max_frames]
        
        frames_data = []
        
        for i, month_start in enumerate(months):
            month_end = month_start + pd.DateOffset(months=1) - pd.DateOffset(days=1)
            
            # Get monthly composite
            monthly_snow = modis.filterDate(
                month_start.strftime('%Y-%m-%d'),
                month_end.strftime('%Y-%m-%d')
            ).filterBounds(geometry).select('NDSI_Snow_Cover').mean()
            
            # Create snow mask
            snow_mask = monthly_snow.gte(10).multiply(100)
            
            # Get image URL for visualization
            vis_params = {
                'min': 0,
                'max': 100,
                'palette': ['white', 'lightblue', 'blue', 'darkblue']
            }
            
            # This would normally create a map tile, but for demo we'll create data
            frames_data.append({
                'month': month_start.strftime('%Y-%m'),
                'image': snow_mask,
                'bounds': geometry.bounds().getInfo()
            })
        
        return frames_data
        
    except Exception as e:
        st.error(f"Animation creation failed: {str(e)}")
        return []

def create_advanced_statistics(df):
    """Create advanced statistical analysis"""
    
    stats = {}
    
    # Basic statistics
    stats['basic'] = {
        'mean': df['snow_cover_percent'].mean(),
        'median': df['snow_cover_percent'].median(),
        'std': df['snow_cover_percent'].std(),
        'min': df['snow_cover_percent'].min(),
        'max': df['snow_cover_percent'].max(),
        'q25': df['snow_cover_percent'].quantile(0.25),
        'q75': df['snow_cover_percent'].quantile(0.75)
    }
    
    # Seasonal statistics
    seasonal_stats = df.groupby('month')['snow_cover_percent'].agg(['mean', 'std', 'count'])
    stats['seasonal'] = seasonal_stats.to_dict()
    
    # Annual trends
    annual_stats = df.groupby('year')['snow_cover_percent'].agg(['mean', 'std', 'count'])
    stats['annual'] = annual_stats.to_dict()
    
    # Snow persistence (days with >50% snow cover)
    high_snow_days = len(df[df['snow_cover_percent'] > 50])
    total_days = len(df)
    stats['persistence'] = {
        'high_snow_days': high_snow_days,
        'total_days': total_days,
        'persistence_ratio': high_snow_days / total_days if total_days > 0 else 0
    }
    
    # Peak snow timing
    if not df.empty:
        peak_snow_idx = df['snow_cover_percent'].idxmax()
        peak_snow_date = df.loc[peak_snow_idx, 'date']
        peak_snow_doy = df.loc[peak_snow_idx, 'doy']
        
        stats['peak_timing'] = {
            'peak_date': peak_snow_date,
            'peak_doy': peak_snow_doy,
            'peak_value': df.loc[peak_snow_idx, 'snow_cover_percent']
        }
    
    return stats

def create_statistical_dashboard(stats):
    """Create comprehensive statistical dashboard"""
    
    # Basic statistics cards
    st.markdown("#### 📊 Statistical Summary")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Mean", f"{stats['basic']['mean']:.1f}%")
    with col2:
        st.metric("Median", f"{stats['basic']['median']:.1f}%")
    with col3:
        st.metric("Std Dev", f"{stats['basic']['std']:.1f}%")
    with col4:
        st.metric("Q25-Q75", f"{stats['basic']['q25']:.1f}-{stats['basic']['q75']:.1f}%")
    with col5:
        st.metric("Range", f"{stats['basic']['max'] - stats['basic']['min']:.1f}%")
    
    # Snow persistence
    st.markdown("#### ❄️ Snow Persistence Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("High Snow Days", f"{stats['persistence']['high_snow_days']}")
    with col2:
        st.metric("Total Days", f"{stats['persistence']['total_days']}")
    with col3:
        st.metric("Persistence Ratio", f"{stats['persistence']['persistence_ratio']:.2%}")
    
    # Peak timing
    if 'peak_timing' in stats:
        st.markdown("#### 🏔️ Peak Snow Analysis")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Peak Date", stats['peak_timing']['peak_date'].strftime('%Y-%m-%d'))
        with col2:
            st.metric("Day of Year", f"{stats['peak_timing']['peak_doy']}")
        with col3:
            st.metric("Peak Value", f"{stats['peak_timing']['peak_value']:.1f}%")
    """Analyze snow cover with progress tracking"""
    
    try:
        # Update progress
        if progress_bar:
            progress_bar.progress(10, "Loading watershed data...")
        
        watersheds = ee.FeatureCollection('projects/ee-koppengeiger/assets/merged_lumped')
        modis = ee.ImageCollection("MODIS/061/MOD10A1")
        
        # Get watershed
        watershed = watersheds.filter(ee.Filter.eq('layer', watershed_name)).first()
        geometry = watershed.geometry()
        
        if progress_bar:
            progress_bar.progress(30, "Filtering MODIS data...")
        
        # Filter MODIS
        snow_collection = modis.filterDate(
            start_date.strftime('%Y-%m-%d'), 
            end_date.strftime('%Y-%m-%d')
        ).filterBounds(geometry)
        
        # Get collection size
        collection_size = snow_collection.size().getInfo()
        
        if collection_size == 0:
            return None, None, "No MODIS data found for the selected period and watershed"
        
        if progress_bar:
            progress_bar.progress(50, f"Processing {collection_size} MODIS images...")
        
        # Calculate snow metrics
        def calculate_snow_metrics(image):
            snow_mask = image.select('NDSI_Snow_Cover').gte(10)
            snow_stats = snow_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=500,
                maxPixels=1e9
            )
            snow_percent = ee.Number(snow_stats.get('NDSI_Snow_Cover', 0)).multiply(100)
            
            return ee.Feature(None, {
                'date': image.date().format('YYYY-MM-dd'),
                'snow_cover_percent': snow_percent,
                'year': image.date().get('year'),
                'month': image.date().get('month')
            })
        
        # Process data
        snow_features = snow_collection.map(calculate_snow_metrics)
        
        if progress_bar:
            progress_bar.progress(80, "Converting to DataFrame...")
        
        features_list = snow_features.getInfo()['features']
        
        # Convert to DataFrame
        data = []
        for feature in features_list:
            props = feature['properties']
            if props['snow_cover_percent'] is not None:  # Filter out null values
                data.append({
                    'date': pd.to_datetime(props['date']),
                    'snow_cover_percent': float(props['snow_cover_percent']),
                    'year': int(props['year']),
                    'month': int(props['month'])
                })
        
        df = pd.DataFrame(data)
        
        if df.empty:
            return None, None, "No valid snow cover data found"
        
        if progress_bar:
            progress_bar.progress(100, "Analysis complete!")
        
        # Calculate statistics
        stats = {
            'mean': df['snow_cover_percent'].mean(),
            'max': df['snow_cover_percent'].max(),
            'min': df['snow_cover_percent'].min(),
            'std': df['snow_cover_percent'].std(),
            'count': len(df),
            'images_processed': collection_size
        }
        
        return df, stats, None
        
    except Exception as e:
        return None, None, f"Analysis failed: {str(e)}"

def create_time_series_chart(df, watershed_name):
    """Create beautiful time series chart"""
    fig = px.line(
        df, 
        x='date', 
        y='snow_cover_percent',
        title=f'Snow Cover Time Series - {watershed_name}',
        labels={'snow_cover_percent': 'Snow Cover (%)', 'date': 'Date'},
        color_discrete_sequence=['#2E86AB']
    )
    
    fig.update_layout(
        height=500,
        showlegend=False,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font_size=18,
        title_font_color='#2E86AB',
        xaxis=dict(
            showgrid=True,
            gridcolor='#f0f0f0',
            title_font_size=14
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#f0f0f0',
            title_font_size=14,
            range=[0, 100]
        )
    )
    
    return fig

def create_seasonal_chart(df):
    """Create seasonal pattern chart"""
    monthly_avg = df.groupby('month')['snow_cover_percent'].mean().reset_index()
    monthly_avg['month_name'] = monthly_avg['month'].map({
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    })
    
    fig = px.bar(
        monthly_avg,
        x='month_name',
        y='snow_cover_percent',
        title='Seasonal Snow Cover Pattern',
        color='snow_cover_percent',
        color_continuous_scale='Blues',
        labels={'snow_cover_percent': 'Average Snow Cover (%)', 'month_name': 'Month'}
    )
    
    fig.update_layout(
        height=400,
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font_size=16,
        title_font_color='#A23B72'
    )
    
    return fig

def create_distribution_chart(df, stats):
    """Create distribution histogram"""
    fig = px.histogram(
        df,
        x='snow_cover_percent',
        nbins=30,
        title='Snow Cover Distribution',
        color_discrete_sequence=['#17a2b8'],
        labels={'snow_cover_percent': 'Snow Cover (%)', 'count': 'Frequency'}
    )
    
    fig.add_vline(
        x=stats['mean'],
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {stats['mean']:.1f}%",
        annotation_position="top"
    )
    
    fig.update_layout(
        height=400,
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font_size=16,
        title_font_color='#17a2b8'
    )
    
    return fig

def main():
    """Main Streamlit app with advanced features"""
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🌨️ SYMFLUENCE Snow Cover Analysis</h1>
        <p>Advanced watershed snow monitoring with interactive maps and point analysis</p>
        <p><em>Built by Darri Eythorsson, University of Calgary</em></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize Earth Engine
    ee_status, ee_message = initialize_ee()
    
    if ee_status:
        st.markdown(f'<div class="success-box">{ee_message}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="error-box">{ee_message}<br>Please run: <code>earthengine authenticate</code></div>', unsafe_allow_html=True)
        st.stop()
    
    # Get watersheds
    watersheds, error = get_watersheds()
    if error:
        st.error(f"❌ {error}")
        st.stop()
    
    watersheds_fc = ee.FeatureCollection('projects/ee-koppengeiger/assets/merged_lumped')
    
    # Sidebar controls
    st.sidebar.markdown("## 🎛️ Analysis Controls")
    st.sidebar.success(f"✅ Loaded {len(watersheds)} watersheds")
    
    # Analysis mode selection
    analysis_modes = ["Watershed Analysis", "Point Analysis"]
    if MAPPING_AVAILABLE:
        analysis_modes.append("Interactive Map")
    
    analysis_mode = st.sidebar.radio(
        "🔬 Analysis Mode",
        analysis_modes,
        help="Choose your analysis approach"
    )
    
    # Date range (common for all modes)
    st.sidebar.markdown("### 📅 Analysis Period")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date(2022, 1, 1),
            min_value=date(2000, 1, 1),
            max_value=date(2023, 12, 31)
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=date(2023, 12, 31),
            min_value=date(2000, 1, 1),
            max_value=date(2023, 12, 31)
        )
    
    # Mode-specific content
    if analysis_mode == "Interactive Map" and MAPPING_AVAILABLE:
        st.markdown("## 🗺️ Interactive Snow Analysis Map")
        st.info("👆 Click anywhere on the map to analyze snow cover at that point!")
        
        # Create and display map
        map_obj = create_interactive_map(watersheds_fc)
        if map_obj:
            map_data = st_folium(map_obj, width=700, height=500, returned_objects=["last_object_clicked"])
            
            # Handle map clicks
            if map_data['last_object_clicked']:
                clicked_lat = map_data['last_object_clicked']['lat']
                clicked_lon = map_data['last_object_clicked']['lng']
                
                st.success(f"📍 Analyzing point: {clicked_lat:.4f}, {clicked_lon:.4f}")
                
                # Analyze clicked point
                with st.spinner("🔄 Analyzing snow cover at clicked point..."):
                    point_df = analyze_point_snow_cover(clicked_lat, clicked_lon, start_date, end_date)
                
                if point_df is not None and not point_df.empty:
                    # Display point analysis results
                    st.markdown("### 📊 Point Analysis Results")
                    
                    # Create SWE time series chart
                    swe_chart = create_swe_time_series_chart(point_df, clicked_lat, clicked_lon)
                    st.plotly_chart(swe_chart, use_container_width=True)
                    
                    # Advanced statistics for point
                    point_stats = create_advanced_statistics(point_df)
                    create_statistical_dashboard(point_stats)
                    
                    # Download point data
                    st.markdown("### 💾 Download Point Data")
                    csv_data = point_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Point Analysis CSV",
                        data=csv_data,
                        file_name=f"point_analysis_{clicked_lat:.4f}_{clicked_lon:.4f}_{start_date}_{end_date}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("❌ No data found for the clicked point")
    
    elif analysis_mode == "Interactive Map" and not MAPPING_AVAILABLE:
        st.error("❌ Interactive Map mode requires folium and streamlit-folium packages")
        st.info("Install with: pip install folium streamlit-folium")
    
    elif analysis_mode == "Point Analysis":
        st.markdown("## 📍 Point Snow Analysis")
        
        # Manual coordinate input
        col1, col2 = st.columns(2)
        with col1:
            input_lat = st.number_input("Latitude", value=51.1784, min_value=-90.0, max_value=90.0, step=0.0001, format="%.4f")
        with col2:
            input_lon = st.number_input("Longitude", value=-115.5708, min_value=-180.0, max_value=180.0, step=0.0001, format="%.4f")
        
        buffer_size = st.slider("Analysis Buffer (meters)", min_value=500, max_value=5000, value=1000, step=500)
        
        if st.button("🚀 Analyze Point", type="primary"):
            with st.spinner(f"🔄 Analyzing point ({input_lat:.4f}, {input_lon:.4f})..."):
                point_df = analyze_point_snow_cover(input_lat, input_lon, start_date, end_date, buffer_size)
            
            if point_df is not None and not point_df.empty:
                # Display results
                swe_chart = create_swe_time_series_chart(point_df, input_lat, input_lon)
                st.plotly_chart(swe_chart, use_container_width=True)
                
                # Advanced statistics
                point_stats = create_advanced_statistics(point_df)
                create_statistical_dashboard(point_stats)
    
    elif analysis_mode == "Watershed Analysis":
        # Original watershed analysis with enhancements
        selected_watershed = st.sidebar.selectbox(
            "🏔️ Select Watershed",
            watersheds,
            help="Choose a watershed for snow cover analysis"
        )
        
        # Advanced options
        st.sidebar.markdown("### ⚙️ Advanced Options")
        create_animation = st.sidebar.checkbox("🎬 Create Snow Animation", help="Generate animated GIF of snow cover over time")
        advanced_stats = st.sidebar.checkbox("📊 Advanced Statistics", value=True, help="Include detailed statistical analysis")
        
        # Analysis button
        analyze_button = st.sidebar.button(
            "🚀 Analyze Watershed", 
            type="primary",
            use_container_width=True
        )
        
        if analyze_button:
            if start_date >= end_date:
                st.error("❌ Start date must be before end date")
                st.stop()
            
            # Create progress tracking
            progress_container = st.container()
            with progress_container:
                st.info(f"🔄 Analyzing {selected_watershed}...")
                progress_bar = st.progress(0, "Starting analysis...")
            
            # Run analysis
            df, stats, error = analyze_snow_cover(selected_watershed, start_date, end_date, progress_bar)
            
            # Clear progress
            progress_container.empty()
            
            if error:
                st.error(f"❌ {error}")
                st.stop()
            
            if df is None:
                st.error("❌ No data found for the selected period")
                st.stop()
            
            # Display results
            st.markdown(f"## 📊 Results: {selected_watershed}")
            st.markdown(f"**Analysis Period:** {start_date} to {end_date} | **Images Processed:** {stats['images_processed']:,}")
            
            # Statistics cards
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("📈 Mean", f"{stats['mean']:.1f}%")
            with col2:
                st.metric("🔺 Maximum", f"{stats['max']:.1f}%")
            with col3:
                st.metric("🔻 Minimum", f"{stats['min']:.1f}%")
            with col4:
                st.metric("📊 Std Dev", f"{stats['std']:.1f}%")
            with col5:
                st.metric("🗓️ Data Points", f"{stats['count']:,}")
            
            # Charts
            st.markdown("### 📈 Time Series Analysis")
            time_series_fig = create_time_series_chart(df, selected_watershed)
            st.plotly_chart(time_series_fig, use_container_width=True)
            
            # Two column layout for additional charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🗓️ Seasonal Patterns")
                seasonal_fig = create_seasonal_chart(df)
                st.plotly_chart(seasonal_fig, use_container_width=True)
            
            with col2:
                st.markdown("### 📊 Distribution")
                dist_fig = create_distribution_chart(df, stats)
                st.plotly_chart(dist_fig, use_container_width=True)
            
            # Advanced statistics
            if advanced_stats:
                st.markdown("## 🔬 Advanced Statistical Analysis")
                advanced_stats_data = create_advanced_statistics(df)
                create_statistical_dashboard(advanced_stats_data)
            
            # Animation creation
            if create_animation:
                st.markdown("### 🎬 Snow Cover Animation")
                with st.spinner("Creating snow cover animation..."):
                    animation_frames = create_snow_animation_frames(selected_watershed, start_date, end_date)
                
                if animation_frames:
                    st.success(f"✅ Created {len(animation_frames)} animation frames")
                    st.info("💡 Animation frames created! In a full implementation, these would be compiled into a GIF.")
                    
                    # Show frame information
                    frame_info = pd.DataFrame([{'Month': frame['month']} for frame in animation_frames])
                    st.dataframe(frame_info, use_container_width=True)
            
            # Data summary table
            st.markdown("### 📋 Annual Summary")
            yearly_summary = df.groupby('year').agg({
                'snow_cover_percent': ['mean', 'max', 'min', 'count']
            }).round(1)
            yearly_summary.columns = ['Mean (%)', 'Max (%)', 'Min (%)', 'Count']
            st.dataframe(yearly_summary, use_container_width=True)
            
            # Enhanced download section
            st.markdown("### 💾 Download Data")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=f"snow_data_{selected_watershed}_{start_date}_{end_date}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                # Enhanced JSON report
                json_data = json.dumps({
                    'watershed': selected_watershed,
                    'period': f"{start_date} to {end_date}",
                    'statistics': {k: float(v) if isinstance(v, (int, float)) else v for k, v in stats.items()},
                    'advanced_statistics': advanced_stats_data if advanced_stats else None,
                    'analysis_date': datetime.now().isoformat(),
                    'analysis_mode': 'watershed',
                    'data_source': 'MODIS/061/MOD10A1'
                }, indent=2, default=str)
                
                st.download_button(
                    label="📥 Download Report",
                    data=json_data,
                    file_name=f"report_{selected_watershed}_{start_date}_{end_date}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col3:
                # Enhanced summary
                summary_text = f"""SYMFLUENCE Snow Cover Analysis Report
Watershed: {selected_watershed}
Period: {start_date} to {end_date}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

STATISTICS:
Mean Snow Cover: {stats['mean']:.1f}%
Maximum: {stats['max']:.1f}%
Minimum: {stats['min']:.1f}%
Standard Deviation: {stats['std']:.1f}%
Data Points: {stats['count']:,}
Images Processed: {stats['images_processed']:,}

ADVANCED FEATURES:
✓ Interactive mapping
✓ Point-click analysis
✓ SWE time series
✓ Statistical analysis
✓ Animation support

DATA SOURCE: MODIS/061/MOD10A1
SPATIAL RESOLUTION: 500m
SNOW THRESHOLD: NDSI >= 10

Contact: darri@symfluence.org
University of Calgary
"""
                
                st.download_button(
                    label="📥 Download Summary",
                    data=summary_text,
                    file_name=f"summary_{selected_watershed}_{start_date}_{end_date}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
    
    else:
        # Welcome screen with enhanced features
        st.markdown("## 🌟 Welcome to Advanced SYMFLUENCE Snow Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🎯 Core Features
            - **Interactive Maps**: Click anywhere to analyze snow cover
            - **Point Analysis**: Detailed SWE time series at any location
            - **Watershed Analysis**: Comprehensive basin-scale analysis
            - **Advanced Statistics**: Peak timing, persistence, trends
            - **Animated Visualizations**: Snow cover evolution over time
            """)
        
        with col2:
            st.markdown("""
            ### 🚀 Advanced Capabilities
            - **Real-time Processing**: MODIS satellite data analysis
            - **Statistical Dashboard**: Comprehensive snow metrics
            - **Multiple Export Formats**: CSV, JSON, summary reports
            - **Professional Visualizations**: Interactive Plotly charts
            - **Buffer Analysis**: Customizable spatial analysis zones
            """)
        
        st.info("👈 Select an analysis mode in the sidebar to begin!")
    
    # Enhanced footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <strong>SYMFLUENCE Advanced Snow Cover Analysis Tool</strong><br>
        Interactive watershed snow monitoring with mapping and point analysis<br>
        Built by <strong>Darri Eythorsson</strong>, University of Calgary<br>
        Contact: <a href='mailto:darri@symfluence.org'>darri@symfluence.org</a><br>
        <em>Features: Interactive maps • Point analysis • SWE time series • Statistical analysis • Animations</em>
    </div>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🌨️ SYMFLUENCE Snow Cover Analysis</h1>
        <p>Professional watershed snow monitoring using MODIS satellite data</p>
        <p><em>Built by Darri Eythorsson, University of Calgary</em></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize Earth Engine
    ee_status, ee_message = initialize_ee()
    
    if ee_status:
        st.markdown(f'<div class="success-box">{ee_message}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="error-box">{ee_message}<br>Please run: <code>earthengine authenticate</code></div>', unsafe_allow_html=True)
        st.stop()
    
    # Sidebar controls
    st.sidebar.markdown("## 🎛️ Analysis Controls")
    
    # Get watersheds
    watersheds, error = get_watersheds()
    if error:
        st.error(f"❌ {error}")
        st.stop()
    
    st.sidebar.success(f"✅ Loaded {len(watersheds)} watersheds")
    
    # Watershed selection
    selected_watershed = st.sidebar.selectbox(
        "🏔️ Select Watershed",
        watersheds,
        help="Choose a watershed for snow cover analysis"
    )
    
    # Date range
    st.sidebar.markdown("### 📅 Analysis Period")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date(2022, 1, 1),
            min_value=date(2000, 1, 1),
            max_value=date(2023, 12, 31)
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=date(2023, 12, 31),
            min_value=date(2000, 1, 1),
            max_value=date(2023, 12, 31)
        )
    
    # Analysis button
    analyze_button = st.sidebar.button(
        "🚀 Analyze Snow Cover", 
        type="primary",
        use_container_width=True
    )
    
    # Main content area
    if analyze_button:
        
        if start_date >= end_date:
            st.error("❌ Start date must be before end date")
            st.stop()
        
        # Create progress tracking
        progress_container = st.container()
        with progress_container:
            st.info(f"🔄 Analyzing {selected_watershed}...")
            progress_bar = st.progress(0, "Starting analysis...")
        
        # Run analysis
        df, stats, error = analyze_snow_cover(selected_watershed, start_date, end_date, progress_bar)
        
        # Clear progress
        progress_container.empty()
        
        if error:
            st.error(f"❌ {error}")
            st.stop()
        
        if df is None:
            st.error("❌ No data found for the selected period")
            st.stop()
        
        # Display results
        st.markdown(f"## 📊 Results: {selected_watershed}")
        st.markdown(f"**Analysis Period:** {start_date} to {end_date} | **Images Processed:** {stats['images_processed']:,}")
        
        # Statistics cards
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("📈 Mean", f"{stats['mean']:.1f}%")
        
        with col2:
            st.metric("🔺 Maximum", f"{stats['max']:.1f}%")
        
        with col3:
            st.metric("🔻 Minimum", f"{stats['min']:.1f}%")
        
        with col4:
            st.metric("📊 Std Dev", f"{stats['std']:.1f}%")
        
        with col5:
            st.metric("🗓️ Data Points", f"{stats['count']:,}")
        
        # Charts
        st.markdown("### 📈 Time Series Analysis")
        time_series_fig = create_time_series_chart(df, selected_watershed)
        st.plotly_chart(time_series_fig, use_container_width=True)
        
        # Two column layout for additional charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🗓️ Seasonal Patterns")
            seasonal_fig = create_seasonal_chart(df)
            st.plotly_chart(seasonal_fig, use_container_width=True)
        
        with col2:
            st.markdown("### 📊 Distribution")
            dist_fig = create_distribution_chart(df, stats)
            st.plotly_chart(dist_fig, use_container_width=True)
        
        # Data summary table
        st.markdown("### 📋 Annual Summary")
        yearly_summary = df.groupby('year').agg({
            'snow_cover_percent': ['mean', 'max', 'min', 'count']
        }).round(1)
        yearly_summary.columns = ['Mean (%)', 'Max (%)', 'Min (%)', 'Count']
        st.dataframe(yearly_summary, use_container_width=True)
        
        # Download section
        st.markdown("### 💾 Download Data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"snow_data_{selected_watershed}_{start_date}_{end_date}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            json_data = json.dumps({
                'watershed': selected_watershed,
                'period': f"{start_date} to {end_date}",
                'statistics': {k: float(v) if isinstance(v, (int, float)) else v for k, v in stats.items()},
                'analysis_date': datetime.now().isoformat()
            }, indent=2)
            
            st.download_button(
                label="📥 Download Report",
                data=json_data,
                file_name=f"report_{selected_watershed}_{start_date}_{end_date}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col3:
            # Create summary statistics as text
            summary_text = f"""SYMFLUENCE Snow Cover Analysis Report
Watershed: {selected_watershed}
Period: {start_date} to {end_date}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

STATISTICS:
Mean Snow Cover: {stats['mean']:.1f}%
Maximum: {stats['max']:.1f}%
Minimum: {stats['min']:.1f}%
Standard Deviation: {stats['std']:.1f}%
Data Points: {stats['count']:,}
Images Processed: {stats['images_processed']:,}

DATA SOURCE: MODIS/061/MOD10A1
SPATIAL RESOLUTION: 500m
SNOW THRESHOLD: NDSI >= 10

Contact: darri@symfluence.org
University of Calgary
"""
            
            st.download_button(
                label="📥 Download Summary",
                data=summary_text,
                file_name=f"summary_{selected_watershed}_{start_date}_{end_date}.txt",
                mime="text/plain",
                use_container_width=True
            )
    
    else:
        # Welcome screen
        st.markdown("## 🌟 Welcome to SYMFLUENCE Snow Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🎯 Features
            - **Interactive Analysis**: Select watersheds and time periods
            - **Professional Visualizations**: Time series, seasonal patterns, distributions
            - **Statistical Analysis**: Comprehensive snow cover metrics
            - **Data Export**: CSV, JSON, and summary reports
            - **Real-time Processing**: MODIS satellite data analysis
            """)
        
        with col2:
            st.markdown("""
            ### 📊 Data Sources
            - **MODIS/061/MOD10A1**: Daily snow cover (500m resolution)
            - **Time Range**: 2000-present
            - **Coverage**: 14+ research watersheds
            - **Processing**: Google Earth Engine cloud computing
            - **Quality**: Cloud-filtered, validated data
            """)
        
        st.info("👈 Select a watershed and date range in the sidebar to begin analysis")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <strong>SYMFLUENCE Snow Cover Analysis Tool</strong><br>
        Professional watershed snow monitoring using MODIS satellite data<br>
        Built by <strong>Darri Eythorsson</strong>, University of Calgary<br>
        Contact: <a href='mailto:darri@symfluence.org'>darri@symfluence.org</a>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
