import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import timedelta, datetime

# --- SAYFA AYARLARI (EN BAŞTA OLMALI) ---
st.set_page_config(layout="wide", page_title="Borsa Pro Terminal & Backtest")

# --- GLOBAL SABİTLER ---
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
    if sayi >= 1_000_000_000: return f"{sayi / 1_000_000_000:.2f} Milyar"
    elif sayi >= 1_000_000: return f"{sayi / 1_000_000:.2f} Milyon"
    else: return f"{sayi:,.0f}"

def renkli_yazi(metin, durum):
    if durum == "iyi": return f":green[{metin}]"
    elif durum == "orta": return f":orange[{metin}]"
    else: return f":red[{metin}]"

# --- HİSSE LİSTESİ YÖNETİMİ ---
@st.cache_data
def hisseleri_getir():
    try:
        with open('hisseler.txt', 'r', encoding='utf-8') as dosya:
            return sorted([h.strip() for h in dosya.read().split(',')])
    except FileNotFoundError:
        return ["THYAO", "GARAN", "ASELS"]

# --- TEKNİK İNDİKATÖRLER (HER İKİ MODÜL İÇİN) ---
def rsi_hesapla(seri, periyot=14):
    delta = seri.diff()
    kazanc = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    kayip = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = kazanc / kayip
    return 100 - (100 / (1 + rs))

def macd_hesapla(seri):
    exp12 = seri.ewm(span=12, adjust=False).mean()
    exp26 = seri.ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

# --- MODÜL 1: CANLI ANALİZ VE AI RAPORU ---
def yapay_zeka_analizi_yap(hisse_kodu):
    try:
        tam_kod = hisse_kodu + ".IS"
        hisse = yf.Ticker(tam_kod)
        
        df = hisse.history(period="1y", interval="1d")
        if df.empty: return "❌ Yetersiz veri."

        info = hisse.info

        # Teknik Hesaplar
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['SMA200'] = df['Close'].rolling(window=200).mean()
        df['RSI'] = rsi_hesapla(df['Close'])
        macd, signal = macd_hesapla(df['Close'])
        
        son_fiyat = df['Close'].iloc[-1]
        son_rsi = df['RSI'].iloc[-1]
        son_macd = macd.iloc[-1]
        son_sig = signal.iloc[-1]
        son_sma200 = df['SMA200'].iloc[-1]
        
        # Sentez
        if son_fiyat > son_sma200: trend = "Yükseliş (Boğa) 🐂"
        else: trend = "Düşüş (Ayı) 🐻"
        
        tek_yorum = []
        if son_rsi < 30: tek_yorum.append("RSI Dipte")
        elif son_rsi > 70: tek_yorum.append("RSI Zirvede")
        if son_macd > son_sig: tek_yorum.append("MACD Al")
        else: tek_yorum.append("MACD Sat")
        teknik_txt = ", ".join(tek_yorum) if tek_yorum else "Nötr"
        
        fk = info.get('trailingPE', 0)
        pb = info.get('priceToBook', 0)
        
        puan = 0
        if son_rsi < 35: puan += 2
        if son_macd > son_sig: puan += 2
        if son_fiyat > son_sma200: puan += 1
        if fk > 0 and fk < 10: puan += 2
        
        if puan >= 5: karar, renk = "GÜÇLÜ AL", "green"
        elif puan >= 3: karar, renk = "İZLE / KADEMELİ", "orange"
        else: karar, renk = "SAT / UZAK DUR", "red"
            
        rapor = f"""
        ### 🤖 {hisse_kodu} Analiz Raporu
        **1. Trend:** {trend}
        **2. Teknik:** {teknik_txt}
        **3. Temel:** F/K: {fk:.2f} | PD/DD: {pb:.2f}
        ---
        **🧠 YAPAY ZEKA KARARI:** :{renk}[**{karar}**] (Güven: {puan}/7)
        """
        return rapor
    except Exception as e: return f"Analiz hatası: {e}"

