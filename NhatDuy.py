"use strict";

import os
import sys
import time
import ssl
import json
import random
import string
import hashlib
import threading
import re
from collections import defaultdict
from urllib.parse import urlparse, urlencode
from datetime import datetime
import requests
import psutil
import gc
from bs4 import BeautifulSoup
import paho.mqtt.client as mqtt

cookie_attempts = defaultdict(lambda: {'count': 0, 'last_reset': time.time(), 'banned_until': 0, 'permanent_ban': False})
cookie_delays = {}
active_threads = {}
cleanup_lock = threading.Lock()

def clr():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def handle_failed_connection(cookie_hash):
    global cookie_attempts
    
    current_time = time.time()
    
    if current_time - cookie_attempts[cookie_hash]['last_reset'] > 43200:
        cookie_attempts[cookie_hash]['count'] = 0
        cookie_attempts[cookie_hash]['last_reset'] = current_time
        cookie_attempts[cookie_hash]['banned_until'] = 0
    
    if cookie_attempts[cookie_hash]['banned_until'] > 0:
        ban_count = getattr(cookie_attempts[cookie_hash], 'ban_count', 0) + 1
        cookie_attempts[cookie_hash]['ban_count'] = ban_count
        
        if ban_count >= 5:
            cookie_attempts[cookie_hash]['permanent_ban'] = True
            print(f"Cookie {cookie_hash[:10]} Đã Bị Ngưng Hoạt Động Vĩnh Viễn Để Tránh Đầy Memory, Lí Do: Acc Die, CheckPoint v.v")
            
            for key in list(active_threads.keys()):
                if key.startswith(cookie_hash):
                    active_threads[key].stop()
                    del active_threads[key]

def cleanup_global_memory():
    global active_threads, cookie_attempts
    
    with cleanup_lock:
        current_time = time.time()
        
        expired_cookies = []
        for cookie_hash, data in cookie_attempts.items():
            if data['permanent_ban'] or (current_time - data['last_reset'] > 86400):
                expired_cookies.append(cookie_hash)
        
        for cookie_hash in expired_cookies:
            del cookie_attempts[cookie_hash]
            for key in list(active_threads.keys()):
                if key.startswith(cookie_hash):
                    active_threads[key].stop()
                    del active_threads[key]
        
        gc.collect()
        
        process = psutil.Process()
        memory_info = process.memory_info()
        print(f"Memory Usage: {memory_info.rss / (1024**3):.2f} GB")

def parse_cookie_string(cookie_string):
    cookie_dict = {}
    cookies = cookie_string.split(";")
    for cookie in cookies:
        if "=" in cookie:
            key, value = cookie.strip().split("=", 1)
            cookie_dict[key] = value
    return cookie_dict

def generate_offline_threading_id() -> str:
    ret = int(time.time() * 1000)
    value = random.randint(0, 4294967295)
    binary_str = format(value, "022b")[-22:]
    msgs = bin(ret)[2:] + binary_str
    return str(int(msgs, 2))

def get_headers(url: str, options: dict = {}, ctx: dict = {}, customHeader: dict = {}) -> dict:
    headers = {
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.facebook.com/",
        "Host": urlparse(url).netloc,
        "Origin": "https://www.facebook.com",
        "User-Agent": "Mozilla/5.0 (Linux; Android 9; SM-G973U Build/PPR1.180610.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Mobile Safari/537.36",
        "Connection": "keep-alive",
    }

    if "user_agent" in options:
        headers["User-Agent"] = options["user_agent"]

    for key in customHeader:
        headers[key] = customHeader[key]

    if "region" in ctx:
        headers["X-MSGR-Region"] = ctx["region"]

    return headers

def json_minimal(data):
    return json.dumps(data, separators=(",", ":"))

class Counter:
    def __init__(self, initial_value=0):
        self.value = initial_value
        
    def increment(self):
        self.value += 1
        return self.value
        
    @property
    def counter(self):
        return self.value

