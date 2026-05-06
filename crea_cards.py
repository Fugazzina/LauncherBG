import requests
from PIL import Image, ImageDraw, ImageFont
import os

# --- CONFIGURAZIONE ---
TRAKT_ID = os.getenv('TRAKT_ID')
TMDB_KEY = os.getenv('TMDB_KEY')
USER = os.getenv('TRAKT_USER')
# --------------------

FOLDER = "./sfondi_projectivity/" # La cartella per il launcher

if not os.path.exists(FOLDER): os.makedirs(FOLDER)

def get_trakt_movies():
    """Recupera i film raccomandati (o una lista) da Trakt"""
    url = f"https://api.trakt.tv/users/{USER}/recommendations/movies"
    headers = {'trakt-api-version': '2', 'trakt-api-set-id': TRAKT_ID}
    return requests.get(url, headers=headers).json()

def get_tmdb_data(tmdb_id):
    """Ottiene dettagli, loghi e voti da TMDB"""
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_KEY}&append_to_response=images&language=it-IT"
    return requests.get(url).json()

def create_card(data):
    """Crea la grafica stile streaming"""
    # 1. Sfondo
    bg_url = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
    img = Image.open(requests.get(bg_url, stream=True).raw).convert("RGBA")
    w, h = img.size

    # 2. Sfumatura nera a sinistra (Vignette)
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x in range(int(w * 0.7)):
        alpha = int(230 * (1 - x / (w * 0.7)))
        draw.line([(x, 0), (x, h)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)

    # 3. Logo del Film
    draw = ImageDraw.Draw(img)
    logos = [l for l in data['images']['logos'] if l['file_extension'] == '.png']
    y_pos = int(h * 0.3)
    
    if logos:
        l_url = f"https://image.tmdb.org/t/p/w500{logos[0]['file_path']}"
        logo = Image.open(requests.get(l_url, stream=True).raw).convert("RGBA")
        logo.thumbnail((650, 350))
        img.paste(logo, (100, y_pos), logo)
        y_pos += logo.height + 30
    else:
        # Fallback se non c'è il logo
        draw.text((100, y_pos), data['title'], fill="white")
        y_pos += 100

    # 4. Info e Descrizione
    # Nota: Assicurati di avere un file .ttf nella cartella o usa un font di sistema
    try: font = ImageFont.truetype("Arial.ttf", 35)
    except: font = ImageFont.load_default()

    info = f"{data['release_date'][:4]}  |  ⭐ {data['vote_average']:.1f}  |  {data['runtime']}m"
    draw.text((100, y_pos), info, font=font, fill=(200, 200, 200))
    
    desc = data['overview'][:220] + "..."
    draw.text((100, y_pos + 60), desc, font=font, fill=(160, 160, 160))

    # 5. Salvataggio
    img.convert("RGB").save(f"{FOLDER}{data['id']}.jpg", quality=92)

# --- ESECUZIONE ---
movies = get_trakt_movies()
for m in movies[:10]: # Elabora i primi 10
    try:
        details = get_tmdb_data(m['ids']['tmdb'])
        create_card(details)
        print(f"Generata card per: {details['title']}")
    except:
        continue