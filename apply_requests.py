import re

files = ['dashboard.html', 'index.html']

for filename in files:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Remove double scrollbar (matrix height and overflow)
    content = content.replace('style="height: 80vh;"', '')
    content = content.replace('style="max-height: 50vh;"', '')
    content = content.replace('<div class="overflow-auto flex-1">', '<div class="w-full">')

    # 2. Move Top 10 above filters
    # Find Top 10 section
    top10_match = re.search(r'(<section>\s*<h2 class="text-2xl font-bold.*?</div>\s*<p id="no-history-msg".*?</p>\s*</section>)', content, re.DOTALL)
    if top10_match:
        top10_section = top10_match.group(1)
        # Remove it from its current position
        content = content.replace(top10_section, '')
        # Insert it right after <div id="dashboard-content" class="hidden space-y-4">
        content = content.replace('<div id="dashboard-content" class="hidden space-y-4">', 
                                  '<div id="dashboard-content" class="hidden space-y-4">\n        <!-- Top 10 Discounts -->\n        ' + top10_section)

    # 3. Add Theme Switcher dropdown to Header
    theme_selector = """
            <div class="glass-panel p-2 rounded-xl flex items-center gap-2">
                <span class="text-xs font-semibold text-slate-300">Tema:</span>
                <select id="theme-selector" onchange="changeTheme(this.value)" class="bg-transparent text-emerald-400 font-bold text-xs outline-none cursor-pointer">
                    <option value="dark" class="bg-slate-800 text-white">Futurista (Escuro)</option>
                    <option value="light" class="bg-slate-100 text-slate-900">Clean SaaS (Claro)</option>
                    <option value="dracula" class="bg-slate-800 text-pink-400">Drácula</option>
                </select>
            </div>
    """
    if 'id="theme-selector"' not in content:
        content = content.replace('<div class="glass-panel p-3 rounded-xl flex items-center gap-3">',
                                  theme_selector + '\n            <div class="glass-panel p-3 rounded-xl flex items-center gap-3">')

    # 4. Inject CSS variables for themes
    css_vars = """
        :root {
            --bg-body: #0f172a;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --panel-bg: rgba(30, 41, 59, 0.7);
            --panel-border: rgba(255, 255, 255, 0.1);
            --matrix-header-bg: rgba(30, 41, 59, 0.95);
            --row-hover: rgba(30, 41, 59, 0.5);
            --btn-normal-bg: #334155;
            --btn-normal-border: #475569;
            --btn-normal-text: #e2e8f0;
            --btn-hover-bg: #475569;
            --price-badge-bg: rgba(148, 163, 184, 0.1);
            --price-badge-border: rgba(51, 65, 85, 0.5);
            --price-badge-hover: rgba(51, 65, 85, 0.5);
        }
        :root[data-theme="light"] {
            --bg-body: #f8fafc;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --panel-bg: rgba(255, 255, 255, 0.9);
            --panel-border: rgba(0, 0, 0, 0.1);
            --matrix-header-bg: rgba(241, 245, 249, 0.95);
            --row-hover: rgba(241, 245, 249, 0.8);
            --btn-normal-bg: #ffffff;
            --btn-normal-border: #cbd5e1;
            --btn-normal-text: #475569;
            --btn-hover-bg: #f1f5f9;
            --price-badge-bg: #ffffff;
            --price-badge-border: #cbd5e1;
            --price-badge-hover: #f1f5f9;
        }
        :root[data-theme="dracula"] {
            --bg-body: #282a36;
            --text-main: #f8f8f2;
            --text-muted: #6272a4;
            --panel-bg: rgba(68, 71, 90, 0.8);
            --panel-border: #6272a4;
            --matrix-header-bg: rgba(40, 42, 54, 0.95);
            --row-hover: rgba(68, 71, 90, 0.5);
            --btn-normal-bg: #44475a;
            --btn-normal-border: #6272a4;
            --btn-normal-text: #f8f8f2;
            --btn-hover-bg: #6272a4;
            --price-badge-bg: rgba(98, 114, 164, 0.1);
            --price-badge-border: rgba(98, 114, 164, 0.5);
            --price-badge-hover: rgba(98, 114, 164, 0.3);
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-body) !important;
            color: var(--text-main) !important;
            transition: background-color 0.3s, color 0.3s;
        }
        .glass-panel {
            background: var(--panel-bg) !important;
            border: 1px solid var(--panel-border) !important;
            transition: background-color 0.3s, border-color 0.3s;
        }
        .btn-filter-normal {
            background-color: var(--btn-normal-bg) !important;
            border-color: var(--btn-normal-border) !important;
            color: var(--btn-normal-text) !important;
        }
        .btn-filter-normal:hover { background-color: var(--btn-hover-bg) !important; }
        .matrix-row:hover { background-color: var(--row-hover) !important; }
        .price-cell-gray {
            background-color: var(--price-badge-bg) !important;
            border-color: var(--price-badge-border) !important;
        }
        .price-cell-gray:hover { background-color: var(--price-badge-hover) !important; }
        #matrix-header-wrapper {
            background-color: var(--matrix-header-bg) !important;
        }
        
        [data-theme="light"] .text-slate-200, 
        [data-theme="light"] .text-slate-300, 
        [data-theme="light"] .text-slate-400 { color: var(--text-main) !important; }
        
        [data-theme="dracula"] .text-slate-200, 
        [data-theme="dracula"] .text-slate-300, 
        [data-theme="dracula"] .text-slate-400 { color: var(--text-main) !important; }
        
        [data-theme="light"] .text-emerald-400 { color: #059669 !important; }
        [data-theme="dracula"] .text-emerald-400 { color: #50fa7b !important; }
    """
    
    if '--bg-body' not in content:
        content = content.replace("</style>", css_vars + "\n    </style>")

    # 5. Add changeTheme function
    theme_js = """
    function changeTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('letsflygo-theme', theme);
    }
    // Load saved theme
    const savedTheme = localStorage.getItem('letsflygo-theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        document.addEventListener('DOMContentLoaded', () => {
            const sel = document.getElementById('theme-selector');
            if(sel) sel.value = savedTheme;
        });
    }
    """
    if 'function changeTheme' not in content:
        content = content.replace('<script>', '<script>\n' + theme_js)

    # 6. Update JS Hardcoded Classes
    content = content.replace("bg-slate-700 border-slate-600 text-slate-200 hover:bg-slate-600", "btn-filter-normal")
    content = content.replace("hover:bg-slate-800/50 transition-colors", "matrix-row transition-colors")
    content = content.replace("'price-badge-gray border-slate-700/50 hover:bg-slate-700/50'", "'price-badge-gray price-cell-gray border min-h-[44px]'")
    content = content.replace("bg-slate-800/95 shadow-md backdrop-blur-md", "shadow-md backdrop-blur-md\" id=\"matrix-header-wrapper")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
