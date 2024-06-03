import asyncio,logging,os,random,string,re,subprocess,time,shutil,platform,requests,dotenv,html,hashlib
from telethon import TelegramClient, events
from telethon.tl.types import MessageEntityUrl
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file, override=True)

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_GROUP = int(os.getenv("LOG_GROUP_ID"))
is_win = platform.system()=='Windows'

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def find_all_urls(message):
    ret = list()
    if message.entities is None:
        return ret
    for entity in message.entities:
        if type(entity) == MessageEntityUrl:
            url = message.text[entity.offset:entity.offset+entity.length]
            if url.startswith('http://') or url.startswith('https://'):
                ret.append(url)
            else:
                ret.append('http://'+url)
    return ret
def humanify(byte_size):
    siz_list = ['KB', 'MB', 'GB']
    for i in range(len(siz_list)):
        if byte_size/1024**(i+1) < 1024:
            return "{} {}".format(round(byte_size/1024**(i+1), 2), siz_list[i])
def progress_bar(percentage):
    prefix_char = '█'
    suffix_char = '▒'
    progressbar_length = 10
    prefix = round(percentage/progressbar_length) * prefix_char
    suffix = (progressbar_length-round(percentage/progressbar_length)) * suffix_char
    return "{}{} {}%".format(prefix, suffix, percentage)
def human_time_to_seconds(human_time):
    return (datetime.strptime(human_time, "%H:%M:%S.%f") - datetime(1900, 1, 1)).total_seconds()
def check(log_file):
    try:
        with open(log_file, 'r') as file:
            content = file.read()
        duration_match = re.search(r"Duration: (.*?), start:", content)
        raw_duration = duration_match.group(1)
        time_matches = re.findall(r"time=(.*?) bitrate", content)
        raw_time = time_matches[-1]
        fraction = human_time_to_seconds(raw_time) / human_time_to_seconds(raw_duration)
        progress = progress_bar(round(fraction * 100, 2))
        status = f"Downloading: {progress}\nDuration: {raw_duration}\nCurrent Time: {raw_time}"
        return status
    except Exception as e:
        print(repr(e))
        return ''
async def senderinfo(event):
    try:
        sender = await event.get_sender()
        items = [
            getattr(sender, 'first_name', getattr(sender, 'title', 'Null')),
            getattr(sender, 'last_name', ''),
            sender.id,
            '@{0}\nUsername-link: https://t.me/{0}'.format(getattr(sender, 'username', '')) if getattr(sender, 'username', False) else 'None',
        ]
        items = [html.escape(str(item)) for item in items]
        return '''

<u><b>User Info:</b></u>
Name: {0} {1}
Chat id: <pre>{2}</pre>
Username: {3}
Permanent link: <a href="tg://user?id={2}">link</a>
'''.format(*items)
    except:
        return ''

async def show_ffmpeg_status(cmd, msg, logfile):
    if is_win:
        subprocess.Popen(cmd, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)
    else:
        os.system(' '.join(cmd)+" 1> /dev/null 2>&1 & ")
    await asyncio.sleep(3)
    last = ''
    last_edit_time = time.time()
    while os.path.isfile(logfile):
        status = check(logfile)
        if last_edit_time+5 < time.time() and last != status:
            await msg.edit(status)
            last = status
            last_edit_time = time.time()
        await asyncio.sleep(2)
class TimeKeeper:
    last = 0
    last_edited_time = 0
async def upload_callback(current, total, event, file_org_name, tk):
    percentage = round(current/total*100, 2)
    if tk.last+2 < percentage and tk.last_edited_time+5 < time.time():
        await event.edit("Uploading {}\nFile Name: {}\nSize: {}\nUploaded: {}".format(progress_bar(percentage), file_org_name, humanify(total), humanify(current)))
        tk.last = percentage
        tk.last_edited_time = time.time()
async def upload_and_send(event, msg, outFilePath, originalFileName, caption):
    tk = TimeKeeper()
    file = await bot.upload_file(
        outFilePath,
        file_name=originalFileName,
        progress_callback=lambda c,t:upload_callback(c,t,msg,originalFileName,tk),
    )
    info = await senderinfo(event)
    await bot.send_file(
        event.chat,
        file=file,
        thumb=f'{outFilePath}.jpg',
        caption=html.escape(caption),
        supports_streaming=True,
        parse_mode='HTML',
        link_preview=False
    )
    await bot.send_file(
        LOG_GROUP,
        file=file,
        thumb=f'{outFilePath}.jpg',
        caption=html.escape(caption)+info,
        supports_streaming=True,
        parse_mode='HTML',
        link_preview=False
    )

