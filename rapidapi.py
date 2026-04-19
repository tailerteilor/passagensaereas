import sqlite3
import pandas as pd
import os
import sys
import time
import argparse
from datetime import datetime, timedelta
import webbrowser
from threading import Timer, Thread
from flask import Flask, render_template_string, request, Response, send_file, jsonify
import requests
import json

app = Flask(__name__)
search_config = {}

AIRPORTS = {}
DESTINOS_DATA = {}
try:
    with open('config/destinos.json', encoding='utf-8') as f:
        DESTINOS_DATA = json.load(f)
        for cat, aps in DESTINOS_DATA.items():
            for ap in aps:
                AIRPORTS[ap['iata']] = ap['cidade']
except Exception as e:
    print(f"Aviso: Não foi possível carregar config/destinos.json - {e}")


# ==========================================
# TEMPLATES HTML
# ==========================================

HTML_FORM = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>LetsFlyGo - Setup Mensal</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; font-family: 'Segoe UI', Tahoma, sans-serif; }
        .card { border: none; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); margin-top: 5vh; }
        .btn-preset { margin: 3px; font-weight: 600; font-size: 0.85rem; border-radius: 20px;}
    </style>
</head>
<body>
<div class="container">
    <div class="row justify-content-center">
        <div class="col-lg-8">
            <div class="card p-5">
                <h2 class="mb-4 text-center" style="color: #2c3e50; font-weight: 800;">🛫 Setup de Busca (Menor Preço por Mês)</h2>
                <form action="/start" method="POST">
                    <div class="row mb-4">
                        <div class="col-md-5 mb-3">
                            <label class="form-label fw-bold text-primary">📍 Origens (IATA)</label>
                            <input type="text" class="form-control form-control-lg text-uppercase mb-2" id="inputOrigens" name="origens" placeholder="Ex: POA, GRU, GIG" required>
                            <div class="d-flex flex-wrap gap-1">
                                {{ BOTÕES_ORIGEM }}
                            </div>
                        </div>
                        <div class="col-md-2 d-flex align-items-center justify-content-center mb-3">
                            <button type="button" class="btn btn-outline-dark fw-bold rounded-circle" style="width:42px;height:42px;padding:0;margin-top:28px" onclick="swapDestOrig()" title="Inverter Destino e Origem">⇔</button>
                        </div>
                        <div class="col-md-5">
                            <label class="form-label fw-bold text-danger">📍 Destinos (IATA)</label>
                            <input type="text" class="form-control form-control-lg text-uppercase mb-2" id="inputDestino" name="destino" placeholder="Ex: EZE, SCL, MVD" required>
                            <div class="d-flex flex-wrap gap-1">
                                {{ BOTÕES_DESTINO }}
                            </div>
                        </div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-12">
                            <div id="estimativaBox" class="alert alert-info w-100 mb-0 d-none" style="font-size:0.92rem;"></div>
                        </div>
                    </div>
                    <div class="d-flex gap-2">
                        <button type="submit" class="btn btn-primary btn-lg flex-grow-1 fw-bold shadow-sm">🚀 Iniciar Varredura</button>
                        <button type="button" class="btn btn-outline-secondary btn-lg fw-bold" onclick="saveConfig()" title="Salvar configuração atual">💾 Salvar Config</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
