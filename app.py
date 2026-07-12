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
    graph_width = st.sidebar.slider("Custom Width (px)", min_value=800, max_value=2500, value=1200, step=100) if not use_container_width else None

    st.sidebar.divider()
    st.sidebar.header("📈 Advanced Excel Tools")
    show_markers = st.sidebar.checkbox("Show Data Points (Markers)", value=False)
    show_data_labels = st.sidebar.checkbox("Show Data Labels", value=False)
    show_trendlines = st.sidebar.checkbox("Show Linear Trend Lines", value=False)
    
    st.sidebar.divider()
    st.sidebar.header("⚙️ DCS Trend Settings")
    selected_params = st.sidebar.multiselect("Select Parameters to Trend", [c for c in numeric_cols if c not in ['Time', 'Elapsed_Minutes', 'index']])
    
    # Time Window Configuration
    selected_window_label = st.sidebar.selectbox("Select Window Size", ["10 Min", "15 Min", "20 Min", "25 Min", "30 Min", "45 Min", "1 Hour", "2 Hours", "All Data"])
    window_map = {"10 Min": 10, "15 Min": 15, "20 Min": 20, "25 Min": 25, "30 Min": 30, "45 Min": 45, "1 Hour": 60, "2 Hours": 120, "All Data": len(df)}
    window_size = window_map[selected_window_label]
    
    max_time, min_time = int(df['Elapsed_Minutes'].max()), int(df['Elapsed_Minutes'].min())
    valid_max_start = max(min_time, max_time - window_size)
    
    if "start_time" not in st.session_state: st.session_state.start_time = min_time
    if "annotations" not in st.session_state:
        st.session_state.annotations = pd.read_csv("annotations.csv") if os.path.exists("annotations.csv") else pd.DataFrame(columns=["Time", "Event Description"])

    if st.session_state.start_time > valid_max_start: st.session_state.start_time = valid_max_start
    
    start_time = st.sidebar.slider("Scroll Timeline", min_value=min_time, max_value=valid_max_start, key="start_time")
    df_filtered = df.loc[(df['Elapsed_Minutes'] >= start_time) & (df['Elapsed_Minutes'] <= start_time + window_size)].copy()

    # Y-Axis Limits
    st.sidebar.subheader("Y-Axis Limits")
    y_limits = {p: [st.sidebar.number_input(f"Min {p}", value=limits_cache.get(p, (0.0, 100.0))[0]), st.sidebar.number_input(f"Max {p}", value=limits_cache.get(p, (0.0, 100.0))[1])] for p in selected_params}

    # ----------------- ANNOTATIONS -----------------
    st.sidebar.divider()
    st.sidebar.header("📌 Event Annotations")
    with st.sidebar.expander("➕ Add Marker"):
        annot_time = st.selectbox("Time", df_filtered['Time'].tolist())
        annot_text = st.text_input("Description")
        if st.button("Add"):
            st.session_state.annotations = pd.concat([st.session_state.annotations, pd.DataFrame([{"Time": annot_time, "Event Description": annot_text}])], ignore_index=True)
            st.session_state.annotations.to_csv("annotations.csv", index=False); st.rerun()
    
    show_annots = st.sidebar.checkbox("👁️ Show Annotations", value=True)
    st.session_state.annotations = st.sidebar.data_editor(st.session_state.annotations, num_rows="dynamic", use_container_width=True)
    if not st.session_state.annotations.equals(pd.read_csv("annotations.csv") if os.path.exists("annotations.csv") else pd.DataFrame()):
        st.session_state.annotations.to_csv("annotations.csv", index=False)

    # ----------------- MAIN PLOT -----------------
    if selected_params:
        fig = go.Figure()
        color_palette = pcolors.qualitative.Bold + pcolors.qualitative.Vivid
        num_vars = len(selected_params)
        margin_size = 30 + (num_vars * 25)
        shift_size = 0.04
        
        left_idxs = [i for i in range(num_vars) if i % 2 == 0]
        right_idxs = [i for i in range(num_vars) if i % 2 != 0]
        domain_start = shift_size * max(0, len(left_idxs) - 1)
        domain_end = 1.0 - (shift_size * max(0, len(right_idxs) - 1))
        
        layout_updates = {"xaxis": dict(title="Time", domain=[domain_start, domain_end], showgrid=True, gridcolor='rgba(255,255,255,0.1)'), "hovermode": "x unified", "height": graph_height, "template": "plotly_dark", "margin": dict(t=70, l=margin_size, r=margin_size, b=50)}
        if graph_width: layout_updates["width"] = graph_width
            
        for i, param in enumerate(selected_params):
            line_color = color_palette[i % len(color_palette)]
            mode = 'lines' + ('+markers' if show_markers else '') + ('+text' if show_data_labels else '')
            # FIX: Mapping index 0 to 'y', index 1+ to 'y2', 'y3', etc.
            yaxis_key = 'y' if i == 0 else f'y{i+1}'
            fig.add_trace(go.Scatter(x=df_filtered['Time'], y=df_filtered[param], mode=mode, text=df_filtered[param].round(2) if show_data_labels else None, name=param, yaxis=yaxis_key, line=dict(width=2.5, color=line_color)))
            
            # FIX: Mapping layout keys correctly to 'yaxis' for index 0, 'yaxis2' etc.
            layout_key = 'yaxis' if i == 0 else f'yaxis{i+1}'
            pos = -(left_idxs.index(i) * shift_size) if i % 2 == 0 else 1 + (right_idxs.index(i) * shift_size)
            layout_updates[layout_key] = dict(range=y_limits[param], title=dict(text=param, font=dict(color=line_color, size=11)), tickfont=dict(color=line_color, size=10), side="left" if i % 2 == 0 else "right", position=pos, anchor="free", overlaying="y", showgrid=False)
            
        fig.update_layout(**layout_updates)
        if show_annots:
            for _, r in st.session_state.annotations.iterrows():
                if str(r["Time"]) in df_filtered['Time'].astype(str).values:
                    fig.add_vline(x=r["Time"], line_dash="dot", line_color="white", opacity=0.7)
                    fig.add_annotation(x=r["Time"], y=1.05, yref="paper", text=f"🚩 {r['Event Description']}", showarrow=False, font=dict(color="white", size=13), bgcolor="rgba(40,40,40,0.8)", bordercolor="white", borderwidth=1)
        
        st.plotly_chart(fig, use_container_width=use_container_width)
