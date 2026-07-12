import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Configure the page
st.set_page_config(page_title="Startup Process Viewer", layout="wide")
st.title("Startup Process Data Viewer")

@st.cache_data
def load_data():
    try:
        df = pd.read_excel("Process_Data_StartUp.xlsx")
        df['Elapsed_Minutes'] = df.index
        if 'Time' not in df.columns:
            df['Time'] = df['Elapsed_Minutes']
        return df
    except FileNotFoundError:
        st.error("Error: 'Process_Data_StartUp.xlsx' not found in the directory.")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.sidebar.header("DCS Trend Settings")
    
    # 1. Parameter Selection
    available_params = [col for col in df.columns if col not in ['Time', 'Elapsed_Minutes']]
    selected_params = st.sidebar.multiselect("Select Parameters to Trend", available_params)
    
    # 2. Time Window Expansion
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
    
    # 3. Session State setup for synchronizing buttons and slider
    if "start_time" not in st.session_state:
        st.session_state.start_time = min_time

    # Auto-adjust if window size changes and pushes limits out of bounds
    if st.session_state.start_time > max_time - window_size and window_size < len(df):
        st.session_state.start_time = max(min_time, max_time - window_size)

    # Callbacks for the Prev/Next buttons
    def go_previous():
        st.session_state.start_time = max(min_time, st.session_state.start_time - window_size)
        
    def go_next():
        st.session_state.start_time = min(max_time - window_size, st.session_state.start_time + window_size)

    # 4. Sidebar Slider Configuration
    if window_size < len(df):
        st.sidebar.subheader("Time Navigation")
        # Notice key="start_time". This links the slider directly to st.session_state.start_time
        start_time = st.sidebar.slider(
            "Scroll Timeline", 
            min_value=min_time, 
            max_value=max_time - window_size, 
            key="start_time" 
        )
        end_time = start_time + window_size
    else:
        start_time = min_time
        end_time = max_time
        st.sidebar.info("Showing all data. Slider disabled.")
        
    mask = (df['Elapsed_Minutes'] >= start_time) & (df['Elapsed_Minutes'] <= end_time)
    df_filtered = df.loc[mask]

    # 5. Y-Axis Limits
    st.sidebar.subheader("Y-Axis Limits")
    y_limits = {}
    for param in selected_params:
        with st.sidebar.expander(f"{param} Limits"):
            min_val = float(df[param].min())
            max_val = float(df[param].max())
            
            y_min = st.number_input(f"Min for {param}", value=min_val, key=f"min_{param}")
            y_max = st.number_input(f"Max for {param}", value=max_val, key=f"max_{param}")
            y_limits[param] = [y_min, y_max]

    # 6. Plotting and Main Screen Buttons
    if selected_params:
        
        # Add Pagination Buttons above the graph on the main screen
        if window_size < len(df):
            col1, spacer, col2 = st.columns([1, 4, 1])
            with col1:
                st.button("⬅️ Previous", on_click=go_previous, use_container_width=True, disabled=(st.session_state.start_time <= min_time))
            with col2:
                st.button("Next ➡️", on_click=go_next, use_container_width=True, disabled=(st.session_state.start_time >= max_time - window_size))
        
        # Build Chart
        fig = go.Figure()
        for param in selected_params:
            fig.add_trace(go.Scatter(
                x=df_filtered['Time'], 
                y=df_filtered[param], 
                mode='lines', 
                name=param
            ))
            
        global_y_min = min([limits[0] for limits in y_limits.values()]) if y_limits else 0
        global_y_max = max([limits[1] for limits in y_limits.values()]) if y_limits else 100
        
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Process Values",
            yaxis_range=[global_y_min, global_y_max],
            hovermode="x unified",
            height=600,
            template="plotly_dark",
            margin=dict(t=30) # Reduces top margin space right below the buttons
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Please select at least one parameter from the sidebar to view the trend.")
