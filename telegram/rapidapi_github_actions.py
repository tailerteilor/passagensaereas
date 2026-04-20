import sqlite3
import pandas as pd
import os
import sys
import time
from datetime import datetime, timedelta
import requests
import json
import glob

print("Iniciando rotina isolada LetsFlyGo para o Telegram...")

# Limpa relatórios antigos da pasta para garantir que o Telegram só receba o novo
if os.path.exists('whatsapp_message.txt'):
    os.remove('whatsapp_message.txt')

# Carrega a configuração do github folder
config_path = '../github/config_telegram.json'
if not os.path.exists(config_path):
    print(f"ERRO: {config_path} não encontrado!")
    sys.exit(1)

with open(config_path, encoding='utf-8') as f:
    search_config = json.load(f)

ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# A API Key DEVE vir dos Secrets do GitHub Actions (variavel de ambiente)
api_key = os.environ.get("RAPIDAPI_KEY")
if not api_key:
    # Fallback apenas para teste local seu antes de subir para o github
    print("Aviso: RAPIDAPI_KEY nao encontrada no ambiente. Usando a padrao.")
    api_key = "cc1a5e6bd4msh55d5e01c0e0b40ap10ebe7jsnd0c1b2553339"

AIRPORTS = {}
try:
    with open('../config/destinos.json', encoding='utf-8') as f:
        dest_data = json.load(f)
        for cat, aps in dest_data.items():
            for ap in aps:
                AIRPORTS[ap['iata']] = ap['cidade']
except:
    pass

