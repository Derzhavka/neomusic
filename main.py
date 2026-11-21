import asyncio, json, logging, os, sqlite3
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)
TOKEN=os.getenv("BOT_TOKEN","").strip()
KEY=os.getenv("HMS_API_KEY","").strip()
BASE=os.getenv("DEEPSEEK_BASE_URL","https://100milionseek.top/v1").rstrip("/")
MODEL=os.getenv("DEEPSEEK_MODEL","deepseek-v4.1-flash-free")
DBFILE=os.getenv("DATABASE_PATH","/data/neomusic.sqlite3")
if not TOKEN: raise RuntimeError("BOT_TOKEN is missing")
bot=Bot(TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp=Dispatcher(); state={}
db=sqlite3.connect(DBFILE,check_same_thread=False); db.row_factory=sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT);
CREATE TABLE IF NOT EXISTS favorites(user_id INTEGER,track_id TEXT,title TEXT,artist TEXT,link TEXT,preview TEXT,cover TEXT,PRIMARY KEY(user_id,track_id));
CREATE TABLE IF NOT EXISTS playlists(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,name TEXT,description TEXT,tracks TEXT);
""");db.commit()

def esc(v):return str(v or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def menu():return InlineKeyboardMarkup(inline_keyboard=[
 [InlineKeyboardButton(text="✨ AI DJ",callback_data="ai"),InlineKeyboardButton(text="🔎 Поиск",callback_data="search")],
 [InlineKeyboardButton(text="🎭 Настроение",callback_data="moods"),InlineKeyboardButton(text="📀 Плейлисты",callback_data="lists")],
 [InlineKeyboardButton(text="❤️ Избранное",callback_data="fav"),InlineKeyboardButton(text="🎲 Микс дня",callback_data="daily")],
 [InlineKeyboardButton(text="👤 Профиль",callback_data="profile")]])
def trackkb(t):
 rows=[[InlineKeyboardButton(text="▶️ Превью 30 сек",callback_data="play:"+t["id"]),InlineKeyboardButton(text="❤️",callback_data="like:"+t["id"])]]
 if t.get("link"):rows.append([InlineKeyboardButton(text="🎧 Deezer",url=t["link"])])
 return InlineKeyboardMarkup(inline_keyboard=rows)
def cap(t):return f"<b>{esc(t.get('title'))}</b> — {esc(t.get('artist'))}\n💿 {esc(t.get('album',''))}"
async def deezer(q,n=8):
 async with httpx.AsyncClient(timeout=20) as c:r=await c.get("https://api.deezer.com/search",params={"q":q,"limit":n});r.raise_for_status()
 return [{"id":str(x["id"]),"title":x["title"],"artist":x["artist"]["name"],"album":x["album"]["title"],"link":x.get("link"),"preview":x.get("preview"),"cover":x["album"].get("cover_medium")} for x in r.json().get("data",[])]
async def ai(q):
 if not KEY:return None
 async with httpx.AsyncClient(timeout=40) as c:
  r=await c.post(BASE+"/chat/completions",headers={"Authorization":"Bearer "+KEY},json={"model":MODEL,"messages":[{"role":"system","content":"Ты музыкальный куратор. По запросу создай JSON строго формата {queries:[поисковые запросы на Deezer],title:название,description:описание}. Запросы — реальные артисты/жанры/стили. Ответ на русском."},{"role":"user","content":q}]});r.raise_for_status()
 return r.json()["choices"][0]["message"]["content"]
async def mix(q):
 qs=[q];title="Подборка";desc="Собрано под твой запрос."
 raw=await ai(q)
 if raw:
  try:
   j=json.loads(raw[raw.find("{"):raw.rfind("}")+1]);qs=j.get("queries",qs);title=j.get("title",title);desc=j.get("description",desc)
  except Exception:logging.warning("AI returned non-JSON")
 ts=[]
 for term in qs[:3]:
  try:ts+=await deezer(str(term),5)
  except Exception:logging.exception("catalog search failed")
 return title,desc,list({t["id"]:t for t in ts}.values())[:12]
async def send_tracks(m,title,desc,ts):
 if not ts:await m.answer("Треки не нашлись — попробуй другой запрос.",reply_markup=menu());return
 await m.answer(f"🎧 <b>{esc(title)}</b>\n{esc(desc)}\n\nНайдено: {len(ts)}",reply_markup=menu())
 for t in ts:
  try:
   if t.get("cover"):await m.answer_photo(t["cover"],caption=cap(t),reply_markup=trackkb(t))
   else:await m.answer(cap(t),reply_markup=trackkb(t))
  except Exception:await m.answer(cap(t),reply_markup=trackkb(t))
@dp.message(CommandStart())
async def start(m):
 db.execute("INSERT OR IGNORE INTO users(id,username) VALUES(?,?)",(m.from_user.id,m.from_user.username));db.commit()
 await m.answer("🎧 <b>NEO MUSIC</b>\nТвоя музыка. Твоё настроение.\n\nВыбирай:",reply_markup=menu())
@dp.message(Command("help"))
async def help(m):await m.answer("Нажимай кнопки меню: AI DJ — настроение/описание, Поиск — артист или песня.",reply_markup=menu())
@dp.callback_query(F.data=="ai")
async def ai_start(c):state[c.from_user.id]="ai";await c.message.answer("✨ Опиши настроение, жанр, ситуацию или исполнителей. Например: «ночная поездка, грустный рэп, похожий на Miyagi».");await c.answer()
@dp.callback_query(F.data=="search")
async def search_start(c):state[c.from_user.id]="search";await c.message.answer("🔎 Введи имя исполнителя или название песни.");await c.answer()
@dp.callback_query(F.data=="moods")
async def moods(c):
 moods=[[("🌙 Ночь","night"),("💔 Грусть","sad")],[("⚡ Энергия","energy"),("🌧 Дождь","rain")],[("💗 Романтика","love"),("🏋️ Спорт","gym")],[("🧘 Спокойствие","calm"),("🚗 Дорога","drive")]]
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a,callback_data="mood:"+b) for a,b in row] for row in moods]+[[InlineKeyboardButton(text="⬅️ Меню",callback_data="home")]])
 await c.message.answer("Выбери настроение:",reply_markup=kb);await c.answer()
@dp.callback_query(F.data.startswith("mood:"))
async def mood(c):
 q={"night":"ночная музыка для города","sad":"меланхоличная грустная музыка","energy":"энергичная мотивационная музыка","rain":"атмосфера дождливого вечера","love":"романтичная музыка","gym":"энергичная музыка для тренировок","calm":"спокойная музыка","drive":"музыка для поездки"}.get(c.data[5:],"музыка")
 await c.answer("Ищу…");t,d,ts=await mix(q);await send_tracks(c.message,t,d,ts)
@dp.callback_query(F.data=="daily")
async def daily(c):await c.answer("Собираю…");t,d,ts=await mix("микс дня, популярные современные песни и разные жанры");await send_tracks(c.message,"☀️ Микс дня · "+t,d,ts)
@dp.message()
async def input_text(m):
 mode=state.pop(m.from_user.id,None)
 if not mode or not m.text:return
 if mode=="search":
  try:ts=await deezer(m.text,10);await send_tracks(m,"🔎 "+m.text,"Результаты поиска",ts)
  except Exception:await m.answer("Поиск временно недоступен.")
 else:
  await m.answer("✨ Подбираю музыку…")
  try:
   t,d,ts=await mix(m.text)
   if mode=="playlist" and ts:
    db.execute("INSERT INTO playlists(user_id,name,description,tracks) VALUES(?,?,?,?)",(m.from_user.id,t,d,json.dumps(ts,ensure_ascii=False)));db.commit()
    await m.answer("📀 Сохранил плейлист в твою библиотеку.")
   await send_tracks(m,t,d,ts)
  except Exception:logging.exception("playlist error");await m.answer("Не получилось собрать подборку, попробуй ещё.")
@dp.callback_query(F.data.startswith("like:"))
async def like(c):
 try:
  async with httpx.AsyncClient(timeout=15) as x:r=await x.get("https://api.deezer.com/track/"+c.data[5:]);r.raise_for_status();t=r.json()
  db.execute("INSERT OR REPLACE INTO favorites VALUES(?,?,?,?,?,?,?)",(c.from_user.id,str(t["id"]),t["title"],t["artist"]["name"],t.get("link"),t.get("preview"),t["album"].get("cover_medium")));db.commit();await c.answer("В избранном ❤️")
 except Exception:await c.answer("Не удалось сохранить",show_alert=True)
@dp.callback_query(F.data.startswith("play:"))
async def play(c):
 try:
  async with httpx.AsyncClient(timeout=15) as x:r=await x.get("https://api.deezer.com/track/"+c.data[5:]);r.raise_for_status();t=r.json()
  if t.get("preview"):await c.message.answer_audio(t["preview"],title=t["title"],performer=t["artist"]["name"],caption="30-секундное превью")
  else:await c.message.answer("Превью недоступно. Полная версия: "+(t.get("link") or "Deezer"))
  await c.answer()
 except Exception:await c.answer("Превью не удалось загрузить.",show_alert=True)
@dp.callback_query(F.data=="fav")
async def favorites(c):
 rs=db.execute("SELECT * FROM favorites WHERE user_id=? ORDER BY rowid DESC",(c.from_user.id,)).fetchall()
 if not rs:await c.message.answer("Избранное пусто — нажми ❤️ у трека.");await c.answer();return
 await c.message.answer(f"❤️ <b>Избранное · {len(rs)}</b>")
 for t in rs:await c.message.answer(cap(t),reply_markup=trackkb(dict(t)))
 await c.answer()
@dp.callback_query(F.data=="lists")
async def lists(c):
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✨ Создать AI-плейлист",callback_data="newpl")],[InlineKeyboardButton(text="📂 Мои плейлисты",callback_data="mypl")],[InlineKeyboardButton(text="⬅️ Меню",callback_data="home")]])
 await c.message.answer("📀 <b>Плейлисты</b>",reply_markup=kb);await c.answer()
@dp.callback_query(F.data=="newpl")
async def newpl(c):state[c.from_user.id]="playlist";await c.message.answer("Опиши подборку, я создам и сохраню плейлист.");await c.answer()
@dp.callback_query(F.data=="mypl")
async def mypl(c):
 rs=db.execute("SELECT id,name FROM playlists WHERE user_id=? ORDER BY id DESC",(c.from_user.id,)).fetchall()
 if not rs:await c.message.answer("Пока нет сохранённых плейлистов.");await c.answer();return
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📀 "+r["name"],callback_data="pl:"+str(r["id"]))] for r in rs]+[[InlineKeyboardButton(text="⬅️ Назад",callback_data="lists")]])
 await c.message.answer("Твои плейлисты:",reply_markup=kb);await c.answer()
@dp.callback_query(F.data.startswith("pl:"))
async def playlist(c):
 r=db.execute("SELECT * FROM playlists WHERE id=? AND user_id=?",(int(c.data[3:]),c.from_user.id)).fetchone()
 if r:
  await c.message.answer(f"📀 <b>{esc(r['name'])}</b>\n{esc(r['description'])}")
  for t in json.loads(r["tracks"]):await c.message.answer(cap(t),reply_markup=trackkb(t))
 await c.answer()
@dp.callback_query(F.data=="profile")
async def profile(c):
 f=db.execute("SELECT COUNT(*) FROM favorites WHERE user_id=?",(c.from_user.id,)).fetchone()[0];p=db.execute("SELECT COUNT(*) FROM playlists WHERE user_id=?",(c.from_user.id,)).fetchone()[0]
 await c.message.answer(f"👤 <b>Профиль</b>\n❤️ Избранное: {f}\n📀 Плейлисты: {p}",reply_markup=menu());await c.answer()
@dp.callback_query(F.data=="home")
async def home(c):await c.message.answer("🎧 Меню",reply_markup=menu());await c.answer()
async def main():logging.info("NeoMusic bot starting");await dp.start_polling(bot)
if __name__=="__main__":asyncio.run(main())
