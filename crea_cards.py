import requests
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from io import BytesIO
import os
import json
import random
import textwrap

# --- CONFIGURAZIONE ---
TRAKT_ID = os.getenv('TRAKT_ID')
TMDB_KEY = os.getenv('TMDB_KEY')
USER = os.getenv('TRAKT_USER')
TRAKT_ACCESS_TOKEN = os.getenv('TRAKT_ACCESS_TOKEN')
FOLDER = "./sfondi_projectivity/"
TMDB_BASE_URL = "https://api.themoviedb.org/3/"
TMDB_BEARER_TOKEN = os.getenv('TMDB_BEARER_TOKEN')

if not os.path.exists(FOLDER):
    os.makedirs(FOLDER)

tmdb_headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_BEARER_TOKEN}"  # ← CORRETTO
}

IMDB_LOGO_PATH = "/tmp/imdb_logo.png"

def download_imdb_logo():
    if not os.path.exists(IMDB_LOGO_PATH):
        try:
            url = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/IMDB_Logo_2016.svg/500px-IMDB_Logo_2016.svg.png"
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            with open(IMDB_LOGO_PATH, 'wb') as f:
                f.write(r.content)
            print("Logo IMDb scaricato")
        except Exception as e:
            print(f"Errore logo IMDb: {e}")

def download_fonts():
    os.makedirs("/tmp/fonts", exist_ok=True)
    fonts = {
        "/tmp/fonts/Roboto-Light.ttf": "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Light.ttf",
        "/tmp/fonts/Roboto-Bold.ttf": "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf",
    }
    for path, url in fonts.items():
        if not os.path.exists(path):
            try:
                r = requests.get(url)
                with open(path, 'wb') as f:
                    f.write(r.content)
                print(f"Font scaricato: {path}")
            except Exception as e:
                print(f"Errore font: {e}")

def get_font(size, bold=False):
    path = "/tmp/fonts/Roboto-Bold.ttf" if bold else "/tmp/fonts/Roboto-Light.ttf"
    fallbacks = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    try:
        return ImageFont.truetype(path, size)
    except:
        for f in fallbacks:
            try:
                return ImageFont.truetype(f, size)
            except:
                continue
    return ImageFont.load_default()

def resize_image(image, height):
    ratio = height / image.height
    width = int(image.width * ratio)
    return image.resize((width, height), Image.Resampling.LANCZOS)

def resize_logo(image, width, height):
    aspect_ratio = image.width / image.height
    new_width = width
    new_height = int(new_width / aspect_ratio)
    if new_height > height:
        new_height = height
        new_width = int(new_height * aspect_ratio)
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def get_trakt_items():
    all_items = []
    headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': TRAKT_ID,
        'Authorization': f'Bearer {TRAKT_ACCESS_TOKEN}'
    }
    # Film
    r = requests.get("https://api.trakt.tv/recommendations/movies?limit=50", headers=headers)
    print(f"Trakt film: {r.status_code}")
    if r.status_code == 200:
        for item in r.json():
            tmdb_id = item.get('ids', {}).get('tmdb')
            if tmdb_id:
                all_items.append({'tmdb_id': tmdb_id, 'type': 'movie', 'title': item.get('title', '')})
    # Serie
    r2 = requests.get("https://api.trakt.tv/recommendations/shows?limit=50", headers=headers)
    print(f"Trakt serie: {r2.status_code}")
    if r2.status_code == 200:
        for item in r2.json():
            tmdb_id = item.get('ids', {}).get('tmdb')
            if tmdb_id:
                all_items.append({'tmdb_id': tmdb_id, 'type': 'show', 'title': item.get('title', '')})
    random.shuffle(all_items)
    print(f"Totale: {len(all_items)}, selezionati: {min(20, len(all_items))}")
    return all_items[:20]