def formAll(dataFB, FBApiReqFriendlyName=None, docID=None, requireGraphql=None):
    global _req_counter
    if '_req_counter' not in globals():
        _req_counter = Counter(0)
    
    __reg = _req_counter.increment()
    dataForm = {}
    
    if requireGraphql is None:
        dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
        dataForm["jazoest"] = dataFB["jazoest"]
        dataForm["__a"] = 1
        dataForm["__user"] = str(dataFB["FacebookID"])
        dataForm["__req"] = str_base(__reg, 36) 
        dataForm["__rev"] = dataFB["clientRevision"]
        dataForm["av"] = dataFB["FacebookID"]
        dataForm["fb_api_caller_class"] = "RelayModern"
        dataForm["fb_api_req_friendly_name"] = FBApiReqFriendlyName
        dataForm["server_timestamps"] = "true"
        dataForm["doc_id"] = str(docID)
    else:
        dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
        dataForm["jazoest"] = dataFB["jazoest"]
        dataForm["__a"] = 1
        dataForm["__user"] = str(dataFB["FacebookID"])
        dataForm["__req"] = str_base(__reg, 36) 
        dataForm["__rev"] = dataFB["clientRevision"]
        dataForm["av"] = dataFB["FacebookID"]

    return dataForm

def mainRequests(url, data, cookies):
    return {
        "url": url,
        "data": data,
        "headers": {
            "authority": "www.facebook.com",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,vi;q=0.8",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.facebook.com",
            "referer": "https://www.facebook.com/",
            "sec-ch-ua": "\"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"108\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "x-fb-friendly-name": "FriendingCometFriendRequestsRootQueryRelayPreloader",
            "x-fb-lsd": "YCb7tYCGWDI6JLU5Aexa1-"
        },
        "cookies": parse_cookie_string(cookies),
        "verify": True
    }

def digitToChar(digit):
    if digit < 10:
        return str(digit)
    return chr(ord('a') + digit - 10)

def str_base(number, base):
    if number < 0:
        return "-" + str_base(-number, base)
    (d, m) = divmod(number, base)
    if d > 0:
        return str_base(d, base) + digitToChar(m)
    return digitToChar(m)

def generate_session_id():
    return random.randint(1, 2 ** 53)

def generate_client_id():
    def gen(length):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return gen(8) + '-' + gen(4) + '-' + gen(4) + '-' + gen(4) + '-' + gen(12)

# Hàm mới: Lấy danh sách bạn bè
def get_friends_list(dataFB):
    """Lấy danh sách bạn bè của tài khoản bằng endpoint chat/user_info_all."""
    try:
        form = {
            "viewer": str(dataFB["FacebookID"]),
            "fb_dtsg": dataFB["fb_dtsg"],
            "jazoest": dataFB["jazoest"],
            "__user": str(dataFB["FacebookID"]),
            "__a": "1",
            "__req": "1",
            "__rev": dataFB.get("clientRevision", "1015919737")
        }

        headers = get_headers("https://www.facebook.com/chat/user_info_all", customHeader={
            "Content-Type": "application/x-www-form-urlencoded"
        })

        response = requests.post(
            "https://www.facebook.com/chat/user_info_all",
            data=form,
            headers=headers,
            cookies=parse_cookie_string(dataFB["cookieFacebook"]),
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"HTTP Error {response.status_code}")

        content = response.text.replace('for (;;);', '')
        data = json.loads(content)

        if not data or "payload" not in data:
            raise Exception("getFriendsList returned empty object or missing payload.")

        if "error" in data:
            raise Exception(f"API Error: {data.get('errorDescription', 'Unknown error')}")

        # Format the friend list
        friends = data["payload"]
        friend_ids = [str(user_id) for user_id in friends.keys()]
        return True, friend_ids, f"✅ [{datetime.now().strftime('%H:%M:%S')}] Lấy được {len(friend_ids)} bạn bè."
    except Exception as e:
        return False, [], f"❌ [{datetime.now().strftime('%H:%M:%S')}] Lỗi khi lấy danh sách bạn bè: {str(e)}"

# Hàm mới: Đổi tên nhóm và thêm bạn bè
def change_group_name_and_add_friends(dataFB, thread_id, group_name):
    try:
        # Đổi tên nhóm
        success, log = tenbox(group_name, thread_id, dataFB)
        if not success:
            return False, log

        # Lấy danh sách bạn bè
        success, friend_ids, log = get_friends_list(dataFB)
        if not success:
            return False, log
        print(log)

        # Thêm bạn bè vào nhóm (giới hạn mỗi lần 10 bạn, delay 5 giây)
        batch_size = 50  # Reduced batch size
        for i in range(0, len(friend_ids), batch_size):
            batch = friend_ids[i:i + batch_size]
            success, log = add_user_to_group(dataFB, batch, thread_id)
            if not success:
                return False, log
            print(log)
            time.sleep(5)  # Increased delay
        return True, f"✅ [{datetime.now().strftime('%H:%M:%S')}] Đã đổi tên nhóm thành {group_name} và thêm {len(friend_ids)} bạn bè vào nhóm {thread_id}"
    except Exception as e:
        return False, f"❌ [{datetime.now().strftime('%H:%M:%S')}] Lỗi: {str(e)}"