<script>
function setOrigens(val) { document.getElementById('inputOrigens').value = val; updateEstimate(); }
function setDestinos(val) { document.getElementById('inputDestino').value = val; updateEstimate(); }
function swapDestOrig() {
    let orig = document.getElementById('inputOrigens').value;
    let dest = document.getElementById('inputDestino').value;
    document.getElementById('inputOrigens').value = dest;
    document.getElementById('inputDestino').value = orig;
    updateEstimate();
}
function saveConfig() {
    const cfg = {
        origens: document.getElementById('inputOrigens').value,
        destino: document.getElementById('inputDestino').value
    };
    fetch('/save-config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(cfg)})
        .then(r => r.json()).then(() => { alert('✅ Configuração salva em config/config.json!'); });
}
async function loadConfig() {
    const r = await fetch('/load-config');
    const cfg = await r.json();
    if (cfg.origens) document.getElementById('inputOrigens').value = cfg.origens;
    if (cfg.destino) document.getElementById('inputDestino').value = cfg.destino;
    updateEstimate();
}
function updateEstimate() {
    const origens = document.getElementById('inputOrigens').value.split(',').filter(s=>s.trim()).length;
    const destinos = document.getElementById('inputDestino').value.split(',').filter(s=>s.trim()).length;
    const el = document.getElementById('estimativaBox');
    if (!origens || !destinos) { el.classList.add('d-none'); return; }
    const total = origens * destinos;
    const secs = total * 1.5;
    const mins = Math.floor(secs / 60);
    const secsR = Math.round(secs % 60);
    el.classList.remove('d-none');
    el.innerHTML = `
        <strong>📊 Estimativa:</strong>
        ${origens} origens × ${destinos} destinos =
        <strong>${total} requisições</strong>
        <span class="text-muted">(≈ ${mins}m ${secsR}s)</span>`;
}
['inputOrigens','inputDestino'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateEstimate);
});
window.addEventListener('DOMContentLoaded', () => { loadConfig(); });
</script>
</body>
</html>
"""

HTML_PROGRESS = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Buscando Voos...</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background:#0f172a; color:#f1f5f9; font-family:'Segoe UI',sans-serif; }
        #logTerminal { height:380px; overflow-y:scroll; color:#4ade80; font-family:monospace; font-size:13px; background:#0a0f1e; border-radius:8px; padding:12px; }
        .progress { height:28px; border-radius:12px; background:#1e293b; }
        .progress-bar { background: linear-gradient(90deg,#3b82f6,#34d399); transition: width 0.4s ease; font-size:13px; font-weight:600; }
    </style>
</head>
<body class="p-4">
<div class="container" style="max-width:860px">
    <h3 class="text-center mb-3" style="background:linear-gradient(90deg,#60a5fa,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:800">✈️ LetsFlyGo — Buscando Voos...</h3>

    <!-- Progress bar -->
    <div class="mb-3">
        <div class="d-flex justify-content-between mb-1">
            <span id="progLabel" class="text-slate-400" style="color:#94a3b8;font-size:13px">Iniciando...</span>
            <span id="progPct" style="color:#94a3b8;font-size:13px">0%</span>
        </div>
        <div class="progress">
            <div id="progressBar" class="progress-bar" role="progressbar" style="width:0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0 / 0</div>
        </div>
        <div class="d-flex justify-content-between mt-1">
            <span id="etaLabel" style="color:#64748b;font-size:11px"></span>
            <span id="reqLabel"  style="color:#64748b;font-size:11px"></span>
        </div>
    </div>

    <!-- Terminal log -->
    <div class="mb-3">
        <pre id="logTerminal"></pre>
    </div>

    <div class="text-center" id="btnDashboard" style="display:none">
        <a href="/dashboard" class="btn btn-success btn-lg fw-bold px-5">Ir para o Relatório 📊</a>
    </div>
</div>
<script>
    const term = document.getElementById('logTerminal');
    const bar  = document.getElementById('progressBar');
    const pct  = document.getElementById('progPct');
    const lbl  = document.getElementById('progLabel');
    const eta  = document.getElementById('etaLabel');
    const req  = document.getElementById('reqLabel');

    let totalReqs = 0, doneReqs = 0, startTime = null;

    const source = new EventSource("/stream");
    source.onmessage = function(event) {
        const msg = event.data;

        // Parse special control messages
        const mTotal    = msg.match(/\[TOTAL:(\d+)\]/);
        const mProgress = msg.match(/\[PROGRESSO:(\d+)\/(\d+)\]/);

        if (mTotal) {
            totalReqs = parseInt(mTotal[1]);
            startTime = Date.now();
            bar.textContent = `0 / ${totalReqs}`;
            req.textContent = `Total: ${totalReqs} requisições`;
            return;
        }
        if (mProgress) {
            doneReqs = parseInt(mProgress[1]);
            const pctVal = totalReqs ? Math.round(doneReqs / totalReqs * 100) : 0;
            bar.style.width = pctVal + '%';
            bar.textContent  = `${doneReqs} / ${totalReqs}`;
            pct.textContent  = pctVal + '%';
            lbl.textContent  = `Rota ${doneReqs} de ${totalReqs}`;
            if (startTime && doneReqs > 0) {
                const elapsed = (Date.now() - startTime) / 1000;
                const remaining = Math.round(elapsed / doneReqs * (totalReqs - doneReqs));
                const m = Math.floor(remaining / 60), s = remaining % 60;
                eta.textContent = `ETA: ~${m}m ${s}s`;
            }
            return;
        }

        // Regular log line
        if (!msg.startsWith('[TOTAL') && !msg.startsWith('[PROGRESSO')) {
            term.textContent += msg + "\\n";
            term.scrollTop = term.scrollHeight;
        }

        if (msg.includes("[CONCLUIDO]")) {
            source.close();
            bar.style.width = '100%';
            bar.textContent = `${totalReqs} / ${totalReqs}`;
            pct.textContent = '100%';
            eta.textContent = 'Concluído!';
            document.getElementById('btnDashboard').style.display = 'block';
        }
    };
</script>
</body>
</html>
"""