def get_tmdb_data(tmdb_id, media_type='movie'):
    if media_type == 'show':
        url = f"{TMDB_BASE_URL}tv/{tmdb_id}?language=it-IT"
        data = requests.get(url, headers=tmdb_headers).json()
        if not data.get('overview'):
            data = requests.get(f"{TMDB_BASE_URL}tv/{tmdb_id}?language=en-US", headers=tmdb_headers).json()
        data['title'] = data.get('name', '')
        data['release_date'] = data.get('first_air_date', '')
        data['runtime'] = data.get('episode_run_time', [0])[0] if data.get('episode_run_time') else 0
        img_url = f"{TMDB_BASE_URL}tv/{tmdb_id}/images?language=it,en,null"
    else:
        url = f"{TMDB_BASE_URL}movie/{tmdb_id}?language=it-IT"
        data = requests.get(url, headers=tmdb_headers).json()
        if not data.get('overview'):
            data = requests.get(f"{TMDB_BASE_URL}movie/{tmdb_id}?language=en-US", headers=tmdb_headers).json()
        img_url = f"{TMDB_BASE_URL}movie/{tmdb_id}/images?language=it,en,null"
    img_data = requests.get(img_url, headers=tmdb_headers).json()
    data['images'] = img_data
    logos = img_data.get('logos', [])
    print(f"  → Loghi: {len([l for l in logos if l.get('file_path','').endswith('.png')])} PNG")
    return data

def get_logo(data):
    logos = data.get('images', {}).get('logos', [])
    png_logos = [l for l in logos if l.get('file_path', '').endswith('.png')]
    if not png_logos:
        png_logos = logos
    for lang in ['it', 'en', '']:
        candidates = [l for l in png_logos if l.get('iso_639_1', '') == lang]
        if candidates:
            return sorted(candidates, key=lambda x: x.get('vote_average', 0), reverse=True)[0]['file_path']
    if png_logos:
        return sorted(png_logos, key=lambda x: x.get('vote_average', 0), reverse=True)[0]['file_path']
    return None

def draw_imdb_badge(bckg, draw, x, y, score):
    font_score = get_font(55, bold=True)
    try:
        imdb_logo = Image.open(IMDB_LOGO_PATH).convert("RGBA")
        imdb_logo.thumbnail((110, 55), Image.Resampling.LANCZOS)
        bckg.paste(imdb_logo, (x, y), imdb_logo)
        draw.text((x + 120, y + 8), f"{score:.1f}", font=font_score, fill="white")
    except:
        font_badge = get_font(40, bold=True)
        draw.rounded_rectangle([x, y, x + 100, y + 50], radius=6, fill=(245, 197, 24))
        draw.text((x + 10, y + 8), "IMDb", font=font_badge, fill=(0, 0, 0))
        draw.text((x + 115, y + 5), f"{score:.1f}", font=font_score, fill="white")

