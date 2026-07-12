import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import plotly.colors as pcolors
import os

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
    
    graph_height = st.sidebar.slider("Graph Height (px)", min_value=500, max_value=1500, value=700, step=50)
    use_container_width = st.sidebar.checkbox("Maximize Width to Screen", value=True)
    if not use_container_width:
        graph_width = st.sidebar.slider("Custom Width (px)", min_value=800, max_value=2500, value=1200, step=100)
    else:
        graph_width = None

    st.sidebar.divider()
    
    st.sidebar.header("📈 Advanced Excel Tools")
    show_markers = st.sidebar.checkbox("Show Data Points (Markers)", value=False)
    show_data_labels = st.sidebar.checkbox("Show Data Labels", value=False)
    show_trendlines = st.sidebar.checkbox("Show Linear Trend Lines", value=False)
    
    st.sidebar.divider()
    st.sidebar.header("⚙️ DCS Trend Settings")
    
    available_params = [col for col in numeric_cols if col not in ['Time', 'Elapsed_Minutes', 'index']]
    selected_params = st.sidebar.multiselect("Select Parameters to Trend", available_params)
    
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
    
    if "start_time" not in st.session_state:
        st.session_state.start_time = min_time
        
    # FIX: Persistent Annotation Loading
    if "annotations" not in st.session_state:
        if os.path.exists("annotations.csv"):
            st.session_state.annotations = pd.read_csv("annotations.csv")
        else:
            st.session_state.annotations = pd.DataFrame(columns=["Time", "Event Description"])

    if st.session_state.start_time > valid_max_start:
        st.session_state.start_time = valid_max_start
    if st.session_state.start_time < min_time:
        st.session_state.start_time = min_time

    def go_previous():
        st.session_state.start_time = max(min_time, st.session_state.start_time - window_size)
        
    def go_next():
        st.session_state.start_time = min(valid_max_start, st.session_state.start_time + window_size)

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
    df_filtered = df.loc[mask].copy()

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

    # ----------------- EVENT ANNOTATIONS TOOL -----------------
    st.sidebar.divider()
    st.sidebar.header("📌 Event Annotations")
    
    if not df_filtered.empty:
        with st.sidebar.expander("➕ Add New Marker"):
            annot_time = st.selectbox("Select Time", df_filtered['Time'].tolist())
            annot_text = st.text_input("Event Description")
            if st.button("Add to Timeline"):
                if annot_text:
                    new_row = pd.DataFrame([{"Time": annot_time, "Event Description": annot_text}])
                    st.session_state.annotations = pd.concat([st.session_state.annotations, new_row], ignore_index=True)
                    # FIX: Save to CSV instantly
                    st.session_state.annotations.to_csv("annotations.csv", index=False)
                    st.rerun() # Refreshes the app slightly to update the UI instantly

        show_annots = st.sidebar.checkbox("👁️ Show Annotations on Graph", value=True)
        
        if not st.session_state.annotations.empty:
            st.sidebar.caption("Edit text, or select rows to delete:")
            edited_annots = st.sidebar.data_editor(
                st.session_state.annotations,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True
            )
            # FIX: If the user deleted or edited a row, save the changes to the CSV
            if not edited_annots.equals(st.session_state.annotations):
                st.session_state.annotations = edited_annots
                st.session_state.annotations.to_csv("annotations.csv", index=False)
                st.rerun()
                
            if st.sidebar.button("Clear All Annotations"):
                st.session_state.annotations = pd.DataFrame(columns=["Time", "Event Description"])
                st.session_state.annotations.to_csv("annotations.csv", index=False)
                st.rerun()

    # ----------------- MAIN SCREEN -----------------
    if selected_params:
        if valid_max_start > min_time:
            col1, spacer, col2 = st.columns([1, 8, 1])
            with col1:
                st.button("⬅️ Previous", on_click=go_previous, use_container_width=True, disabled=(st.session_state.start_time <= min_time))
            with col2:
                st.button("Next ➡️", on_click=go_next, use_container_width=True, disabled=(st.session_state.start_time >= valid_max_start))
        
        fig = go.Figure()
        color_palette = pcolors.qualitative.Bold + pcolors.qualitative.Vivid
        
        left_axes_indices = [i for i in range(len(selected_params)) if i % 2 == 0]
        right_axes_indices = [i for i in range(len(selected_params)) if i % 2 != 0]
        
        shift_size = 0.05 
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
            "margin": dict(t=70, l=10, r=10, b=50), 
            "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        }
        
        if graph_width:
            layout_updates["width"] = graph_width

        for i, param in enumerate(selected_params):
            y_axis_name = f'y{i+1}' if i > 0 else 'y'
            line_color = color_palette[i % len(color_palette)]
            is_left = (i % 2 == 0)
            
            plot_mode = 'lines'
            if show_markers and show_data_labels:
                plot_mode = 'lines+markers+text'
            elif show_markers:
                plot_mode = 'lines+markers'
            elif show_data_labels:
                plot_mode = 'lines+text'
            
            fig.add_trace(go.Scatter(
                x=df_filtered['Time'], 
                y=df_filtered[param], 
                mode=plot_mode, 
                text=df_filtered[param].round(2) if show_data_labels else None, 
                textposition="top center",
                name=param,
                yaxis=y_axis_name,
                line=dict(width=2.5, color=line_color),
                marker=dict(size=7) if show_markers else None
            ))
            
            if show_trendlines and len(df_filtered) > 1:
                y_vals = df_filtered[param].dropna()
                x_idx = np.arange(len(df_filtered))[df_filtered[param].notna()]
                
                if len(y_vals) > 1:
                    z = np.polyfit(x_idx, y_vals, 1)
                    p = np.poly1d(z)
                    trend_y = p(np.arange(len(df_filtered)))
                    
                    fig.add_trace(go.Scatter(
                        x=df_filtered['Time'],
                        y=trend_y,
                        mode='lines',
                        name=f"{param} Trend",
                        yaxis=y_axis_name,
                        line=dict(width=2, color=line_color, dash='dot'), 
                        showlegend=False,
                        hoverinfo='skip'
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
                # The 'standoff' property controls the space between title and ticks. 
                # Setting it to 0 or a very low value pulls them closer together.
                "title": dict(
                    text=param, 
                    font=dict(color=line_color, size=12),
                    standoff=0 
                ),
                "tickfont": dict(color=line_color, size=10),
                "side": "left" if is_left else "right",
                "position": position,
                "anchor": "free",
                "overlaying": "y" if i > 0 else None,
                "showgrid": False
            }
            layout_updates[y_axis_key] = axis_config
            
        fig.update_layout(**layout_updates)

        if show_annots and not st.session_state.annotations.empty:
            for _, row in st.session_state.annotations.iterrows():
                ann_time = row["Time"]
                ann_text = row["Event Description"]
                
                # Convert the time to a string strictly for comparison to prevent type mismatch bugs
                if str(ann_time) in df_filtered['Time'].astype(str).values:
                    fig.add_vline(
                        x=ann_time, 
                        line_dash="dot", 
                        line_color="white",
                        opacity=0.7
                    )
                    fig.add_annotation(
                        x=ann_time,
                        y=1.05, 
                        yref="paper",
                        text=f"🚩 {ann_text}",
                        showarrow=False,
                        font=dict(color="white", size=13),
                        bgcolor="rgba(40,40,40,0.8)", 
                        bordercolor="white",
                        borderwidth=1
                    )

        st.plotly_chart(fig, use_container_width=use_container_width)
        
    else:
        st.info("Please select at least one parameter from the sidebar to view the trend.")
