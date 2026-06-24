from __future__ import annotations
from dataclasses import asdict,is_dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import math,random,re
from typing import Any,Iterable,Mapping
from zipfile import ZipFile,ZIP_DEFLATED
from PIL import Image,ImageDraw,ImageEnhance,ImageFilter,ImageFont

PAGE_WIDTH=1080; PAGE_HEIGHT=1620; MAGAZINE_STYLE_VERSION='premium_v4_reference_layout'
SAFETY_FOOTER='No guarantees. Bet responsibly. This analysis is for informational purposes only.'
ASSET_DIRS=(Path('assets/team_logos'),Path('assets/report_logos'),Path('assets/licensed_logos'))
RED=(190,30,28); BLUE=(19,66,108); BLACK=(13,14,16); PAPER=(244,235,211); CREAM=(255,248,230); GREEN=(61,205,84); TEXT=(14,17,21)
NO_VERIFIED='Data unavailable'; NOT_PROVIDED='Not provided'

def _row(v:Any)->Mapping[str,Any]:
    if isinstance(v,Mapping): return v
    if is_dataclass(v): return asdict(v)
    if hasattr(v,'to_dict'):
        d=v.to_dict(); return d if isinstance(d,Mapping) else {}
    return getattr(v,'__dict__',{}) or {}
def _bad(v):
    if v is None: return True
    if isinstance(v,float) and math.isnan(v): return True
    return str(v).strip().lower() in {'','nan','none','null','n/a','na','nat','--'}
def _text(r,*keys,default=''):
    d=_row(r)
    for k in keys:
        v=d.get(k)
        if not _bad(v): return str(v).strip()
    return default
def _num(r,*keys):
    for k in keys:
        v=_row(r).get(k)
        if _bad(v): continue
        try: return float(str(v).replace('%','').replace(',',''))
        except Exception: pass
    return None
def _font(n,b=False):
    names=('DejaVuSansCondensed-Bold.ttf','DejaVuSans-Bold.ttf','LiberationSans-Bold.ttf') if b else ('DejaVuSansCondensed.ttf','DejaVuSans.ttf','LiberationSans-Regular.ttf')
    for root in ('/usr/share/fonts/truetype/dejavu','/usr/share/fonts/truetype/liberation2','/usr/share/fonts/truetype/liberation'):
        for name in names:
            try: return ImageFont.truetype(str(Path(root)/name),n)
            except Exception: pass
    return ImageFont.load_default()
def _fit(t,w,start,mini=18,b=True):
    d=ImageDraw.Draw(Image.new('RGB',(10,10)))
    for s in range(start,mini-1,-2):
        f=_font(s,b)
        if d.textbbox((0,0),str(t or ''),font=f)[2]<=w: return f
    return _font(mini,b)
def _slug(s): return re.sub(r'[^a-z0-9]+','_',str(s or '').lower()).strip('_')
def find_local_team_logo(team_name:str)->Path|None:
    stem=_slug(team_name)
    if not stem: return None
    variants={stem,stem.replace('_','-'),stem.replace('_','')}
    for folder in ASSET_DIRS:
        for v in variants:
            for ext in ('.png','.jpg','.jpeg','.webp'):
                p=folder/f'{v}{ext}'
                if p.exists(): return p
    return None
def _load(v):
    try:
        if isinstance(v,(bytes,bytearray)): return Image.open(BytesIO(v)).convert('RGBA')
        if isinstance(v,Image.Image): return v.convert('RGBA')
        if isinstance(v,(str,Path)) and Path(v).exists(): return Image.open(v).convert('RGBA')
    except Exception: return None
    return None