def create_card(data):
    if not data.get('backdrop_path'):
        print(f"  → Nessun backdrop, salto.")
        return
    if data.get('success') == False:
        print(f"  → Film non trovato, salto.")
        return

    # Carica bckg.png e overlay.png dal repository
    bckg = Image.open("bckg.png").convert("RGBA")
    overlay = Image.open("overlay.png").convert("RGBA")

    # Scarica backdrop e ridimensiona a 1500px di altezza
    # 1500 > 1080 = il bordo inferiore va SEMPRE fuori canvas = nessuna riga!
    bg_url = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
    image_response = requests.get(bg_url)
    if image_response.status_code != 200:
        print(f"  → Errore download backdrop")
        return
    show_image = Image.open(BytesIO(image_response.content)).convert("RGBA")
    show_image = resize_image(show_image, 1500)

    # Incolla backdrop a destra
    bckg.paste(show_image, (bckg.width - show_image.width, 0))

    draw = ImageDraw.Draw(bckg)

    # Font
    font_info = get_font(50)
    font_overview = get_font(50)
    font_title = get_font(190)

    # Posizioni (stesse del progetto originale)
    info_position = (210, 650)
    overview_position = (210, 730)
    shadow_offset = 2
    shadow_color = "black"
    metadata_color = (150, 150, 150)

    # Incolla overlay (gradiente precostruito)
    bckg.paste(overlay, (bckg.width - overlay.width, 0), overlay)

    # Logo
    logo_path = get_logo(data)
    if logo_path:
        logo_url = f"https://image.tmdb.org/t/p/original{logo_path}"
        logo_response = requests.get(logo_url)
        try:
            if logo_response.status_code == 200:
                logo_image = Image.open(BytesIO(logo_response.content)).convert("RGBA")
                logo_image = resize_logo(logo_image, 1000, 500)
                logo_position = (210, info_position[1] - logo_image.height - 25)
                bckg.paste(logo_image, logo_position, logo_image)
                print(f"  → Logo PNG usato")
            else:
                draw.text((210, 420), data.get('title', ''), fill="white", font=font_title)
        except UnidentifiedImageError:
            draw.text((210, 420), data.get('title', ''), fill="white", font=font_title)
    else:
        draw.text((210, 420), data.get('title', ''), fill="white", font=font_title)
        print(f"  → Titolo testuale usato")

    # Metadati
    genres = ", ".join([g['name'] for g in data.get('genres', [])[:3]])
    year = data.get('release_date', '')[:4]
    runtime = data.get('runtime', 0)
    vote = data.get('vote_average', 0)
    hours, minutes = divmod(runtime, 60)
    duration = f"{hours}h{minutes}min" if hours > 0 else f"{minutes}min"
    info = f"{genres}  •  {year}  •  {duration}"

    draw.text((info_position[0] + shadow_offset, info_position[1] + shadow_offset), info, font=font_info, fill=shadow_color)
    draw.text(info_position, info, font=font_info, fill=metadata_color)

    # IMDb badge
    if vote and vote > 0:
        draw_imdb_badge(bckg, draw, 210, info_position[1] + 60, vote)

    # Descrizione
    overview = data.get('overview', '')
    if overview:
        wrapped = "\n".join(textwrap.wrap(overview, width=65, max_lines=2, placeholder=" ..."))
        ov_pos = (210, info_position[1] + 130)
        draw.text((ov_pos[0] + shadow_offset, ov_pos[1] + shadow_offset), wrapped, font=font_overview, fill=shadow_color)
        draw.text(ov_pos, wrapped, font=font_overview, fill="white")

    # Salva
    safe_title = "".join(c for c in data.get('title', 'film') if c.isalnum() or c in (' ', '_')).strip()
    filename = f"{data['id']}_{safe_title.replace(' ', '_')[:25]}.jpg"
    save_path = os.path.join(FOLDER, filename)
    bckg.convert("RGB").save(save_path, quality=95)
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
    files = [f for f in os.listdir(FOLDER) if f.endswith('.jpg')]
    with open(os.path.join(FOLDER, "index.txt"), 'w') as f:
        for filename in files:
            f.write(f"{base_url}{filename}\n")
    print(f"Index: {len(files)} immagini")

def generate_json():
    base_url = "https://raw.githubusercontent.com/Fugazzina/LauncherBG/main/sfondi_projectivity/"
    files = [f for f in os.listdir(FOLDER) if f.endswith('.jpg')]
    wallpapers = [{"location": f.replace('.jpg',''), "title": f.replace('.jpg',''), "author": "TMDB", "url_img": f"{base_url}{f}"} for f in files]
    with open(os.path.join(FOLDER, "wallpapers.json"), 'w') as f:
        json.dump(wallpapers, f, indent=2)
    print(f"JSON: {len(wallpapers)} immagini")

# --- ESECUZIONE ---
print("=== Avvio ===")
download_fonts()
download_imdb_logo()
clear_old_images()

items = get_trakt_items()
print(f"Elementi: {len(items)}")

count = 0
for item in items:
    try:
        print(f"\nElaborazione: {item['title']} ({item['type']})")
        details = get_tmdb_data(item['tmdb_id'], item['type'])
        create_card(details)
        count += 1
    except Exception as e:
        print(f"  ✗ Errore: {e}")
        continue

generate_index()
generate_json()
print(f"\n=== Completato: {count} cards ===")
