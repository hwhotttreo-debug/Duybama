import discord
from discord.ext import commands
import asyncio
import os
import re
import time
import json
import base64
import random
import threading
import requests
from discord import ButtonStyle
from discord.ui import Button, Modal, TextInput
from datetime import datetime
from typing import Dict, Any

# Nhập dữ liệu khi khởi chạy (bỏ input đi)
TOKEN = "MTQzNjQwODc5NTIwMTkyOTI0Ng.G4TILB.XS3lOPCwMxgIwHWDTrms5NwYo5Al_Wtcghqx14"
IDADMIN_GOC = 1259541498278707213# dán ID Discord của bạn vào đây (bỏ ngoặc kép)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'\033[35m{bot.user} đã kết nối thành công')

# RAM lưu trạng thái
admins = [IDADMIN_GOC]
saved_files = {}
running_tasks = {}
active_tokens = {}
discord_threads = {}
discord_states = {}

# Lưu thông tin task
task_info = {}

@bot.command()
async def add(ctx, member: str):
    if ctx.author.id != IDADMIN_GOC:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    
    # Try to parse as mention first
    try:
        # Check if it's a mention
        if member.startswith('<@') and member.endswith('>'):
            member_id = int(member[2:-1].replace('!', ''))  # Remove <@ > and ! if present
        else:
            member_id = int(member)  # Try to parse as raw ID
        
        # Try to get the user
        try:
            target_member = await bot.fetch_user(member_id)
        except discord.NotFound:
            return await ctx.send("Không tìm thấy người dùng với ID này.")
            
        if target_member.id in admins:
            return await ctx.send("Người này đã là Owner rồi.")
            
        admins.append(target_member.id)
        await ctx.send(f"Đã thêm `{target_member.name}` (ID: {target_member.id}) vào danh sách Owner.")
        
    except ValueError:
        await ctx.send("Vui lòng nhập ID hợp lệ hoặc đề cập (@tag) người dùng.")

@bot.command()
async def xoa(ctx, member: str):
    if ctx.author.id != IDADMIN_GOC:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    
    # Try to parse as mention first
    try:
        # Check if it's a mention
        if member.startswith('<@') and member.endswith('>'):
            member_id = int(member[2:-1].replace('!', ''))  # Remove <@ > and ! if present
        else:
            member_id = int(member)  # Try to parse as raw ID
        
        # Check if it's the root admin
        if member_id == IDADMIN_GOC:
            return await ctx.send("Không thể xóa admin gốc.")
            
        if member_id in admins:
            try:
                target_member = await bot.fetch_user(member_id)
                name = target_member.name
            except:
                name = str(member_id)
                
            admins.remove(member_id)
            await ctx.send(f"Đã xoá `{name}` (ID: {member_id}) khỏi danh sách Owner.")
        else:
            await ctx.send("Người này không có trong danh sách Owner.")
            
    except ValueError:
        await ctx.send("Vui lòng nhập ID hợp lệ hoặc đề cập (@tag) người dùng.")

@bot.command()
async def list(ctx):
    msg = "**Danh sách Owner hiện tại:**\n"
    for admin_id in admins:
        try:
            user = await bot.fetch_user(admin_id)
            if admin_id == IDADMIN_GOC:
                msg += f"- <@{IDADMIN_GOC}> **(Admin Gốc)**\n"
            else:
                msg += f"- **{user.name} - {admin_id} (Owner)**\n"
        except Exception as e:
            msg += f"- **{admin_id} (Không tìm được tên) (Owner)**\n"
    await ctx.send(msg)

# Lưu file
@bot.command()
async def setfile(ctx):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    if not ctx.message.attachments:
        return await ctx.send("Vui lòng đính kèm file.")
    admin_id = str(ctx.author.id)
    file = ctx.message.attachments[0]
    filename = file.filename
    os.makedirs(f"data/{admin_id}", exist_ok=True)
    path = f"data/{admin_id}/{filename}"
    await file.save(path)
    await ctx.send(f"Đã lưu file `{filename}` vào thư mục của bạn.")

# Xem các file đã lưu
@bot.command()
async def xemfileset(ctx):
    admin_id = str(ctx.author.id)
    folder = f"data/{admin_id}"
    if not os.path.exists(folder):
        return await ctx.send("Bạn chưa lưu file nào.")
    files = os.listdir(folder)
    if not files:
        return await ctx.send("Bạn chưa lưu file nào.")
    msg = f"**Danh sách file của `{ctx.author.name}`:**\n"
    for fname in files:
        path = os.path.join(folder, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                preview = f.read(100).replace('\n', ' ')
                msg += f"`{fname}`: {preview}...\n"
        except:
            msg += f"`{fname}`: (Không đọc được nội dung)\n"
    await ctx.send(msg)


def get_uid(cookie):
    try:
        return re.search('c_user=(\\d+)', cookie).group(1)
    except:
        return '0'

def get_fb_dtsg_jazoest(cookie, target_id):
    try:
        response = requests.get(
            f'https://mbasic.facebook.com/privacy/touch/block/confirm/?bid={target_id}&ret_cancel&source=profile',
            headers={'cookie': cookie, 'user-agent': 'Mozilla/5.0'})
        fb_dtsg = re.search('name="fb_dtsg" value="([^"]+)"', response.text).group(1)
        jazoest = re.search('name="jazoest" value="([^"]+)"', response.text).group(1)
        return fb_dtsg, jazoest
    except:
        return None, None

def send_message(idcanspam, fb_dtsg, jazoest, cookie, message_body):
    try:
        uid = get_uid(cookie)
        timestamp = int(time.time() * 1000)
        data = {
            'thread_fbid': idcanspam,
            'action_type': 'ma-type:user-generated-message',
            'body': message_body,
            'client': 'mercury',
            'author': f'fbid:{uid}',
            'timestamp': timestamp,
            'source': 'source:chat:web',
            'offline_threading_id': str(timestamp),
            'message_id': str(timestamp),
            'ephemeral_ttl_mode': '',
            '__user': uid,
            '__a': '1',
            '__req': '1b',
            '__rev': '1015919737',
            'fb_dtsg': fb_dtsg,
            'jazoest': jazoest
        }
        headers = {
            'Cookie': cookie,
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.facebook.com',
            'Referer': f'https://www.facebook.com/messages/t/{idcanspam}'
        }
        response = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers)
        return response.status_code == 200
    except:
        return False

# Gửi loop
async def spam_loop(ctx, idgroup, cookie, filename, delay, admin_id):
    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, idgroup)
    if not fb_dtsg:
        await ctx.send("Cookie không hợp lệ.")
        return
    path = saved_files.get(filename)
    if not path:
        await ctx.send("Không tìm thấy file.")
        return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    start_time = time.time()
    task_info[idgroup] = {'admin_id': admin_id, 'start_time': start_time, 'task_count': 0}
    
    print(f"[+] Bắt đầu spam vào nhóm {idgroup}...")
    await ctx.send(f"Bắt đầu gửi tin nhắn đến nhóm `{idgroup}`...")
    
    while idgroup in running_tasks:
        success = send_message(idgroup, fb_dtsg, jazoest, cookie, content)
        if success:
            print(f"[+] Đã gửi 1 tin nhắn vào nhóm {idgroup}")
        else:
            print(f"[!] Gửi thất bại vào nhóm {idgroup}")
        await asyncio.sleep(float(delay))

