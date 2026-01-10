import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import timedelta, datetime
import time
import requests  # Telegram mesajları için gerekli

# --- 1. AYARLAR (EN BAŞTA OLMALI) ---
st.set_page_config(layout="wide", page_title="Mobil Borsa Pro")

# ==============================================================================
# 📢 TELEGRAM AYARLARI (SENİN BİLGİLERİNLE DOLDURULDU)
# ==============================================================================
# Senin paylaştığın Token:
TELEGRAM_BOT_TOKEN = "8552712750:AAGsNtOWhzirbPBpmbxmGhdRHEosEfv7n0Q"

# Senin paylaştığın Chat ID:
TELEGRAM_CHAT_ID = "7946675166"
# ==============================================================================

# --- 2. CSS ---
st.markdown("""
<style>
    @media (max-width: 600px) { h1 {font-size:18px!important;} .stMetric {font-size:12px!important;} .main .block-container {padding-top:1rem;} } 
    div[data-testid="stHorizontalBlock"] {gap:0.1rem;}
    .stButton button {height: 18px !important; padding: 0px 2px !important; font-size: 10px !important; width: 100%; text-align: left; background-color: #f8f9fa; border: none !important;}
    .stButton button:hover {background-color: #e9ecef; border: 1px solid #ced4da !important;}
    .rise-box {border-top: 3px solid #2e7d32; background-color: #f1f8e9; padding: 2px; text-align: center; font-weight: bold; font-size: 11px; color: #1b5e20; margin-bottom: 5px;}
    .fall-box {border-top: 3px solid #c62828; background-color: #ffebee; padding: 2px; text-align: center; font-weight: bold; font-size: 11px; color: #b71c1c; margin-bottom: 5px;}
    .header-info { font-size: 18px; font-weight: bold; margin:0; padding:0; }
</style>
""", unsafe_allow_html=True)

# --- 3. SABITLER ---
BIST_30 = ["AKBNK","ALARK","ARCLK","ASELS","ASTOR","BIMAS","BRSAN","DOAS","EKGYO","ENKAI","EREGL","FROTO","GARAN","GUBRF","HEKTS","ISCTR","KCHOL","KONTR","KOZAL","KRDMD","ODAS","OYAKC","PETKM","PGSUS","SAHOL","SASA","SISE","TCELL","THYAO","TOASO","TSKB","TTKOM","TUPRS","VAKBN","YKBNK"]

# --- 4. YARDIMCI FONKSİYONLAR ---
def format_tl(val):
    if val is None: return "-"
    if val >= 1e9: return f"{val/1e9:.2f} Mrd"
    if val >= 1e6: return f"{val/1e6:.2f} Mn"
    return f"{val:,.0f}"

@st.cache_data
def get_hisseler():
    try:
        with open('hisseler.txt', 'r', encoding='utf-8') as f:
            return sorted([x.strip() for x in f.read().split(',')])
    except: return sorted(BIST_30)

def piyasa_acik_mi():
    tr_now = datetime.utcnow() + timedelta(hours=3)
    if tr_now.weekday() >= 5: return False
    simdi_dk = tr_now.hour * 60 + tr_now.minute
    if (9*60+55) <= simdi_dk <= (18*60+10): return True
    return False

# --- 📢 TELEGRAM FONKSİYONU ---
def telegrama_mesaj_at(mesaj):
    if not TELEGRAM_BOT_TOKEN or "BURAYA" in TELEGRAM_BOT_TOKEN:
        return 
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# --- 5. TEKNİK ANALİZ FONKSİYONLARI ---
def teknik_hesapla(df):
    df = df.copy()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + gain / loss))
    df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['MACD_Hist'] = df['MACD'] - df['MACD'].ewm(span=9, adjust=False).mean()
    df['EMA_Diff'] = abs(df['EMA12'] - df['EMA26'])
    sma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()
    df['BB_Lower'] = sma20 - (2 * std20)
    df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
    df['Range'] = df['High'] - df['Low']
    df['Range_SMA5'] = df['Range'].rolling(5).mean()
    
    # MOMENTUM İÇİN EKSTRA
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_60'] = df['Close'].ewm(span=60, adjust=False).mean()
    df['Return_1M'] = df['Close'].pct_change(periods=21) * 100
    df['Return_3M'] = df['Close'].pct_change(periods=63) * 100
    return df

