from __future__ import annotations

LANGUAGES = {
    "English": "en",
    "Español": "es",
}

TEXT = {
    "language": {"en": "Language", "es": "Idioma"},
    "market_snapshot_title": {"en": "Market Snapshot Capture", "es": "Captura de Mercado"},
    "market_snapshot_caption": {
        "en": "One-button line-movement capture using The Odds API. Captures current sportsbook prices for later CLV and market-movement learning.",
        "es": "Captura de movimiento de línea con un botón usando The Odds API. Guarda precios actuales para CLV y aprendizaje de mercado.",
    },
    "odds_weather_title": {"en": "Odds + Weather Decision Layer", "es": "Capa de Decisión: Cuotas + Clima"},
    "odds_weather_caption": {
        "en": "Combines sportsbook market data, WeatherAPI context, and optional SportsDataIO context before the fusion layer.",
        "es": "Combina mercado de apuestas, contexto de WeatherAPI y contexto opcional de SportsDataIO antes de la capa de fusión.",
    },
    "api_sources": {"en": "API sources", "es": "Fuentes API"},
    "odds_api_key": {"en": "Odds API key", "es": "Clave de Odds API"},
    "weatherapi_key": {"en": "WeatherAPI key", "es": "Clave de WeatherAPI"},
    "sportsdataio_key": {"en": "SportsDataIO key", "es": "Clave de SportsDataIO"},
    "game_setup": {"en": "Game setup", "es": "Configuración del partido"},
    "game": {"en": "Game", "es": "Partido"},
    "sport_search": {"en": "Sport/feed search", "es": "Buscar deporte/feed"},
    "weather_location": {"en": "Weather location / venue city", "es": "Ubicación del clima / ciudad del estadio"},
    "league_hint": {"en": "League / competition hint", "es": "Liga / competencia"},
    "scan_target": {"en": "Scan target", "es": "Objetivo de escaneo"},
    "all_sports": {"en": "All sports", "es": "Todos los deportes"},
    "one_league": {"en": "One league/sport", "es": "Una liga/deporte"},
    "one_team": {"en": "One team/player", "es": "Un equipo/jugador"},
    "book_regions": {"en": "Bookmaker regions", "es": "Regiones de casas de apuestas"},
    "markets": {"en": "Markets", "es": "Mercados"},
    "max_sport_feeds": {"en": "Max sport feeds", "es": "Máximo de feeds deportivos"},
    "max_events": {"en": "Max events per feed", "es": "Máximo de eventos por feed"},
    "snapshot_settings": {"en": "Snapshot settings", "es": "Configuración de captura"},
    "snapshot_label": {"en": "Snapshot label", "es": "Etiqueta de captura"},
    "output_folder": {"en": "Output folder", "es": "Carpeta de salida"},
    "cache_controls": {"en": "Cache / cost controls", "es": "Caché / control de costos"},
    "max_api_calls": {"en": "Max API calls", "es": "Máximo de llamadas API"},
    "cache_ttl": {"en": "Cache TTL seconds", "es": "Segundos de caché TTL"},
    "source_status": {"en": "Source status", "es": "Estado de fuentes"},
    "enabled": {"en": "Enabled", "es": "Activo"},
    "missing": {"en": "Missing", "es": "Falta"},
    "manual_weather": {"en": "Manual weather preview", "es": "Vista manual del clima"},
    "temperature": {"en": "Temperature °F", "es": "Temperatura °F"},
    "wind": {"en": "Wind mph", "es": "Viento mph"},
    "rain": {"en": "Rain mm", "es": "Lluvia mm"},
    "run_snapshot": {"en": "Capture market snapshot", "es": "Capturar mercado"},
    "run_layer": {"en": "Run odds + weather layer", "es": "Ejecutar cuotas + clima"},
    "decision_output": {"en": "Decision output", "es": "Salida de decisión"},
    "weather_risk": {"en": "Weather risk", "es": "Riesgo climático"},
    "weather_score": {"en": "Weather score", "es": "Puntaje climático"},
    "markets_selected": {"en": "Markets selected", "es": "Mercados seleccionados"},
    "config": {"en": "Run config", "es": "Configuración"},
    "enter_fields": {"en": "Enter fields, then run the layer.", "es": "Ingresa los campos y ejecuta la capa."},
}


def tr(key: str, lang_code: str) -> str:
    values = TEXT.get(key, {})
    return values.get(lang_code, values.get("en", key))
