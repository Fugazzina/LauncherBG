import requests
from PIL import Image, ImageDraw, ImageFont
import os
import json
import random

# --- CONFIGURAZIONE ---
TRAKT_ID = os.getenv('TRAKT_ID')
TMDB_KEY = os.getenv('TMDB_KEY')
USER = os.getenv('TRAKT_USER')
TRAKT_ACCESS_TOKEN = os.getenv('TRAKT_ACCESS_TOKEN')
FOLDER = "./sfondi_projectivity/"

if not os.path.exists(FOLDER):
    os.makedirs(FOLDER)

IMDB_LOGO_PATH = "/tmp/imdb_logo.png"

def download_imdb_logo():
    if not os.path.exists(IMDB_LOGO_PATH):
        try:
            url = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/IMDB_Logo_2016.svg/200px-IMDB_Logo_2016.svg.png"
            r = requests.get(url)
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
    """Recupera film E serie raccomandate da Trakt"""
    all_items = []

    # Film raccomandati
    url_movies = "https://api.trakt.tv/recommendations/movies?limit=50"
    headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': TRAKT_ID,
        'Authorization': f'Bearer {TRAKT_ACCESS_TOKEN}'
    }
    r = requests.get(url_movies, headers=headers)
    print(f"Trakt film status: {r.status_code}")
    if r.status_code == 200:
        for item in r.json():
            tmdb_id = item.get('ids', {}).get('tmdb')
            if tmdb_id:
                all_items.append({'tmdb_id': tmdb_id, 'type': 'movie', 'title': item.get('title', '')})

    # Serie raccomandate
    url_shows = "https://api.trakt.tv/recommendations/shows?limit=50"
    r2 = requests.get(url_shows, headers=headers)
    print(f"Trakt serie status: {r2.status_code}")
    if r2.status_code == 200:
        for item in r2.json():
            tmdb_id = item.get('ids', {}).get('tmdb')
            if tmdb_id:
                all_items.append({'tmdb_id': tmdb_id, 'type': 'show', 'title': item.get('title', '')})

    # Mescola casualmente e prendi 20
    random.shuffle(all_items)
    print(f"Totale disponibili: {len(all_items)}, selezionati: {min(20, len(all_items))}")
    return all_items[:20]

def get_tmdb_data(tmdb_id, media_type='movie'):
    if media_type == 'show':
        url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_KEY}&language=it-IT"
        data = requests.get(url).json()
        if not data.get('overview'):
            url_en = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_KEY}&language=en-US"
            data = requests.get(url_en).json()
        # Normalizza i campi per le serie
        data['title'] = data.get('name', data.get('title', ''))
        data['release_date'] = data.get('first_air_date', '')
        data['runtime'] = data.get('episode_run_time', [0])[0] if data.get('episode_run_time') else 0
        img_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/images?api_key={TMDB_KEY}"
    else:
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
    font_score = get_font_montserrat(30, "bold")
    try:
        imdb_logo = Image.open(IMDB_LOGO_PATH).convert("RGBA")
        imdb_logo.thumbnail((90, 45), Image.Resampling.LANCZOS)
        img.paste(imdb_logo, (x, y), imdb_logo)
        draw.text((x + 100, y + 5), f"{score:.1f}", font=font_score, fill=(255, 255, 255))
    except:
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

    w, h = 1920, 1080

    # 1. Canvas nero
    img = Image.new('RGBA', (w, h), (0, 0, 0, 255))

    # 2. Scarica backdrop
    bg_url = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
    backdrop = Image.open(requests.get(bg_url, stream=True).raw).convert("RGBA")

    # 3. Ridimensiona backdrop — altezza 50% dello schermo, allineato in alto
    target_h = int(h * 0.50)
    target_w = int(target_h * backdrop.width / backdrop.height)

    # Se troppo stretto, allarga fino al bordo destro
    if target_w < int(w * 0.55):
        target_w = int(w * 0.55)
        target_h = int(target_w * backdrop.height / backdrop.width)

    backdrop = backdrop.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # 4. Posizione: angolo in alto a DESTRA, tocca il bordo
    pos_x = w - target_w  # nessun margine, arriva al bordo
    pos_y = 0

    # 5. Sfumatura MORBIDA sul lato sinistro del backdrop
    fade_overlay = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    fade_draw = ImageDraw.Draw(fade_overlay)

    # Sfumatura sinistra: dal nero totale al trasparente su 45% della larghezza
    fade_width = int(target_w * 0.45)
    for gx in range(fade_width):
        progress = gx / fade_width
        # Curva molto morbida (esponente basso = sfumatura graduale)
        alpha = int(255 * (1 - progress) ** 2.0)
        fade_draw.line([(gx, 0), (gx, target_h)], fill=(0, 0, 0, alpha))
    
    # Sfumatura basso: dal trasparente al nero su 10% dell'altezza
    fade_bottom_start = int(target_h * 0.85)
    for gy in range(fade_bottom_start, target_h):
        progress = (gy - fade_bottom_start) / (target_h - fade_bottom_start)
        alpha = int(255 * progress ** 0.9)
    
        backdrop = Image.alpha_composite(backdrop, fade_overlay)

    # 6. Incolla backdrop sul canvas nero
    img.paste(backdrop, (pos_x, pos_y), backdrop)
    draw = ImageDraw.Draw(img)

    # 7. Testo — colonna sinistra
    margin_left = 80
    text_max_width = int(w * 0.42)
    y = int(h * 0.08)

    # 8. Logo PNG film
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

    # 9. Metadati
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

    # 10. Badge IMDb
    vote = data.get('vote_average', 0)
    if vote and vote > 0:
        draw_imdb_badge(draw, img, margin_left, y, vote)
        y += 60

    # 11. Descrizione — testo pulito senza sfondo
    font_desc = get_font_montserrat(26, "regular")
    overview = data.get('overview', '')
    if overview:
        if len(overview) > 300:
            overview = overview[:297] + "..."
        lines = wrap_text(overview, font_desc, text_max_width, draw)
        y += 8
        for line in lines[:4]:
            draw.text((margin_left, y), line, font=font_desc, fill=(190, 190, 190, 255))
            y += 36

    # 12. Salva
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

items = get_trakt_movies()
print(f"Elementi da elaborare: {len(items)}")

count = 0
for item in items:
    try:
        title = item['title']
        tmdb_id = item['tmdb_id']
        media_type = item['type']
        print(f"\nElaborazione: {title} (TMDB: {tmdb_id}, tipo: {media_type})")
        details = get_tmdb_data(tmdb_id, media_type)
        create_card(details)
        count += 1
    except Exception as e:
        print(f"  ✗ Errore su '{title}': {e}")
        continue

generate_index()
generate_json()
print(f"\n=== Completato: {count} cards generate ===")
