from __future__ import annotations


def install() -> None:
    try:
        from . import magazine_book_export as m
    except Exception:
        return
    if getattr(m, '_aba_magazine_value_safety_patch_v1', False):
        return
    base = m.render_full_pick_magazine_page

    def wrapped(pick, background_image=None, report_name=None, page_number=1, total_pages=1, logo_image=None, background_mode='hero_right', logo_mode='header', background_opacity=0.9, logo_opacity=1.0, use_team_logo=True, language=None):
        img = base(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        lang = m._lang(pick, language)
        d = m.ImageDraw.Draw(img, 'RGBA')
        sy = 456
        d.rounded_rectangle((20, sy, m.PAGE_WIDTH - 20, sy + 106), radius=13, fill=m.BLACK, outline=m.CREAM, width=3)
        labels = [('ODDS', 110), ('CONFIDENCE', 150), ('EDGE', 120), ('EV', 120), ('UNITS', 110), ('RISK', 150)]
        x = 344
        values = [
            m._fmt(m._get(pick, 'american_odds', 'odds_american', 'decimal_price', 'odds_at_pick', 'best_price', 'odds'), 'odds'),
            m._pct(m._num(pick, 'learned_model_probability', 'model_probability_clean', 'model_probability', 'final_probability')),
            m._edge(m._num(pick, 'model_market_edge', 'edge')),
            m._fmt(m._get(pick, 'expected_value_per_unit', 'profit_expected_value', 'expected_value', 'ev'), 'ev'),
            m._fmt(m._get(pick, 'recommended_stake_units', 'suggested_stake_units', 'units', default='1.0'), 'unit'),
            m._clean(m._get(pick, 'risk', 'risk_level', 'risk_label', 'profit_guard_status', default=m.NO_VERIFIED), True),
        ]
        colors = [m.CREAM, m.GREEN, m.DANGER if str(values[2]).startswith('-') else m.GREEN, m.DANGER if str(values[3]).startswith('-') else m.GREEN, m.CREAM, m.GREEN]
        if str(values[2]).startswith('-') or str(values[3]).startswith('-'):
            values[5] = 'REVISAR' if lang == 'es' else 'REVIEW'
            colors[5] = m.DANGER
        trend = m._tr('TREND', lang)
        d.text((50, sy + 16), trend, font=m._fit(trend, 190, 25, 14, True), fill=m.RED)
        pick_text = m._tr(m._clean(m._pick(pick), True), lang).upper()
        m._txt_auto(d, 50, sy + 52, pick_text, 210, 38, 30, 8, m.CREAM, True, 1)
        _, home = m._teams(pick)
        m._badge(img, d, m._team_label(home, lang), 268, sy + 27, 58, 50, m.BLUE, False)
        for (label, width), value, color in zip(labels, values, colors):
            m._metric(d, x, sy + 6, width, label, str(value), color, lang)
            x += width
        m._aba_magazine_value_safety_patch_v1 = True
        return img

    m.render_full_pick_magazine_page = wrapped