def skor_hesapla(df):
    try:
        if len(df) < 26: return 0
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        if 25 <= curr['RSI'] <= 40 and curr['RSI'] > prev['RSI']: score += 1
        if curr['MACD_Hist'] > prev['MACD_Hist']: score += 1
        if curr['EMA_Diff'] < prev['EMA_Diff']: score += 1
        if curr['Low'] <= curr['BB_Lower'] and curr['Close'] > curr['BB_Lower']: score += 1
        if curr['Volume'] >= (1.3 * curr['Vol_SMA20']): score += 1
        if curr['Range'] > curr['Range_SMA5']: score += 1
        return score
    except: return 0

def ai_analiz_tekil(kod):
    try:
        t = yf.Ticker(kod + ".IS")
        h = t.history(period="3mo")
        if h.empty: return "Veri Yok"
        df = teknik_hesapla(h)
        score = skor_hesapla(df)
        decision = "AL" if score >= 3 else "BEKLE"
        color = "green" if score >= 3 else "orange" if score == 2 else "gray"
        return f":{color}[**{decision}** ({score}/6)] RSI:{df.iloc[-1]['RSI']:.0f}"
    except: return "Hata"

# --- 6. MODÜLLER ---

# A) MOMENTUM TARAMA
@st.cache_data(ttl=3600)
def momentum_taramasi(hisse_listesi):
    sonuc_listesi = []
    start_date = (datetime.now() - timedelta(days=220)).strftime("%Y-%m-%d")
    tickers = [x + ".IS" for x in hisse_listesi]
    data = yf.download(tickers, start=start_date, group_by='ticker', progress=False, threads=True)
    
    for hisse in hisse_listesi:
        try:
            df = data[hisse + ".IS"].copy()
            df.dropna(inplace=True)
            if len(df) > 65:
                df = teknik_hesapla(df)
                last = df.iloc[-1]
                cond_mom = last['Return_3M'] > 0
                cond_trend = last['EMA_20'] > last['EMA_60']
                
                if cond_mom and cond_trend:
                    rsi_note = "Normal"
                    if last['RSI'] > 70: rsi_note = "Aşırı Alım (>70)"
                    elif last['RSI'] < 30: rsi_note = "Aşırı Satım (<30)"
                    elif last['RSI'] > 50: rsi_note = "Güçlü (>50)"
                    
                    sonuc_listesi.append({
                        'Hisse': hisse, 'Fiyat': last['Close'], 'Getiri 3A %': last['Return_3M'],
                        'Getiri 1A %': last['Return_1M'], 'RSI': last['RSI'], 'Durum': rsi_note
                    })
        except: continue
    if sonuc_listesi:
        return pd.DataFrame(sonuc_listesi).sort_values(by='Getiri 3A %', ascending=False)
    return pd.DataFrame()

# B) BACKTEST (AI TEK GÜN)
@st.cache_data(ttl=3600)
def backtest_gecmis_analiz(tarih, hisse_listesi):
    results = []
    target_date_str = tarih.strftime("%Y-%m-%d")
    start_date = (tarih - timedelta(days=120)).strftime("%Y-%m-%d")
    end_date = (tarih + timedelta(days=5)).strftime("%Y-%m-%d")
    tickers = [x + ".IS" for x in hisse_listesi]
    data = yf.download(tickers, start=start_date, end=end_date, group_by='ticker', progress=False, threads=True)
    for hisse in hisse_listesi:
        try:
            df = data[hisse + ".IS"].copy()
            df.dropna(inplace=True)
            if not isinstance(df.index, pd.DatetimeIndex): df.index = pd.to_datetime(df.index)
            past_data = df[df.index < target_date_str]
            if len(past_data) > 26:
                past_data = teknik_hesapla(past_data)
                score = skor_hesapla(past_data)
                if score >= 3:
                    prev_close = past_data.iloc[-1]['Close']
                    future_data = df[df.index >= target_date_str].head(1)
                    if not future_data.empty:
                        open_price = future_data.iloc[0]['Open']
                        close_price = future_data.iloc[0]['Close']
                        profit = ((close_price - open_price) / open_price) * 100
                        results.append({'Durum': '✅ Test', 'Hisse': hisse, 'AI': int(score), 'RSI': int(past_data.iloc[-1]['RSI']), 'Öneri': prev_close, 'Açılış': open_price, 'Kapanış': close_price, 'Kar %': profit})
                    else:
                        results.append({'Durum': '🔮 Tahmin', 'Hisse': hisse, 'AI': int(score), 'RSI': int(past_data.iloc[-1]['RSI']), 'Öneri': prev_close, 'Açılış': None, 'Kapanış': None, 'Kar %': None})
        except: continue
    if results:
        return pd.DataFrame(results).sort_values(by=['AI', 'RSI'], ascending=[False, True]).head(10)
    return pd.DataFrame()