@st.cache_data(ttl=300)
def piyasa_durumunu_getir(hisse_listesi):
    try:
        semboller = [h + ".IS" for h in hisse_listesi]
        data = yf.download(semboller, period="5d", group_by='ticker', progress=False, threads=True)
        sonuclar = []
        for h in hisse_listesi:
            try:
                h_kod = h + ".IS"
                if h_kod in data.columns.levels[0]:
                    df = data[h_kod].dropna()
                    if len(df) >= 2:
                        son = df['Close'].iloc[-1]
                        onceki = df['Close'].iloc[-2]
                        yuzde = ((son - onceki) / onceki) * 100
                        sonuclar.append({"Kod": h, "Son": son, "Yuzde": yuzde})
            except: continue
        return pd.DataFrame(sonuclar)
    except: return pd.DataFrame()

# --- MODÜL 2: BACKTEST FİLTRESİ ---
@st.cache_data(ttl=3600)
def en_hacimli_100_getir(tum_liste, tarih):
    t_son = tarih.strftime("%Y-%m-%d")
    t_bas = (tarih - timedelta(days=5)).strftime("%Y-%m-%d")
    semboller = [h + ".IS" for h in tum_liste]
    try:
        data = yf.download(semboller, start=t_bas, end=t_son, group_by='ticker', progress=False, threads=True)
        hacim_skorlari = []
        for h in tum_liste:
            kod = h + ".IS"
            if kod in data.columns.levels[0]:
                vol = data[kod]['Volume'].mean()
                hacim_skorlari.append((h, vol))
        hacim_skorlari.sort(key=lambda x: x[1] if not pd.isna(x[1]) else 0, reverse=True)
        return [x[0] for x in hacim_skorlari[:100]]
    except: return tum_liste[:100]

# --- BAŞLANGIÇ AYARLARI ---
if 'periyot' not in st.session_state:
    st.session_state.periyot = "1d"
    st.session_state.aralik = "1m"
if 'secilen_hisse_kodu' not in st.session_state:
    st.session_state.secilen_hisse_kodu = "THYAO"

tum_hisseler = hisseleri_getir()

# ==============================================================================
# ANA ARAYÜZ (TABLAR)
# ==============================================================================
st.title("Borsa Pro Terminal & Backtest")

tab_terminal, tab_backtest = st.tabs(["📈 Canlı Terminal & AI", "🧪 Geriye Dönük Test"])

# ==============================================================================
# SEKME 1: CANLI TERMİNAL
# ==============================================================================
with tab_terminal:
    col_sol, col_orta, col_sag = st.columns([2, 1, 1]) 

    # SOL SÜTUN
    with col_sol:
        try: secili_index = tum_hisseler.index(st.session_state.secilen_hisse_kodu)
        except: secili_index = 0

        def hisse_degisti():
            st.session_state.secilen_hisse_kodu = st.session_state.sb_hisse

        secilen_hisse = st.selectbox("Hisse Seç:", tum_hisseler, index=secili_index, key="sb_hisse", on_change=hisse_degisti)
        hisse_kodu = st.session_state.secilen_hisse_kodu

        if hisse_kodu:
            tam_kod = hisse_kodu + ".IS"
            try:
                hisse_obj = yf.Ticker(tam_kod)
                info = hisse_obj.info
                
                # Kartlar
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Fiyat", f"{info.get('currentPrice', 0)} TL")
                c2.metric("Hacim", format_tl(info.get('volume', 0)))
                c3.metric("F/K", f"{info.get('trailingPE', 0):.2f}")
                c4.metric("Zirve", f"{info.get('fiftyTwoWeekHigh', 0)} TL")
                
                st.divider()
                
                # Grafik
                veri = hisse_obj.history(period=st.session_state.periyot, interval=st.session_state.aralik)
                if not veri.empty:
                    fig = go.Figure(data=[go.Candlestick(x=veri.index, open=veri['Open'], high=veri['High'], low=veri['Low'], close=veri['Close'])])
                    fig.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                
                # DÜZELTME: Grafik Süre Butonları (Karışıklığı önlemek için burada)
                st.caption("Grafik Zaman Aralığı:")
                b_cols = st.columns(6)
                def btn(p, i):
                    st.session_state.periyot = p
                    st.session_state.aralik = i
                    st.rerun()
                    
                if b_cols[0].button("1G", key="btn_1g"): btn("1d", "1m")
                if b_cols[1].button("5G", key="btn_5g"): btn("5d", "5m")
                if b_cols[2].button("1A", key="btn_1a"): btn("1mo", "30m")
                if b_cols[3].button("6A", key="btn_6a"): btn("6mo", "1h")
                if b_cols[4].button("YB", key="btn_ytd"): btn("ytd", "1h")
                if b_cols[5].button("MAX", key="btn_max"): btn("max", "1d")

                st.divider() # AYIRICI ÇİZGİ
                
                # YAPAY ZEKA RAPOR BUTONU (En altta, ayrı duruyor)
                if st.button(f"🧠 {hisse_kodu} İçin Detaylı AI Raporu Oluştur", use_container_width=True, key="btn_ai_run"):
                    with st.spinner("Yapay zeka verileri analiz ediyor..."):
                        rapor = yapay_zeka_analizi_yap(hisse_kodu)
                        st.markdown(rapor)

            except Exception as e:
                st.error(f"Veri çekilemedi: {e}")

    # ORTA SÜTUN (GEÇMİŞ)
    with col_orta:
        st.caption("📅 Son 10 Gün")
        if hisse_kodu:
            tam_kod = hisse_kodu + ".IS"
            try:
                hist = yf.Ticker(tam_kod).history(period="1mo")
                if not hist.empty:
                    hist = hist.sort_index(ascending=False).head(10)
                    df_hist = pd.DataFrame({
                        "Tarih": hist.index.strftime('%d.%m'),
                        "Kapanış": hist['Close'].values
                    })
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)
            except: st.info("Veri yok")

    # SAĞ SÜTUN (PİYASA)
    with col_sag:
        st.caption("📊 Piyasa")
        with st.spinner("."):
            df_piyasa = piyasa_durumunu_getir(tum_hisseler)
        
        if not df_piyasa.empty:
            artan = df_piyasa.sort_values('Yuzde', ascending=False).head(10)
            azalan = df_piyasa.sort_values('Yuzde', ascending=True).head(10)
            
            c1, c2 = st.columns(2)
            with c1:
                st.success("🚀")
                for _, r in artan.iterrows():
                    if st.button(f"{r['Kod']}\n%{r['Yuzde']:.1f}", key=f"u{r['Kod']}"):
                        st.session_state.secilen_hisse_kodu = r['Kod']
                        st.rerun()
            with c2:
                st.error("🔻")
                for _, r in azalan.iterrows():
                    if st.button(f"{r['Kod']}\n%{r['Yuzde']:.1f}", key=f"d{r['Kod']}"):
                        st.session_state.secilen_hisse_kodu = r['Kod']
                        st.rerun()

