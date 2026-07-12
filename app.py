import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Configure the page to look more like a wide-screen DCS monitor
st.set_page_config(page_title="Startup Process Viewer", layout="wide")
st.title("Startup Process Data Viewer")

# Cache the data so it doesn't reload on every slider movement
@st.cache_data
def load_data():
    try:
        # Load the exact file referenced
        df = pd.read_excel("Process_Data_StartUp.xlsx")
        
        # Create a reliable integer column for the slider math
        df['Elapsed_Minutes'] = df.index
        
        # If 'Time' doesn't exist, create it from the elapsed minutes
        if 'Time' not in df.columns:
            df['Time'] = df['Elapsed_Minutes']
            
        return df
    except FileNotFoundError:
        st.error("Error: 'Process_Data_StartUp.xlsx' not found in the directory.")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.sidebar.header("DCS Trend Settings")
    
    # 1. Parameter Selection (exclude structural columns)
    available_params = [col for col in df.columns if col not in ['Time', 'Elapsed_Minutes']]
    selected_params = st.sidebar.multiselect("Select Parameters to Trend", available_params)
    
    # 2. Time Window & Slider
    st.sidebar.subheader("Time Navigation (Minutes)")
    time_window_options = {"15 Min": 15, "30 Min": 30, "1 Hour": 60, "2 Hours": 120, "All Data": len(df)}
    selected_window_label = st.sidebar.selectbox("Select Time Window", list(time_window_options.keys()))
    window_size = time_window_options[selected_window_label]
    
    # Calculate slider limits using the numerical Elapsed_Minutes column
    max_time = int(df['Elapsed_Minutes'].max())
    min_time = int(df['Elapsed_Minutes'].min())
    
    if window_size < len(df):
        start_time = st.sidebar.slider("Scroll Timeline", min_value=min_time, max_value=max_time - window_size, value=min_time)
        end_time = start_time + window_size
    else:
        start_time = min_time
        end_time = max_time
        st.sidebar.info("Showing all data. Slider disabled.")
        
    # Filter dataframe based on the numerical slider selection
    mask = (df['Elapsed_Minutes'] >= start_time) & (df['Elapsed_Minutes'] <= end_time)
    df_filtered = df.loc[mask]

    # 3. Dynamic Y-Axis Limits for selected parameters
    st.sidebar.subheader("Y-Axis Limits")
    y_limits = {}
    for param in selected_params:
        with st.sidebar.expander(f"{param} Limits"):
            # Use pandas min/max to establish default limits for the inputs
            min_val = float(df[param].min())
            max_val = float(df[param].max())
            
            y_min = st.number_input(f"Min for {param}", value=min_val, key=f"min_{param}")
            y_max = st.number_input(f"Max for {param}", value=max_val, key=f"max_{param}")
            y_limits[param] = [y_min, y_max]

    # 4. Plotting the Data
    if selected_params:
        fig = go.Figure()
        
        for param in selected_params:
            fig.add_trace(go.Scatter(
                x=df_filtered['Time'],  # Still plotting the actual Time string/stamp on the X-axis
                y=df_filtered[param], 
                mode='lines', 
                name=param
            ))
            
        # Update Y-axis to the absolute max/min of all selected limits
        global_y_min = min([limits[0] for limits in y_limits.values()]) if y_limits else 0
        global_y_max = max([limits[1] for limits in y_limits.values()]) if y_limits else 100
        
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Process Values",
            yaxis_range=[global_y_min, global_y_max],
            hovermode="x unified",
            height=600,
            template="plotly_dark"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Please select at least one parameter from the sidebar to view the trend.")