# C) SİMÜLASYON (AI TEKNİK)
@st.cache_data(ttl=3600)
def simulasyon_calistir(baslangic_tarihi, baslangic_bakiye, hisse_listesi):
    start_buffer = (baslangic_tarihi - timedelta(days=100)).strftime("%Y-%m-%d")
    tickers = [x + ".IS" for x in hisse_listesi]
    raw_data = yf.download(tickers, start=start_buffer, group_by='ticker', progress=False, threads=True)
    nakit = baslangic_bakiye
    portfoy = {}
    gunluk_ozet = []
    islem_gecmisi = []
    
    if len(raw_data) == 0: return None, None
    sim_dates = [d for d in raw_data.index if d >= pd.Timestamp(baslangic_tarihi)]
    
    processed_data = {}
    for hisse in hisse_listesi:
        try:
            df = raw_data[hisse + ".IS"].copy()
            df.dropna(inplace=True)
            if len(df) > 30:
                df = teknik_hesapla(df)
                prev = df.shift(1)
                c1 = (df['RSI']>=25)&(df['RSI']<=45)&(df['RSI']>prev['RSI'])
                c2 = df['MACD_Hist']>prev['MACD_Hist']
                c3 = df['EMA_Diff']<prev['EMA_Diff']
                c4 = (df['Low']<=df['BB_Lower'])&(df['Close']>df['BB_Lower'])
                c5 = df['Volume']>=(1.2*df['Vol_SMA20'])
                c6 = df['Range']>df['Range_SMA5']
                df['Score'] = c1.astype(int)+c2.astype(int)+c3.astype(int)+c4.astype(int)+c5.astype(int)+c6.astype(int)
                df['Signal_Score'] = df['Score'].shift(1)
                processed_data[hisse] = df
        except: continue

    for d in sim_dates:
        satilacaklar = []
        portfoy_degeri = 0
        for hisse, veri in portfoy.items():
            if hisse in processed_data and d in processed_data[hisse].index:
                row = processed_data[hisse].loc[d]
                curr = row['Close']
                maliyet = veri['Maliyet']
                if row['Open'] > maliyet:
                    nakit += row['Open'] * veri['Adet']
                    islem_gecmisi.append({'Tarih': d, 'Hisse': hisse, 'İşlem': 'SAT (Gap)', 'Fiyat': row['Open'], 'Kar/Zarar': (row['Open']-maliyet)*veri['Adet']})
                    satilacaklar.append(hisse)
                elif row['High'] >= maliyet * 1.01:
                    satis = maliyet * 1.01
                    nakit += satis * veri['Adet']
                    islem_gecmisi.append({'Tarih': d, 'Hisse': hisse, 'İşlem': 'SAT (Kar)', 'Fiyat': satis, 'Kar/Zarar': (satis-maliyet)*veri['Adet']})
                    satilacaklar.append(hisse)
                else:
                    portfoy_degeri += curr * veri['Adet']
            else: portfoy_degeri += veri['Adet'] * veri['Maliyet']
        
        for h in satilacaklar: del portfoy[h]
        
        bos = 5 - len(portfoy)
        if bos > 0 and nakit > 1000:
            cands = []
            for hisse, df in processed_data.items():
                if d in df.index and hisse not in portfoy:
                    s = df.loc[d]['Signal_Score']
                    if s >= 3: cands.append({'H': hisse, 'S': s, 'R': df.loc[d]['RSI']})
            if cands:
                cands.sort(key=lambda x: (-x['S'], x['R']))
                picks = cands[:bos]
                butce = nakit / len(picks)
                for p in picks:
                    h = p['H']
                    op = processed_data[h].loc[d]['Open']
                    adet = int(butce / op)
                    if adet > 0:
                        portfoy[h] = {'Adet': adet, 'Maliyet': op}
                        nakit -= adet * op
                        portfoy_degeri += adet * op
                        islem_gecmisi.append({'Tarih': d, 'Hisse': h, 'İşlem': 'AL', 'Fiyat': op, 'Kar/Zarar': 0})
        
        gunluk_ozet.append({'Tarih': d, 'Bakiye': nakit+portfoy_degeri, 'Nakit': nakit})
    return pd.DataFrame(gunluk_ozet), pd.DataFrame(islem_gecmisi)