# Hàm hiện có: Đổi tên nhóm
def tenbox(newTitle, threadID, dataFB):
    try:
        message_id = generate_offline_threading_id()
        timestamp = int(time.time() * 1000)
        form_data = {
            "client": "mercury",
            "action_type": "ma-type:log-message",
            "author": f"fbid:{dataFB['FacebookID']}",
            "thread_id": str(threadID),
            "timestamp": timestamp,
            "timestamp_relative": str(int(time.time())),
            "source": "source:chat:web",
            "source_tags[0]": "source:chat",
            "offline_threading_id": message_id,
            "message_id": message_id,
            "threading_id": generate_offline_threading_id(),
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

        response = requests.post(
            "https://www.facebook.com/messaging/set_thread_name/",
            data=form_data,
            headers=get_headers("https://www.facebook.com", customHeader={"Content-Length": str(len(form_data))}),
            cookies=parse_cookie_string(dataFB["cookieFacebook"]),
            timeout=10
        )

        if response.status_code == 200:
            return True, f"✅ [{datetime.now().strftime('%H:%M:%S')}] Đã đổi tên thành: {newTitle}"
        else:
            return False, f"❌ [{datetime.now().strftime('%H:%M:%S')}] Lỗi HTTP {response.status_code} khi đổi tên."
    except Exception as e:
        return False, f"❌ [{datetime.now().strftime('%H:%M:%S')}] Lỗi: {e}"

def change_nickname(nickname, thread_id, participant_id, dataFB):
    try:
        form = {
            "nickname": nickname,
            "participant_id": str(participant_id),
            "thread_or_other_fbid": str(thread_id),
            "source": "thread_settings",
            "dpr": "1",
            "fb_dtsg": dataFB["fb_dtsg"],
            "jazoest": dataFB["jazoest"],
            "__user": str(dataFB["FacebookID"]),
            "__a": "1",
            "__req": str_base(Counter().increment(), 36),
            "__rev": dataFB.get("clientRevision", "1015919737")
        }

        headers = get_headers("https://www.facebook.com/messaging/save_thread_nickname/", customHeader={
            "Content-Type": "application/x-www-form-urlencoded"
        })

        response = requests.post(
            "https://www.facebook.com/messaging/save_thread_nickname/",
            data=form,
            headers=headers,
            cookies=parse_cookie_string(dataFB["cookieFacebook"]),
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"HTTP Error {response.status_code}")

        content = response.text.replace('for (;;);', '')
        data = json.loads(content)

        if "error" in data:
            error_code = data.get("error")
            if error_code == 1545014:
                raise Exception("Trying to change nickname of user who isn't in thread")
            if error_code == 1357031:
                raise Exception("Thread doesn't exist or has no messages")
            raise Exception(f"API Error: {data.get('errorDescription', 'Unknown error')}")

        return True, f"✅ [{datetime.now().strftime('%H:%M:%S')}] Đã đổi biệt danh cho user {participant_id} thành {nickname} trong box {thread_id}"
    except Exception as e:
        return False, f"❌ [{datetime.now().strftime('%H:%M:%S')}] Lỗi khi đổi biệt danh cho user {participant_id}: {str(e)}"
        
def get_thread_info_graphql(thread_id, dataFB):
    try:
        form = {
            "queries": json.dumps({
                "o0": {
                    "doc_id": "3449967031715030",
                    "query_params": {
                        "id": str(thread_id),
                        "message_limit": 0,
                        "load_messages": False,
                        "load_read_receipts": False,
                        "before": None
                    }
                }
            }, separators=(",", ":")),
            "batch_name": "MessengerGraphQLThreadFetcher",
            "fb_dtsg": dataFB["fb_dtsg"],
            "jazoest": dataFB["jazoest"],
            "__user": str(dataFB["FacebookID"]),
            "__a": "1",
            "__req": str_base(Counter().increment(), 36),
            "__rev": dataFB.get("clientRevision", "1015919737")
        }

        headers = get_headers("https://www.facebook.com/api/graphqlbatch/", customHeader={
            "Content-Type": "application/x-www-form-urlencoded"
        })

        response = requests.post(
            "https://www.facebook.com/api/graphqlbatch/",
            data=form,
            headers=headers,
            cookies=parse_cookie_string(dataFB["cookieFacebook"]),
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"HTTP Error {response.status_code}")

        content = response.text.replace('for (;;);', '')
        response_parts = content.split("\n")
        if not response_parts or not response_parts[0].strip():
            raise Exception("Empty response from API")

        data = json.loads(response_parts[0])

        if "error" in data:
            raise Exception(f"API Error: {data.get('errorDescription', 'Unknown error')}")

        if data.get("error_results", 0) != 0:
            raise Exception("Error results in response")

        message_thread = data["o0"]["data"]["message_thread"]
        thread_id = (message_thread["thread_key"]["thread_fbid"] 
                     if message_thread["thread_key"].get("thread_fbid") 
                     else message_thread["thread_key"]["other_user_id"])

        participant_ids = [edge["node"]["messaging_actor"]["id"] 
                          for edge in message_thread["all_participants"]["edges"]]

        return True, participant_ids, f"✅ [{datetime.now().strftime('%H:%M:%S')}] Lấy được {len(participant_ids)} thành viên trong box {thread_id}"
    except Exception as e:
        return False, [], f"❌ [{datetime.now().strftime('%H:%M:%S')}] Lỗi khi lấy thông tin box {thread_id}: {str(e)}"

# Hàm hiện có: Tạo nhóm mới
def create_new_group(dataFB, participant_ids, group_title):
    """Create a new Facebook group with the given participants and title."""
    try:
        if not isinstance(participant_ids, list):
            raise ValueError("participant_ids should be an array.")
        
        if len(participant_ids) < 2:
            raise ValueError("participant_ids should have at least 2 IDs.")

        pids = [{"fbid": str(pid)} for pid in participant_ids]
        pids.append({"fbid": str(dataFB["FacebookID"])})

        form = {
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "MessengerGroupCreateMutation",
            "av": str(dataFB["FacebookID"]),
            "doc_id": "577041672419534",
            "variables": json.dumps({
                "input": {
                    "entry_point": "jewel_new_group",
                    "actor_id": str(dataFB["FacebookID"]),
                    "participants": pids,
                    "client_mutation_id": str(random.randint(1, 1024)),
                    "thread_settings": {
                        "name": group_title,
                        "joinable_mode": "PRIVATE",
                        "thread_image_fbid": None
                    }
                }
            }, separators=(",", ":")),
            "fb_dtsg": dataFB["fb_dtsg"],
            "jazoest": dataFB["jazoest"],
            "__user": str(dataFB["FacebookID"]),
            "__a": "1",
            "__req": "1",
            "__rev": dataFB.get("clientRevision", "1015919737")
        }

        headers = get_headers("https://www.facebook.com/api/graphql/", customHeader={
            "Content-Type": "application/x-www-form-urlencoded"
        })

        response = requests.post(
            "https://www.facebook.com/api/graphql/",
            data=form,
            headers=headers,
            cookies=parse_cookie_string(dataFB["cookieFacebook"]),
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"HTTP Error {response.status_code}")

        content = response.text.replace('for (;;);', '')
        data = json.loads(content)

        if "errors" in data:
            raise Exception(f"API Error: {data['errors'][0]['message']}")

        thread_id = data["data"]["messenger_group_thread_create"]["thread"]["thread_key"]["thread_fbid"]
        return True, thread_id, f"✅ [{datetime.now().strftime('%H:%M:%S')}] Đã tạo nhóm: {group_title} (ID: {thread_id})"
    except Exception as e:
        return False, None, f"❌ [{datetime.now().strftime('%H:%M:%S')}] Lỗi khi tạo nhóm {group_title}: {str(e)}"

# Hàm hiện có: Thêm người dùng vào nhóm
def add_user_to_group(dataFB, user_ids, thread_id, max_retries=3):
    """Add users to an existing Facebook group with retry logic."""
    for attempt in range(max_retries):
        try:
            if not isinstance(user_ids, list):
                user_ids = [user_ids]

            # Validate user IDs and thread ID
            for user_id in user_ids:
                if not isinstance(user_id, (str, int)) or not str(user_id).isdigit():
                    raise ValueError(f"Invalid user_id: {user_id}. Must be a number or string of digits.")
            if not isinstance(thread_id, (str, int)) or not str(thread_id).isdigit():
                raise ValueError(f"Invalid thread_id: {thread_id}. Must be a number or string of digits.")

            message_and_otid = generate_offline_threading_id()
            form = {
                "client": "mercury",
                "action_type": "ma-type:log-message",
                "author": f"fbid:{dataFB['FacebookID']}",
                "thread_id": "",
                "timestamp": str(int(time.time() * 1000)),
                "timestamp_absolute": "Today",
                "timestamp_
