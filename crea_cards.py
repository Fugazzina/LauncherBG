def create_card(data):
    if not data.get('backdrop_path'):
        print(f"  → Nessun backdrop per '{data.get('title', 'N/A')}', salto.")
        return
    if data.get('success') == False:
        print(f"  → Film non trovato su TMDB, salto.")
        return

    # 1. Canvas nero 1920x1080
    w, h = 1920, 1080
    img = Image.new('RGBA', (w, h), (0, 0, 0, 255))

    # 2. Scarica il backdrop e ridimensionalo
    bg_url = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
    backdrop = Image.open(requests.get(bg_url, stream=True).raw).convert("RGBA")
    
    # Ridimensiona il backdrop a circa il 55% della larghezza
    # mantenendo le proporzioni, allineato in alto a destra
    backdrop_w = int(w * 0.60)
    backdrop_h = int(backdrop_w * backdrop.height / backdrop.width)
    if backdrop_h > int(h * 0.75):
        backdrop_h = int(h * 0.75)
        backdrop_w = int(backdrop_h * backdrop.width / backdrop.height)
    
    backdrop = backdrop.resize((backdrop_w, backdrop_h), Image.Resampling.LANCZOS)
    
    # Posizione: allineato in alto a destra con margine
    pos_x = w - backdrop_w - 20
    pos_y = 0
    
    # 3. Applica sfumatura ai bordi del backdrop
    # Sfumatura sinistra del backdrop
    fade_overlay = Image.new('RGBA', (backdrop_w, backdrop_h), (0, 0, 0, 0))
    fade_draw = ImageDraw.Draw(fade_overlay)
    
    fade_width = int(backdrop_w * 0.35)
    for gx in range(fade_width):
        progress = gx / fade_width
        alpha = int(255 * (1 - progress) ** 1.5)
        fade_draw.line([(gx, 0), (gx, backdrop_h)], fill=(0, 0, 0, alpha))
    
    # Sfumatura basso del backdrop
    fade_bottom = int(backdrop_h * 0.35)
    for gy in range(backdrop_h - fade_bottom, backdrop_h):
        progress = (gy - (backdrop_h - fade_bottom)) / fade_bottom
        alpha = int(255 * progress ** 0.8)
        fade_draw.line([(0, gy), (backdrop_w, gy)], fill=(0, 0, 0, alpha))
    
    backdrop = Image.alpha_composite(backdrop, fade_overlay)
    
    # Incolla il backdrop sul canvas nero
    img.paste(backdrop, (pos_x, pos_y), backdrop)
    draw = ImageDraw.Draw(img)

    # 4. Layout testo - colonna sinistra
    margin_left = 80
    text_max_width = int(w * 0.42)
    y = int(h * 0.08)

    # 5. Logo PNG film
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

    # 6. Metadati
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

    # 7. Badge IMDb
    vote = data.get('vote_average', 0)
    if vote and vote > 0:
        draw_imdb_badge(draw, img, margin_left, y, vote)
        y += 60

    # 8. Descrizione
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

    # 9. Salva
    safe_title = "".join(c for c in data.get('title', 'film') if c.isalnum() or c in (' ', '_')).strip()
    safe_title = safe_title.replace(' ', '_')[:25]
    filename = f"{data['id']}_{safe_title}.jpg"
    save_path = os.path.join(FOLDER, filename)
    img.convert("RGB").save(save_path, quality=95)
    print(f"  ✓ Salvata: {filename}")
