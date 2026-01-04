import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import timedelta, datetime

# --- SAYFA AYARLARI ---
st.set_page_config(layout="wide", page_title="Mobil Borsa")

# --- MOBİL TASARIM (CSS) ---
st.markdown("""
    <style>
    @media (max-width: 600px) {
        h1 {font-size: 20px !important;}
        .stMetric {font-size: 14px !important;}
        .main .block-container {padding-top: 1rem; padding-left: 0.5rem; padding-right: 0.5rem;}
    }
    div[data-testid="stHorizontalBlock"] {gap: 0.3rem;}
    </style>
    """, unsafe_allow_html=True)

# --- SABİTLER ---
BIST_30 = [
    "AKBNK", "ALARK", "ARCLK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "DOAS",
    "EKGYO", "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR",
    "KCHOL", "KONTR", "KOZAL", "KRDMD", "ODAS", "OYAKC", "PETKM", "PGSUS",
    "SAHOL", "SASA", "SISE", "TCELL", "THYAO", "TOASO", "TSKB", "TTKOM",
    "TUPRS", "VAKBN", "YKBNK"
]

# --- YARDIMCI FONKSİYONLAR ---
def format_tl(sayi):
    if sayi is None: return "-"
    if sayi >= 1_000_000_000: return f"{sayi / 1_000_000_000:.2f} Mrd"
    elif sayi >= 1_000_000: return f"{sayi / 1_000_000:.2f} Mn"
    else: return f"{sayi:,.0f}"

@st.cache_data
def hisseleri_getir():
    try:
        with open('hisseler.txt', 'r', encoding='utf-8') as f:
            return sorted([h.strip() for h in f.read().split(',')])
    except:
        return ["THYAO", "GARAN", "ASELS"]

# --- TEKNİK ANALİZ ---
def teknik_hesapla(df):
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    # RSI
    delta = df['Close'].diff()
    kazanc = (delta.where(delta > 0, 0)).rolling(14).mean()
    kayip = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = kazanc / kayip
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    return df, macd, signal

def yapay_zeka_raporu(kod):
    try:
        hisse = yf.Ticker(kod + ".IS")
        df = hisse.history(period="1y")
        if df.empty: return "Veri yok."
        
        df, macd, signal = teknik_hesapla(df)
        son = df.iloc[-1]
        
        puan = 0
        if son['RSI'] < 35: puan += 2
        if macd.iloc[-1] > signal.iloc[-1]: puan += 2
        if son['Close'] > son['SMA200']: puan += 1
        
        karar = "AL" if puan >= 4 else "İZLE" if puan >= 2 else "SAT"
        renk = "green" if puan >= 4 else "orange" if puan >= 2 else "red"
        
        return f"""
        **🤖 AI Sinyali:** :{renk}[**{karar}**] (Puan: {puan}/5)  
        *RSI:* {son['RSI']:.0f} | *Trend:* {"Pozitif" if son['Close'] > son['SMA200'] else "Negatif"}
        """
    except Exception as e: return f"Hata: {e}"

@st.cache_data(ttl=300)
def piyasa_tara(liste):
    try:
        semboller = [h + ".IS" for h in liste]
        data = yf.download(semboller, period="5d", group_by='ticker', progress=False)
        res = []
        for h in liste:
            try:
                k = h + ".IS"
                if k in data.columns.levels[0]:
                    d = data[k].dropna()
                    if len(d) > 1:
                        s = d['Close'].iloc[-1]
                        o = d['Close'].iloc[-2]
                        res.append({"Kod": h, "Yuzde": ((s-o)/o)*100})
            except: continue
        return pd.DataFrame(res)
    except: return pd.DataFrame()

# --- BACKTEST ---
@st.cache_data(ttl=3600)
def hacimli_100(liste, tarih):
    try:
        t2 = tarih.strftime("%Y-%m-%d")
        t1 = (tarih - timedelta(days=5)).strftime("%Y-%m-%d")
        s = [h + ".IS" for h in liste]
        d = yf.download(s, start=t1, end=t2, group_by='ticker', progress=False)
        v = []
        for h in liste:
            k = h + ".IS"
            if k in d.columns.levels[0]:
                v.append((h, d[k]['Volume'].mean()))
        v.sort(key=lambda x: x[1] if x[1] else 0, reverse=True)
        return [x[0] for x in v[:100]]
    except: return liste[:100]

# --- ARAYÜZ ---
if 'secilen_hisse_kodu' not in st.session_state:
    st.session_state.secilen_hisse_kodu = "THYAO"

liste = hisseleri_getir()

st.title("📱 Cep Terminali")
tab1, tab2 = st.tabs(["Canlı Analiz", "Backtest"])

