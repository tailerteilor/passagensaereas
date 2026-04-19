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
if not os.path.exists('html_reports'):
    os.makedirs('html_reports')
for f in glob.glob('html_reports/*.html'):
    os.remove(f)

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

def save_standalone_html(ts):
    safe_ts = ts.replace(':', '-').replace(' ', '_')
    html_dir = 'html_reports'
    
    try:
        conn = sqlite3.connect('passagens_telegram.db')
        df = pd.read_sql("SELECT * FROM historico_voos", conn)
        conn.close()
        
        cur_df = df[df['data_pesquisa'] == ts]
        if cur_df.empty: 
            print("Nenhum dado salvo. Cancelando relatório HTML.")
            return

        meses = sorted(cur_df['mes_voo'].unique())
        th_style = 'padding:10px 14px;background:#0f172a;color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.05em'
        ths = f'<th style="{th_style}">Rota</th>' + ''.join(f'<th style="{th_style};text-align:center">{m}</th>' for m in meses)

        rows_html = ''
        for (orig, dest), rdf in sorted(cur_df.groupby(['origem','destino'])):
            city_o = AIRPORTS.get(orig, orig)
            city_d = AIRPORTS.get(dest, dest)
            tds = f'<td style="padding:10px 14px;font-weight:600;white-space:nowrap">{city_o} → {city_d}<br><small style="color:#94a3b8;font-weight:400">{orig}→{dest}</small></td>'
            for mes in meses:
                mdf = rdf[rdf['mes_voo'] == mes]
                if mdf.empty: tds += '<td style="padding:8px;text-align:center;color:#475569">-</td>'; continue
                min_p = mdf['preco'].min()
                dates = sorted(mdf[mdf['preco'] == min_p]['data_voo'].unique())
                
                def make_link(d, o=orig, ds=dest):
                    p = d.split('/')
                    iso = f"{p[2]}-{p[1]}-{p[0]}" if len(p)==3 else d
                    url = f"https://www.google.com/travel/flights?q=Flights%20from%20{o}%20to%20{ds}%20on%20{iso}"
                    return f'<a href="{url}" target="_blank" style="display:inline-block;margin:2px;padding:2px 7px;background:#1e40af33;border:1px solid #3b82f680;border-radius:5px;color:#93c5fd;font-size:11px;text-decoration:none">{d}</a>'
                
                dlinks = ''.join(make_link(d) for d in dates)
                tds += f'<td style="padding:8px;text-align:center"><div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:6px 10px;display:inline-block"><b style="color:#f1f5f9">R${min_p:.2f}</b><div style="margin-top:4px">{dlinks}</div></div></td>'
            rows_html += f'<tr style="border-bottom:1px solid #1e293b">{tds}</tr>'

        html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>LetsFlyGo Relatório (Telegram) - {ts}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#f1f5f9;font-family:system-ui,sans-serif;padding:32px}}h1{{background:linear-gradient(90deg,#60a5fa,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:2rem;margin-bottom:4px}}table{{width:100%;border-collapse:collapse}}a{{text-decoration:none}}</style>
</head><body>
<h1>LetsFlyGo (Relatório Cloud)</h1>
<p style="color:#64748b;margin-bottom:24px">Pesquisa realizada em: {ts}</p>
<div style="overflow-x:auto;border-radius:12px;border:1px solid #1e293b">
<table><thead><tr>{ths}</tr></thead><tbody>{rows_html}</tbody></table>
</div>
<p style="color:#334155;font-size:11px;margin-top:20px">Gerado automaticamente pelo GitHub Actions.</p>
</body></html>"""

        filename = f"{html_dir}/LetsFlyGo_{safe_ts}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"[OK] HTML do Telegram pronto em {filename}!")
    except Exception as e:
        print(f"[ERRO] Falha ao compilar HTML: {e}")

def generate_telegram_message(ts):
    conn = sqlite3.connect('passagens_telegram.db')
    df = pd.read_sql("SELECT * FROM historico_voos", conn)
    conn.close()
    
    timestamps = sorted(df['data_pesquisa'].unique())
    if len(timestamps) < 2:
        return f"✈️ *LetsFlyGo - Nuvem*\nPesquisa: {ts}\n\n*(Nenhum histórico anterior para comparar quedas de preço)*\n\nBaixe o arquivo HTML abaixo para acessar os links direto de compra do Google Flights."
    
    current_ts = ts
    prev_ts = timestamps[-2] # Pega a penúltima pesquisa
    
    def get_mins(t):
        d = df[df['data_pesquisa'] == t]
        if d.empty: return {}
        mins = {}
        for (o, dest, m), group in d.groupby(['origem', 'destino', 'mes_voo']):
            min_p = group['preco'].min()
            dates = group[group['preco'] == min_p]['data_voo'].unique()
            mins[f"{o}||{dest}||{m}"] = {'price': min_p, 'dates': dates}
        return mins
        
    cur_mins = get_mins(current_ts)
    prev_mins = get_mins(prev_ts)
    
    discounts = []
    for k, c_data in cur_mins.items():
        if k in prev_mins:
            p_data = prev_mins[k]
            diff = ((c_data['price'] - p_data['price']) / p_data['price']) * 100
            if diff < 0:
                o, d, m = k.split('||')
                discounts.append({
                    'orig': o, 'dest': d, 'mes': m,
                    'old': p_data['price'], 'new': c_data['price'],
                    'perc': diff, 'dates': c_data['dates']
                })
                
    discounts.sort(key=lambda x: x['perc'])
    top10 = discounts[:10]
    
    msg = f"✈️ *LetsFlyGo - Nuvem*\nPesquisa: {ts}\n\n"
    if not top10:
        msg += "Nenhuma queda de preço registrada desde a última pesquisa.\n\n"
    else:
        msg += "🔥 *Top 10 Quedas de Preço:*\n"
        for i, d in enumerate(top10):
            days = sorted([x.split('/')[0] for x in d['dates']])
            d_str = " e ".join(days) if len(days) <= 3 else ", ".join(days[:3]) + "..."
            c_orig = AIRPORTS.get(d['orig'], d['orig'])
            c_dest = AIRPORTS.get(d['dest'], d['dest'])
            
            msg += f"{i+1}. {c_orig} ➔ {c_dest} ({d['mes']})\n"
            msg += f"   De R${d['old']:.2f} por *R${d['new']:.2f}* ({d['perc']:.1f}%)\n"
            msg += f"   📅 Dia(s): {d_str}\n\n"
            
    msg += "Baixe o arquivo HTML abaixo para acessar os links de compra!"
    return msg

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
    
    save_standalone_html(ts)
    
    # Gera a mensagem do Telegram e salva em um txt para o Action ler
    telegram_msg = generate_telegram_message(ts)
    with open('msg.txt', 'w', encoding='utf-8') as f:
        f.write(telegram_msg)

if __name__ == "__main__":
    run_search()
    print("Rotina isolada concluida com sucesso!")