# ==============================================================================
# SEKME 2: BACKTEST
# ==============================================================================
with tab_backtest:
    st.markdown("### 🧪 Profesyonel Backtest + Akıllı Filtre")
    st.caption("Strateji: RSI + MACD + Hacim Puanlaması (50 Puan Üstü)")
    
    # 1. AYARLAR
    c1, c2, c3 = st.columns(3)
    with c1:
        d1 = datetime(2025, 12, 19)
        analiz_tarihi = st.date_input("📅 Alış Tarihi", value=d1, key="bt_d1")
    with c2:
        d2 = datetime(2026, 1, 4)
        test_tarihi = st.date_input("📅 Satış Tarihi", value=d2, key="bt_d2")
    with c3:
        filtre_secimi = st.selectbox(
            "🔍 Hisse Havuzu",
            ["🌍 Tüm Hisseler", "🏆 Sadece BIST 30", "🔥 En Yüksek Hacimli 100"],
            key="bt_filter"
        )

    if analiz_tarihi >= test_tarihi:
        st.error("⚠️ Satış tarihi alıştan sonra olmalı!")
    else:
        # SİMÜLASYON BAŞLAT BUTONU
        if st.button("Analizi Başlat 🚀", key="btn_start_bt"):
            
            # Havuz Belirle
            if filtre_secimi == "🏆 Sadece BIST 30":
                aktif_liste = BIST_30
                st.info("Analiz **BIST 30** üzerinde yapılıyor.")
            elif filtre_secimi == "🔥 En Yüksek Hacimli 100":
                with st.spinner("Hacimler hesaplanıyor..."):
                    aktif_liste = en_hacimli_100_getir(tum_hisseler, analiz_tarihi)
                st.info("Analiz **En Hacimli 100** üzerinde yapılıyor.")
            else:
                aktif_liste = tum_hisseler
                st.info(f"Analiz **Tüm Hisseler ({len(aktif_liste)})** üzerinde yapılıyor.")

            # Verileri İndir
            t_basla = (analiz_tarihi - timedelta(days=90)).strftime("%Y-%m-%d")
            t_bitis = (test_tarihi + timedelta(days=5)).strftime("%Y-%m-%d")
            semboller = [h + ".IS" for h in aktif_liste]
            semboller.append("XU100.IS") 
            
            with st.spinner("Veriler çekiliyor..."):
                try:
                    data = yf.download(semboller, start=t_basla, end=t_bitis, group_by='ticker', progress=False, threads=True)
                except Exception as e:
                    st.error(f"Veri hatası: {e}")
                    st.stop()

            rapor = []
            bar = st.progress(0)
            
            for i, hisse in enumerate(aktif_liste):
                bar.progress((i+1)/len(aktif_liste))
                try:
                    kod = hisse + ".IS"
                    if kod in data.columns.levels[0]:
                        df = data[kod].dropna()
                        
                        str_analiz = str(analiz_tarihi)
                        str_test = str(test_tarihi)
                        idx_alis = df.index.get_indexer([str_analiz], method='pad')[0]
                        idx_satis = df.index.get_indexer([str_test], method='pad')[0]
                        
                        if idx_alis == -1 or idx_satis == -1: continue
                        
                        gecmis = df.loc[:df.index[idx_alis]]
                        if len(gecmis) < 30: continue
                        
                        closes = gecmis['Close']
                        volumes = gecmis['Volume']
                        
                        # Puanlama
                        rsi_val = rsi_hesapla(closes).iloc[-1]
                        macd, sig = macd_hesapla(closes)
                        son_hacim = volumes.iloc[-1]
                        ort_hacim = volumes.rolling(10).mean().iloc[-1]
                        
                        puan = 0
                        sinyaller = []
                        if rsi_val < 30: puan += 40; sinyaller.append("RSI Dip")
                        elif rsi_val < 40: puan += 20
                        if macd.iloc[-1] > sig.iloc[-1]: puan += 30; sinyaller.append("MACD Al")
                        if son_hacim > ort_hacim * 1.2: puan += 30; sinyaller.append("Hacim+")
                        
                        if puan >= 50:
                            f_alis = df.iloc[idx_alis]['Close']
                            f_satis = df.iloc[idx_satis]['Close']
                            getiri = ((f_satis - f_alis) / f_alis) * 100
                            rapor.append({
                                "Hisse": hisse, "Puan": puan, "Neden": ", ".join(sinyaller),
                                "Getiri": getiri, "Kod": kod
                            })
                except: continue
            
            bar.empty()
            st.divider()
            
            # SONUÇLAR
            df_rapor = pd.DataFrame(rapor)
            if not df_rapor.empty:
                secilenler = df_rapor.sort_values(by="Puan", ascending=False).head(3)
                st.subheader("🤖 Yapay Zeka Seçimi")
                cols = st.columns(3)
                total_kar = 0
                grafik_data = pd.DataFrame()
                t_s = analiz_tarihi.strftime("%Y-%m-%d")
                t_e = test_tarihi.strftime("%Y-%m-%d")

                for index, (idx, row) in enumerate(secilenler.iterrows()):
                    total_kar += row['Getiri']
                    with cols[index % 3]:
                        renk = "green" if row['Getiri'] > 0 else "red"
                        st.markdown(f"#### {row['Hisse']}")
                        st.progress(int(row['Puan']))
                        st.caption(f"Puan: {row['Puan']}")
                        st.metric("Getiri", f"%{row['Getiri']:.2f}")
                    
                    if row['Kod'] in data.columns.levels[0]:
                        seri = data[row['Kod']]['Close'].loc[t_s:t_e]
                        norm = ((seri - seri.iloc[0]) / seri.iloc[0]) * 100
                        grafik_data[row['Hisse']] = norm

                if "XU100.IS" in data.columns.levels[0]:
                    xu = data["XU100.IS"]['Close'].loc[t_s:t_e]
                    grafik_data["BIST 100"] = ((xu - xu.iloc[0]) / xu.iloc[0]) * 100
                
                st.info(f"🏆 Portföy Ortalaması: **%{total_kar/len(secilenler):.2f}**")
                st.line_chart(grafik_data)
                with st.expander("Detaylı Tablo"): st.dataframe(df_rapor.sort_values("Puan", ascending=False))
            else:
                st.warning("Puanı 50 üzeri olan hisse bulunamadı.")