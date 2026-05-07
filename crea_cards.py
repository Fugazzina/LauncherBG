import requests
from PIL import Image, ImageDraw, ImageFont
import os
import json

# --- CONFIGURAZIONE ---
TRAKT_ID = os.getenv('TRAKT_ID')
TMDB_KEY = os.getenv('TMDB_KEY')
USER = os.getenv('TRAKT_USER')
TRAKT_ACCESS_TOKEN = os.getenv('TRAKT_ACCESS_TOKEN')
FOLDER = "./sfondi_projectivity/"

if not os.path.exists(FOLDER):
    os.makedirs(FOLDER)

# Logo IMDb ufficiale scaricato una volta sola
IMDB_LOGO_PATH = "/tmp/imdb_logo.png"

def download_imdb_logo():
    """Scarica il logo IMDb ufficiale"""
    if not os.path.exists(IMDB_LOGO_PATH):
        try:
            url = "https://upload.wikimedia.org/wikipedia/commons/6/69/IMDB_Logo_2016.svg"
            # Usiamo un PNG diretto invece di SVG
            url_png = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/IMDB_Logo_2016.svg/200px-IMDB_Logo_2016.svg.png"
            r = requests.get(url_png)
            with open(IMDB_LOGO_PATH, 'wb') as f:
                f.write(r.content)
            print("Logo IMDb scaricato")
        except Exception as e:
            print(f"Errore download logo IMDb: {e}")

def download_fonts():
    os.makedirs("/tmp/fonts", exist_ok=True)
    fonts = {
        "/tmp/fonts/Montserrat-Bold.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf",
        "/tmp/fonts/Montserrat-Regular.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf",
        "/tmp/fonts/Montserrat-Light.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Light.ttf",
    }
    for path, url in fonts.items():
        if not os.path.exists(path):
            try:
                r = requests.get(url)
                with open(path, 'wb') as f:
                    f.write(r.content)
                print(f"Font scaricato: {path}")
            except Exception as e:
                print(f"Errore download font: {e}")

def get_font_montserrat(size, style="regular"):
    paths = {
        "bold": "/tmp/fonts/Montserrat-Bold.ttf",
        "regular": "/tmp/fonts/Montserrat-Regular.ttf",
        "light": "/tmp/fonts/Montserrat-Light.ttf",
    }
    fallbacks = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    try:
        return ImageFont.truetype(paths.get(style, paths["regular"]), size)
    except:
        for f in fallbacks:
            try:
                return ImageFont.truetype(f, size)
            except:
                continue
    return ImageFont.load_default()

def get_trakt_movies():
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
    return [{'movie': item} for item in response.json()]

def get_tmdb_data(tmdb_id):
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_KEY}&language=it-IT"
    data = requests.get(url).json()
    if not data.get('overview'):
        url_en = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_KEY}&language=en-US"
        data = requests.get(url_en).json()
    img_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/images?api_key={TMDB_KEY}"
    img_data = requests.get(img_url).json()
    data['images'] = img_data
    logos = img_data.get('logos', [])
    print(f"  → Loghi trovati: {len(logos)} (PNG: {len([l for l in logos if l.get('file_path','').endswith('.png')])})")
    return data

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

def draw_imdb_badge(draw, img, x, y, score):
    """Usa il logo IMDb ufficiale + voto"""
    font_score = get_font_montserrat(30, "bold")
    
    # Prova a usare il logo IMDb scaricato
    try:
        imdb_logo = Image.open(IMDB_LOGO_PATH).convert("RGBA")
        imdb_logo.thumbnail((90, 45), Image.Resampling.LANCZOS)
        img.paste(imdb_logo, (x, y), imdb_logo)
        # Voto accanto al logo
        draw.text((x + 100, y + 5), f"{score:.1f}", font=font_score, fill=(255, 255, 255))
    except:
        # Fallback badge giallo disegnato
        font_badge = get_font_montserrat(20, "bold")
        badge_w, badge_h = 72, 34
        draw.rounded_rectangle([x, y, x + badge_w, y + badge_h], radius=5, fill=(245, 197, 24))
        draw.text((x + 7, y + 7), "IMDb", font=font_badge, fill=(0, 0, 0))
        draw.text((x + badge_w + 10, y + 4), f"{score:.1f}", font=font_score, fill=(255, 255, 255))