# D) MOMENTUM DİNAMİK SİMÜLASYON (AL-SAT ve TELEGRAMLI)
@st.cache_data(ttl=3600)
def momentum_dinamik_simulasyon(baslangic_tarihi, hisse_listesi, baslangic_bakiye=100000):
    start_buffer = (baslangic_tarihi - timedelta(days=220)).strftime("%Y-%m-%d")
    tickers = [x + ".IS" for x in hisse_listesi]
    
    # Tüm veriyi çek
    raw_data = yf.download(tickers, start=start_buffer, group_by='ticker', progress=False, threads=True)
    
    nakit = baslangic_bakiye
    portfoy = {} # {Hisse: {Adet: 100, Maliyet: 50.0}}
    gunluk_ozet = []
    islem_gecmisi = []
    max_hisse = 5
    
    if len(raw_data) == 0: return None, None
    sim_dates = [d for d in raw_data.index if d >= pd.Timestamp(baslangic_tarihi)]
    
    # 1. Veri İşleme
    processed_data = {}
    for hisse in hisse_listesi:
        try:
            df = raw_data[hisse + ".IS"].copy()
            df.dropna(inplace=True)
            if len(df) > 65:
                df = teknik_hesapla(df) 
                processed_data[hisse] = df
        except: continue
        
    # 2. Gün Gün Simülasyon
    for d in sim_dates:
        satilacaklar = []
        portfoy_degeri = 0
        
        # --- SATIŞ KONTROLÜ (TP/SL) ---
        for hisse, veri in portfoy.items():
            if hisse in processed_data and d in processed_data[hisse].index:
                row = processed_data[hisse].loc[d]
                curr_price = row['Close']
                high_price = row['High']
                low_price = row['Low']
                open_price = row['Open']
                
                maliyet = veri['Maliyet']
                adet = veri['Adet']
                
                # Kar Al: %5, Zarar Kes: %3
                take_profit_price = maliyet * 1.05
                stop_loss_price = maliyet * 0.97
                
                satis_fiyati = None
                satis_nedeni = ""
                
                if open_price >= take_profit_price:
                    satis_fiyati = open_price
                    satis_nedeni = "Gap ile Kar Al (Gap TP)"
                elif open_price <= stop_loss_price:
                    satis_fiyati = open_price
                    satis_nedeni = "Gap ile Stop (Gap SL)"
                elif high_price >= take_profit_price:
                    satis_fiyati = take_profit_price
                    satis_nedeni = "Kar Al (+%5)"
                elif low_price <= stop_loss_price:
                    satis_fiyati = stop_loss_price
                    satis_nedeni = "Stop Loss (-%3)"
                
                if satis_fiyati:
                    kar_zarar = (satis_fiyati - maliyet) * adet
                    nakit += satis_fiyati * adet
                    islem_gecmisi.append({
                        'Tarih': d, 'Hisse': hisse, 'İşlem': 'SAT', 
                        'Fiyat': satis_fiyati, 'Durum': satis_nedeni, 
                        'Kar/Zarar': kar_zarar
                    })
                    satilacaklar.append(hisse)
                    
                    # 🚀 TELEGRAM BİLDİRİMİ (Sadece son 2 gün için atar, eskiyi spamlamaz)
                    if (datetime.now() - d).days < 2:
                        emoji = "💰" if kar_zarar > 0 else "🛑"
                        msg = f"{emoji} **SATIŞ SİNYALİ**\n\nHisse: {hisse}\nFiyat: {satis_fiyati:.2f}\nNeden: {satis_nedeni}\nKar/Zarar: {kar_zarar:.0f} TL"
                        telegrama_mesaj_at(msg)

                else:
                    portfoy_degeri += curr_price * adet 
            else:
                portfoy_degeri += veri['Adet'] * veri['Maliyet']
        
        for h in satilacaklar: del portfoy[h]
        
        # --- ALIM KONTROLÜ (MOMENTUM) ---
        bos_yer = max_hisse - len(portfoy)
        if bos_yer > 0 and nakit > 1000:
            candidates = []
            for hisse, df in processed_data.items():
                if d in df.index and hisse not in portfoy: 
                    row = df.loc[d]
                    cond_mom = row['Return_3M'] > 0
                    cond_trend = row['EMA_20'] > row['EMA_60']
                    
                    if cond_mom and cond_trend:
                        candidates.append({
                            'Hisse': hisse, 'Getiri_3M': row['Return_3M'], 'Fiyat': row['Close']
                        })
            
            if candidates:
                candidates.sort(key=lambda x: x['Getiri_3M'], reverse=True)
                picks = candidates[:bos_yer]
                
                butce_per_hisse = nakit / len(picks)
                for pick in picks:
                    h = pick['Hisse']
                    fiyat = pick['Fiyat']
                    adet = int(butce_per_hisse / fiyat)
                    
                    if adet > 0:
                        portfoy[h] = {'Adet': adet, 'Maliyet': fiyat}
                        harcanan = adet * fiyat
                        nakit -= harcanan
                        portfoy_degeri += harcanan
                        islem_gecmisi.append({
                            'Tarih': d, 'Hisse': h, 'İşlem': 'AL', 
                            'Fiyat': fiyat, 'Durum': 'Momentum Giriş', 
                            'Kar/Zarar': 0
                        })
                        
                        # 🚀 TELEGRAM BİLDİRİMİ (Sadece güncel işlemler)
                        if (datetime.now() - d).days < 2:
                            msg = f"🚀 **AL SİNYALİ**\n\nHisse: {h}\nFiyat: {fiyat:.2f}\nAdet: {adet}\nStrateji: Momentum Rotasyon"
                            telegrama_mesaj_at(msg)
                        
        gunluk_ozet.append({'Tarih': d, 'Bakiye': nakit + portfoy_degeri})
        
    return pd.DataFrame(gunluk_ozet), pd.DataFrame(islem_gecmisi)

