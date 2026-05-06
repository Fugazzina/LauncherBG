import requests
from PIL import Image, ImageDraw, ImageFont
import os
import textwrap

# --- CONFIGURAZIONE (da GitHub Secrets) ---
TRAKT_ID = os.getenv('TRAKT_ID')
TMDB_KEY = os.getenv('TMDB_KEY')
USER = os.getenv('TRAKT_USER')
TRAKT_ACCESS_TOKEN = os.getenv('TRAKT_ACCESS_TOKEN')
FOLDER = "./sfondi_projectivity/"

if not os.path.exists(FOLDER):
    os.makedirs(FOLDER)

def get_font(size):
    """Carica un font compatibile con Linux e Windows"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (GitHub)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # Linux alternativo
        "C:/Windows/Fonts/arialbd.ttf",  # Windows
        "C:/Windows/Fonts/arial.ttf",    # Windows fallback
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    return ImageFont.load_default()

def get_trakt_movies():
    """Recupera le raccomandazioni con autenticazione OAuth"""
    url = "https://api.trakt.tv/recommendations/movies?limit=15"
    headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': TRAKT_ID,
        'Authorization': f'Bearer {TRAKT_ACCESS_TOKEN}'
    }
    response = requests.get(url, headers=headers)
    print(f"Trakt status: {response.status_code}")
    if response.status_code != 200:
        print(f"Errore Trakt: {response.text}")
        return []
    
    # Raccomandazioni: ogni item è direttamente il film
    return [{'movie': item} for item in response.json()]

def get_tmdb_data(tmdb_id):
    """Ottiene dettagli, loghi e voti da TMDB"""
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_KEY}&append_to_response=images&language=it-IT"
    response = requests.get(url)
    data = response.json()
    # Se la descrizione è vuota in italiano, prende quella in inglese
    if not data.get('overview'):
        url_en = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_KEY}&append_to_response=images&language=en-US"
        data = requests.get(url_en).json()
    return data

def wrap_text(text, font, max_width, draw):
    """Divide il testo in righe che non escono dai bordi"""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

def create_card(data):
    """Crea la grafica stile streaming"""

    # Controllo dati essenziali
    if not data.get('backdrop_path'):
        print(f"  → Nessun backdrop per '{data.get('title', 'N/A')}', salto.")
        return
    if data.get('success') == False:
        print(f"  → Film non trovato su TMDB, salto.")
        return

    # 1. Scarica lo sfondo
    bg_url = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
    response = requests.get(bg_url, stream=True)
    img = Image.open(response.raw).convert("RGBA")
    w, h = img.size

    # 2. Sfumatura nera a sinistra
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    gradient_width = int(w * 0.65)
    for x in range(gradient_width):
        alpha = int(220 * (1 - x / gradient_width))
        draw_overlay.line([(x, 0), (x, h)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 3. Logo del film (PNG trasparente da TMDB)
    logos = []
    if data.get('images') and data['images'].get('logos'):
        logos = [l for l in data['images']['logos'] if l.get('file_extension') == '.png' and l.get('iso_639_1') in ['it', 'en', None]]

    y_pos = int(h * 0.28)

    if logos:
        logo_url = f"https://image.tmdb.org/t/p/w500{logos[0]['file_path']}"
        try:
            logo = Image.open(requests.get(logo_url, stream=True).raw).convert("RGBA")
            logo.thumbnail((600, 280), Image.Resampling.LANCZOS)
            img.paste(logo, (100, y_pos), logo)
            y_pos += logo.height + 25
        except:
            # Fallback testo se il logo non si carica
            font_title = get_font(72)
            draw.text((100, y_pos), data.get('title', ''), font=font_title, fill="white")
            y_pos += 90
    else:
        font_title = get_font(72)
        draw.text((100, y_pos), data.get('title', ''), font=font_title, fill="white")
        y_pos += 90

    # 4. Anno | Voto | Durata
    font_info = get_font(32)
    anno = data.get('release_date', '')[:4] or 'N/A'
    voto = data.get('vote_average', 0)
    durata = data.get('runtime', 0)
    info = f"{anno}   ·   ⭐ {voto:.1f}   ·   {durata} min"
    draw.text((100, y_pos), info, font=font_info, fill=(210, 210, 210, 255))
    y_pos += 55

    # 5. Descrizione con a capo automatico
    font_desc = get_font(27)
    overview = data.get('overview', 'Nessuna descrizione disponibile.')
    if len(overview) > 280:
        overview = overview[:277] + "..."

    max_text_width = int(w * 0.45)
    lines = wrap_text(overview, font_desc, max_text_width, draw)

    for line in lines[:4]:  # Massimo 4 righe
        draw.text((100, y_pos), line, font=font_desc, fill=(170, 170, 170, 255))
        y_pos += 36

    # 6. Salvataggio
    filename = f"{data['id']}_{data.get('title','film').replace(' ','_')[:30]}.jpg"
    # Rimuove caratteri non validi nel nome file
    filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.')).rstrip()
    save_path = os.path.join(FOLDER, filename)
    img.convert("RGB").save(save_path, quality=92)
    print(f"  ✓ Card salvata: {filename}")

# --- ESECUZIONE ---
print("=== Avvio generazione cards ===")
print(f"Utente Trakt: {USER}")

movies = get_trakt_movies()
print(f"Film trovati su Trakt: {len(movies)}")

count = 0
for m in movies[:10]:
    try:
        # La struttura corretta per le raccomandazioni Trakt è m['movie']
        movie_info = m.get('movie', m)  # Funziona sia per raccomandazioni che per watchlist
        title = movie_info.get('title', 'Sconosciuto')
        tmdb_id = movie_info.get('ids', {}).get('tmdb')

        if not tmdb_id:
            print(f"  → Nessun TMDB ID per '{title}', salto.")
            continue

        print(f"\nElaborazione: {title} (TMDB: {tmdb_id})")
        details = get_tmdb_data(tmdb_id)
        create_card(details)
        count += 1

    except Exception as e:
        print(f"  ✗ Errore su '{title}': {e}")
        continue

print(f"\n=== Completato: {count} cards generate ===")