def init_db():
    conn = sqlite3.connect('passagens_telegram.db')
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS historico_voos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem TEXT, destino TEXT, mes_voo TEXT, data_voo TEXT,
            preco REAL, cia_aerea TEXT, voo_id TEXT, hr_saida TEXT, hr_chegada TEXT,
            data_pesquisa TEXT
        )
    ''')
    cur.execute("DELETE FROM historico_voos WHERE data_pesquisa < datetime('now', '-10 days')")
    conn.commit()
    conn.close()

def save_whatsapp_text(ts):
    try:
        conn = sqlite3.connect('passagens_telegram.db')
        df = pd.read_sql("SELECT * FROM historico_voos", conn)
        conn.close()
        
        timestamps = sorted(df['data_pesquisa'].unique())
        if not timestamps:
            print("Nenhum dado salvo. Cancelando relatório.")
            return

        current_ts = ts
        if current_ts not in timestamps:
            current_ts = timestamps[-1]
            
        previous_ts = timestamps[-2] if len(timestamps) > 1 else None

        min_data = {}
        for _, row in df.iterrows():
            t = row['data_pesquisa']
            orig = row['origem']
            dest = row['destino']
            mes = row['mes_voo']
            price = float(row['preco'])
            dv = row['data_voo']
            
            route = f"{orig}||{dest}"
            
            if t not in min_data: min_data[t] = {}
            if route not in min_data[t]: min_data[t][route] = {}
            
            if mes not in min_data[t][route]:
                min_data[t][route][mes] = {'price': price, 'dates': set([dv])}
            elif price < min_data[t][route][mes]['price']:
                min_data[t][route][mes] = {'price': price, 'dates': set([dv])}
            elif price == min_data[t][route][mes]['price']:
                min_data[t][route][mes]['dates'].add(dv)
                
        all_routes = set()
        for t, d in min_data.items():
            for r in d.keys():
                all_routes.add(r)
        
        meses = sorted(df['mes_voo'].unique())
        
        matrix_rows = {}
        discounts = []
        
        for route in all_routes:
            route_latest_ts = None
            route_prev_ts = None
            for i in range(len(timestamps)-1, -1, -1):
                t = timestamps[i]
                if route in min_data.get(t, {}):
                    if not route_latest_ts:
                        route_latest_ts = t
                    elif not route_prev_ts:
                        route_prev_ts = t
                        break
            
            matrix_rows[route] = {}
            orig, dest = route.split('||')
            
            for mes in meses:
                cur_cell = min_data.get(route_latest_ts, {}).get(route, {}).get(mes) if route_latest_ts else None
                prev_cell = min_data.get(route_prev_ts, {}).get(route, {}).get(mes) if route_prev_ts else None
                
                if not cur_cell:
                    continue
                
                diff_perc = None
                if prev_cell:
                    diff_perc = ((cur_cell['price'] - prev_cell['price']) / prev_cell['price']) * 100
                    if diff_perc < 0:
                        discounts.append({
                            'orig': orig, 'dest': dest, 'mes': mes,
                            'old': prev_cell['price'], 'new': cur_cell['price'],
                            'perc': diff_perc, 'dates': list(cur_cell['dates'])
                        })
                        
                matrix_rows[route][mes] = {
                    'price': cur_cell['price'], 'diffPerc': diff_perc,
                    'dates': list(cur_cell['dates'])
                }

        def get_city(code):
            return AIRPORTS.get(code, code)

        text = f"✈️ *LetsFlyGo* ✈️\nPesquisa: {current_ts}\n\n"
        
        discounts.sort(key=lambda x: x['perc'])
        top10 = discounts[:10]
        
        if top10:
            text += "🔥 *Top quedas de preço:*\n"
            for i, d in enumerate(top10):
                dates_list = sorted([x.split('/')[0] for x in d['dates']])
                if len(dates_list) <= 3:
                    dates_str = f" [Dia(s) {' e '.join(dates_list)}]" if dates_list else ""
                else:
                    dates_str = f" [Dia(s) {', '.join(dates_list[:3])}...]"
                
                text += f"{i+1}. {d['orig']}→{d['dest']} {d['mes']}: R${d['new']:.2f} ({d['perc']:.1f}%){dates_str}\n"
            text += "\n"
            
        text += "📊 *Preços mínimos mensais:*\n"
        for route in sorted(matrix_rows.keys()):
            orig, dest = route.split('||')
            text += f"*{get_city(orig)} → {get_city(dest)}*\n"
            
            for mes in meses:
                cell = matrix_rows[route].get(mes)
                if not cell: continue
                
                trend = ""
                if cell['diffPerc'] is not None:
                    if cell['diffPerc'] < 0:
                        trend = f" 📉{cell['diffPerc']:.1f}%"
                    elif cell['diffPerc'] > 0:
                        trend = f" 📈+{cell['diffPerc']:.1f}%"
                
                dates_list = sorted([x.split('/')[0] for x in cell['dates']])
                if len(dates_list) <= 3:
                    dates_str = f" [Dia(s) {' e '.join(dates_list)}]" if dates_list else ""
                else:
                    dates_str = f" [Dia(s) {', '.join(dates_list[:3])}...]"
                
                text += f"  {mes}: R${cell['price']:.2f}{trend}{dates_str}\n"
        
        with open('whatsapp_message.txt', 'w', encoding='utf-8') as f:
            f.write(text)
            
        print("[OK] Texto do WhatsApp gerado em whatsapp_message.txt!")
    except Exception as e:
        print(f"[ERRO] Falha ao compilar texto: {e}")

def run_search():
    init_db()
    origens = [o.strip() for o in search_config['origens'].split(',') if o.strip()]
    destinos = [d.strip() for d in search_config['destino'].split(',') if d.strip()]
    
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "kiwi-com-cheap-flights.p.rapidapi.com"
    }
    conn = sqlite3.connect('passagens_telegram.db')
    cur = conn.cursor()
    dt_start = datetime.now().strftime("%Y-%m-%dT00:00:00")
    dt_end = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT23:59:59")

    for dest in destinos:
        for orig in origens:
            print(f"-> Buscando rota {orig} para {dest}...")
            params = {
                "source": orig, "destination": dest,
                "outboundDepartmentDateStart": dt_start,
                "outboundDepartmentDateEnd": dt_end,
                "currency": "BRL", "limit": "25"
            }
            try:
                res = requests.get("https://kiwi-com-cheap-flights.p.rapidapi.com/one-way", headers=headers, params=params)
                if res.status_code == 200:
                    itineraries = res.json().get('itineraries', [])
                    for voo in itineraries:
                        preco = float(voo['price']['amount'])
                        seg = voo['sector']['sectorSegments'][0]['segment']
                        dt = datetime.strptime(seg['source']['localTime'].split('+')[0], "%Y-%m-%dT%H:%M:%S")
                        cur.execute("INSERT INTO historico_voos (origem, destino, mes_voo, data_voo, preco, cia_aerea, voo_id, hr_saida, hr_chegada, data_pesquisa) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (orig, dest, dt.strftime("%Y-%m"), dt.strftime("%d/%m/%Y"), preco, seg['carrier']['name'], f"{seg['carrier']['code']}{seg['code']}", dt.strftime("%H:%M"), "N/A", ts))
                    conn.commit()
            except Exception as e:
                print(f"Erro na conexao com a API: {e}")
            time.sleep(1.5)
    conn.close()
    
    save_whatsapp_text(ts)
if __name__ == "__main__":
    run_search()
    print("Rotina isolada concluida com sucesso!")