@st.cache_data(ttl=300) 
def get_daily_movers(hisse_listesi):
    s = [x+".IS" for x in hisse_listesi]
    d = yf.download(s, period="2d", progress=False, threads=True)['Close']
    if isinstance(d, pd.Series): d = d.to_frame()
    if len(d) >= 2:
        son = d.iloc[-1]
        onceki = d.iloc[-2]
        yuzdeler = ((son - onceki) / onceki) * 100
        df = pd.DataFrame({'Hisse': yuzdeler.index.str.replace('.IS',''), 'Yüzde': yuzdeler.values})
        return df.dropna()
    return pd.DataFrame()

# --- 7. ARAYÜZ ---
if 'kod' not in st.session_state: st.session_state.kod = "THYAO"
L = get_hisseler()
durum = piyasa_acik_mi()
auto_refresh = False

c_baslik, c_kontrol = st.columns([6, 3])
with c_baslik: st.title("📱 Cep Terminali")
with c_kontrol:
    if durum:
        k1, k2 = st.columns(2)
        with k1: 
            if st.button("Yenile ⚡"): st.rerun()
        with k2:
            auto_refresh = st.checkbox("Canlı (60s)", value=False)
    else:
        st.markdown('<div class="market-closed">🌙 Borsa Kapalı</div>', unsafe_allow_html=True)

if auto_refresh and durum: timer_placeholder = st.empty()