@bot.command()
async def treo(ctx, id_box: str, cookie: str, filename: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    admin_id = str(ctx.author.id)
    file_path = f"data/{admin_id}/{filename}"

    if not os.path.exists(file_path):
        return await ctx.send(f"File `{filename}` không tồn tại trong thư mục của bạn.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(file_path, 'r', encoding='utf-8') as f:
        message_body = f.read().strip()

    print(f"[+] Đã bắt đầu spam box {id_box} với file {filename} (delay: {speed}s)")
    await ctx.send(f"**[INFO]** Bắt đầu spam box `{id_box}` với file `{filename}` mỗi `{speed}` giây.")

    task_id = f"ngonmess_{id_box}_{time.time()}"
    async def spam_loop_task():
        while True:
            success = send_message(id_box, fb_dtsg, jazoest, cookie, message_body)
            if success:
                print(f"[+] Đã gửi 1 tin nhắn vào box {id_box}")
            else:
                print(f"[!] Gửi thất bại vào box {id_box}")
            await asyncio.sleep(speed)

    task = asyncio.create_task(spam_loop_task())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"đã tạo task")
    
@bot.command()
async def stoptask(ctx, task_number: str = None):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    is_root_admin = (ctx.author.id == IDADMIN_GOC)
    user_tasks = []

    # Chỉ lấy task Facebook
    for task_id, info in task_info.items():
        if is_root_admin or info['admin_id'] == ctx.author.id:
            task_type = task_id.split('_')[0]
            box_id = task_id.split('_')[1]
            duration = str(datetime.now() - datetime.fromtimestamp(info['start_time'])).split('.')[0]
            
            try:
                admin = await bot.fetch_user(info['admin_id'])
                admin_name = admin.name
            except:
                admin_name = f"ID {info['admin_id']}"
            
            user_tasks.append({
                'id': task_id,
                'type': task_type,
                'box_id': box_id,
                'duration': duration,
                'admin': admin_name,
                'admin_id': info['admin_id']
            })

    if not user_tasks:
        return await ctx.send("Không có task nào đang chạy.")

    # Xử lý lệnh dừng task
    if task_number is not None:
        if task_number.lower() == 'all':
            stopped_count = 0
            for task in user_tasks:
                if is_root_admin or task['admin_id'] == ctx.author.id:
                    if task['id'] in running_tasks:
                        running_tasks[task['id']].cancel()
                        del running_tasks[task['id']]
                        del task_info[task['id']]
                        stopped_count += 1
            return await ctx.send(f"Đã dừng {stopped_count} task.")

        try:
            task_index = int(task_number) - 1
            if 0 <= task_index < len(user_tasks):
                task = user_tasks[task_index]
                if not is_root_admin and task['admin_id'] != ctx.author.id:
                    return await ctx.send("Bạn không có quyền dừng task này!")
                
                if task['id'] in running_tasks:
                    running_tasks[task['id']].cancel()
                    del running_tasks[task['id']]
                    del task_info[task['id']]
                    return await ctx.send(f"Đã dừng task số {task_number}.")
            return await ctx.send("Số task không hợp lệ.")
        except ValueError:
            return await ctx.send("Vui lòng nhập số task hoặc 'all'.")

    # Hiển thị danh sách task
    msg = "**Danh sách task đang chạy:**\n"
    msg += "(Bạn là admin gốc, có thể dừng mọi task)\n" if is_root_admin else ""
    
    for i, task in enumerate(user_tasks, 1):
        msg += f"{i}. {task['type']} - Box: {task['box_id']} - Owner: {task['admin']} (Đã chạy: {task['duration']})\n"
    
    msg += "\nNhập `.stoptask [số]` để dừng task hoặc `.stoptask all` để dừng tất cả"
    await ctx.send(msg)
 
@bot.command()
async def danhsachtask(ctx, task_number: str = None):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    is_root_admin = (ctx.author.id == IDADMIN_GOC)
    user_tasks = []

    # Chỉ lấy task Facebook
    for task_id, info in task_info.items():
        if is_root_admin or info['admin_id'] == ctx.author.id:
            task_type = task_id.split('_')[0]
            box_id = task_id.split('_')[1]
            duration = str(datetime.now() - datetime.fromtimestamp(info['start_time'])).split('.')[0]
            
            try:
                admin = await bot.fetch_user(info['admin_id'])
                admin_name = admin.name
            except:
                admin_name = f"ID {info['admin_id']}"
            
            user_tasks.append({
                'id': task_id,
                'type': task_type,
                'box_id': box_id,
                'duration': duration,
                'admin': admin_name,
                'admin_id': info['admin_id']
            })

    if not user_tasks:
        return await ctx.send("Không có task nào đang chạy.")

    # Xử lý lệnh dừng task
    if task_number is not None:
        if task_number.lower() == 'all':
            stopped_count = 0
            for task in user_tasks:
                if is_root_admin or task['admin_id'] == ctx.author.id:
                    if task['id'] in running_tasks:
                        running_tasks[task['id']].cancel()
                        del running_tasks[task['id']]
                        del task_info[task['id']]
                        stopped_count += 1
            return await ctx.send(f"Đã dừng {stopped_count} task.")

        try:
            task_index = int(task_number) - 1
            if 0 <= task_index < len(user_tasks):
                task = user_tasks[task_index]
                if not is_root_admin and task['admin_id'] != ctx.author.id:
                    return await ctx.send("Bạn không có quyền dừng task này!")
                
                if task['id'] in running_tasks:
                    running_tasks[task['id']].cancel()
                    del running_tasks[task['id']]
                    del task_info[task['id']]
                    return await ctx.send(f"Đã dừng task số {task_number}.")
            return await ctx.send("Số task không hợp lệ.")
        except ValueError:
            return await ctx.send("Vui lòng nhập số task hoặc 'all'.")

    # Hiển thị danh sách task
    msg = "**Danh sách task đang chạy:**\n"
    msg += "(Bạn là admin gốc, có thể dừng mọi task)\n" if is_root_admin else ""
    
    for i, task in enumerate(user_tasks, 1):
        msg += f"{i}. {task['type']} - Box: {task['box_id']} - Owner: {task['admin']} (Đã chạy: {task['duration']})\n"
    
    msg += "\nNhập `!stoptask [số]` để dừng task hoặc `!stoptask all` để dừng tất cả"
    await ctx.send(msg)
   
@bot.command()
async def nhay(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhay.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt` trong thư mục data.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    task_id = f"nhay_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            send_message(id_box, fb_dtsg, jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"đã tạo task")
        
@bot.command()
async def codelag(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhay.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt`.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

# Biểu tượng cố định
    task_id = f"codelag_{id_box}_{time.time()}"

    async def loop_codelag():
        index = 0
        while True:
            message = f"{lines[index]} {icon}"
            send_message(id_box, fb_dtsg, jazoest, cookie, message)
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_codelag())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"đã tạo task")

