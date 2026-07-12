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
        
        # If there isn't a dedicated 'Time' column, assume each row is 1 minute
        if 'Time' not in df.columns:
            df.insert(0, 'Time', df.index)
            
        return df
    except FileNotFoundError:
        st.error("Error: 'Process_Data_StartUp.xlsx' not found in the directory.")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.sidebar.header("DCS Trend Settings")
    
    # 1. Parameter Selection
    available_params = [col for col in df.columns if col != 'Time']
    selected_params = st.sidebar.multiselect("Select Parameters to Trend", available_params)
    
    # 2. Time Window & Slider
    st.sidebar.subheader("Time Navigation (Minutes)")
    time_window_options = {"15 Min": 15, "30 Min": 30, "1 Hour": 60, "2 Hours": 120, "All Data": len(df)}
    selected_window_label = st.sidebar.selectbox("Select Time Window", list(time_window_options.keys()))
    window_size = time_window_options[selected_window_label]
    
    # Calculate slider limits
    max_time = int(df['Time'].max())
    min_time = int(df['Time'].min())
    
    if window_size < len(df):
        start_time = st.sidebar.slider("Scroll Timeline", min_value=min_time, max_value=max_time - window_size, value=min_time)
        end_time = start_time + window_size
    else:
        start_time = min_time
        end_time = max_time
        st.sidebar.info("Showing all data. Slider disabled.")
        
    # Filter dataframe based on time selection
    mask = (df['Time'] >= start_time) & (df['Time'] <= end_time)
    df_filtered = df.loc[mask]

    # 3. Dynamic Y-Axis Limits for selected parameters
    st.sidebar.subheader("Y-Axis Limits")
    y_limits = {}
    for param in selected_params:
        with st.sidebar.expander(f"{param} Limits"):
            min_val = float(df[param].min())
            max_val = float(df[param].max())
            
            # Allow user to overwrite limits manually
            y_min = st.number_input(f"Min for {param}", value=min_val, key=f"min_{param}")
            y_max = st.number_input(f"Max for {param}", value=max_val, key=f"max_{param}")
            y_limits[param] = [y_min, y_max]

    # 4. Plotting the Data
    if selected_params:
        fig = go.Figure()
        
        for param in selected_params:
            fig.add_trace(go.Scatter(
                x=df_filtered['Time'], 
                y=df_filtered[param], 
                mode='lines', 
                name=param
            ))
            
        # Update layout to reflect user-defined axes
        # Note: For simplicity in a single chart, this sets the global Y-axis to the max/min of ALL selected limits. 
        # For multiple separate Y-axes (like a complex DCS trend), Plotly subplots can be added later.
        global_y_min = min([limits[0] for limits in y_limits.values()]) if y_limits else 0
        global_y_max = max([limits[1] for limits in y_limits.values()]) if y_limits else 100
        
        fig.update_layout(
            xaxis_title="Time (Minutes)",
            yaxis_title="Process Values",
            yaxis_range=[global_y_min, global_y_max],
            hovermode="x unified",
            height=600,
            template="plotly_dark" # Dark mode for that authentic control room feel
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Please select at least one parameter from the sidebar to view the trend.")