@bot.on(events.NewMessage(pattern=r"^(https?://.+)(?: \| (.+))$", func=lambda e: e.is_private))
async def handler(event):
    msg = await event.respond('wait...')
    tmpdir = os.path.join('files', ''.join([random.choice(string.ascii_letters+string.digits) for i in range(15)]))
    os.makedirs(tmpdir)
    try:
        inFileName = find_all_urls(event.message)[0]
        orgFileName = event.pattern_match[2]
        outFileName = hashlib.md5(orgFileName.encode()).hexdigest()+'.mp4'
        outFilePath = os.path.join(tmpdir, outFileName)
        cmd = ['python' if is_win else 'python3', 'converter.py', inFileName, outFilePath]
        await show_ffmpeg_status(cmd, msg, f"{outFilePath}.log")
        await msg.edit('Now uploading...')
        parts = 1
        if 1024**3*2 < os.path.getsize(outFilePath):
            cmd = ['python' if is_win else 'python3', 'splitter.py', outFilePath]
            await show_ffmpeg_status(cmd, msg, f"{outFilePath}.log")
            with open(f"{outFilePath}.parts", 'r') as f:
                parts = int(f.read().strip())
        for i in range(parts):
            i+=1
            await upload_and_send(event,
                msg,
                outFilePath if parts==1 else f'{outFilePath}{i}.mp4',
                f'{orgFileName}.mp4' if parts==1 else f'{orgFileName}_{i}.mp4',
                event.pattern_match[2] if parts==1 else f'{event.pattern_match[2]} part {i}'
            )
        await msg.delete()
    except Exception as e:
        await msg.edit(repr(e))
    shutil.rmtree(tmpdir)

@bot.on(events.NewMessage(pattern=r"^/add_proxy (http://(?:[a-zA-Z0-9\-_.]+:[a-zA-Z0-9\-_.]+@)?[a-zA-Z0-9\-_.]+:\d+)$", func=lambda e: e.is_private))
async def handler(event):
    msg = await event.respond("checking proxy...")
    try:
        proxy = event.pattern_match[1]
        p = {'http': proxy,'https': proxy}
        r = requests.get('http://ip-api.com/json', proxies=p, timeout=5).json()
        os.environ["PROXY_URL"] = proxy
        dotenv.set_key(dotenv_file, "PROXY_URL", proxy)
        presult = '\n'.join([f"{k}: `{r[k]}`" for k in r])
        await msg.edit(presult)
        await msg.edit(presult+'\n\nproxy added successfully ✅')
    except Exception as e:
        await msg.edit("Error: "+repr(e))

@bot.on(events.NewMessage(pattern=r"^/proxy_status$", func=lambda e: e.is_private))
async def handler(event):
    msg = await event.respond("checking proxy...")
    try:
        proxy = os.getenv("PROXY_URL", '')
        use_proxy = os.getenv("USE_PROXY", 'False')=='True'
        p = {'http': proxy,'https': proxy} if use_proxy else None
        r = requests.get('http://ip-api.com/json', proxies=p, timeout=5).json()
        await msg.edit('\n'.join([f"{k}: `{r[k]}`" for k in r]))
    except Exception as e:
        await msg.edit("Error: "+repr(e))

@bot.on(events.NewMessage(pattern=r"^/proxy_on$", func=lambda e: e.is_private))
async def handler(event):
    os.environ["USE_PROXY"] = 'True'
    dotenv.set_key(dotenv_file, "USE_PROXY", 'True')
    await event.respond("proxy is on")

@bot.on(events.NewMessage(pattern=r"^/proxy_off$", func=lambda e: e.is_private))
async def handler(event):
    os.environ["USE_PROXY"] = 'False'
    dotenv.set_key(dotenv_file, "USE_PROXY", 'False')
    await event.respond("proxy is off")

with bot:
    bot.run_until_disconnected()