def create_card(data):
    if not data.get('backdrop_path'):
        print(f"  → Nessun backdrop per '{data.get('title', 'N/A')}', salto.")
        return
    if data.get('success') == False:
        print(f"  → Film non trovato su TMDB, salto.")
        return

    # 1. Scarica backdrop
    bg_url = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
    img = Image.open(requests.get(bg_url, stream=True).raw).convert("RGBA")
    img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
    w, h = 1920, 1080

    # 2. Overlay scuro - stile Malena
    # Metà sinistra: gradiente da nero a trasparente
    # Metà inferiore: completamente nera per le app
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    # --- ZONA SINISTRA: nera solida fino al 25% ---
    solid_w = int(w * 0.25)
    draw_ov.rectangle([0, 0, solid_w, h], fill=(0, 0, 0, 255))

    # --- GRADIENTE SINISTRA: dal 25% al 65% ---
    gradient_start = solid_w
    gradient_end = int(w * 0.65)
    for gx in range(gradient_start, gradient_end):
        progress = (gx - gradient_start) / (gradient_end - gradient_start)
        alpha = int(255 * (1 - progress) ** 1.8)
        draw_ov.line([(gx, 0), (gx, h)], fill=(0, 0, 0, alpha))

    # --- ZONA INFERIORE: nera solida dal 50% in giù ---
    # Questo è il punto chiave per far leggere le app
    bottom_solid_start = int(h * 0.50)
    draw_ov.rectangle([0, bottom_solid_start, w, h], fill=(0, 0, 0, 255))

    # --- GRADIENTE TRA IMMAGINE E ZONA NERA: dal 38% al 50% ---
    fade_start = int(h * 0.38)
    fade_end = bottom_solid_start
    for gy in range(fade_start, fade_end):
        progress = (gy - fade_start) / (fade_end - fade_start)
        alpha = int(255 * progress ** 0.7)
        draw_ov.line([(0, gy), (w, gy)], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 3. Layout testo - tutto nella metà superiore sinistra
    margin_left = 80
    text_max_width = int(w * 0.40)
    y = int(h * 0.08)  # Inizia dall'8% dall'alto

    # 4. Logo PNG film
    logos = []
    if data.get('images') and data['images'].get('logos'):
        all_logos = data['images']['logos']
        png_logos = [l for l in all_logos if l.get('file_path', '').endswith('.png')]
        if not png_logos:
            png_logos = all_logos
        for lang in ['it', 'en', '']:
            candidates = [l for l in png_logos if l.get('iso_639_1', '') == lang]
            if candidates:
                logos = sorted(candidates, key=lambda x: x.get('vote_average', 0), reverse=True)
                break
        if not logos:
            logos = sorted(png_logos, key=lambda x: x.get('vote_average', 0), reverse=True)

    logo_placed = False
    if logos:
        logo_url = f"https://image.tmdb.org/t/p/w500{logos[0]['file_path']}"
        try:
            logo = Image.open(requests.get(logo_url, stream=True).raw).convert("RGBA")
            logo.thumbnail((520, 200), Image.Resampling.LANCZOS)
            img.paste(logo, (margin_left, y), logo)
            y += logo.height + 25
            logo_placed = True
            print(f"  → Logo PNG usato")
        except Exception as e:
            print(f"  → Errore logo: {e}")

    if not logo_placed:
        font_title = get_font_montserrat(80, "bold")
        draw.text((margin_left, y), data.get('title', ''), font=font_title, fill=(255, 255, 255, 255))
        y += 90
        print(f"  → Titolo testuale usato")

    # 5. Metadati: Generi • Durata • Anno
    genres = " • ".join([g['name'] for g in data.get('genres', [])[:3]])
    runtime = data.get('runtime', 0)
    hours = runtime // 60
    minutes = runtime % 60
    duration = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
    year = data.get('release_date', '')[:4]
    meta_parts = []
    if genres:
        meta_parts.append(genres)
    if duration and runtime:
        meta_parts.append(duration)
    if year:
        meta_parts.append(year)
    meta_line = "  •  ".join(meta_parts)
    font_meta = get_font_montserrat(28, "light")
    draw.text((margin_left, y), meta_line, font=font_meta, fill=(200, 200, 200, 255))
    y += 48

    # 6. Badge IMDb ufficiale + voto
    vote = data.get('vote_average', 0)
    if vote and vote > 0:
        draw_imdb_badge(draw, img, margin_left, y, vote)
        y += 60

    # 7. Descrizione
    font_desc = get_font_montserrat(26, "regular")
    overview = data.get('overview', '')
    if overview:
        if len(overview) > 300:
            overview = overview[:297] + "..."
        lines = wrap_text(overview, font_desc, text_max_width, draw)
        y += 8
        for line in lines[:4]:
            draw.text((margin_left, y), line, font=font_desc, fill=(190, 190, 190, 220))
            y += 36

    # 8. Salva
    safe_title = "".join(c for c in data.get('title', 'film') if c.isalnum() or c in (' ', '_')).strip()
    safe_title = safe_title.replace(' ', '_')[:25]
    filename = f"{data['id']}_{safe_title}.jpg"
    save_path = os.path.join(FOLDER, filename)
    img.convert("RGB").save(save_path, quality=95)
    print(f"  ✓ Salvata: {filename}")

def clear_old_images():
    deleted = 0
    for f in os.listdir(FOLDER):
        if f.endswith('.jpg'):
            os.remove(os.path.join(FOLDER, f))
            deleted += 1
    print(f"Eliminate {deleted} immagini vecchie")

def generate_index():
    base_url = "https://raw.githubusercontent.com/Fugazzina/LauncherBG/main/sfondi_projectivity/"
    index_path = os.path.join(FOLDER, "index.txt")
    files = [f for f in os.listdir(FOLDER) if f.endswith('.jpg')]
    with open(index_path, 'w') as f:
        for filename in files:
            f.write(f"{base_url}{filename}\n")
    print(f"Index generato con {len(files)} immagini")

def generate_json():
    base_url = "https://raw.githubusercontent.com/Fugazzina/LauncherBG/main/sfondi_projectivity/"
    json_path = os.path.join(FOLDER, "wallpapers.json")
    files = [f for f in os.listdir(FOLDER) if f.endswith('.jpg')]
    wallpapers = []
    for filename in files:
        title = filename.replace('.jpg', '').split('_', 1)[-1].replace('_', ' ')
        wallpapers.append({
            "location": title,
            "title": title,
            "author": "TMDB",
            "url_img": f"{base_url}{filename}"
        })
    with open(json_path, 'w') as f:
        json.dump(wallpapers, f, indent=2)
    print(f"JSON generato con {len(wallpapers)} immagini")

# --- ESECUZIONE ---
print("=== Avvio generazione cards ===")
download_fonts()
download_imdb_logo()
clear_old_images()

movies = get_trakt_movies()
print(f"Film trovati: {len(movies)}")

count = 0
for m in movies[:10]:
    try:
        movie_info = m.get('movie', m)
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

generate_index()
generate_json()
print(f"\n=== Completato: {count} cards generate ===")