t1, t2, t3, t4 = st.tabs(["Canlı İzleme", "AI Analiz (Tek Gün)", "Borsacı (Simülasyon)", "Momentum Analiz"])

with t1:
    col_input, col_header_info = st.columns([1.2, 8.8])
    with col_input:
        idx = L.index(st.session_state.kod) if st.session_state.kod in L else 0
        sel = st.selectbox("Hisse", L, index=idx, label_visibility="collapsed")
    
    if sel:
        st.session_state.kod = sel
        try:
            tk = yf.Ticker(sel+".IS")
            inf = tk.info
            with col_header_info:
                st.markdown(f"**{sel}** | {inf.get('currentPrice',0)} TL")

            c_graf, c_list = st.columns([2.3, 1.2]) 
            with c_graf:
                with st.container(border=True, height=450):
                    st.markdown(ai_analiz_tekil(sel))
                    per_sec = st.radio("Periyot", ["5dk", "1sa", "4sa", "1G"], horizontal=True, label_visibility="collapsed")
                    if per_sec == "5dk":   p, i = "5d", "5m"
                    elif per_sec == "1sa": p, i = "1y", "60m"
                    elif per_sec == "4sa": p, i = "2y", "60m"
                    else: p, i = "2y", "1d"
                    df = tk.history(period=p, interval=i)
                    if not df.empty:
                        if per_sec == "4sa":
                             ohlc = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
                             df = df.resample('4h').agg(ohlc).dropna()
                        df['T'] = df.index.strftime('%d-%m %H:%M')
                        fig = go.Figure(data=[go.Candlestick(x=df['T'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
                        fig.update_layout(height=300, margin=dict(t=5,b=0,l=0,r=0), xaxis_rangeslider_visible=False)
                        st.plotly_chart(fig, use_container_width=True)

            with c_list:
                with st.container(border=True, height=450):
                    if st.button("Piyasa ⟳"): 
                        st.session_state.piyasa_df = get_daily_movers(L)
                    
                    if 'piyasa_df' not in st.session_state: st.session_state.piyasa_df = get_daily_movers(L)
                    df_mov = st.session_state.piyasa_df
                    if not df_mov.empty:
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown('<div class="rise-box">Yükselen</div>', unsafe_allow_html=True)
                            for _, r in df_mov.sort_values('Yüzde', ascending=False).head(12).iterrows():
                                if st.button(f"{r['Hisse']} %{r['Yüzde']:.1f}", key=f"u{r['Hisse']}"):
                                    st.session_state.kod = r['Hisse']
                                    st.rerun()
                        with c2:
                            st.markdown('<div class="fall-box">Düşen</div>', unsafe_allow_html=True)
                            for _, r in df_mov.sort_values('Yüzde', ascending=True).head(12).iterrows():
                                if st.button(f"{r['Hisse']} %{r['Yüzde']:.1f}", key=f"d{r['Hisse']}"):
                                    st.session_state.kod = r['Hisse']
                                    st.rerun()
        except: st.error("Veri yok")

with t2:
    st.markdown("### 🧠 AI Analiz")
    c1, c2 = st.columns([1, 4])
    tarih = c1.date_input("Tarih", datetime.now() + timedelta(days=1))
    if c1.button("Başlat"):
        res = backtest_gecmis_analiz(datetime.combine(tarih, datetime.min.time()), L)
        if not res.empty:
            st.dataframe(res, column_config={"AI": st.column_config.NumberColumn(format="%d"), "RSI": st.column_config.NumberColumn(format="%d"), "Öneri": st.column_config.NumberColumn(format="%.2f"), "Açılış": st.column_config.NumberColumn(format="%.2f"), "Kapanış": st.column_config.NumberColumn(format="%.2f"), "Kar %": st.column_config.NumberColumn(format="%.2f%%")}, use_container_width=True, hide_index=True)
        else: st.warning("Sonuç yok")

with t3:
    st.markdown("### 🤖 Sanal Borsacı (Teknik)")
    col1, col2 = st.columns(2)
    start_sim = col1.date_input("Başlangıç", datetime.now() - timedelta(days=90))
    if col2.button("SİMÜLASYON BAŞLAT"):
        res_bal, res_tr = simulasyon_calistir(datetime.combine(start_sim, datetime.min.time()), 100000, L)
        if res_bal is not None:
            final = res_bal.iloc[-1]['Bakiye']
            st.metric("Son Bakiye", f"{final:,.0f} TL", delta=f"%{((final-100000)/100000)*100:.1f}")
            st.line_chart(res_bal.set_index('Tarih')['Bakiye'])
            st.dataframe(res_tr.sort_values('Tarih', ascending=False), column_config={"Tarih": st.column_config.DateColumn(format="DD.MM.YYYY"), "Fiyat": st.column_config.NumberColumn(format="%.2f TL"), "Kar/Zarar": st.column_config.NumberColumn(format="%.2f TL")}, use_container_width=True, hide_index=True)

with t4:
    st.markdown("### 🚀 Momentum Stratejisi")
    mod = st.radio("Mod Seçiniz:", ["Canlı Piyasa Taraması", "Dinamik Simülasyon (Al-Sat)"], horizontal=True)
    if mod == "Canlı Piyasa Taraması":
        st.info("Kriterler: 3 Aylık Getiri > 0 VE EMA(20) > EMA(60)")
        if st.button("TARAMAYI BAŞLAT 🔎"):
            with st.spinner("Hisseler taranıyor..."):
                mom_df = momentum_taramasi(L)
                if not mom_df.empty:
                    st.success(f"{len(mom_df)} adet potansiyel hisse bulundu.")
                    st.dataframe(mom_df, column_config={"Fiyat": st.column_config.NumberColumn(format="%.2f TL"), "Getiri 3A %": st.column_config.NumberColumn(format="%.2f%%"), "Getiri 1A %": st.column_config.NumberColumn(format="%.2f%%"), "RSI": st.column_config.NumberColumn(format="%.1f")}, use_container_width=True, hide_index=True)
                else: st.warning("Kriterlere uyan hisse bulunamadı.")
    else: 
        st.info("Seçtiğin tarihten BUGÜNE kadar çalışır. Robot 5 hisse alır. %5 Kâr veya %3 Zarar görünce satar ve hemen YENİSİNİ alır.")
        c1, c2 = st.columns([1, 2])
        sim_start_date = c1.date_input("Simülasyon Başlangıç", datetime.now() - timedelta(days=90))
        if c1.button("SİMÜLASYONU BAŞLAT 🏁"):
            with st.spinner("Robot geçmişte işlem yapıyor..."):
                res_df, trades_df = momentum_dinamik_simulasyon(datetime.combine(sim_start_date, datetime.min.time()), L)
                if res_df is not None and not res_df.empty:
                    son_bakiye = res_df.iloc[-1]['Bakiye']
                    kar = son_bakiye - 100000
                    yuzde = (kar / 100000) * 100
                    m1, m2 = st.columns(2)
                    m1.metric("Son Bakiye", f"{son_bakiye:,.0f} TL", delta=f"{kar:,.0f} TL")
                    m2.metric("Toplam Getiri", f"%{yuzde:.2f}")
                    st.line_chart(res_df.set_index('Tarih')['Bakiye'])
                    with st.expander("İşlem Geçmişi (Al-Sat Kayıtları)"):
                        st.dataframe(trades_df.sort_values('Tarih', ascending=False), column_config={"Tarih": st.column_config.DateColumn(format="DD.MM.YYYY"), "Fiyat": st.column_config.NumberColumn(format="%.2f TL"), "Kar/Zarar": st.column_config.NumberColumn(format="%.2f TL")}, use_container_width=True, hide_index=True)
                else: st.error("Veri alınamadı veya tarih aralığı çok kısa.")

if auto_refresh and durum:
    time.sleep(1)
    st.rerun()

# --- EN ALTA EKLENECEK TEST KODU ---
st.markdown("---")
st.subheader("🛠 Bağlantı Testi")
if st.button("Telegram'a Test Mesajı Gönder 📨"):
    telegrama_mesaj_at("👋 Merhaba Patron! Ben Borsa Robotun. Bağlantımız süper çalışıyor! 🚀")
    st.success("Mesaj gönderildi! Telefonunu kontrol et.")