# ==========================================
# BANCO DE DADOS E AUXILIARES
# ==========================================
def init_db():
    conn = sqlite3.connect('passagens.db')
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS historico_voos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem TEXT, destino TEXT, mes_voo TEXT, data_voo TEXT,
            preco REAL, cia_aerea TEXT, voo_id TEXT, hr_saida TEXT, hr_chegada TEXT,
            data_pesquisa TEXT
        )
    ''')
    cur.execute("PRAGMA table_info(historico_voos)")
    columns = [col[1] for col in cur.fetchall()]
    if "data_pesquisa" not in columns:
        cur.execute("ALTER TABLE historico_voos ADD COLUMN data_pesquisa TEXT DEFAULT '2020-01-01 00:00:00'")
    # Apaga registros com mais de 10 dias
    cur.execute("DELETE FROM historico_voos WHERE data_pesquisa < datetime('now', '-10 days')")
    conn.commit()
    conn.close()

def generate_whatsapp_text(ts, prev_ts=None):
    """Gera texto WhatsApp a partir do banco de dados."""
    try:
        conn = sqlite3.connect('passagens.db')
        df = pd.read_sql("SELECT * FROM historico_voos", conn)
        conn.close()
        if df.empty: return ""

        cur = df[df['data_pesquisa'] == ts]
        text = f"✈️ *LetsFlyGo* ✈️\nPesquisa: {ts}\n\n"

        routes = cur.groupby(['origem','destino'])
        text += "📊 *Preços mínimos mensais:*\n"
        for (orig, dest), rdf in sorted(routes):
            city_o = AIRPORTS.get(orig, orig)
            city_d = AIRPORTS.get(dest, dest)
            text += f"*{city_o} \u2192 {city_d}*\n"
            for mes, mdf in sorted(rdf.groupby('mes_voo')):
                min_p = mdf['preco'].min()
                dates = sorted(mdf[mdf['preco'] == min_p]['data_voo'].unique())
                # extract day only from DD/MM/YYYY
                days = [d.split('/')[0] for d in dates if '/' in d]
                if len(days) <= 3:
                    days_str = ' e '.join(days)
                else:
                    days_str = ', '.join(days[:3]) + '...'
                text += f"  {mes}: R${min_p:.2f} [Dia(s) {days_str}]\n"
            text += "\n"
        return text
    except Exception as e:
        return f"[Erro ao gerar relatório: {e}]"

def save_reports(ts):
    """Salva texto WhatsApp e HTML após a pesquisa."""
    safe_ts = ts.replace(':', '-').replace(' ', '_')

    # Save WhatsApp text
    wpp_dir = 'whatsapp'
    if not os.path.exists(wpp_dir): os.makedirs(wpp_dir)
    wpp_text = generate_whatsapp_text(ts)
    with open(f"{wpp_dir}/{safe_ts}.txt", 'w', encoding='utf-8') as f:
        f.write(wpp_text)

    # Save standalone HTML
    html_dir = 'htmls'
    if not os.path.exists(html_dir): os.makedirs(html_dir)
    try:
        conn = sqlite3.connect('passagens.db')
        df = pd.read_sql("SELECT * FROM historico_voos", conn)
        conn.close()
        cur_df = df[df['data_pesquisa'] == ts]
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
<title>LetsFlyGo - {ts}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#f1f5f9;font-family:system-ui,sans-serif;padding:32px}}h1{{background:linear-gradient(90deg,#60a5fa,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:2rem;margin-bottom:4px}}table{{width:100%;border-collapse:collapse}}a{{text-decoration:none}}</style>
</head><body>
<h1>LetsFlyGo Analytics</h1>
<p style="color:#64748b;margin-bottom:24px">Pesquisa: {ts}</p>
<div style="overflow-x:auto;border-radius:12px;border:1px solid #1e293b">
<table><thead><tr>{ths}</tr></thead><tbody>{rows_html}</tbody></table>
</div>
<p style="color:#334155;font-size:11px;margin-top:20px">Gerado por LetsFlyGo em {ts}</p>
</body></html>"""
        with open(f"{html_dir}/{safe_ts}.html", 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception as e:
        print(f"[save_reports] Erro ao salvar HTML: {e}")


# ==========================================
# ROTAS
# ==========================================
@app.route('/')
def index():
    botoes_orig = ""
    botoes_dest = ""
    for category, aps in DESTINOS_DATA.items():
        iatas = ", ".join([ap['iata'] for ap in aps])
        cat_name = category.replace('_', ' ').title()
        # Highlight logic: make the first or largest category primary/danger-bold, others secondary
        btn_class_orig = "btn-primary fw-bold" if category == "tudo" or category == "top_50_brasil" else "btn-outline-secondary"
        btn_class_dest = "btn-danger fw-bold" if category == "tudo" or category == "top_50_brasil" else "btn-outline-danger"
        botoes_orig += f'<button type="button" class="btn btn-sm {btn_class_orig} btn-preset" onclick="setOrigens(\'{iatas}\')">{cat_name}</button>\n'
        botoes_dest += f'<button type="button" class="btn btn-sm {btn_class_dest} btn-preset" onclick="setDestinos(\'{iatas}\')">{cat_name}</button>\n'
    
    html = HTML_FORM.replace('{{ BOTÕES_ORIGEM }}', botoes_orig).replace('{{ BOTÕES_DESTINO }}', botoes_dest)
    return render_template_string(html)

@app.route('/start', methods=['POST'])
def start():
    global search_config
    search_config = {
        'origens': request.form.get('origens', '').upper(),
        'destino': request.form.get('destino', '').upper(),
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    init_db()
    return render_template_string(HTML_PROGRESS)

@app.route('/stream')
def stream():
    def gerador():
        log = lambda m: f"data: {m}\n\n"
        if not search_config: yield log("[ERRO] Configurações perdidas."); return

        origens  = [o.strip() for o in search_config['origens'].split(',') if o.strip()]
        destinos = [d.strip() for d in search_config['destino'].split(',') if d.strip()]

        total_reqs = len(origens) * len(destinos)
        yield log(f"[TOTAL:{total_reqs}]")
        yield log(f"Iniciando: {len(origens)} origens x {len(destinos)} destinos = {total_reqs} requisicoes")

        done_reqs = 0
        headers = {
            "x-rapidapi-key": "cc1a5e6bd4msh55d5e01c0e0b40ap10ebe7jsnd0c1b2553339",
            "x-rapidapi-host": "kiwi-com-cheap-flights.p.rapidapi.com"
        }

        conn = sqlite3.connect('passagens.db')
        cur  = conn.cursor()

        dt_start = datetime.now().strftime("%Y-%m-%dT00:00:00")
        dt_end = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT23:59:59")

        for dest in destinos:
            for orig in origens:
                yield log(f"Buscando {orig} ➡ {dest} ...")
                params = {
                    "source": orig, "destination": dest,
                    "outboundDepartmentDateStart": dt_start,
                    "outboundDepartmentDateEnd": dt_end,
                    "currency": "BRL", "limit": "25"
                }
                try:
                    res = requests.get("https://kiwi-com-cheap-flights.p.rapidapi.com/one-way", headers=headers, params=params)
                    if res.status_code == 200:
                        res_json = res.json()
                        itineraries = res_json.get('itineraries', [])
                        if not os.path.exists('json'): os.makedirs('json')
                        safe_ts = search_config['timestamp'].replace(':', '-')
                        with open(f"json/raw_{orig}_{dest}_{safe_ts}.json", "w", encoding='utf-8') as f:
                            json.dump(res_json, f, indent=4)
                        for voo in itineraries:
                            preco = float(voo['price']['amount'])
                            seg   = voo['sector']['sectorSegments'][0]['segment']
                            dt    = datetime.strptime(seg['source']['localTime'].split('+')[0], "%Y-%m-%dT%H:%M:%S")
                            cur.execute("INSERT INTO historico_voos (origem, destino, mes_voo, data_voo, preco, cia_aerea, voo_id, hr_saida, hr_chegada, data_pesquisa) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (orig, dest, dt.strftime("%Y-%m"), dt.strftime("%d/%m/%Y"), preco,
                                 seg['carrier']['name'], f"{seg['carrier']['code']}{seg['code']}",
                                 dt.strftime("%H:%M"), "N/A", search_config['timestamp']))
                        conn.commit()
                        yield log(f"  ✓ {len(itineraries)} voos encontrados")
                except Exception as e:
                    yield log(f"  ⚠️ Erro: {str(e)}")
                done_reqs += 1
                yield log(f"[PROGRESSO:{done_reqs}/{total_reqs}]")
                time.sleep(1.5)
        conn.close()
        save_reports(search_config.get('timestamp', ''))
        yield log("[CONCLUIDO]")
    return Response(gerador(), mimetype='text/event-stream')

@app.route('/dashboard')
def dashboard():
    with open('dashboard.html', encoding='utf-8') as f:
        html = f.read()
    return render_template_string(html, AIRPORTS_JSON=json.dumps(AIRPORTS))

@app.route('/passagens.db')
def serve_db():
    return send_file('passagens.db')

@app.route('/save-config', methods=['POST'])
def save_config_route():
    data = request.get_json()
    if not os.path.exists('config'): os.makedirs('config')
    with open('config/config.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True})

@app.route('/load-config')
def load_config_route():
    if os.path.exists('config/config.json'):
        with open('config/config.json', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({})

def run_auto_search():
    """Executa busca automaticamente sem browser (modo CLI)."""
    origens = [o.strip() for o in search_config['origens'].split(',') if o.strip()]
    destinos = [d.strip() for d in search_config['destino'].split(',') if d.strip()]
    headers = {
        "x-rapidapi-key": "cc1a5e6bd4msh55d5e01c0e0b40ap10ebe7jsnd0c1b2553339",
        "x-rapidapi-host": "kiwi-com-cheap-flights.p.rapidapi.com"
    }
    conn = sqlite3.connect('passagens.db')
    cur = conn.cursor()
    dt_start = datetime.now().strftime("%Y-%m-%dT00:00:00")
    dt_end = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT23:59:59")

    for dest in destinos:
        for orig in origens:
            print(f"[AUTO] Buscando {orig} -> {dest}...")
            params = {
                "source": orig, "destination": dest,
                "outboundDepartmentDateStart": dt_start,
                "outboundDepartmentDateEnd": dt_end,
                "currency": "BRL", "limit": "25"
            }
            try:
                res = requests.get("https://kiwi-com-cheap-flights.p.rapidapi.com/one-way", headers=headers, params=params)
                if res.status_code == 200:
                    res_json = res.json()
                    itineraries = res_json.get('itineraries', [])
                    if not os.path.exists('json'): os.makedirs('json')
                    safe_ts = search_config['timestamp'].replace(':', '-')
                    with open(f"json/raw_{orig}_{dest}_{safe_ts}.json", 'w', encoding='utf-8') as jf:
                        json.dump(res_json, jf, indent=4)
                    for voo in itineraries:
                        preco = float(voo['price']['amount'])
                        seg = voo['sector']['sectorSegments'][0]['segment']
                        dt = datetime.strptime(seg['source']['localTime'].split('+')[0], "%Y-%m-%dT%H:%M:%S")
                        cur.execute("INSERT INTO historico_voos (origem, destino, mes_voo, data_voo, preco, cia_aerea, voo_id, hr_saida, hr_chegada, data_pesquisa) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (orig, dest, dt.strftime("%Y-%m"), dt.strftime("%d/%m/%Y"), preco, seg['carrier']['name'], f"{seg['carrier']['code']}{seg['code']}", dt.strftime("%H:%M"), "N/A", search_config['timestamp']))
                    conn.commit()
                    print(f"[AUTO] {len(itineraries)} voos salvos.")
            except Exception as e:
                print(f"[AUTO] Erro: {e}")
            time.sleep(2)
    conn.close()
    save_reports(search_config['timestamp'])
    print("[AUTO] Concluido. Relatorios salvos.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LetsFlyGo Flight Search')
    parser.add_argument('-noview', action='store_true', help='Nao abrir browser')
    parser.add_argument('config_file', nargs='?', default=None, help='Arquivo config JSON para auto-busca')
    args = parser.parse_args()

    if args.config_file and os.path.exists(args.config_file):
        with open(args.config_file, encoding='utf-8') as cf:
            cfg = json.load(cf)
        search_config.update(cfg)
        search_config['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        init_db()
        Thread(target=run_auto_search, daemon=True).start()

    if not args.noview:
        Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000/')).start()

    app.run(debug=False, use_reloader=False, port=5000)