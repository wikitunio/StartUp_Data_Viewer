import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import plotly.colors as pcolors

# Configure the page
st.set_page_config(page_title="Startup Process Viewer", layout="wide")
st.title("Startup Process Data Viewer")

# 1. Optimized Data Loading & Caching
# show_spinner=False stops the UI from flickering during fast reloads
@st.cache_data(show_spinner=False)
def load_data():
    try:
        df = pd.read_excel("Process_Data_StartUp.xlsx")
        df['Elapsed_Minutes'] = df.index
        if 'Time' not in df.columns:
            df['Time'] = df['Elapsed_Minutes']
            
        # PERFORMANCE BOOST: Pre-calculate min/max limits for all numeric columns once.
        # This stops the app from recalculating the entire Excel sheet on every click.
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        limits_cache = {}
        for col in numeric_cols:
            if col not in ['Time', 'Elapsed_Minutes', 'index']:
                c_min, c_max = df[col].min(), df[col].max()
                
                # Safely handle empty columns or flatlined tags
                if pd.isna(c_min) or pd.isna(c_max):
                    c_min, c_max = 0.0, 100.0
                elif c_min == c_max:
                    c_min -= 1.0
                    c_max += 1.0
                limits_cache[col] = (float(c_min), float(c_max))
                
        return df, numeric_cols, limits_cache
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(), [], {}

df, numeric_cols, limits_cache = load_data()

if not df.empty:
    st.sidebar.header("DCS Trend Settings")
    
    # 2. Parameter Selection
    available_params = [col for col in numeric_cols if col not in ['Time', 'Elapsed_Minutes', 'index']]
    selected_params = st.sidebar.multiselect("Select Parameters to Trend", available_params)
    
    # 3. Time Window Configuration
    st.sidebar.subheader("Time Window")
    time_window_options = {
        "10 Min": 10, "15 Min": 15, "20 Min": 20, "25 Min": 25, 
        "30 Min": 30, "45 Min": 45, "1 Hour": 60, "2 Hours": 120, 
        "All Data": len(df)
    }
    selected_window_label = st.sidebar.selectbox("Select Window Size", list(time_window_options.keys()))
    window_size = time_window_options[selected_window_label]
    
    max_time = int(df['Elapsed_Minutes'].max())
    min_time = int(df['Elapsed_Minutes'].min())
    
    # CRITICAL FIX: Safe bounds calculation to prevent slider crashes
    if window_size >= (max_time - min_time):
        window_size = (max_time - min_time)
        
    valid_max_start = max(min_time, max_time - window_size)
    
    # Initialize session state for the slider
    if "start_time" not in st.session_state:
        st.session_state.start_time = min_time

    # CRITICAL FIX: Force the slider state back into safe bounds BEFORE it renders
    if st.session_state.start_time > valid_max_start:
        st.session_state.start_time = valid_max_start
    if st.session_state.start_time < min_time:
        st.session_state.start_time = min_time

    def go_previous():
        st.session_state.start_time = max(min_time, st.session_state.start_time - window_size)
        
    def go_next():
        st.session_state.start_time = min(valid_max_start, st.session_state.start_time + window_size)

    # 4. Sidebar Slider Configuration
    if valid_max_start > min_time:
        st.sidebar.subheader("Time Navigation")
        start_time = st.sidebar.slider(
            "Scroll Timeline", 
            min_value=min_time, 
            max_value=valid_max_start, 
            key="start_time" 
        )
        end_time = start_time + window_size
    else:
        start_time = min_time
        end_time = max_time
        st.sidebar.info("Time window covers the available data. Slider disabled.")
        
    mask = (df['Elapsed_Minutes'] >= start_time) & (df['Elapsed_Minutes'] <= end_time)
    df_filtered = df.loc[mask]

    # 5. Y-Axis Limits (Using High-Speed Cache)
    st.sidebar.subheader("Y-Axis Limits")
    y_limits = {}
    for param in selected_params:
        with st.sidebar.expander(f"{param} Limits"):
            # Fetch default limits instantly from the pre-calculated dictionary
            def_min, def_max = limits_cache.get(param, (0.0, 100.0))
            
            y_min = st.number_input(f"Min for {param}", value=def_min, key=f"min_{param}")
            y_max = st.number_input(f"Max for {param}", value=def_max, key=f"max_{param}")
            
            # Prevent crashes if a user accidentally types a minimum that is higher than the maximum
            if y_min >= y_max:
                st.warning("Max must be greater than Min.")
                y_min, y_max = def_min, def_max
                
            y_limits[param] = [y_min, y_max]

    # 6. Plotting and Main Screen Buttons
    if selected_params:
        if valid_max_start > min_time:
            col1, spacer, col2 = st.columns([1, 4, 1])
            with col1:
                st.button("⬅️ Previous", on_click=go_previous, use_container_width=True, disabled=(st.session_state.start_time <= min_time))
            with col2:
                st.button("Next ➡️", on_click=go_next, use_container_width=True, disabled=(st.session_state.start_time >= valid_max_start))
        
        fig = go.Figure()
        
        layout_updates = {
            "xaxis_title": "Time",
            "hovermode": "x unified",
            "height": 650,
            "template": "plotly_dark",
            "margin": dict(t=30, l=50, r=50)
        }
        
        # Load a highly distinct color palette for the lines
        color_palette = pcolors.qualitative.Bold + pcolors.qualitative.Vivid
        
        for i, param in enumerate(selected_params):
            y_axis_name = f'y{i+1}' if i > 0 else 'y'
            # Assign a distinct color to this specific parameter
            line_color = color_palette[i % len(color_palette)]
            
            fig.add_trace(go.Scatter(
                x=df_filtered['Time'], 
                y=df_filtered[param], 
                mode='lines', 
                name=param,
                yaxis=y_axis_name,
                line=dict(width=2, color=line_color) # Apply the color to the line
            ))
            
            y_min, y_max = y_limits[param]
            y_axis_key = f'yaxis{i+1}' if i > 0 else 'yaxis'
            
            axis_config = {
                "range": [y_min, y_max],
                "fixedrange": False,
                "titlefont": dict(color=line_color), # Match the axis text color to the line color
                "tickfont": dict(color=line_color)   # Match the axis numbers to the line color
            }
            
            if i == 0:
                axis_config["title"] = param
                axis_config["side"] = "left"
            elif i == 1:
                axis_config["title"] = param
                axis_config["overlaying"] = "y"
                axis_config["side"] = "right"
            else:
                axis_config["overlaying"] = "y"
                axis_config["showticklabels"] = False
                
            layout_updates[y_axis_key] = axis_config
        
        fig.update_layout(**layout_updates)
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("Please select at least one parameter from the sidebar to view the trend.")
