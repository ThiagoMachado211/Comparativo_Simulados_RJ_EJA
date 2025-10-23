# app.py
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Comparativo de Simulados - EJA RJ", layout="wide")

# -------------------- parâmetros de fonte --------------------
font_size = 18                 # base para opções do rádio, dropdown, eixos, hover e rótulos sobre os pontos
font_size_label_area = 26      # rótulo "Área (aba)"
font_size_label_regional = 26  # rótulo "Regional"

# -------------------- helpers de UI --------------------
def styled_label(text: str, size: int, weight: int = 600, color: str = "#111", mt: int = 0, mb: int = 6):
    st.markdown(
        f"<div style='font-size:{size}px; font-weight:{weight}; color:{color}; "
        f"margin:{mt}px 0 {mb}px 0;'>{text}</div>",
        unsafe_allow_html=True,
    )

# CSS para opções do rádio, espaçamentos e selectbox
st.markdown(
    f"""
    <style>
      h1.app-title {{ text-align: center; margin-top: 0; }}

      /* Radio: opções maiores e com espaço */
      div[data-testid="stRadio"] label p {{
        font-size: {font_size}px !important;
        line-height: {font_size*1.2}px !important;
      }}
      div[data-testid="stRadio"] label {{
        margin: {int(font_size*0.25)}px 0 !important;
      }}
      div[data-testid="stRadio"] {{
        margin-bottom: {int(font_size*0.9)}px !important;
      }}

      /* Selectbox: fonte/altura e espaço acima */
      div[data-testid="stSelectbox"] {{
        margin-top: {int(font_size*0.6)}px !important;
      }}
      div[data-testid="stSelectbox"] div[data-baseweb="select"] * {{
        font-size: {font_size}px !important;
        line-height: {font_size*1.2}px !important;
      }}
      div[data-testid="stSelectbox"] > div:first-child {{
        min-height: {int(font_size*2)}px !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- arquivos --------------------
NOTAS_FILE = "Comparativo_Simulados_RJ_EJA.xlsx"
PARTIC_FILE = "Participacao_Simulados_RJ_EJA.xlsx"

AREAS = ["Redação", "Linguagens e Códigos", "Ciências Humanas",
         "Ciências da Natureza", "Matemática"]

AREAS_DIA1 = {"Redação", "Linguagens e Códigos", "Ciências Humanas"}
AREAS_DIA2 = {"Ciências da Natureza", "Matemática"}

# -------------------- parsing --------------------
def str_to_float_br(x):
    if isinstance(x, str):
        x = x.replace(".", "").replace(",", ".")
    return pd.to_numeric(x, errors="coerce")

def percent_br_to_float(x):
    """'86,65%' -> 86.65 (não divide por 100, usamos escala 0-100)."""
    if isinstance(x, str):
        x = x.replace("%", "").strip()
    return str_to_float_br(x)

def tidy_notas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename_map = {
        df.columns[0]: "Regional",
        df.columns[1]: "2º ano - 1º simulado",
        df.columns[2]: "2º ano - 2º simulado",
        df.columns[3]: "3º ano - 1º simulado",
        df.columns[4]: "3º ano - 2º simulado",
    }
    df = df.rename(columns=rename_map)
    for col in list(rename_map.values())[1:]:
        df[col] = df[col].apply(str_to_float_br)
    df["Regional"] = df["Regional"].astype(str).str.strip()
    df = df.dropna(how="all")
    return df

def tidy_participacao(df: pd.DataFrame) -> pd.DataFrame:
    """
    Espera uma aba única com linhas 'Dia 1' e 'Dia 2' e colunas:
      '1º Simulado - 2º Ano', '2º Simulado - 2º Ano',
      '1º Simulado - 3º Ano', '2º Simulado - 3º Ano'
    Valores podem vir como '86,65%'.
    """
    df = df.copy()
    # Garante que a primeira coluna é o rótulo do Dia
    df.columns = [str(c).strip() for c in df.columns]
    if df.columns[0] == "" or df.columns[0].lower() in {"", "unnamed: 0", "index"}:
        df.columns = ["Dia"] + df.columns[1:].tolist()
    else:
        df = df.rename(columns={df.columns[0]: "Dia"})

    # Normaliza os nomes que vamos usar
    col_map = {}
    for c in df.columns:
        c_norm = c.lower().strip()
        if "1º simulado" in c_norm and "2º ano" in c_norm:
            col_map[c] = "2ano_s1"
        elif "2º simulado" in c_norm and "2º ano" in c_norm:
            col_map[c] = "2ano_s2"
        elif "1º simulado" in c_norm and "3º ano" in c_norm:
            col_map[c] = "3ano_s1"
        elif "2º simulado" in c_norm and "3º ano" in c_norm:
            col_map[c] = "3ano_s2"

    df = df.rename(columns=col_map)
    for c in ["2ano_s1", "2ano_s2", "3ano_s1", "3ano_s2"]:
        if c in df.columns:
            df[c] = df[c].apply(percent_br_to_float)

    df["Dia"] = df["Dia"].astype(str).str.strip()
    return df

@st.cache_data(show_spinner=True)
def load_notas(path: str) -> dict:
    xl = pd.ExcelFile(path)
    data = {}
    for area in AREAS:
        df = xl.parse(sheet_name=area, header=0)
        data[area] = tidy_notas(df)
    return data

@st.cache_data(show_spinner=True)
def load_participacao(path: str) -> pd.DataFrame | None:
    try:
        xl = pd.ExcelFile(path)
        df = xl.parse(sheet_name=xl.sheet_names[0], header=0)
        return tidy_participacao(df)
    except Exception:
        return None

# -------------------- gráficos --------------------
def make_line_notas(y1, y2, titulo=""):
    """Notas: linha com 2 pontos, hover no 2º (Δ/Δ%) e cor azul↑/vermelho↓."""
    x_labels = ["1º Simulado", "2º Simulado"]
    y_values = [y1, y2]

    delta_abs = y2 - y1 if pd.notnull(y1) and pd.notnull(y2) else None
    delta_pct = (delta_abs / y1 * 100) if (pd.notnull(delta_abs) and y1 not in (None, 0)) else None

    azul, vermelho, cinza = "#1f77b4", "#d62728", "#9e9e9e"
    if pd.notnull(y1) and pd.notnull(y2):
        line_color = azul if y2 > y1 else vermelho if y2 < y1 else cinza
    else:
        line_color = cinza

    t1 = "%{x}: %{y:.2f}<extra></extra>"
    if delta_pct is None:
        t2 = "%{x}: %{y:.2f}<br>Variação absoluta: %{customdata[0]:.2f}<extra></extra>"
    else:
        t2 = "%{x}: %{y:.2f}<br>Variação absoluta: %{customdata[0]:.2f}<br>Variação percentual: %{customdata[1]:.2f}%<extra></extra>"

    customdata = [[None, None], [delta_abs, delta_pct]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_labels, y=y_values,
        mode="lines+markers+text",
        line=dict(color=line_color, width=2),
        marker=dict(size=max(8, int(font_size * 0.7)), color=[cinza, line_color]),
        text=[f"{y1:.2f}" if pd.notnull(y1) else "", f"{y2:.2f}" if pd.notnull(y2) else ""],
        textposition="top center",
        textfont=dict(size=font_size),
        customdata=customdata,
        hovertemplate=[t1, t2],
        name="", showlegend=False
    ))
    fig.update_layout(
        title=titulo,
        font=dict(size=font_size),
        hoverlabel=dict(font_size=font_size),
        xaxis=dict(title="", tickfont=dict(size=font_size)),
        yaxis=dict(title="", tickfont=dict(size=font_size), range=[-50, 700]),
        margin=dict(t=50, r=10, b=10, l=10),
        height=420,
    )
    return fig


def make_line_participacao(p1, p2, titulo=""):
    """
    Participação (pode vir em 0–1 ou 0–100).
    Hover do 2º ponto mostra:
      - Δ em pontos percentuais (pp)
      - Δ% (variação relativa)
    Cores: azul↑, vermelho↓, cinza neutro.
    """
    # Detecta escala
    vals = [v for v in [p1, p2] if pd.notnull(v)]
    scale_0_1 = (len(vals) > 0 and max(vals) <= 1.00001)

    # Valores para exibição (sempre em % no texto/hover)
    disp1 = p1 * 100 if (pd.notnull(p1) and scale_0_1) else p1
    disp2 = p2 * 100 if (pd.notnull(p2) and scale_0_1) else p2
    y_plot = [p1, p2] if scale_0_1 else [disp1, disp2]  # eixo 0–1 ou 0–100

    # Deltas
    delta_pp = None
    delta_rel = None
    if pd.notnull(p1) and pd.notnull(p2):
        delta_pp = (p2 - p1) * (100 if scale_0_1 else 1)               # pontos percentuais
        if p1 != 0:
            delta_rel = ((p2 - p1) / p1) * 100                          # variação relativa %

    # Cores
    azul, vermelho, cinza = "#1f77b4", "#d62728", "#9e9e9e"
    if pd.notnull(p1) and pd.notnull(p2):
        line_color = azul if p2 > p1 else (vermelho if p2 < p1 else cinza)
    else:
        line_color = cinza

    # Hovers
    t1 = f"%{{x}}: {disp1:.2f}%<extra></extra>" if pd.notnull(disp1) else "%{x}<extra></extra>"
    if delta_rel is None:
        t2 = f"%{{x}}: {disp2:.2f}%<br>Variação absoluta: %{{customdata[0]:.2f}}%<extra></extra>"
    else:
        t2 = (
            f"%{{x}}: {disp2:.2f}%%"
            f"<br>Variação absoluta: %{{customdata[0]:.2f}}%"
            f"<br>Variação relativa: %{{customdata[1]:.2f}}%"
            "<extra></extra>"
        )

    customdata = [[None, None], [delta_pp, delta_rel]]

    # Gráfico
    x_labels = ["1º Simulado", "2º Simulado"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_labels, y=y_plot,
        mode="lines+markers+text",
        line=dict(color=line_color, width=2),
        marker=dict(size=max(8, int(font_size * 0.7)), color=[cinza, line_color]),
        text=[f"{disp1:.2f}%" if pd.notnull(disp1) else "",
              f"{disp2:.2f}%" if pd.notnull(disp2) else ""],
        textposition="top center",
        textfont=dict(size=font_size),
        customdata=customdata,
        hovertemplate=[t1, t2],
        name="", showlegend=False
    ))
    fig.update_layout(
        title=titulo,
        font=dict(size=font_size),
        hoverlabel=dict(font_size=font_size),
        xaxis=dict(title="", tickfont=dict(size=font_size)),
        yaxis=dict(
            title="Participação (%)",
            tickfont=dict(size=font_size),
            range=[0, 1] if scale_0_1 else [0, 100]
        ),
        margin=dict(t=50, r=10, b=10, l=10),
        height=420,
    )
    return fig



# -------------------- UI --------------------
st.markdown("<h1 class='app-title'>Comparativo de Simulados por Área: Turmas EJA</h1>", unsafe_allow_html=True)

# Carrega dados
try:
    data_notas = load_notas(NOTAS_FILE)
except Exception as e:
    st.error(f"Não consegui abrir '{NOTAS_FILE}'. Detalhes: {e}")
    st.stop()

data_part = load_participacao(PARTIC_FILE)  # pode ser None (não quebra)

col_left, col_right = st.columns([1, 5], gap="large")

with col_left:
    styled_label("Área:", font_size_label_area)
    area = st.radio("Área (aba)", AREAS, index=0, label_visibility="collapsed")
    df_area = data_notas[area]

    styled_label("Regional:", font_size_label_regional, mt=8)
    regional = st.selectbox(
        "Regional",
        sorted(df_area["Regional"].dropna().unique().tolist()),
        label_visibility="collapsed",
    )

with col_right:
    df_sel = df_area[df_area["Regional"] == regional]
    if df_sel.empty:
        st.warning("Regional não encontrada nessa aba.")
        st.stop()

    y2_1 = float(df_sel["2º ano - 1º simulado"].iloc[0])
    y2_2 = float(df_sel["2º ano - 2º simulado"].iloc[0])
    y3_1 = float(df_sel["3º ano - 1º simulado"].iloc[0])
    y3_2 = float(df_sel["3º ano - 2º simulado"].iloc[0])

    # Notas — lado a lado
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("<h3 style='text-align:center; margin: 0 0 8px 0;'>2º Ano</h3>",
                    unsafe_allow_html=True)
        st.plotly_chart(make_line_notas(y2_1, y2_2), use_container_width=True)
    with c2:
        st.markdown("<h3 style='text-align:center; margin: 0 0 8px 0;'>3º Ano</h3>",
                    unsafe_allow_html=True)
        st.plotly_chart(make_line_notas(y3_1, y3_2), use_container_width=True)

    # Participação — só quando Regional == MINAS GERAIS
    if regional.strip().upper() == "MINAS GERAIS" and data_part is not None:
        dia_escolhido = "Dia 1" if area in AREAS_DIA1 else "Dia 2"
        row = data_part[data_part["Dia"].str.strip().str.lower() == dia_escolhido.lower()]
        if not row.empty and all(col in row.columns for col in ["2ano_s1", "2ano_s2", "3ano_s1", "3ano_s2"]):
            p2_s1 = float(row["2ano_s1"].iloc[0])
            p2_s2 = float(row["2ano_s2"].iloc[0])
            p3_s1 = float(row["3ano_s1"].iloc[0])
            p3_s2 = float(row["3ano_s2"].iloc[0])

            st.markdown("<hr/>", unsafe_allow_html=True)
            c3, c4 = st.columns(2, gap="large")
            with c3:
                st.markdown(
                    f"<h3 style='text-align:center; margin: 0 0 8px 0;'>Participação – 2º ano ({dia_escolhido})</h3>",
                    unsafe_allow_html=True,
                )
                st.plotly_chart(make_line_participacao(p2_s1, p2_s2), use_container_width=True)
            with c4:
                st.markdown(
                    f"<h3 style='text-align:center; margin: 0 0 8px 0;'>Participação – 3º ano ({dia_escolhido})</h3>",
                    unsafe_allow_html=True,
                )
                st.plotly_chart(make_line_participacao(p3_s1, p3_s2), use_container_width=True)

    with st.expander("Ver dados da regional selecionada"):
        st.dataframe(df_sel.reset_index(drop=True), use_container_width=True)

























