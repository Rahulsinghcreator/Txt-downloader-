import os,sys,re,time,math,platform
from datetime import datetime

def seconds_to_human_time(sec):
    hrs = sec // 3600
    sec %= 3600
    mins = sec // 60
    sec %= 60
    return "%02d:%02d:%02d" % (hrs, mins, sec) 
def human_time_to_seconds(human_time):
    return (datetime.strptime(raw_duration, "%H:%M:%S.%f") - datetime(1900, 1, 1)).total_seconds()

redir = '1>NUL 2>"{}"' if platform.system()=='Windows' else '1> "{}" 2>&1'
inFileName = sys.argv[1]
logFilePath = f"{inFileName}.log"
redir = redir.format(logFilePath)
size_gb = os.path.getsize(inFileName)/1024**3
part_count = math.ceil(size_gb/2) # number of 2 gb parts
with open(f"{inFileName}.parts", 'w') as f:
    f.write(str(part_count))
if part_count == 1:
    exit()
cmd = f'ffmpeg -i "{inFileName}" 1>NUL 2>"{inFileName}.info"'
os.system(cmd)
with open(f"{inFileName}.info", 'r') as f:
    content = f.read()
os.remove(f"{inFileName}.info")
duration_match = re.search(r"Duration: (.*?), start:", content)
raw_duration = duration_match.group(1)
one_part_len_seconds = round(human_time_to_seconds(raw_duration)/part_count)
one_part_length_human = seconds_to_human_time(one_part_len_seconds)
for i in range(1, part_count):
    start = seconds_to_human_time(one_part_len_seconds*(i-1))
    cmd2 = f'ffmpeg -i {inFileName} -ss {start} -t {one_part_length_human} -c copy "{inFileName}{i}.mp4" {redir}'
    os.system(cmd2)
    cmd2 = f'ffmpeg -i {inFileName}{i}.mp4 -ss 00:00:01 -vframes 1 {inFileName}{i}.mp4.jpg'
    os.system(cmd2)
# last part splitted below
start = seconds_to_human_time(one_part_len_seconds*(part_count-1))
cmd2 = f'ffmpeg -i {inFileName} -ss {start} -c copy "{inFileName}{part_count}.mp4" {redir}'
os.system(cmd2)
cmd2 = f'ffmpeg -i {inFileName}{part_count}.mp4 -ss 00:00:01 -vframes 1 {inFileName}{part_count}.mp4.jpg'
os.system(cmd2)
time.sleep(3)
os.remove(logFilePath)