@bot.command()
async def tabcodelag(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("codelag_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task codelag nào chạy.")

    admin_list = list(admin_task_count.items())

    msg = "**Danh sách admin đang có task:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("codelag_"):
                box_id = task_id.split("_")[1]
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Box ID: {box_id} | Thời gian chạy: {formatted_time}")

        if not tasks:
            await ctx.send("Admin này không có task codelag nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi.")

# Lệnh tabnhay
@bot.command()
async def tabnhaymess(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("nhay_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task nhay nào chạy.")

    admin_list = list(admin_task_count.items())

    msg = "**Danh sách admin đang có task:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("nhay_"):
                box_id = task_id.split("_")[1]
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Box ID: {box_id} | Thời gian chạy: {formatted_time}")

        if not tasks:
            await ctx.send("Admin này không có task nhay nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi.")
def get_guid():
    section_length = int(time.time() * 1000)
    
    def replace_func(c):
        nonlocal section_length
        r = (section_length + random.randint(0, 15)) % 16
        section_length //= 16
        return hex(r if c == "x" else (r & 7) | 8)[2:]

    return "".join(replace_func(c) if c in "xy" else c for c in "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx")

# Hàm chuẩn hóa cookie
def normalize_cookie(cookie, domain='www.facebook.com'):
    headers = {
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(f'https://{domain}/', headers=headers, timeout=10)
        if response.status_code == 200:
            set_cookie = response.headers.get('Set-Cookie', '')
            new_tokens = re.findall(r'([a-zA-Z0-9_-]+)=[^;]+', set_cookie)
            cookie_dict = dict(re.findall(r'([a-zA-Z0-9_-]+)=([^;]+)', cookie))
            for token in new_tokens:
                if token not in cookie_dict:
                    cookie_dict[token] = ''
            return ';'.join(f'{k}={v}' for k, v in cookie_dict.items() if v)
    except:
        pass
    return cookie

# Hàm lấy thông tin từ cookie (giữ nguyên theo code bạn gửi)
def get_uid_fbdtsg(ck):
    try:
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Connection': 'keep-alive',
            'Cookie': ck,
            'Host': 'www.facebook.com',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        
        try:
            response = requests.get('https://www.facebook.com/', headers=headers)
            
            if response.status_code != 200:
                print(f"Status Code >> {response.status_code}")
                return None, None, None, None, None, None
                
            html_content = response.text
            
            user_id = None
            fb_dtsg = None
            jazoest = None
            
            script_tags = re.findall(r'<script id="__eqmc" type="application/json[^>]*>(.*?)</script>', html_content)
            for script in script_tags:
                try:
                    json_data = json.loads(script)
                    if 'u' in json_data:
                        user_param = re.search(r'__user=(\d+)', json_data['u'])
                        if user_param:
                            user_id = user_param.group(1)
                            break
                except:
                    continue
            
            fb_dtsg_match = re.search(r'"f":"([^"]+)"', html_content)
            if fb_dtsg_match:
                fb_dtsg = fb_dtsg_match.group(1)
            
            jazoest_match = re.search(r'jazoest=(\d+)', html_content)
            if jazoest_match:
                jazoest = jazoest_match.group(1)
            
            revision_match = re.search(r'"server_revision":(\d+),"client_revision":(\d+)', html_content)
            rev = revision_match.group(1) if revision_match else ""
            
            a_match = re.search(r'__a=(\d+)', html_content)
            a = a_match.group(1) if a_match else "1"
            
            req = "1b"
                
            return user_id, fb_dtsg, rev, req, a, jazoest
                
        except requests.exceptions.RequestException as e:
            print(f"Lỗi Kết Nối Khi Lấy UID/FB_DTSG: {e}")
            return get_uid_fbdtsg(ck)
            
    except Exception as e:
        print(f"Lỗi: {e}")
        return None, None, None, None, None, None

# Hàm lấy thông tin người dùng (giữ nguyên)
def get_info(uid: str, cookie: str, fb_dtsg: str, a: str, req: str, rev: str) -> Dict[str, Any]:
    try:
        form = {
            "ids[0]": uid,
            "fb_dtsg": fb_dtsg,
            "__a": a,
            "__req": req,
            "__rev": rev
        }
        
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': cookie,
            'Origin': 'https://www.facebook.com',
            'Referer': 'https://www.facebook.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        
        response = requests.post(
            "https://www.facebook.com/chat/user_info/",
            headers=headers,
            data=form
        )
        
        if response.status_code != 200:
            return {"error": f"Lỗi Kết Nối: {response.status_code}"}
        
        try:
            text_response = response.text
            if text_response.startswith("for (;;);"):
                text_response = text_response[9:]
            
            res_data = json.loads(text_response)
            
            if "error" in res_data:
                return {"error": res_data.get("error")}
            
            if "payload" in res_data and "profiles" in res_data["payload"]:
                return format_data(res_data["payload"]["profiles"])
            else:
                return {"error": f"Không Tìm Thấy Thông Tin Của {uid}"}
                
        except json.JSONDecodeError:
            return {"error": "Lỗi Khi Phân Tích JSON"}
            
    except Exception as e:
        print(f"Lỗi Khi Get Info: {e}")
        return {"error": str(e)}

# Hàm định dạng dữ liệu (giữ nguyên)
def format_data(profiles):
    if not profiles:
        return {"error": "Không Có Data"}
    
    first_profile_id = next(iter(profiles))
    profile = profiles[first_profile_id]
    
    return {
        "id": first_profile_id,
        "name": profile.get("name", ""),
        "url": profile.get("url", ""),
        "thumbSrc": profile.get("thumbSrc", ""),
        "gender": profile.get("gender", "")
    }

# Hàm gửi bình luận (đã sửa lỗi get_guid)
def cmt_gr_pst(cookie, grid, postIDD, ctn, user_id, fb_dtsg, rev, req, a, jazoest, uidtag=None, nametag=None):
    try:
        if not all([user_id, fb_dtsg, jazoest]):
            print("Thiếu user_id, fb_dtsg hoặc jazoest")
            return False
            
        pstid_enc = base64.b64encode(f"feedback:{postIDD}".encode()).decode()
        
        client_mutation_id = str(round(random.random() * 19))
        session_id = get_guid()  # Đã sửa: get_guid() được định nghĩa trước
        crt_time = int(time.time() * 1000)
        
        variables = {
            "feedLocation": "DEDICATED_COMMENTING_SURFACE",
            "feedbackSource": 110,
            "groupID": grid,
            "input": {
                "client_mutation_id": client_mutation_id,
                "actor_id": user_id,
                "attachments": None,
                "feedback_id": pstid_enc,
                "formatting_style": None,
                "message": {
                    "ranges": [],
                    "text": ctn
                },
                "attribution_id_v2": f"SearchCometGlobalSearchDefaultTabRoot.react,comet.search_results.default_tab,tap_search_bar,{crt_time},775647,391724414624676,,",
                "vod_video_timestamp": None,
                "is_tracking_encrypted": True,
                "tracking": [],
                "feedback_source": "DEDICATED_COMMENTING_SURFACE",
                "session_id": session_id
            },
            "inviteShortLinkKey": None,
            "renderLocation": None,
            "scale": 3,
            "useDefaultActor": False,
            "focusCommentID": None,
            "__relay_internal__pv__IsWorkUserrelayprovider": False
        }
        
        if uidtag and nametag:
            name_position = ctn.find(nametag)
            if name_position != -1:
                variables["input"]["message"]["ranges"] = [
                    {
                        "entity": {
                            "id": uidtag
                        },
                        "length": len(nametag),
                        "offset": name_position
                    }
                ]
            
        payload = {
            'av': user_id,
            '__crn': 'comet.fbweb.CometGroupDiscussionRoute',
            'fb_dtsg': fb_dtsg,
            'jazoest': jazoest,
            'fb_api_caller_class': 'RelayModern',
            'fb_api_req_friendly_name': 'useCometUFICreateCommentMutation',
            'variables': json.dumps(variables),
            'server_timestamps': 'true',
            'doc_id': '24323081780615819'
        }
        
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': cookie,
            'Origin': 'https://www.facebook.com',
            'Referer': f'https://www.facebook.com/groups/{grid}',
            'User-Agent': 'python-http/0.27.0'
        }
        
        response = requests.post('https://www.facebook.com/api/graphql', data=payload, headers=headers)
        print(f"Mã trạng thái cho bài {postIDD}: {response.status_code}")
        print(f"Phản hồi: {response.text[:500]}...")  # In 500 ký tự đầu
        
        if response.status_code == 200:
            try:
                json_response = response.json()
                if 'errors' in json_response:
                    print(f"Lỗi GraphQL: {json_response['errors']}")
                    return False
                if 'data' in json_response and 'comment_create' in json_response['data']:
                    print("Bình luận đã được đăng")
                    return True
                print("Không tìm thấy comment_create trong phản hồi")
                return False
            except ValueError:
                print("Phản hồi JSON không hợp lệ")
                return False
        else:
            return False
    except Exception as e:
        print(f"Lỗi khi gửi bình luận: {e}")
        return False

# Hàm lấy ID bài viết và nhóm
def extract_post_group_id(post_link):
    post_match = re.search(r'facebook\.com/.+/permalink/(\d+)', post_link)
    group_match = re.search(r'facebook\.com/groups/(\d+)', post_link)
    if not post_match or not group_match:
        return None, None
    return post_match.group(1), group_match.group(1)

# Lệnh nhaytop
@bot.command()
async def nhaytop(ctx, cookie: str, delay: float):
    if ctx.author.id not in admins:
        await ctx.send("Bạn không có quyền sử dụng lệnh này.")
        return

    # Kiểm tra file nhay.txt
    path = "chui.txt"
    if not os.path.exists(path):
        await ctx.send("Không tìm thấy file `nhay.txt`.")
        return

    # Yêu cầu link bài viết
    await ctx.send("Vui lòng nhập link bài viết (ví dụ: https://facebook.com/groups/123/permalink/456):")
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        post_link = msg.content.strip()
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ nhập link bài viết.")
        return

    # Lấy post_id và group_id
    post_id, group_id = extract_post_group_id(post_link)
    if not post_id or not group_id:
        await ctx.send("Link bài viết không hợp lệ hoặc không tìm được group_id.")
        return

    # Chuẩn hóa cookie
    cookie = normalize_cookie(cookie)
    
    # Kiểm tra cookie
    user_id, fb_dtsg, rev, req, a, jazoest = get_uid_fbdtsg(cookie)
    if not user_id or not fb_dtsg or not jazoest:
        await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")
        return

    # Đọc nội dung từ chui.txt
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        await ctx.send("File `nhay.txt` rỗng.")
        return

    task_id = f"nhaytop_{post_id}_{time.time()}"
    
    async def loop_nhaytop():
        index = 0
        while True:
            message = lines[index]
            success = cmt_gr_pst(cookie, group_id, post_id, message, user_id, fb_dtsg, rev, req, a, jazoest)
            if success:
                print(f"[+] Đã gửi bình luận vào bài {post_id}: {message}")  # Thông báo trên Termux
            else:
                print(f"[!] Gửi bình luận thất bại vào bài {post_id}")  # Thông báo trên Termux
            index = (index + 1) % len(lines)
            await asyncio.sleep(delay)

    task = asyncio.create_task(loop_nhaytop())
    running_tasks[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'post_id': post_id,
        'group_id': group_id
    }
    await ctx.send(f"Đã tạo task thành công")

@bot.command()
async def tabnhaytop(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("nhaytop_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task nhaytop nào chạy.")

    admin_list = list(admin_task_count.items())
    msg = "**Danh sách admin đang có task nhaytop:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("nhaytop_"):
                post_id = info['post_id']
                group_id = info['group_id']
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Group ID: {group_id}, Post ID: {post_id}\nThời gian chạy: {formatted_time}\n\n")

        if not tasks:
            await ctx.send("Admin này không có task nhaytop nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except ValueError:
        await ctx.send("Vui lòng nhập số hợp lệ.")
    except Exception as e:
        await ctx.send(f"Đã xảy ra lỗi: {str(e)}")
        
@bot.command()
async def treoso(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "so.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt` trong thư mục data.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    task_id = f"so_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            send_message(id_box, fb_dtsg, jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"đã tạo task")
    
@bot.command()
async def ideamess(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "chui.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt` trong thư mục data.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    task_id = f"cay_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            send_message(id_box, fb_dtsg, jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"")

@bot.command()
async def tabideamess(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("cay_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task ideamess nào chạy.")

    admin_list = list(admin_task_count.items())

    msg = "**Danh sách admin đang có task:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("nhay_"):
                box_id = task_id.split("_")[1]
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Box ID: {box_id} | Thời gian chạy: {formatted_time}")

        if not tasks:
            await ctx.send("Admin này không có task nhay nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi.")

@bot.command()
async def nhay2c(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "2c.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt` trong thư mục data.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    task_id = f"2c_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            send_message(id_box, fb_dtsg, jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"đã tạo task")

def send_message(idcanspam, fb_dtsg, jazoest, cookie, message_body, tag_uid=None, tag_name=None):
    try:
        uid = get_uid(cookie)
        timestamp = int(time.time() * 1000)
        
        data = {
            'thread_fbid': idcanspam,
            'action_type': 'ma-type:user-generated-message',
            'body': message_body,
            'client': 'mercury',
            'author': f'fbid:{uid}',
            'timestamp': timestamp,
            'source': 'source:chat:web',
            'offline_threading_id': str(timestamp),
            'message_id': str(timestamp),
            'ephemeral_ttl_mode': '',
            '__user': uid,
            '__a': '1',
            '__req': '1b',
            '__rev': '1015919737',
            'fb_dtsg': fb_dtsg,
            'jazoest': jazoest
        }
        
        if tag_uid and tag_name:
            tag_text = f"@{tag_name}"
            tag_position = message_body.find(tag_text)
            if tag_position != -1:
                data['profile_xmd[0][offset]'] = str(tag_position)
                data['profile_xmd[0][length]'] = str(len(tag_text))
                data['profile_xmd[0][id]'] = tag_uid
                data['profile_xmd[0][type]'] = 'p'
        
        headers = {
            'Cookie': cookie,
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.facebook.com',
            'Referer': f'https://www.facebook.com/messages/t/{idcanspam}'
        }
        
        response = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers)
        return response.status_code == 200
    except:
        return False

@bot.command()
async def nhaytag(ctx, id_box: str, cookie: str, tag_uid: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhay.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt` trong thư mục data.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    tag_name = None
    try:
        user_id, fb_dtsg, rev, req, a, jazoest = get_uid_fbdtsg(cookie)
        if user_id and fb_dtsg:
            info = get_info(tag_uid, cookie, fb_dtsg, a, req, rev)
            if "error" not in info:
                tag_name = info.get("name")
    except:
        pass

    if not tag_name:
        await ctx.send("Không thể lấy tên từ ID, vui lòng nhập tên thủ công (ví dụ: Nguyen Van A):")
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
            
        try:
            msg = await bot.wait_for('message', timeout=30.0, check=check)
            tag_name = msg.content.strip()
            if not tag_name:
                return await ctx.send("Tên không được để trống!")
        except asyncio.TimeoutError:
            return await ctx.send("Hết thời gian chờ nhập tên.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    task_id = f"nhaytag_{id_box}_{time.time()}"
    
    async def loop_nhaytag():
        index = 0
        while True:
            message = f"{lines[index]} @{tag_name}"
            success = send_message(id_box, fb_dtsg, jazoest, cookie, message, tag_uid, tag_name)
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhaytag())
    running_tasks[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id, 
        'start_time': time.time(),
        'tag_uid': tag_uid,
        'tag_name': tag_name
    }
    await ctx.send(f"tạo task thành công")
            
@bot.command()
async def tabnhaytag(ctx):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    # Lấy tất cả task nhaytag đang chạy
    nhaytag_tasks = [task_id for task_id in task_info if task_id.startswith("nhaytag_")]

    if not nhaytag_tasks:
        return await ctx.send("Hiện không có task nhaytag nào đang chạy.")

    # Phân loại task theo admin
    admin_task_count = {}
    for task_id in nhaytag_tasks:
        admin_id = task_info[task_id]['admin_id']
        if admin_id not in admin_task_count:
            admin_task_count[admin_id] = 0
        admin_task_count[admin_id] += 1

    # Hiển thị danh sách admin
    admin_list = list(admin_task_count.items())
    msg = "**Danh sách admin đang có task nhaytag:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("nhaytag_"):
                box_id = task_id.split("_")[1]
                start_time = info['start_time']
                duration = str(datetime.now() - datetime.fromtimestamp(start_time)).split('.')[0]
                tag_name = info.get('tag_name', 'Không xác định')
                tasks.append(f"Box ID: {box_id} | Tag: {tag_name} | Thời gian chạy: {duration}")

        if not tasks:
            await ctx.send("Admin này không có task nhaytag nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except ValueError:
        await ctx.send("Vui lòng nhập số hợp lệ.")
    except Exception as e:
        await ctx.send(f"Đã xảy ra lỗi: {str(e)}")

@bot.command()
async def nhayicon(ctx, id_box: str, cookie: str, icon: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhayicon.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt` trong thư mục data.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    task_id = f"nhayicon_{id_box}_{time.time()}"
    
    async def loop_nhayicon():
        index = 0
        while True:
            # Thêm icon vào cuối mỗi tin nhắn
            message = f"{lines[index]}{icon}"
            success = send_message(id_box, fb_dtsg, jazoest, cookie, message)
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhayicon())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"đã tạo task")
            
@bot.command()
async def tabnhayicon(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("nhayicon_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task nhayicon nào chạy.")

    admin_list = list(admin_task_count.items())

    msg = "**Danh sách admin đang có task nhayicon:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("nhayicon_"):
                box_id = task_id.split("_")[1]
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Box ID: {box_id} | Icon: {icon} | Thời gian chạy: {formatted_time}")

        if not tasks:
            await ctx.send("Admin này không có task nhayicon nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi.")

@bot.command()
async def treotop(ctx, cookie: str, delay: float, filename: str):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này")

    # 1. Kiểm tra file trong thư mục cá nhân
    file_path = f"data/{ctx.author.id}/{filename}"
    if not os.path.exists(file_path):
        return await ctx.send(f"Không tìm thấy file `{filename}` trong thư mục của bạn")

    # 2. Đọc TOÀN BỘ nội dung file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_content = f.read().strip()
            
        if len(full_content) > 8000:
            return await ctx.send("Nội dung quá dài (tối đa 8000 ký tự)")
        if not full_content:
            return await ctx.send("File không có nội dung")
    except UnicodeDecodeError:
        return await ctx.send("Lỗi định dạng file (dùng UTF-8)")
    except Exception as e:
        return await ctx.send(f"Lỗi đọc file: {str(e)}")

    # 3. Yêu cầu link bài viết
    await ctx.send("🔗 Nhập link bài viết Facebook (VD: https://facebook.com/groups/123/permalink/456):")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        post_link = msg.content.strip()
    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ nhập link")

    # 4. Trích xuất ID
    post_id, group_id = extract_post_group_id(post_link)
    if not post_id or not group_id:
        return await ctx.send("Link bài viết không hợp lệ")

    # 5. Kiểm tra cookie
    cookie = normalize_cookie(cookie)
    user_id, fb_dtsg, rev, req, a, jazoest = get_uid_fbdtsg(cookie)
    if not user_id or not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ")

    # 6. Tạo task gửi NGUYÊN VĂN
    task_id = f"treotop_full_{post_id}_{int(time.time())}"
    
    async def spam_task():
        while task_id in running_tasks:
            try:
                success = cmt_gr_pst(
                    cookie=cookie,
                    grid=group_id,
                    postIDD=post_id,
                    ctn=full_content,  # Gửi nguyên văn
                    user_id=user_id,
                    fb_dtsg=fb_dtsg,
                    rev=rev,
                    req=req,
                    a=a,
                    jazoest=jazoest
                )
                
                if success:
                    print(f"[✅] Đã Treo Thành Công Vào Post {post_id}")
                else:
                    print(f"[❌] Gửi thất bại post {post_id}")
                    
                await asyncio.sleep(delay)
            except Exception as e:
                print(f"[🔥] Lỗi: {str(e)}")
                await asyncio.sleep(10)

    running_tasks[task_id] = asyncio.create_task(spam_task())
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'post_id': post_id,
        'group_id': group_id,
        'file_path': file_path,
        'content_preview': full_content[:100] + '...' if len(full_content) > 100 else full_content,
        'type': 'treotop_full'  # Đánh dấu gửi full content
    }
    
    await ctx.send(
        f"Đã Bắt Đầu Treo Top\n"
        f"├ File Ngôn: `{filename}`\n"
        f"├ Post: `{post_id}`\n"
        f"├ Delay: {delay}s\n"
        f"└ Dừng: **`.stoptask {len(running_tasks)}`**"
    )

def send_message_with_image(idcanspam, fb_dtsg, jazoest, cookie, message_body, image_url=None):
    try:
        uid = get_uid(cookie)
        timestamp = int(time.time() * 1000)
        
        # Bước 1: Tải ảnh về trước
        image_data = None
        if image_url:
            try:
                response = requests.get(image_url, stream=True)
                if response.status_code == 200:
                    image_data = response.content
            except Exception as e:
                print(f"Lỗi khi tải ảnh: {e}")
                return False

        # Bước 2: Tạo payload gửi tin nhắn
        data = {
            'thread_fbid': idcanspam,
            'action_type': 'ma-type:user-generated-message',
            'body': message_body,
            'client': 'mercury',
            'author': f'fbid:{uid}',
            'timestamp': timestamp,
            'source': 'source:chat:web',
            'offline_threading_id': str(timestamp),
            'message_id': str(timestamp),
            'ephemeral_ttl_mode': '',
            '__user': uid,
            '__a': '1',
            '__req': '1b',
            '__rev': '1015919737',
            'fb_dtsg': fb_dtsg,
            'jazoest': jazoest
        }

        headers = {
            'Cookie': cookie,
            'User-Agent': 'Mozilla/5.0',
            'Origin': 'https://www.facebook.com',
            'Referer': f'https://www.facebook.com/messages/t/{idcanspam}'
        }

        # Bước 3: Gửi tin nhắn kèm ảnh
        if image_data:
            # Tạo boundary ngẫu nhiên
            boundary = '----WebKitFormBoundary' + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
            
            # Tạo multipart form data
            form_data = []
            
            # Thêm các trường dữ liệu
            for key, value in data.items():
                form_data.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n')
            
            # Thêm phần ảnh
            form_data.append(
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="file"; filename="image.jpg"\r\n'
                f'Content-Type: image/jpeg\r\n\r\n'
            )
            
            # Ghép tất cả lại
            body = b''
            for part in form_data:
                body += part.encode('utf-8')
            body += image_data
            body += f'\r\n--{boundary}--\r\n'.encode('utf-8')
            
            headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
            response = requests.post(
                'https://www.facebook.com/messaging/send/',
                data=body,
                headers=headers
            )
        else:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            response = requests.post(
                'https://www.facebook.com/messaging/send/',
                data=data,
                headers=headers
            )
            
        return response.status_code == 200
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn: {e}")
        return False

@bot.command()
async def listbox(ctx, cookie: str, limit: int = 100):
    """Lấy danh sách nhóm Facebook từ cookie với phân trang"""
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    # Kiểm tra giới hạn
    if limit < 1 or limit > 500:
        return await ctx.send("Lỗi: Giới hạn phải từ 1-500 nhóm!")

    # Hiển thị thông báo đang xử lý
    processing_msg = await ctx.send("Đang lấy danh sách box, vui lòng chờ...")

    class FacebookThreadExtractor:
        def __init__(self, cookie):
            self.cookie = cookie
            self.session = requests.Session()
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
            ]
            self.facebook_tokens = {}
            
        def get_facebook_tokens(self):
            headers = {
                'Cookie': self.cookie,
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            }
            
            sites = ['https://www.facebook.com', 'https://mbasic.facebook.com']
            
            for site in sites:
                try:
                    response = self.session.get(site, headers=headers, timeout=10)
                    c_user_match = re.search(r"c_user=(\d+)", self.cookie)
                    if c_user_match:
                        self.facebook_tokens["FacebookID"] = c_user_match.group(1)
                    
                    fb_dtsg_match = re.search(r'"token":"(.*?)"', response.text) or re.search(r'name="fb_dtsg" value="(.*?)"', response.text)
                    if fb_dtsg_match:
                        self.facebook_tokens["fb_dtsg"] = fb_dtsg_match.group(1)
                    
                    jazoest_match = re.search(r'jazoest=(\d+)', response.text)
                    if jazoest_match:
                        self.facebook_tokens["jazoest"] = jazoest_match.group(1)
                    
                    if self.facebook_tokens.get("fb_dtsg") and self.facebook_tokens.get("jazoest"):
                        break
                        
                except Exception:
                    continue
            
            self.facebook_tokens.update({
                "__rev": "1015919737",
                "__req": "1b",
                "__a": "1",
                "__comet_req": "15"
            })
            
            return len(self.facebook_tokens) > 4
        
        def get_thread_list(self, limit=100):
            if not self.get_facebook_tokens():
                return {"error": "Không thể lấy token từ Facebook. Kiểm tra lại cookie."}
            
            form_data = {
                "av": self.facebook_tokens.get("FacebookID", ""),
                "__user": self.facebook_tokens.get("FacebookID", ""),
                "__a": self.facebook_tokens["__a"],
                "__req": self.facebook_tokens["__req"],
                "__hs": "19234.HYP:comet_pkg.2.1..2.1",
                "dpr": "1",
                "__ccg": "EXCELLENT",
                "__rev": self.facebook_tokens["__rev"],
                "__comet_req": self.facebook_tokens["__comet_req"],
                "fb_dtsg": self.facebook_tokens.get("fb_dtsg", ""),
                "jazoest": self.facebook_tokens.get("jazoest", ""),
                "lsd": "null",
                "__spin_r": self.facebook_tokens.get("client_revision", ""),
                "__spin_b": "trunk",
                "__spin_t": str(int(time.time())),
            }
            
            queries = {
                "o0": {
                    "doc_id": "3336396659757871",
                    "query_params": {
                        "limit": limit,
                        "before": None,
                        "tags": ["INBOX"],
                        "includeDeliveryReceipts": False,
                        "includeSeqID": True,
                    }
                }
            }
            
            form_data["queries"] = json.dumps(queries)
            
            headers = {
                'Cookie': self.cookie,
                'User-Agent': random.choice(self.user_agents),
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
                'Origin': 'https://www.facebook.com',
                'Referer': 'https://www.facebook.com/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'X-FB-Friendly-Name': 'MessengerThreadListQuery',
                'X-FB-LSD': 'null'
            }
            
            try:
                response = self.session.post(
                    'https://www.facebook.com/api/graphqlbatch/',
                    data=form_data,
                    headers=headers,
                    timeout=15
                )
                
                if response.status_code != 200:
                    return {"error": f"HTTP Error: {response.status_code}"}
                
                response_text = response.text.split('{"successful_results"')[0]
                data = json.loads(response_text)
                
                if "o0" not in data:
                    return {"error": "Không tìm thấy dữ liệu thread list"}
                
                if "errors" in data["o0"]:
                    return {"error": f"Facebook API Error: {data['o0']['errors'][0]['summary']}"}
                
                threads = data["o0"]["data"]["viewer"]["message_threads"]["nodes"]
                thread_list = []
                
                for thread in threads:
                    if not thread.get("thread_key") or not thread["thread_key"].get("thread_fbid"):
                        continue
                    
                    thread_list.append({
                        "thread_id": thread["thread_key"]["thread_fbid"],
                        "thread_name": thread.get("name", "Không có tên")
                    })
                
                return {
                    "success": True,
                    "thread_count": len(thread_list),
                    "threads": thread_list
                }
                
            except json.JSONDecodeError as e:
                return {"error": f"Lỗi parse JSON: {str(e)}"}
            except Exception as e:
                return {"error": f"Lỗi không xác định: {str(e)}"}

    # Lấy dữ liệu box
    extractor = FacebookThreadExtractor(cookie)
    result = extractor.get_thread_list(limit=limit)
    
    await processing_msg.delete()
    
    if "error" in result:
        return await ctx.send(f"Lỗi: {result['error']}")
    
    threads = result['threads']
    pages = []
    items_per_page = 10
    
    for i in range(0, len(threads), items_per_page):
        pages.append(threads[i:i + items_per_page])
    
    if not threads:
        return await ctx.send("Không tìm thấy box nào!")

    # Chỉ lấy 25 box đầu tiên
    threads_to_show = threads[:25]
    
    # Tạo embed hiển thị
    embed = discord.Embed(
        title=f"Danh Sách Box",
        color=0xB8F0FF
    )
    
    for i, thread in enumerate(threads_to_show, 1):
        thread_name = thread.get('thread_name', 'Không có tên') or 'Không có tên'
        display_name = f"{thread_name[:50]}{'...' if len(thread_name) > 50 else ''}"
        
        embed.add_field(
            name=f"{i}. {display_name}",
            value=f"ID: {thread['thread_id']}",
            inline=False
        )
    
    await ctx.send(embed=embed)

# Thêm vào bot.py (phần commands)

@bot.command()
async def nhaynamebox(ctx, id_box: str, cookie: str, speed: float):
    """Liên tục đổi tên box Facebook với nội dung từ file chui.txt"""
    if ctx.author.id not in admins:
        return await ctx.send("❌ Bạn không có quyền sử dụng lệnh này")

    # 1. Kiểm tra và đọc file chui.txt
    try:
        with open('chui.txt', 'r', encoding='utf-8') as f:
            names = [line.strip() for line in f if line.strip()]
            if not names:
                return await ctx.send("⚠️ File chui.txt trống hoặc không có nội dung")
    except Exception as e:
        return await ctx.send(f"❌ Lỗi khi đọc file chui.txt: {str(e)}")

    # 2. Lấy thông tin Facebook từ cookie
    try:
        dataFB = dataGetHome(cookie)
        if "FacebookID" not in dataFB or not dataFB.get("fb_dtsg"):
            return await ctx.send("⚠️ Cookie không hợp lệ hoặc thiếu thông tin đăng nhập")
    except Exception as e:
        return await ctx.send(f"❌ Lỗi khi xử lý cookie: {str(e)}")

    # 3. Tạo và chạy task
    task_id = f"nhayname_{id_box}_{int(time.time())}"
    
    async def name_change_task():
        index = 0
        while task_id in running_tasks:
            try:
                current_name = names[index]
                result = tenbox(current_name, id_box, dataFB)
                
                if result.get('success'):
                    log_msg = f"Đã đổi tên box {id_box} thành: {current_name}"
                    print(log_msg)
                else:
                    error_msg = f"Lỗi khi đổi tên: {result.get('error', 'Không rõ lỗi')}"
                    print(error_msg)
                
                index = (index + 1) % len(names)
                await asyncio.sleep(speed)
                
            except Exception as e:
                error_msg = f"⚠️ Có lỗi xảy ra: {str(e)}"
                print(error_msg)
                await asyncio.sleep(10)  # Chờ 10s nếu có lỗi

    running_tasks[task_id] = asyncio.create_task(name_change_task())
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'thread_id': id_box,
        'names': names,
        'current_index': 0,
        'type': 'nhaynamebox'
    }
    
    # 4. Gửi thông báo bắt đầu
    embed = discord.Embed(
        title="Bắt Đầu Nhây Name Box",
        description=f"ID Box {id_box}",
        color=0xB8F0FF
    )
    embed.add_field(name="Delay", value=f"{speed} giây", inline=True)
    embed.add_field(name="Dừng task", value=f"Dùng lệnh `!stoptask {len(running_tasks)}`", inline=False)
    
    await ctx.send(embed=embed)

# ========== API FUNCTIONS ==========

def digitToChar(digit):
    if digit < 10:
        return str(digit)
    return chr(ord("a") + digit - 10)

def str_base(number, base):
    if number < 0:
        return "-" + str_base(-number, base)
    (d, m) = divmod(number, base)
    if d > 0:
        return str_base(d, base) + digitToChar(m)
    return digitToChar(m)

def parse_cookie_string(cookie_string):
    cookie_dict = {}
    cookies = cookie_string.split(";")

    for cookie in cookies:
        if "=" in cookie:
            key, value = cookie.split("=")
        else:
            pass
        try: 
            cookie_dict[key] = value
        except: 
            pass

    return cookie_dict

def Headers(setCookies, dataForm=None, Host=None):
    if (Host == None): Host = "www.facebook.com"
    headers = {}
    headers["Host"] = Host
    headers["Connection"] = "keep-alive"
    if (dataForm != None):
        headers["Content-Length"] = str(len(dataForm))
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
    headers["Accept"] = "*/*"
    headers["Origin"] = "https://" + Host
    headers["Sec-Fetch-Site"] = "same-origin"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Referer"] = "https://" + Host
    headers["Accept-Language"] = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
    
    return headers

def mainRequests(urlRequests, dataForm, setCookies):
    return {
        "headers": Headers(setCookies, dataForm),
        "timeout": 5,
        "url": urlRequests,
        "data": dataForm,
        "cookies": parse_cookie_string(setCookies),
        "verify": True
    }

def gen_threading_id():
    return str(
        int(format(int(time.time() * 1000), "b") + 
        ("0000000000000000000000" + 
        format(int(random.random() * 4294967295), "b"))
        [-22:], 2)
    )

def dataGetHome(setCookies):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    ]
    
    dictValueSaved = {}
    
    try:
        c_user = re.search(r"c_user=(\d+)", setCookies)
        if c_user:
            dictValueSaved["FacebookID"] = c_user.group(1)
        else:
            dictValueSaved["FacebookID"] = "Unable to retrieve data for FacebookID. Cookie không hợp lệ."
    except:
        dictValueSaved["FacebookID"] = "Unable to retrieve data for FacebookID. It's possible that they have been deleted or modified."
    
    headers = {
        'Cookie': setCookies,
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,/;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    }
    
    sites_to_try = ['https://www.facebook.com', 'https://mbasic.facebook.com', 'https://m.facebook.com']
    fb_dtsg_found = False
    jazoest_found = False
    
    params_to_extract = {
        "fb_dtsg": None,
        "fb_dtsg_ag": None,
        "jazoest": None,
        "hash": None,
        "sessionID": None,
        "clientRevision": None
    }
    
    for site in sites_to_try:
        if fb_dtsg_found and jazoest_found:
            break
            
        try:
            response = requests.get(site, headers=headers)
            
            if not fb_dtsg_found:
                fb_dtsg_match = re.search(r'"token":"(.*?)"', response.text)
                if not fb_dtsg_match:
                    fb_dtsg_match = re.search(r'name="fb_dtsg" value="(.*?)"', response.text)
                
                if fb_dtsg_match:
                    params_to_extract["fb_dtsg"] = fb_dtsg_match.group(1)
                    fb_dtsg_found = True
            
            if not jazoest_found:
                jazoest_match = re.search(r'jazoest=(\d+)', response.text)
                if jazoest_match:
                    params_to_extract["jazoest"] = jazoest_match.group(1)
                    jazoest_found = True
            
            fb_dtsg_ag_match = re.search(r'async_get_token":"(.*?)"', response.text)
            if fb_dtsg_ag_match:
                params_to_extract["fb_dtsg_ag"] = fb_dtsg_ag_match.group(1)
            
            hash_match = re.search(r'hash":"(.*?)"', response.text)
            if hash_match:
                params_to_extract["hash"] = hash_match.group(1)
            
            session_match = re.search(r'sessionId":"(.*?)"', response.text)
            if session_match:
                params_to_extract["sessionID"] = session_match.group(1)
            
            revision_match = re.search(r'client_revision":(\d+)', response.text)
            if revision_match:
                params_to_extract["clientRevision"] = revision_match.group(1)
                
        except Exception as e:
            continue
    
    for param, value in params_to_extract.items():
        if value:
            dictValueSaved[param] = value
        else:
            dictValueSaved[param] = f"Unable to retrieve data for {param}. It's possible that they have been deleted or modified."
    
    dictValueSaved["__rev"] = "1015919737"
    dictValueSaved["__req"] = "1b"
    dictValueSaved["__a"] = "1"
    dictValueSaved["cookieFacebook"] = setCookies
    
    return dictValueSaved

def tenbox(newTitle, threadID, dataFB):
    if not newTitle or not threadID or not dataFB:
        return {
            "success": False,
            "error": "Thiếu thông tin bắt buộc: newTitle, threadID, hoặc dataFB"
        }
    try:
        messageAndOTID = gen_threading_id()
        current_timestamp = int(time.time() * 1000)
        form_data = {
            "client": "mercury",
            "action_type": "ma-type:log-message",
            "author": f"fbid:{dataFB['FacebookID']}",
            "thread_id": str(threadID),
            "timestamp": current_timestamp,
            "timestamp_relative": str(int(time.time())),
            "source": "source:chat:web",
            "source_tags[0]": "source:chat",
            "offline_threading_id": messageAndOTID,
            "message_id": messageAndOTID,
            "threading_id": gen_threading_id(),
            "thread_fbid": str(threadID),
            "thread_name": str(newTitle),
            "log_message_type": "log:thread-name",
            "fb_dtsg": dataFB["fb_dtsg"],
            "jazoest": dataFB["jazoest"],
            "__user": str(dataFB["FacebookID"]),
            "__a": "1",
            "__req": "1",
            "__rev": dataFB.get("clientRevision", "1015919737")
        }
        url = "https://www.facebook.com/messaging/set_thread_name/"
        response = requests.post(**mainRequests(url, form_data, dataFB["cookieFacebook"]))
        if response.status_code == 200:
            try:
                response_data = response.json()
                if "error" in response_data:
                    return {
                        "success": False,
                        "error": f"Lỗi từ Facebook: {response_data.get('error')}"
                    }
                return {
                    "success": True,
                    "message": f"Đã đổi tên thành: {newTitle}"
                }
            except:
                return {
                    "success": True,
                    "message": f"Đã đổi tên thành: {newTitle} (parse JSON lỗi)"
                }
        else:
            return {
                "success": False,
                "error": f"HTTP Error: {response.status_code}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@bot.command()
async def menu(ctx):
    embed = discord.Embed(
        title="**🌊・Menu Bot **",
        description="Bot By **by 🪽nhatduy 🪽**",
        color=0xB8F0FF
    )
    
    embed.set_thumbnail(url="https://sf-static.upanhlaylink.com/img/image_2025110853ccae0c5df02f3fc215b2839515d3d9.jpg")
    
    # Nội dung menu chính
    embed.add_field(
        name="**👑・Owner VIP Commands**",
        value="""
🔹 **`!add`** — Thêm Người Vào Danh Sách Owner
🔹 **`!xoa`** — Xoá Người Dùng Khỏi Danh Sách Owner
🔹 **`!list`** — Xem Danh Sách Owner
        
**🪽・Bot Commands**
🪽 **`!treo`** — Treo Mess Bất Tử
🪽
🪽 **`!nhay`** — Nhây Mess Đến Chết
🪽 **`!nhayicon`** — Nhây Icon Mess
🪽 **`!nhaytag`** — Nhây Tag Mess
🪽 **`!nhay2c`** — Nhây 2 Chữ
🪽 **`!treoso`** — Treo Sớ Super Múp
🪽 **`!ideamess`** — Nhây Cay Mess
🪽 **`!codelag`** — Code Lag Mess
🪽 **`!nhaytop`** — Nhây Top Vip
🪽 **`!treotop`** — Treo Top Vip
🪽 **`!nhaynamebox`** — Nhây Tên Box
🪽 **`!listbox`** — Show Box Bằng Cookie
🪽 **`!setfile`** — Gửi Kèm File
🪽 **`!xemfileset`** — Xem File Lưu
🪽 **`!danhsachtask`** — Xem Danh Sách Task
🪽 **`!stoptask [số]`** — Xoá Task
🪽 **`!hdan`** — Cách Dùng Lệnh Bot
**`🌊 Bot Nhatduy 🌊`**
        """,
        inline=False
    )
    
    await ctx.send(embed=embed)
 
 
@bot.command()
async def hdan(ctx):
    embed = discord.Embed(
        title="『 **Hướng Dẫn Dùng Lệnh**』",
        description=f"""  
**`Hướng Dẫn`**

**`!treo <idbox> <cookie> <file.txt> <delay>`**
**`!nhay <idbox> <cookie> <delay>`**
**`!nhayicon <idbox> <cookie> <icon> <delay`**
**`!nhaytag <idbox> <cookie> <id> <delay>`**
**`!nhay2c <idbox> <cookie> <delay>`**
**`!treoso <idbox> <cookie> <delay>`**
**`!ideamess <idbox> <cookie> <delay>`**
**`!codelag <idbox> <cookie> <delay>`**
**`!nhaytop <cookie> <delay>`**
**`!treotop <cookie> <delay> <file.txt>`**
**`!nhaynamebox <idbox> <cookie> <delay>`**
**`!listbox <cookie>`**
""",
        color=0xB8F0FF
    )

    await ctx.send(embed=embed)

       
bot.run(TOKEN)