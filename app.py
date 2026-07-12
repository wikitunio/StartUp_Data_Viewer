import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import plotly.colors as pcolors

# Configure the page for a large DCS monitor layout
st.set_page_config(page_title="Startup Process Viewer", layout="wide")
st.title("Startup Process Data Viewer")

# 1. Optimized Data Loading & Caching
@st.cache_data(show_spinner=False)
def load_data():
    try:
        df = pd.read_excel("Process_Data_StartUp.xlsx")
        df['Elapsed_Minutes'] = df.index
        if 'Time' not in df.columns:
            df['Time'] = df['Elapsed_Minutes']
            
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        limits_cache = {}
        for col in numeric_cols:
            if col not in ['Time', 'Elapsed_Minutes', 'index']:
                c_min, c_max = df[col].min(), df[col].max()
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
    # ----------------- SIDEBAR CONTROLS -----------------
    st.sidebar.header("📺 Display Settings")
    
    # Graph Sizing Tools
    graph_height = st.sidebar.slider("Graph Height (px)", min_value=500, max_value=1500, value=700, step=50)
    use_container_width = st.sidebar.checkbox("Maximize Width to Screen", value=True)
    if not use_container_width:
        graph_width = st.sidebar.slider("Custom Width (px)", min_value=800, max_value=2500, value=1200, step=100)
    else:
        graph_width = None

    st.sidebar.divider()
    st.sidebar.header("⚙️ DCS Trend Settings")
    
    # Parameter Selection
    available_params = [col for col in numeric_cols if col not in ['Time', 'Elapsed_Minutes', 'index']]
    selected_params = st.sidebar.multiselect("Select Parameters to Trend", available_params)
    
    # Time Window Configuration
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
    
    if window_size >= (max_time - min_time):
        window_size = (max_time - min_time)
        
    valid_max_start = max(min_time, max_time - window_size)
    
    # Session State Initialization
    if "start_time" not in st.session_state:
        st.session_state.start_time = min_time
    if "annotations" not in st.session_state:
        st.session_state.annotations = []

    # Time bounds correction
    if st.session_state.start_time > valid_max_start:
        st.session_state.start_time = valid_max_start
    if st.session_state.start_time < min_time:
        st.session_state.start_time = min_time

    def go_previous():
        st.session_state.start_time = max(min_time, st.session_state.start_time - window_size)
        
    def go_next():
        st.session_state.start_time = min(valid_max_start, st.session_state.start_time + window_size)

    # Time Navigation Slider
    if valid_max_start > min_time:
        st.sidebar.subheader("Time Navigation")
        start_time = st.sidebar.slider(
            "Scroll Timeline", min_value=min_time, max_value=valid_max_start, key="start_time" 
        )
        end_time = start_time + window_size
    else:
        start_time = min_time
        end_time = max_time
        st.sidebar.info("Time window covers all data.")
        
    mask = (df['Elapsed_Minutes'] >= start_time) & (df['Elapsed_Minutes'] <= end_time)
    df_filtered = df.loc[mask]

    # Y-Axis Limits Configuration
    st.sidebar.subheader("Y-Axis Limits")
    y_limits = {}
    for param in selected_params:
        with st.sidebar.expander(f"{param} Limits"):
            def_min, def_max = limits_cache.get(param, (0.0, 100.0))
            y_min = st.number_input(f"Min for {param}", value=def_min, key=f"min_{param}")
            y_max = st.number_input(f"Max for {param}", value=def_max, key=f"max_{param}")
            if y_min >= y_max:
                st.warning("Max must be greater than Min.")
                y_min, y_max = def_min, def_max
            y_limits[param] = [y_min, y_max]

    # Event Annotations Tool
    st.sidebar.divider()
    st.sidebar.header("📌 Add Event Annotation")
    if not df_filtered.empty:
        annot_time = st.sidebar.selectbox("Select Time", df_filtered['Time'].tolist())
        annot_text = st.sidebar.text_input("Event Description (e.g., Valve Opened)")
        if st.sidebar.button("Add Annotation Marker"):
            if annot_text:
                st.session_state.annotations.append({"time": annot_time, "text": annot_text})
        if st.sidebar.button("Clear All Annotations"):
            st.session_state.annotations = []

    # ----------------- MAIN SCREEN -----------------
    if selected_params:
        # Prev/Next Pagination Buttons
        if valid_max_start > min_time:
            col1, spacer, col2 = st.columns([1, 8, 1])
            with col1:
                st.button("⬅️ Previous", on_click=go_previous, use_container_width=True, disabled=(st.session_state.start_time <= min_time))
            with col2:
                st.button("Next ➡️", on_click=go_next, use_container_width=True, disabled=(st.session_state.start_time >= valid_max_start))
        
        # Plot Construction
        fig = go.Figure()
        color_palette = pcolors.qualitative.Bold + pcolors.qualitative.Vivid
        
        # Mathematical Layout Calculation for Axes
        left_axes_indices = [i for i in range(len(selected_params)) if i % 2 == 0]
        right_axes_indices = [i for i in range(len(selected_params)) if i % 2 != 0]
        
        shift_size = 0.08 
        domain_start = shift_size * max(0, len(left_axes_indices) - 1)
        domain_end = 1.0 - (shift_size * max(0, len(right_axes_indices) - 1))
        
        layout_updates = {
            "xaxis": dict(
                title="Time", 
                domain=[domain_start, domain_end], 
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)'
            ),
            "hovermode": "x unified",
            "height": graph_height,
            "template": "plotly_dark",
            "margin": dict(t=50, l=10, r=10, b=50),
            "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        }
        
        if graph_width:
            layout_updates["width"] = graph_width

        for i, param in enumerate(selected_params):
            y_axis_name = f'y{i+1}' if i > 0 else 'y'
            line_color = color_palette[i % len(color_palette)]
            is_left = (i % 2 == 0)
            
            fig.add_trace(go.Scatter(
                x=df_filtered['Time'], 
                y=df_filtered[param], 
                mode='lines', 
                name=param,
                yaxis=y_axis_name,
                line=dict(width=2.5, color=line_color)
            ))
            
            y_min, y_max = y_limits[param]
            y_axis_key = f'yaxis{i+1}' if i > 0 else 'yaxis'
            
            if is_left:
                idx = left_axes_indices.index(i)
                position = domain_start - (idx * shift_size)
            else:
                idx = right_axes_indices.index(i)
                position = domain_end + (idx * shift_size)
            
            axis_config = {
                "range": [float(y_min), float(y_max)],
                "title": dict(text=param, font=dict(color=line_color, size=14)),
                "tickfont": dict(color=line_color, size=12),
                "side": "left" if is_left else "right",
                "position": position,
                "anchor": "free",
                "overlaying": "y" if i > 0 else None,
                "showgrid": False
            }
            layout_updates[y_axis_key] = axis_config
            
        fig.update_layout(**layout_updates)

        # Draw Annotations
        for ann in st.session_state.annotations:
            if ann["time"] in df_filtered['Time'].values:
                fig.add_vline(
                    x=ann["time"], 
                    line_dash="dot", 
                    line_color="white",
                    annotation_text=f" 🚩 {ann['text']}", 
                    annotation_position="top right",
                    annotation_font=dict(color="white", size=14)
                )

        # Render Chart
        st.plotly_chart(fig, use_container_width=use_container_width)
        
    else:
        st.info("Please select at least one parameter from the sidebar to view the trend.")