def _resample(): return getattr(getattr(Image,'Resampling',Image),'LANCZOS')
def _cover(im,size):
    w,h=size; sc=max(w/max(1,im.width),h/max(1,im.height)); r=im.resize((max(1,int(im.width*sc)),max(1,int(im.height*sc))),_resample()); x=max(0,(r.width-w)//2); y=max(0,(r.height-h)//2); return r.crop((x,y,x+w,y+h))
def _contain(im,size):
    r=im.copy(); r.thumbnail(size,_resample()); return r
def _logo(p,max_size):
    if not p: return None
    try:
        im=Image.open(p).convert('RGBA'); im.thumbnail(max_size,_resample()); return im
    except Exception: return None
def _initials(t):
    p=re.findall(r'[A-Za-z0-9]+',str(t or '').upper()); return ''.join(x[0] for x in p[:3]) or 'TM'
def _badge(d,x,y,w,h,t,c):
    d.rounded_rectangle((x,y,x+w,y+h),radius=9,fill=c,outline=CREAM,width=2)
    f=_fit(_initials(t)[:3],w-10,max(18,h//2),12,True); box=d.textbbox((0,0),_initials(t)[:3],font=f)
    d.text((x+(w-box[2]+box[0])/2,y+(h-box[3]+box[1])/2-2),_initials(t)[:3],font=f,fill='white')
def _logo_or_badge(img,d,team,x,y,w,h,c,use=True):
    im=_logo(find_local_team_logo(team),(w,h)) if use else None
    if im: img.alpha_composite(im,(x+(w-im.width)//2,y+(h-im.height)//2))
    else: _badge(d,x,y,w,h,team,c)
def _game(r): return _text(r,'event','game','event_name','matchup',default='Unknown Matchup')
def _teams(r):
    a=_text(r,'away_team','team_a','team1'); b=_text(r,'home_team','team_b','team2')
    if a and b: return a,b
    g=_game(r)
    for sep in (' at ',' vs ',' VS ',' v ',' @ '):
        if sep in g:
            x,y=g.split(sep,1); return x.strip(),y.strip()
    return _text(r,'team',default='Team A'),_text(r,'opponent',default='Team B')
def _seed(r): return int(sha256('|'.join(str(_row(r).get(k,'')) for k in ('sport','home_team','away_team','prediction','event_start_utc','event')).encode()).hexdigest()[:16],16)
def _pick(r): return _text(r,'prediction','exact_bet','pick','selection','recommended_action','consumer_action',default=NOT_PROVIDED)
def _fmt(v,kind='text'):
    if _bad(v): return NO_VERIFIED
    try:
        n=float(str(v).replace('%','').replace(',',''))
        if kind=='odds': return f'{int(n):+d}' if abs(n)>=100 and n>0 and n.is_integer() else (f'{int(n)}' if abs(n)>=100 and n.is_integer() else f'{n:.2f}'.rstrip('0').rstrip('.'))
        if kind=='ev': return f'{n:+.3f}' if abs(n)<1 else f'{n:+.2f}'
        if kind=='unit': return f'{n:.1f}' if abs(n)<10 else f'{n:.0f}'
        return f'{n:.2f}'.rstrip('0').rstrip('.')
    except Exception: return str(v).strip()
def _pct(n):
    if n is None: return NO_VERIFIED
    n=n/100 if abs(n)>1 else n; return f'{n:.0%}'
def _edge(n):
    if n is None: return NO_VERIFIED
    n=n/100 if abs(n)>1 else n; return f'{n:+.1%}'
def _risk(r): return _text(r,'risk','risk_level','risk_label','profit_guard_status','weather_flag','injury_risk_score',default=NO_VERIFIED).upper()
def _risk_color(x):
    t=str(x).lower()
    if 'high' in t or 'red' in t: return (225,67,62)
    if 'medium' in t or 'yellow' in t or 'moderate' in t: return (235,198,74)
    return GREEN
def _split(v):
    if _bad(v): return []
    nl=chr(10); return [p.strip(' -•') for p in str(v).replace('•',nl).replace(';',nl).replace('|',nl).split(nl) if p.strip(' -•')]
def _wrap(d,t,f,w,m=1):
    words=str(t or '').replace(chr(10),' ').split(); out=[]; cur=''
    for word in words:
        trial=word if not cur else cur+' '+word
        if d.textbbox((0,0),trial,font=f)[2]<=w: cur=trial
        else:
            if cur: out.append(cur)
            cur=word
            if len(out)>=m: break
    if cur and len(out)<m: out.append(cur)
    if len(out)==m and len(' '.join(out).split())<len(words): out[-1]=out[-1].rstrip('.,;:')+'...'
    return out
def _txt(d,x,y,t,f,fill,w,m=1,gap=5):
    for line in _wrap(d,t,f,w,m): d.text((x,y),line,font=f,fill=fill); y+=getattr(f,'size',16)+gap
    return y
def _source(s,t): return f'{t} · Source: {s}'
def _why(r):
    out=[]
    for k in ('why_bullets','why_pick','analysis_summary','reason','explanation'): out+=_split(_row(r).get(k))
    if out: return out[:5]
    items=[]; prob=_pct(_num(r,'learned_model_probability','model_probability_clean','model_probability','final_probability')); market=_pct(_num(r,'market_probability','market_implied_probability')); edge=_edge(_num(r,'model_market_edge','edge')); ev=_fmt(_text(r,'expected_value_per_unit','profit_expected_value','expected_value','ev'),'ev')
    if prob!=NO_VERIFIED: items.append(f'Model projects {prob} probability for {_pick(r)}.')
    if market!=NO_VERIFIED: items.append(f'Market-implied probability checks at {market}.')
    if edge!=NO_VERIFIED: items.append(f'Measured edge: {edge}.')
    if ev!=NO_VERIFIED: items.append(f'Expected value: {ev}.')
    return (items or ['Use only while the line remains playable.'])[:5]
def _pairs(r):
    pairs=[('ODDS SOURCE',_text(r,'odds_source','data_source',default=NO_VERIFIED)),('SPORTSBOOK',_text(r,'bookmaker','sportsbook',default=NO_VERIFIED)),('LINE MOVEMENT',_text(r,'line_movement','price_movement','market_move',default=NO_VERIFIED)),('PUBLIC %',_pct(_num(r,'public_percent','public_bet_percent','public_pct'))),('PRO %',_pct(_num(r,'pro_percent','sharp_percent','smart_money_percent'))),('SHARP MONEY',_text(r,'sharp_money','pro_money','steam_move',default=NO_VERIFIED))]
    return [(a,b) for a,b in pairs if b!=NO_VERIFIED][:6]
def _items(r,keys,fallback,lim):
    out=[]
    for k in keys: out+=_split(_row(r).get(k))
    return (out or [fallback])[:lim]
def _stats(r,prefix):
    fields=(('RECORD',('record','season_record')),('LAST 10',('last_10','last_ten','recent_form')),('TEAM AVG',('team_avg','batting_average','fg_pct')),('RUNS/GAME',('runs_per_game','points_per_game','goals_per_game')),('BULLPEN/DEF',('bullpen_era','def_rating','defense_rating')),('STRIKEOUTS/GAME',('strikeouts_per_game','k_per_game')))
    d=_row(r); out=[]
    for lab,keys in fields:
        val=''
        for k in keys:
            if not _bad(d.get(f'{prefix}_{k}')): val=_fmt(d.get(f'{prefix}_{k}')); break
        if val: out.append((lab,val))
    return out[:6]
def _paper(seed):
    rng=random.Random(seed); img=Image.new('RGBA',(PAGE_WIDTH,PAGE_HEIGHT),PAPER+(255,)); d=ImageDraw.Draw(img,'RGBA')
    for _ in range(560):
        x=rng.randint(0,PAGE_WIDTH-1); y=rng.randint(0,PAGE_HEIGHT-1); q=rng.randint(40,160); d.rectangle((x,y,x+rng.randint(1,3),y+rng.randint(1,3)),fill=(q,q,q,rng.randint(5,20)))
    for _ in range(48):
        x=rng.randint(0,PAGE_WIDTH); y=rng.randint(0,PAGE_HEIGHT); d.line((x,y,x+rng.randint(-70,70),y+rng.randint(-14,14)),fill=(80,52,34,rng.randint(7,20)),width=1)
    d.rectangle((10,10,PAGE_WIDTH-10,PAGE_HEIGHT-10),outline=RED+(220,),width=4); d.rectangle((16,16,PAGE_WIDTH-16,PAGE_HEIGHT-16),outline=BLACK+(180,),width=2)
    return img
def _apply_bg(base,bg=None,mode='watermark',opacity=.12):
    im=_load(bg); mode=str(mode or 'watermark').lower()
    if im is None or mode=='none': return base
    out=base.convert('RGBA'); op=max(0,min(1,float(opacity if opacity is not None else .12)))
    if mode=='full_page': layer=_cover(im,(PAGE_WIDTH,PAGE_HEIGHT)).filter(ImageFilter.GaussianBlur(1)); layer=ImageEnhance.Color(layer).enhance(.38); layer.putalpha(int(255*min(op,.22))); out.alpha_composite(layer); ImageDraw.Draw(out,'RGBA').rectangle((0,0,PAGE_WIDTH,PAGE_HEIGHT),fill=PAPER+(125,))
    elif mode=='header_only': layer=_cover(im,(430,360)).filter(ImageFilter.GaussianBlur(.7)); layer=ImageEnhance.Color(layer).enhance(.55); layer.putalpha(int(255*max(op,.18))); out.alpha_composite(layer,(622,106)); ImageDraw.Draw(out,'RGBA').rectangle((615,100,PAGE_WIDTH-24,460),fill=PAPER+(65,))
    else: layer=_contain(im,(500,360)).filter(ImageFilter.GaussianBlur(.5)); layer=ImageEnhance.Color(layer).enhance(.55); layer.putalpha(int(255*min(max(op,.08),.20))); out.alpha_composite(layer,(PAGE_WIDTH-layer.width-42,124))
    return out
def _user_logo(img,logo,mode,opacity):
    if str(mode or 'header').lower()=='none': return
    im=_load(logo)
    if im is None: return
    im.thumbnail((190,54) if mode=='header' else (440,260),_resample()); im.putalpha(int(255*(min(max(opacity,.08),.18) if mode=='watermark' else max(0,min(1,opacity)))))
    img.alpha_composite(im,(PAGE_WIDTH-im.width-42,170) if mode=='watermark' else (638,17))
def _header(d,img,page,total,logo,logo_mode,logo_opacity):
    d.rectangle((18,18,PAGE_WIDTH-18,74),fill=BLACK); d.rectangle((28,24,260,68),fill=RED); d.text((42,33),'ABA SIGNAL PRO',font=_font(26,True),fill='white'); d.text((286,33),'DAILY SPORTS ANALYSIS',font=_font(25,True),fill='white'); _user_logo(img,logo,logo_mode,logo_opacity); d.rounded_rectangle((872,24,PAGE_WIDTH-38,68),radius=4,fill=CREAM,outline=BLACK); d.text((902,34),f'PAGE {page} OF {total}',font=_font(21,True),fill=BLACK)
def _section(d,x,y,w,h,title,c,icon='★'):
    d.rounded_rectangle((x,y,x+w,y+h),radius=12,fill=CREAM+(245,),outline=BLACK+(230,),width=3); d.rounded_rectangle((x,y,x+w,y+46),radius=8,fill=c); d.text((x+16,y+8),icon,font=_font(22,True),fill=CREAM); d.text((x+50,y+8),title.upper(),font=_font(24,True),fill=CREAM)
def _bullets(d,x,y,items,w,c,n,fs=17,lines=2):
    f=_font(fs)
    for item in items[:n]:
        d.ellipse((x,y+7,x+10,y+17),fill=c); y=_txt(d,x+24,y,item,f,TEXT,w-28,lines,4); y+=6
def _stat(d,x,y,lab,val,w):
    d.text((x,y),lab.upper(),font=_font(15,True),fill=BLACK); box=d.textbbox((0,0),val,font=_font(20,True)); d.text((x+w-(box[2]-box[0]),y-2),val,font=_font(20,True),fill=BLACK); return y+25
def _metric(d,x,y,w,lab,val,col):
    d.rectangle((x,y,x+w,y+80),fill=BLACK,outline=(230,224,204),width=1); d.text((x+10,y+8),lab.upper(),font=_font(14,True),fill=(232,230,220)); _txt(d,x+10,y+35,val.upper(),_fit(val.upper(),w-18,23,14,True),col,w-18,1)
def _team_snap(img,d,x,y,w,team,prefix,c,r,use):
    _logo_or_badge(img,d,team,x,y,42,42,c,use); d.text((x+54,y+5),team.upper(),font=_fit(team.upper(),w-58,22,14,True),fill=c); sy=y+54; stats=_stats(r,prefix) or [('RECORD','N/A'),('LAST 10','N/A'),('TEAM AVG','N/A'),('SCORING','N/A')]
    for lab,val in stats[:5]: sy=_stat(d,x,sy,lab,val,w-10)
    sy+=10; d.text((x,sy),'NOTES',font=_font(16,True),fill=RED); notes=_items(r,(f'{prefix}_notes',f'{prefix}_snapshot',f'{prefix}_context',f'{prefix}_team_snapshot'),'Team data unavailable from current row/API feed.',3); _bullets(d,x,sy+28,notes,w-10,BLUE,3,15,2)
def _players(d,x,y,w,team,prefix,c,r):
    d.text((x,y),team.upper(),font=_fit(team.upper(),w,18,13,True),fill=c); items=_items(r,(f'{prefix}_injuries',f'{prefix}_injury_report',f'{prefix}_lineup_status',f'{prefix}_player_notes','injury_report','injuries','lineup_status','key_players'),'Player/injury data unavailable from current row/API feed.',3); _bullets(d,x,y+30,items,w,c,3,14,2)
def _recommend(r): return _text(r,'final_decision','agent_decision','recommendation','consumer_action','recommended_action',default='PLAY STANDARD'),_text(r,'final_explanation','action_reason','recommendation_reason','decision_reasons',default='Use only if the line remains playable and key news does not change.')
def sanitize_image_filename(value:str,suffix:str='',extension:str='png')->str:
    c=re.sub(r'[^A-Za-z0-9]+','_',str(value or 'magazine').lower()).strip('_') or 'magazine'; s=re.sub(r'[^A-Za-z0-9]+','_',str(suffix or '').lower()).strip('_'); ext=(extension or 'png').lstrip('.'); return f'{c+"_"+s if s else c}.{ext}'
def pick_full_page_filename(pick:Any,index:int,extension:str='png')->str: return sanitize_image_filename(f'pick_{index+1:02d}_{_game(pick)}','full_page',extension)

def render_full_pick_magazine_page(pick:Any,background_image:Any=None,report_name:str|None=None,page_number:int=1,total_pages:int=1,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0,use_team_logo:bool=True)->Image.Image:
    away,home=_teams(pick); red=RED; blue=BLUE; sport=_text(pick,'sport','league',default='Sport N/A'); source=_text(pick,'odds_source','data_source','bookmaker','sportsbook',default='Agent row'); report=(report_name or 'Full Pick Magazine').upper(); date=_text(pick,'report_date','event_date','event_start_utc',default=NOT_PROVIDED)
    img=_apply_bg(_paper(_seed(pick)),background_image,background_mode,background_opacity).convert('RGBA'); d=ImageDraw.Draw(img,'RGBA'); _header(d,img,page_number,total_pages,logo_image,logo_mode,logo_opacity)
    d.text((38,92),f'REPORT: {report}',font=_font(17,True),fill=BLACK); d.text((292,92),'★',font=_font(17,True),fill=BLACK); d.text((326,92),f'SOURCE: {source.upper()}',font=_font(17,True),fill=BLACK); d.text((536,92),'|',font=_font(17,True),fill=BLACK); d.text((572,92),f'DATE: {date.upper()}',font=_font(17,True),fill=BLACK)
    for a in (70,48,35): d.ellipse((650,118,1110,430),fill=BLUE+(a,));
    for i in range(12): d.line((615+i*24,390,845+i*24,128),fill=RED+(42,),width=8)
    d.rounded_rectangle((918,88,1044,166),radius=8,fill=BLACK,outline=CREAM,width=3); d.text((940,104),sport.upper()[:12],font=_font(24,True),fill=CREAM); _logo_or_badge(img,d,sport,946,126,70,34,BLUE,use_team_logo)
    d.text((36,130),away.upper(),font=_fit(away.upper(),600,82,46,True),fill=RED); d.text((38,245),'VS',font=_font(37,True),fill=BLACK); d.line((38,293,86,293),fill=BLACK,width=3); d.text((98,239),home.upper(),font=_fit(home.upper(),530,62,40,True),fill=BLUE)
    season=_text(pick,'season_label','event_stage','competition_round',default=(f'{sport} REGULAR SEASON' if sport!='Sport N/A' else 'MATCHUP ANALYSIS')); d.rectangle((36,330,365,370),fill=BLACK); d.text((52,337),season.upper()[:28],font=_font(23,True),fill=CREAM)
    y=386; ctx=[]
    for k in ('preview_summary','game_summary','sports_context_summary','short_reason','decision_reasons'): ctx+=_split(_row(pick).get(k))
    for line in (ctx or ['Context unavailable from current row/API feed.','Confirm price and lineup news before entry.'])[:3]: y=_txt(d,38,y,line,_font(17),TEXT,610,1,3)
    by=462; d.rounded_rectangle((18,by,PAGE_WIDTH-18,by+90),radius=12,fill=BLACK,outline=CREAM,width=3); d.text((50,by+17),'TENDENCIA',font=_font(23,True),fill=RED); d.text((50,by+50),_pick(pick).upper(),font=_fit(_pick(pick).upper(),210,34,20,True),fill=CREAM); _logo_or_badge(img,d,home,252,by+22,58,48,BLUE,use_team_logo)
    odds=_fmt(_text(pick,'american_odds','odds_american','decimal_price','odds_at_pick','best_price','odds'),'odds'); conf=_pct(_num(pick,'learned_model_probability','model_probability_clean','model_probability','final_probability')); edge=_edge(_num(pick,'model_market_edge','edge')); ev=_fmt(_text(pick,'expected_value_per_unit','profit_expected_value','expected_value','ev'),'ev'); units=_fmt(_text(pick,'recommended_stake_units','suggested_stake_units','units',default='1.0'),'unit'); risk=_risk(pick); market=_text(pick,'market_type','market','bet_type',default=NO_VERIFIED).upper()
    x=340
    for (lab,val,col),w in zip([('ODDS',odds,CREAM),('CONFIDENCE',conf,GREEN),('EDGE',edge,GREEN if not edge.startswith('-') else (225,67,62)),('EV',ev,GREEN if not ev.startswith('-') else (225,67,62)),('UNITS',units,CREAM),('RISK',risk,_risk_color(risk)),('MARKET',market,CREAM)],[92,132,104,110,96,96,104]): _metric(d,x,by+4,w,lab,val,col); x+=w
    _section(d,18,570,342,294,'WHY WE PICKED IT',RED,'★'); _bullets(d,40,632,_why(pick),302,RED,5,17,2)
    _section(d,18,886,342,246,'PRO BETTOR EVIDENCE',BLUE,'◉'); y=948
    for lab,val in _pairs(pick): d.text((42,y),f'{lab}:',font=_font(15,True),fill=BLACK); _txt(d,180,y,val,_font(15,True),BLACK,150,1); y+=27
    d.rectangle((26,1086,352,1124),fill=BLUE); _txt(d,38,1093,_text(pick,'evidence_summary',default='Market and model evidence support this read.'),_font(15,True),CREAM,306,2)
    _section(d,374,570,688,374,'TEAM SNAPSHOTS',BLUE,'♟'); d.line((718,630,718,924),fill=BLACK+(170,),width=1); _team_snap(img,d,398,640,300,away,'away',RED,pick,use_team_logo); _team_snap(img,d,744,640,300,home,'home',BLUE,pick,use_team_logo)
    _section(d,374,958,688,176,'PLAYER / INJURY NOTES',BLUE,'♟'); d.line((718,1014,718,1124),fill=BLACK+(160,),width=1); _players(d,394,1026,310,away,'away',RED,pick); _players(d,740,1026,310,home,'home',BLUE,pick)
    _section(d,18,1156,340,204,'RISK DESK',RED,'♢'); _bullets(d,40,1218,_items(pick,('why_lose','risk_reason','hidden_risk','risk_notes'),f'Risk status: {risk}',5),300,RED,5,14,2)
    _section(d,370,1156,332,204,'MATCHUP NOTES',BLUE,'●'); _bullets(d,392,1218,_items(pick,('matchup_note','matchup_notes','head_to_head','h2h','venue_note','weather_location','sports_context_summary'),'Matchup context unavailable from current row/API feed.',4),292,BLUE,4,15,2)
    _section(d,714,1156,348,204,'CHAIN BETTING NOTES',BLUE,'↗'); _bullets(d,736,1218,_items(pick,('chain_notes','main_read','add_on_legs','parlay_notes'),'Better as an individual straight analysis unless another verified edge exists.',4),308,BLUE,4,15,2)
    action,explain=_recommend(pick); fy=1386; d.rounded_rectangle((18,fy,PAGE_WIDTH-18,1558),radius=12,fill=BLACK,outline=RED,width=3); d.rectangle((18,fy,236,1558),fill=RED); d.text((36,fy+34),'FINAL',font=_font(31,True),fill=CREAM); d.text((36,fy+78),'RECOMMENDATION',font=_font(27,True),fill=CREAM); _txt(d,282,fy+28,action.upper(),_fit(action.upper(),360,52,36,True),GREEN,370,1); _txt(d,282,fy+92,_pick(pick).upper(),_font(31,True),CREAM,340,1); _txt(d,656,fy+38,explain,_font(20),CREAM,360,4)
    d.rectangle((18,1564,PAGE_WIDTH-18,1602),fill=BLACK); footer=SAFETY_FOOTER; box=d.textbbox((0,0),footer,font=_font(16)); d.text(((PAGE_WIDTH-(box[2]-box[0]))/2,1575),footer,font=_font(16),fill=CREAM)
    return img.convert('RGB')
def _png(im):
    b=BytesIO(); im.save(b,format='PNG',optimize=True); return b.getvalue()
def render_full_pick_magazine_page_png(pick:Any,background_image:Any=None,report_name:str|None=None,page_number:int=1,total_pages:int=1,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0,use_team_logo:bool=True)->bytes: return _png(render_full_pick_magazine_page(pick,background_image,report_name,page_number,total_pages,logo_image,background_mode,logo_mode,background_opacity,logo_opacity,use_team_logo))
def render_full_magazine_book_pages(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0,use_team_logo:bool=True)->list[Image.Image]:
    rows=list(picks) or [{'event':'No Picks','prediction':'NO PICK'}]; return [render_full_pick_magazine_page(r,background_image,report_name,i+1,len(rows),logo_image,background_mode,logo_mode,background_opacity,logo_opacity,use_team_logo) for i,r in enumerate(rows)]
def render_full_magazine_book_png(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0,use_team_logo:bool=True)->bytes:
    pages=render_full_magazine_book_pages(picks,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity,use_team_logo); book=Image.new('RGB',(PAGE_WIDTH,PAGE_HEIGHT*len(pages)),PAPER)
    for i,p in enumerate(pages): book.paste(p,(0,PAGE_HEIGHT*i))
    return _png(book)
def render_full_magazine_book_pdf(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0,use_team_logo:bool=True)->bytes:
    pages=[p.convert('RGB') for p in render_full_magazine_book_pages(picks,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity,use_team_logo)]; b=BytesIO(); pages[0].save(b,format='PDF',save_all=True,append_images=pages[1:],resolution=100.0); return b.getvalue()
def render_full_magazine_zip(picks:Iterable[Any],background_image:Any=None,report_name:str|None=None,logo_image:Any=None,background_mode:str='watermark',logo_mode:str='header',background_opacity:float=.12,logo_opacity:float=1.0,use_team_logo:bool=True)->bytes:
    rows=list(picks); pages=render_full_magazine_book_pages(rows,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity,use_team_logo); b=BytesIO()
    with ZipFile(b,'w',compression=ZIP_DEFLATED) as z:
        z.writestr('full_magazine_book.png',render_full_magazine_book_png(rows,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity,use_team_logo)); z.writestr('full_magazine_book.pdf',render_full_magazine_book_pdf(rows,background_image,report_name,logo_image,background_mode,logo_mode,background_opacity,logo_opacity,use_team_logo))
        for i,p in enumerate(pages): z.writestr(pick_full_page_filename(rows[i] if i<len(rows) else {'event':'No Picks'},i),_png(p))
    return b.getvalue()