# SEKME 1
with tab1:
    idx = liste.index(st.session_state.secilen_hisse_kodu) if st.session_state.secilen_hisse_kodu in liste else 0
    hisse = st.selectbox("Hisse:", liste, index=idx, key="sb")
    
    if hisse:
        st.session_state.secilen_hisse_kodu = hisse
        try:
            t_kod = hisse + ".IS"
            obj = yf.Ticker(t_kod)
            inf = obj.info
            
            # Kartlar (2x2)
            c1, c2 = st.columns(2)
            c1.metric("Fiyat", f"{inf.get('currentPrice', 0)}")
            c1.metric("Hacim", format_tl(inf.get('volume', 0)))
            c2.metric("Değişim", f"%{((inf.get('currentPrice',0)-inf.get('previousClose',1))/inf.get('previousClose',1)*100):.2f}")
            c2.metric("Zirve", f"{inf.get('fiftyTwoWeekHigh', 0)}")
            
            st.write("")
            
            # Grafik Süre Seçimi (Yatay)
            periyot = st.radio("Süre:", ["1G", "1H", "1A", "6A", "1Y"], horizontal=True)
            p_map = {"1G":"1d", "1H":"5d", "1A":"1mo", "6A":"6mo", "1Y":"1y"}
            i_map = {"1G":"5m", "1H":"30m", "1A":"1d", "6A":"1d", "1Y":"1d"}
            
            v = obj.history(period=p_map[periyot], interval=i_map[periyot])
            if not v.empty:
                fig = go.Figure(data=[go.Candlestick(x=v.index, open=v['Open'], high=v['High'], low=v['Low'], close=v['Close'])])
                fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            
            # AI Butonu
            if st.button("🧠 AI Analizi", use_container_width=True):
                with st.spinner(".."):
                    st.markdown(yapay_zeka_raporu(hisse))
                    
        except: st.error("Veri yok.")

    with st.expander("📊 Piyasa (Tıkla)"):
        df_p = piyasa_tara(liste)
        if not df_p.empty:
            st.write("**Yükselenler:**")
            top = df_p.sort_values('Yuzde', ascending=False).head(5)
            for _, r in top.iterrows():
                if st.button(f"{r['Kod']} %{r['Yuzde']:.1f}", key=f"k_{r['Kod']}", use_container_width=True):
                    st.session_state.secilen_hisse_kodu = r['Kod']
                    st.rerun()

# SEKME 2
with tab2:
    st.caption("Geçmiş Test")
    c1, c2 = st.columns(2)
    d1 = c1.date_input("Alış", datetime(2025, 12, 19))
    d2 = c2.date_input("Satış", datetime(2026, 1, 4))
    filtre = st.selectbox("Havuz:", ["BIST 30", "Hacimli 100", "Tümü"])
    
    if st.button("Testi Başlat", use_container_width=True):
        st.info("Hesaplanıyor...")
        if filtre == "BIST 30": havuz = BIST_30
        elif filtre == "Hacimli 100": havuz = hacimli_100(liste, d1)
        else: havuz = liste
        
        t1 = (d1 - timedelta(days=60)).strftime("%Y-%m-%d")
        t2 = (d2 + timedelta(days=5)).strftime("%Y-%m-%d")
        s = [h + ".IS" for h in havuz]
        
        try:
            raw = yf.download(s, start=t1, end=t2, group_by='ticker', progress=False)
            res = []
            for h in havuz:
                k = h + ".IS"
                if k in raw.columns.levels[0]:
                    d = raw[k].dropna()
                    idx1 = d.index.get_indexer([str(d1)], method='pad')[0]
                    idx2 = d.index.get_indexer([str(d2)], method='pad')[0]
                    
                    if idx1 != -1 and idx2 != -1:
                        sub = d.iloc[:idx1+1]
                        if len(sub) > 30:
                            _, macd, sig = teknik_hesapla(sub)
                            rsi = sub['Close'].diff()
                            rsi = rsi.where(rsi>0,0).rolling(14).mean() / (-rsi.where(rsi<0,0).rolling(14).mean())
                            rsi = 100 - (100/(1+rsi))
                            
                            score = 0
                            if rsi.iloc[-1] < 35: score += 40
                            if macd.iloc[-1] > sig.iloc[-1]: score += 30
                            
                            if score >= 50:
                                p = ((d.iloc[idx2]['Close']-d.iloc[idx1]['Close'])/d.iloc[idx1]['Close'])*100
                                res.append({"Hisse": h, "Puan": score, "Getiri": p})
            
            if res:
                df_r = pd.DataFrame(res).sort_values("Puan", ascending=False).head(3)
                st.success(f"Ort. Getiri: %{df_r['Getiri'].mean():.2f}")
                st.dataframe(df_r, hide_index=True, use_container_width=True)
            else: st.warning("Hisse bulunamadı.")
        except: st.error("Hata oluştu.")