import discord
from discord.ext import commands
import asyncio
import os
import re
import time
import json
import base64
from main import *
from main.fb import *
import random
import threading
import requests
from io import BytesIO
import aiohttp
import gc
import math
from discord import ButtonStyle, Activity, ActivityType
from discord.ui import Button, View, Modal, TextInput
from datetime import datetime, timedelta
from typing import Dict, Any
from discord.ext import tasks
from collections import defaultdict
import hashlib
import smtplib
import ssl
from email.mime.text import MIMEText

# Nhập dữ liệu khi khởi chạy (bỏ input đi)
TOKEN = "MTQzNjQwODc5NTIwMTkyOTI0Ng.GWXahH.dxghL3Tx_CqQqP8GsE4MyFUBOACBj9nCZj9VZ4"
IDADMIN_GOC = 1259541498278707213 # dán ID Discord của bạn vào đây (bỏ ngoặc kép)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)

# RAM lưu trạng thái
admins = [IDADMIN_GOC]
saved_files = {}
running_task_storage = {}
active_tokens = {}
discord_threads = {}
discord_states = {}

DATA_FOLDER = "data"
os.makedirs(DATA_FOLDER, exist_ok=True)

stop_flags = {}
task_storage = {}
task_info = {}
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
    
    if current_time - cookie_attempts[cookie_hash]['banned_until'] > 43200:
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
        await ctx.send(f"Đã thêm {target_member.name} (ID: {target_member.id}) vào danh sách Owner.")
        
    except ValueError:
        await ctx.send("Vui lòng nhập ID hợp lệ hoặc đề cập (@tag) người dùng.")

def parse_cookie_string(cookie_string):
    cookie_dict = {}
    cookies = cookie_string.split(";")
    for cookie in cookies:
        if "=" in cookie:
            key, value = cookie.split("=")
        else:
            pass
        try: cookie_dict[key] = value
        except: pass
    return cookie_dict

def generate_offline_threading_id() -> str:
    ret = int(time.time() * 1000)
    value = random.randint(0, 4294967295)
    binary_str = format(value, "022b")[-22:]
    msgs = bin(ret)[2:] + binary_str
    return str(int(msgs, 2))
    
def get_headers(
    url: str, options: dict = {}, ctx: dict = {}, customHeader: dict = {}
) -> dict:
    headers = {
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.facebook.com/",
        "Host": url.replace("https://", "").split("/")[0],
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

def get_from(input_str, start_token, end_token):
    start = input_str.find(start_token) + len(start_token)
    if start < len(start_token):
        return ""

    last_half = input_str[start:]
    end = last_half.find(end_token)
    if end == -1:
        raise ValueError(f"Could not find endTime `{end_token}` in the given string.")

    return last_half[:end]

def base36encode(number: int, alphabet="0123456789abcdefghijklmnopqrstuvwxyz"):
    if not isinstance(number, int):
        raise TypeError("number must be an integer")

    base36 = ""
    sign = ""

    if number < 0:
        sign = "-"
        number = -number

    if 0 <= number < len(alphabet):
        return sign + alphabet[number]

    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36

    return sign + base36

def dataSplit(string1, string2, numberSplit1=None, numberSplit2=None, HTML=None, amount=None, string3=None, numberSplit3=None, defaultValue=None):
    if (defaultValue): numberSplit1, numberSplit2 = 1, 0
    if (amount == None):
        return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2]
    elif (amount == 3):
        return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2].split(string3)[numberSplit3]

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
    
    if (requireGraphql == None):
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

class fbTools:
    def __init__(self, dataFB, threadID="0"):
        self.threadID = threadID
        self.dataGet = None
        self.dataFB = dataFB
        self.ProcessingTime = None
        self.last_seq_id = None
    
    def getAllThreadList(self):
        randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))
        dataForm = formAll(self.dataFB, requireGraphql=0)

        dataForm["queries"] = json.dumps({
            "o0": {
                "doc_id": "3336396659757871",
                "query_params": {
                    "limit": 20,
                    "before": None,
                    "tags": ["INBOX"],
                    "includeDeliveryReceipts": False,
                    "includeSeqID": True,
                }
            }
        })
        
        sendRequests = requests.post(**mainRequests("https://www.facebook.com/api/graphqlbatch/", dataForm, self.dataFB["cookieFacebook"]))
        response_text = sendRequests.text
        self.ProcessingTime = sendRequests.elapsed.total_seconds()
        
        if response_text.startswith("for(;;);"):
            response_text = response_text[9:]
        
        if not response_text.strip():
            print("Error: Empty response from Facebook API")
            return False
            
        try:
            response_parts = response_text.split("\n")
            first_part = response_parts[0]
            
            if first_part.strip():
                response_data = json.loads(first_part)
                self.dataGet = first_part
                
                if "o0" in response_data and "data" in response_data["o0"] and "viewer" in response_data["o0"]["data"] and "message_threads" in response_data["o0"]["data"]["viewer"]:
                    self.last_seq_id = response_data["o0"]["data"]["viewer"]["message_threads"]["sync_sequence_id"]
                    return True
                else:
                    print("Error: Expected fields not found in response")
                    return False
            else:
                print("Error: Empty first part of response")
                return False
                
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Response first part: {response_parts[0][:100]}")
            return False
        except KeyError as e:
            print(f"Key Error: {e}")
            print("The expected data structure wasn't found in the response")
            return False
    
    def typeCommand(self, commandUsed):
        listData = []
        
        try:
            if self.dataGet is None:
                return "No data available. Make sure to call getAllThreadList first."
                
            data_to_parse = self.dataGet
            if data_to_parse.startswith("for(;;);"):
                data_to_parse = data_to_parse[9:]
                
            getData = json.loads(data_to_parse)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
        except json.JSONDecodeError as e:
            return f"Failed to decode JSON response: {e}"
        except KeyError as e:
            try:
                error_data = json.loads(data_to_parse)["o0"]
                if "errors" in error_data:
                    return error_data["errors"][0]["summary"]
                else:
                    return f"Unexpected response structure. Missing key: {e}"
            except:
                return f"Unexpected response structure. Missing key: {e}"
        
        dataThread = None
        for getNeedIDThread in getData:
            thread_key = getNeedIDThread.get("thread_key", {})
            thread_fbid = thread_key.get("thread_fbid")
            if thread_fbid and str(thread_fbid) == str(self.threadID):
                dataThread = getNeedIDThread
                break
        
        if dataThread is not None:
            if commandUsed == "getAdmin":
                for dataID in dataThread.get("thread_admins", []):
                    listData.append(str(dataID["id"]))
                exportData = {
                    "adminThreadList": listData
                }
            elif commandUsed == "threadInfomation":
                threadInfoList = dataThread.get("customization_info", {})
                exportData = {
                    "nameThread": dataThread.get("name"), 
                    "IDThread": self.threadID, 
                    "emojiThread": threadInfoList.get("emoji"),
                    "messageCount": dataThread.get("messages_count"),
                    "adminThreadCount": len(dataThread.get("thread_admins", [])),
                    "memberCount": len(dataThread.get("all_participants", {}).get("edges", [])),
                    "approvalMode": "Bật" if (dataThread.get("approval_mode", 0) != 0) else "Tắt",
                    "joinableMode": "Bật" if (dataThread.get("joinable_mode", {}).get("mode") != "0") else "Tắt",
                    "urlJoinableThread": dataThread.get("joinable_mode", {}).get("link", "")
                }
            elif commandUsed == "exportMemberListToJson":
                getMemberList = dataThread.get("all_participants", {}).get("edges", [])
                for exportMemberList in getMemberList:
                    node = exportMemberList.get("node", {})
                    dataUserThread = node.get("messaging_actor", {})
                    if dataUserThread:
                        exportData = json.dumps({
                            dataUserThread.get("id", ""): {
                                "nameFB": str(dataUserThread.get("name", "")),
                                "idFacebook": str(dataUserThread.get("id", "")),
                                "profileUrl": str(dataUserThread.get("url", "")),
                                "avatarUrl": str(dataUserThread.get("big_image_src", {}).get("uri", "")),
                                "gender": str(dataUserThread.get("gender", "")),
                                "usernameFB": str(dataUserThread.get("username", ""))
                            }
                        }, skipkeys=True, allow_nan=True, ensure_ascii=False, indent=5)
                        listData.append(exportData)
                exportData = listData
            else:
                exportData = {
                    "err": "no data"
                }
                
            return exportData
            
        else:
            return "Không lấy được dữ liệu ThreadList, đã xảy ra lỗi T___T"
    
    def getListThreadID(self):
        try:
            if self.dataGet is None:
                return {
                    "ERR": "No data available. Make sure to call getAllThreadList first."
                }
                
            data_to_parse = self.dataGet
            if data_to_parse.startswith("for(;;);"):
                data_to_parse = data_to_parse[9:]
                
            threadIDList = []
            threadNameList = []
            try:
                getData = json.loads(data_to_parse)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
                
                for getThreadID in getData:
                    thread_key = getThreadID.get("thread_key", {})
                    thread_fbid = thread_key.get("thread_fbid")
                    
                    if thread_fbid is not None:
                        threadIDList.append(thread_fbid)
                        threadNameList.append(getThreadID.get("name", "No Name"))
                        
                return {
                    "threadIDList": threadIDList,
                    "threadNameList": threadNameList,
                    "countThread": len(threadIDList)
                }
                
            except (KeyError, json.JSONDecodeError) as e:
                return {
                    "ERR": f"Error processing thread data: {str(e)}"
                }
                
        except Exception as errLog:
            return {
                "ERR": f"Unexpected error: {str(errLog)}"
            }

class MessageSender:
    def __init__(self, fbt, dataFB, fb_instance):
        self.fbt = fbt
        self.dataFB = dataFB
        self.fb_instance = fb_instance
        self.mqtt = None
        self.ws_req_number = 0
        self.ws_task_number = 0
        self.syncToken = None
        self.lastSeqID = None
        self.req_callbacks = {}
        self.cookie_hash = hashlib.md5(dataFB['cookieFacebook'].encode()).hexdigest()
        self.connect_attempts = 0
        self.last_cleanup = time.time()

    def cleanup_memory(self):
        current_time = time.time()
        if current_time - self.last_cleanup > 3600:
            self.req_callbacks.clear()
            gc.collect()
            self.last_cleanup = current_time

    def get_last_seq_id(self):
        success = self.fbt.getAllThreadList()
        if success:
            self.lastSeqID = self.fbt.last_seq_id
        else:
            print("Failed To Get Last Sequence ID. Check Facebook Authentication.")
            return

    def on_disconnect(self, client, userdata, rc):
        global cookie_attempts
        print(f"Disconnected With Code {rc}")
        
        cookie_attempts[self.cookie_hash]['count'] += 1
        current_time = time.time()
        
        if current_time - cookie_attempts[self.cookie_hash]['last_reset'] > 43200:
            cookie_attempts[self.cookie_hash]['count'] = 1
            cookie_attempts[self.cookie_hash]['last_reset'] = current_time
        
        if cookie_attempts[self.cookie_hash]['count'] >= 20:
            print(f"Cookie {self.cookie_hash[:10]} Bị Tạm Ngưng Connect Trong 12 Giờ Vì Disconnect, Nghi Vấn: Die Cookies, Check Point")
            cookie_attempts[self.cookie_hash]['banned_until'] = current_time + 43200
            return
        
        if rc != 0:
            print("Attempting To Reconnect...")
            try:
                time.sleep(min(cookie_attempts[self.cookie_hash]['count'] * 2, 30))
                client.reconnect()
            except:
                print("Reconnect Failed")

    def _messenger_queue_publish(self, client, userdata, flags, rc):
        print(f"Connected To MQTT With Code: {rc}")
        if rc != 0:
            print(f"Connection Failed With Code {rc}")
            return

        topics = [("/t_ms", 0)]
        client.subscribe(topics)

        queue = {
            "sync_api_version": 10,
            "max_deltas_able_to_process": 1000,
            "delta_batch_size": 500,
            "encoding": "JSON",
            "entity_fbid": self.dataFB['FacebookID']
        }

        if self.syncToken is None:
            topic = "/messenger_sync_create_queue"
            queue["initial_titan_sequence_id"] = self.lastSeqID
            queue["device_params"] = None
        else:
            topic = "/messenger_sync_get_diffs"
            queue["last_seq_id"] = self.lastSeqID
            queue["sync_token"] = self.syncToken

        print(f"Publishing To {topic}")
        client.publish(
            topic,
            json_minimal(queue),
            qos=1,
            retain=False,
        )

    def connect_mqtt(self):
        global cookie_attempts
        
        if cookie_attempts[self.cookie_hash]['permanent_ban']:
            print(f"Cookie {self.cookie_hash[:10]} Đã Bị Ngưng Connect Vĩnh Viễn, Lí Do: Die Coọkes, Check Point v.v")
            return False
            
        current_time = time.time()
        if current_time < cookie_attempts[self.cookie_hash]['banned_until']:
            remaining = cookie_attempts[self.cookie_hash]['banned_until'] - current_time
            print(f"Cookie {self.cookie_hash[:10]} Bị Tạm Khóa, Còn {remaining/3600:.1f} Giờ")
            return False

        if not self.lastSeqID:
            print("Error: No last_seq_id Available. Cannot Connect To MQTT.")
            return False

        chat_on = json_minimal(True)
        session_id = generate_session_id()
        user = {
            "u": self.dataFB["FacebookID"],
            "s": session_id,
            "chat_on": chat_on,
            "fg": False,
            "d": generate_client_id(),
            "ct": "websocket",
            "aid": 219994525426954,
            "mqtt_sid": "",
            "cp": 3,
            "ecp": 10,
            "st": ["/t_ms", "/messenger_sync_get_diffs", "/messenger_sync_create_queue"],
            "pm": [],
            "dc": "",
            "no_auto_fg": True,
            "gas": None,
            "pack": [],
        }

        host = f"wss://edge-chat.messenger.com/chat?region=eag&sid={session_id}"
        options = {
            "client_id": "mqttwsclient",
            "username": json_minimal(user),
            "clean": True,
            "ws_options": {
                "headers": {
                    "Cookie": self.dataFB['cookieFacebook'],
                    "Origin": "https://www.messenger.com",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 9; SM-G973U Build/PPR1.180610.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Mobile Safari/537.36",
                    "Referer": "https://www.messenger.com/",
                    "Host": "edge-chat.messenger.com",
                },
            },
            "keepalive": 10,
        }

        self.mqtt = mqtt.Client(
            client_id="mqttwsclient",
            clean_session=True,
            protocol=mqtt.MQTTv31,
            transport="websockets",
        )

        self.mqtt.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLSv1_2)
        self.mqtt.on_connect = self._messenger_queue_publish
        self.mqtt.on_disconnect = self.on_disconnect
        self.mqtt.username_pw_set(username=options["username"])

        parsed_host = urlparse(host)
        self.mqtt.ws_set_options(
            path=f"{parsed_host.path}?{parsed_host.query}",
            headers=options["ws_options"]["headers"],
        )

        print(f"Connecting To {options['ws_options']['headers']['Host']}...")
        try:
            self.mqtt.connect(
                host=options["ws_options"]["headers"]["Host"],
                port=443,
                keepalive=options["keepalive"],
            )

            print("MQTT Connection Established")
            self.mqtt.loop_start()
            return True
        except Exception as e:
            print(f"MQTT Connection Error: {e}")
            cookie_attempts[self.cookie_hash]['count'] += 1
            return False

    def stop(self):
        if self.mqtt:
            print("Stopping MQTT Client...")
            try:
                self.mqtt.disconnect()
                self.mqtt.loop_stop()
            except:
                pass
        self.cleanup_memory()

    def send_typing_indicator(self, thread_id, is_typing=True):
        if self.mqtt is None:
            print("Error: Not connected to MQTT")
            return False
            
        self.ws_req_number += 1
        
        try:
            is_group_thread = 1
            
            task_payload = {
                "thread_key": thread_id,
                "is_group_thread": is_group_thread,
                "is_typing": 1 if is_typing else 0,
                "attribution": 0
            }
            
            payload = json.dumps(task_payload)
            version = "25393437286970779"
            
            content = {
                "app_id": "2220391788200892",
                "payload": json.dumps({
                    "label": "3",
                    "payload": payload,
                    "version": version,
                }),
                "request_id": self.ws_req_number,
                "type": 4,
            }
            
            self.mqtt.publish(
                "/ls_req", 
                json.dumps(content, separators=(",", ":")), 
                qos=1, 
                retain=False
            )
            return True
        except Exception as e:
            print(f"Error sending typing indicator: {e}")
            return False


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
            await ctx.send(f"Đã xoá {name} (ID: {member_id}) khỏi danh sách Owner.")
        else:
            await ctx.send("Người này không có trong danh sách Owner.")
            
    except ValueError:
        await ctx.send("Vui lòng nhập ID hợp lệ hoặc đề cập (@tag) người dùng.")

@bot.command()
async def list(ctx):
    msg = "Danh sách Owner hiện tại:\n"
    for admin_id in admins:
        try:
            user = await bot.fetch_user(admin_id)
            if admin_id == IDADMIN_GOC:
                msg += f"- <@{IDADMIN_GOC}> (Admin Gốc)\n"
            else:
                msg += f"- {user.name} - {admin_id} (Owner)\n"
        except Exception as e:
            msg += f"- {admin_id} (Không tìm được tên) (Owner)\n"
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
    await ctx.send(f"Đã lưu file {filename} vào thư mục của bạn.")

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
    msg = f"Danh sách file của {ctx.author.name}:\n"
    for fname in files:
        path = os.path.join(folder, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                preview = f.read(100).replace('\n', ' ')
                msg += f"{fname}: {preview}...\n"
        except:
            msg += f"{fname}: (Không đọc được nội dung)\n"
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
    while idgroup in running_task_storage:
        success = send_message(idgroup, fb_dtsg, jazoest, cookie, content)
        await asyncio.sleep(float(delay))

@bot.command()
async def treo(ctx, id_box: str, cookie: str, filename: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    admin_id = str(ctx.author.id)
    file_path = f"data/{admin_id}/{filename}"

    if not os.path.exists(file_path):
        return await ctx.send(f"File {filename} không tồn tại trong thư mục của bạn.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(file_path, 'r', encoding='utf-8') as f:
        message_body = f.read().strip()

    print(f"[+] Bắt Đầu Treo Box {id_box} với file {filename} mỗi {speed} giây.")

    task_id = f"ngonmess_{id_box}_{time.time()}"
    async def spam_loop_task():
        while True:
            success = send_message(id_box, fb_dtsg, jazoest, cookie, message_body)
            await asyncio.sleep(speed)

    task = asyncio.create_task(spam_loop_task())
    running_task_storage[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"đã tạo task")
    
class TaskPaginator(View):
    def __init__(self, tasks, author, items_per_page=8, is_root_admin=False):
        super().__init__(timeout=60)
        self.tasks = tasks
        self.author = author
        self.page = 0
        self.items_per_page = items_per_page
        self.max_page = max(0, math.ceil(len(tasks) / items_per_page) - 1)
        self.is_root_admin = is_root_admin
        self.update_buttons()
        self.message = None

    def update_buttons(self):
        self.clear_items()
        
        prev_btn = Button(style=ButtonStyle.blurple, emoji="⬅️", disabled=self.page <= 0)
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)
        
        next_btn = Button(style=ButtonStyle.blurple, emoji="➡️", disabled=self.page >= self.max_page)
        next_btn.callback = self.next_page
        self.add_item(next_btn)
        
        close_btn = Button(style=ButtonStyle.red, emoji="⛔")
        close_btn.callback = self.close
        self.add_item(close_btn)

    def create_embed(self):
        embed = discord.Embed(
            title=f"Danh sách task ({len(self.tasks)} tasks)",
            description=f"Trang {self.page + 1}/{self.max_page + 1}",
            color=0xB8F0FF
        )
        
        start_idx = self.page * self.items_per_page
        for i, task in enumerate(self.tasks[start_idx:start_idx+self.items_per_page], start_idx + 1):
            embed.add_field(
                name=f"ID Task **{i}** | {task['type'].upper()} | Box: {task['box_id']}",
                value=f"{task['admin']}\n{task['duration']}",
                inline=False
            )
        
        if self.is_root_admin:
            embed.set_footer(text="Dùng .stoptask [số] để dừng task hoặc .stoptask all để dừng tất cả")
        else:
            embed.set_footer(text="Dùng .stoptask [số] để dừng task của bạn")
        return embed

    async def prev_page(self, interaction):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def next_page(self, interaction):
        if self.page < self.max_page:
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def close(self, interaction):
        await interaction.message.delete()
        self.stop()

    async def interaction_check(self, interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Chỉ người gửi lệnh mới có thể tương tác!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        try:
            if self.message:
                await self.message.edit(view=None)
        except:
            pass

@bot.command()
async def stoptask(ctx, task_number: str = None):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    # Kiểm tra có phải admin gốc không
    is_root_admin = (ctx.author.id == IDADMIN_GOC)

    # Lấy danh sách task
    user_tasks = []
    for task_id, info in task_info.items():
        # Admin gốc thấy tất cả, admin thường chỉ thấy task của mình
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
        
    if task_number and task_number.lower() == 'all':
        stopped_count = 0
        for task in user_tasks:
            # Admin thường chỉ dừng được task của mình
            if is_root_admin or task['admin_id'] == ctx.author.id:
                if task['id'] in running_task_storage:
                    running_task_storage[task['id']].cancel()
                    del running_task_storage[task['id']]
                    del task_info[task['id']]
                    stopped_count += 1
        return await ctx.send(f"Đã dừng {stopped_count} task.")

    # Nếu không có số task thì hiển thị danh sách
    if not task_number:
        msg = "**Danh sách task đang chạy:**\n" + \
              ("(Bạn là admin gốc, có thể dừng mọi task)\n" if is_root_admin else "")
        
        for i, task in enumerate(user_tasks, 1):
            msg += f"**{i}. {task['type']} - Box: {task['box_id']} - Admin: {task['admin']} (Đã chạy: {task['duration']})**\n"
        
        msg += "\nNhập `.stoptask [số]` để dừng task hoặc `.stoptask all` để dừng tất cả"
        return await ctx.send(msg)

    # Xử lý dừng task theo số
    try:
        task_index = int(task_number) - 1
        if 0 <= task_index < len(user_tasks):
            task = user_tasks[task_index]
            
            # Kiểm tra quyền dừng task
            if not is_root_admin and task['admin_id'] != ctx.author.id:
                return await ctx.send("Bạn không có quyền dừng task này!")
                
            if task['id'] in running_task_storage:
                running_task_storage[task['id']].cancel()
                del running_task_storage[task['id']]
                del task_info[task['id']]
                return await ctx.send(f"Đã dừng task số {task_number}.")
        return await ctx.send("Số task không hợp lệ.")
    except ValueError:
        return await ctx.send("Vui lòng nhập số task hoặc 'all'.")

@bot.command()
async def danhsachtask(ctx, task_number: str = None):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    # Kiểm tra có phải admin gốc không
    is_root_admin = (ctx.author.id == IDADMIN_GOC)

    # Lấy danh sách task
    user_tasks = []
    for task_id, info in task_info.items():
        # Admin gốc thấy tất cả, admin thường chỉ thấy task của mình
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
        
    if task_number and task_number.lower() == 'all':
        stopped_count = 0
        for task in user_tasks:
            # Admin thường chỉ dừng được task của mình
            if is_root_admin or task['admin_id'] == ctx.author.id:
                if task['id'] in running_task_storage:
                    running_task_storage[task['id']].cancel()
                    del running_task_storage[task['id']]
                    del task_info[task['id']]
                    stopped_count += 1
        return await ctx.send(f"Đã dừng {stopped_count} task.")

    # Nếu không có số task thì hiển thị danh sách
    if not task_number:
        msg = "**Danh sách task đang chạy:**\n" + \
              ("(Bạn là admin gốc, có thể dừng mọi task)\n" if is_root_admin else "")
        
        for i, task in enumerate(user_tasks, 1):
            msg += f"**{i}. {task['type']} - Box: {task['box_id']} - Admin: {task['admin']} (Đã chạy: {task['duration']})**\n"
        
        msg += "\nNhập `.stoptask [số]` để dừng task hoặc `.stoptask all` để dừng tất cả"
        return await ctx.send(msg)

    # Xử lý dừng task theo số
    try:
        task_index = int(task_number) - 1
        if 0 <= task_index < len(user_tasks):
            task = user_tasks[task_index]
            
            # Kiểm tra quyền dừng task
            if not is_root_admin and task['admin_id'] != ctx.author.id:
                return await ctx.send("Bạn không có quyền dừng task này!")
                
            if task['id'] in running_task_storage:
                running_task_storage[task['id']].cancel()
                del running_task_storage[task['id']]
                del task_info[task['id']]
                return await ctx.send(f"Đã dừng task số {task_number}.")
        return await ctx.send("Số task không hợp lệ.")
    except ValueError:
        return await ctx.send("Vui lòng nhập số task hoặc 'all'.")
   
@bot.command()
async def nhay(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhay.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file nhay.txt trong thư mục data.")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"[+] Bắt Đầu Nhây Box mỗi {speed} giây.")

    task_id = f"nhay_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(speed)
            send_message(id_box, fb.fb_dtsg, fb.jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'sender': sender
    }
    await ctx.send(f"đã tạo task")
        
@bot.command()
async def codelag(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhay.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file nhay.txt.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"[+] Bắt Đầu Code Lag Box mỗi {speed} giây.")

    icon = """"⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰ "⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰ "⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰"""  
    
    fb = facebook(cookie)
    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    task_id = f"codelag_{id_box}_{time.time()}"

    async def loop_codelag():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(speed)
            
            message = f"{lines[index]} {icon}"
            send_message(id_box, fb_dtsg, jazoest, cookie, message)
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_codelag())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id, 
        'start_time': time.time(),
        'sender': sender
    }
    await ctx.send(f"đã tạo task")

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
        await ctx.send("Không tìm thấy file nhay.txt.")
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
        await ctx.send("File chui.txt rỗng.")
        return

    print(f"[+] Bắt Đầu Nhây Top Mỗi {delay} giây.")	

    task_id = f"nhaytop_{post_id}_{time.time()}"
    
    async def loop_nhaytop():
        index = 0
        while True:
            message = lines[index]
            success = cmt_gr_pst(cookie, group_id, post_id, message, user_id, fb_dtsg, rev, req, a, jazoest)
            index = (index + 1) % len(lines)
            await asyncio.sleep(delay)

    task = asyncio.create_task(loop_nhaytop())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'post_id': post_id,
        'group_id': group_id
    }
    await ctx.send(f"Đã tạo task thành công")

@bot.command()
async def sotop(ctx, cookie: str, delay: float):
    if ctx.author.id not in admins:
        await ctx.send("Bạn không có quyền sử dụng lệnh này.")
        return

    # Kiểm tra file nhay.txt
    path = "so.txt"
    if not os.path.exists(path):
        await ctx.send("Không tìm thấy file nhay.txt.")
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
        await ctx.send("File so.txt rỗng.")
        return

    print(f"[+] Bắt Đầu Sớ Top Mỗi {delay} giây.")	

    task_id = f"sotop_{post_id}_{time.time()}"
    
    async def loop_nhaytop():
        index = 0
        while True:
            message = lines[index]
            success = cmt_gr_pst(cookie, group_id, post_id, message, user_id, fb_dtsg, rev, req, a, jazoest)
            index = (index + 1) % len(lines)
            await asyncio.sleep(delay)

    task = asyncio.create_task(loop_nhaytop())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'post_id': post_id,
        'group_id': group_id
    }
    await ctx.send(f"Đã tạo task thành công")
        
@bot.command()
async def treoso(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "so.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file so.txt trong thư mục data.")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"[+] Bắt Đầu Treo Sớ Mỗi {speed} giây.")	

    task_id = f"so_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(speed)
            send_message(id_box, fb.fb_dtsg, fb.jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id, 
        'start_time': time.time(),
        'sender': sender
    }
    await ctx.send(f"đã tạo task")
    
@bot.command()
async def ideamess(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "chui.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file chui.txt trong thư mục data.")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"[+] Bắt Đầu Ideamess Mỗi {speed} giây.")	

    task_id = f"cay_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(speed)
            send_message(id_box, fb.fb_dtsg, fb.jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'sender': sender
    }
    await ctx.send(f"tạo task thành công")

@bot.command()
async def nhay2c(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "2c.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file nhay.txt trong thư mục data.")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"[+] Bắt Đầu Nhây 2c Mỗi {speed} giây.")

    task_id = f"2c_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(speed)
            send_message(id_box, fb.fb_dtsg, fb.jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_task_storage[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time(), 'sender': sender}
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
        return await ctx.send("Không tìm thấy file nhay.txt trong thư mục data.")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    tag_name = None
    try:
        info = get_info(tag_uid, cookie, fb.fb_dtsg, fb.a, fb.req, fb.rev)
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

    print(f"[+] Bắt Đầu Nhây Tag Mỗi {speed} giây.")	

    task_id = f"nhaytag_{id_box}_{time.time()}"
    
    async def loop_nhaytag():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(speed)
            message = f"{lines[index]} @{tag_name}"
            send_message(id_box, fb.fb_dtsg, fb.jazoest, cookie, message, tag_uid, tag_name)
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhaytag())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id, 
        'start_time': time.time(),
        'tag_uid': tag_uid,
        'tag_name': tag_name,
        'sender': sender
    }
    await ctx.send(f"tạo task thành công")
  
@bot.command()
async def nhaytagfaketen(ctx, id_box: str, cookie: str, fake_name: str, tag_uid: str, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhay.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file nhay.txt.")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"[+] Bắt Đầu Nhây Tag Fake Tên Mỗi {delay} giây.")	

    task_id = f"nhaytagfaketen_{id_box}_{time.time()}"
    
    async def loop_nhaytag():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(delay)
            message = f"{lines[index]} @{fake_name}"
            send_message(
                id_box, 
                fb.fb_dtsg, 
                fb.jazoest, 
                cookie, 
                message,
                tag_uid=tag_uid,
                tag_name=fake_name
            )
            index = (index + 1) % len(lines)
            await asyncio.sleep(delay)

    task = asyncio.create_task(loop_nhaytag())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'tag_uid': tag_uid,
        'fake_name': fake_name,
        'sender': sender
    }
    
    await ctx.send(f"Đã bắt đầu nhây tag fake tên tên fake là **{fake_name}**")

@bot.command()
async def sotagfakten(ctx, id_box: str, cookie: str, fake_name: str, tag_uid: str, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "so.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file so.txt")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"[+] Bắt Đầu Nhây Tag Fake Tên Mỗi {delay} giây.")	

    task_id = f"sotagfakten_{id_box}_{time.time()}"
    
    async def loop_nhaytag():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(delay)
            message = f"{lines[index]} @{fake_name}"
            send_message(
                id_box, 
                fb.fb_dtsg, 
                fb.jazoest, 
                cookie, 
                message,
                tag_uid=tag_uid,
                tag_name=fake_name
            )
            index = (index + 1) % len(lines)
            await asyncio.sleep(delay)

    task = asyncio.create_task(loop_nhaytag())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'tag_uid': tag_uid,
        'fake_name': fake_name,
        'sender': sender
    }
    
    await ctx.send(f"Đã bắt đầu sớ tag fake tên tên fake là **{fake_name}**")
          
@bot.command()
async def sotag(ctx, id_box: str, cookie: str, tag_uid: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "so.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file so.txt trong thư mục data.")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    tag_name = None
    try:
        info = get_info(tag_uid, cookie, fb.fb_dtsg, fb.a, fb.req, fb.rev)
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

    print(f"[+] Bắt Đầu Sớ Tag Mỗi {speed} giây.")	

    task_id = f"sotag_{id_box}_{time.time()}"
    
    async def loop_nhaytag():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(speed)
            message = f"{lines[index]} @{tag_name}"
            send_message(id_box, fb.fb_dtsg, fb.jazoest, cookie, message, tag_uid, tag_name)
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhaytag())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id, 
        'start_time': time.time(),
        'tag_uid': tag_uid,
        'tag_name': tag_name,
        'sender': sender
    }
    await ctx.send(f"tạo task thành công")

@bot.command()
async def nhayicon(ctx, id_box: str, cookie: str, icon: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhayicon.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file nhayicon.txt trong thư mục data.")

    fb = facebook(cookie)
    if not (fb.user_id and fb.fb_dtsg):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    sender = MessageSender(fbTools({
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }), {
        "FacebookID": fb.user_id,
        "fb_dtsg": fb.fb_dtsg,
        "clientRevision": fb.rev,
        "jazoest": fb.jazoest,
        "cookieFacebook": cookie
    }, fb)

    sender.get_last_seq_id()
    
    if not sender.connect_mqtt():
        return await ctx.send("Không thể kết nối MQTT.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"[+] Bắt Đầu Nhây Icon Mỗi {speed} giây.")	

    task_id = f"nhayicon_{id_box}_{time.time()}"
    
    async def loop_nhayicon():
        index = 0
        while True:
            sender.send_typing_indicator(id_box, True)
            await asyncio.sleep(speed)
            message = f"{lines[index]}{icon}"
            send_message(id_box, fb.fb_dtsg, fb.jazoest, cookie, message)
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhayicon())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id, 
        'start_time': time.time(),
        'sender': sender
    }
    await ctx.send(f"đã tạo task")

@bot.command()
async def treotop(ctx, cookie: str, delay: float, filename: str):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này")

    file_path = f"data/{ctx.author.id}/{filename}"
    if not os.path.exists(file_path):
        return await ctx.send(f"Không tìm thấy file {filename} trong thư mục của bạn")

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

    await ctx.send("🔗 Nhập link bài viết Facebook (VD: https://facebook.com/groups/123/permalink/456):")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        post_link = msg.content.strip()
    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ nhập link")

    post_id, group_id = extract_post_group_id(post_link)
    if not post_id or not group_id:
        return await ctx.send("Link bài viết không hợp lệ")

    cookie = normalize_cookie(cookie)
    user_id, fb_dtsg, rev, req, a, jazoest = get_uid_fbdtsg(cookie)
    if not user_id or not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ")

    print(f"[+] Bắt Đầu Treo Top Mỗi {delay} giây.")	

    task_id = f"treotop_full_{post_id}_{int(time.time())}"
    
    async def spam_task():
        while task_id in running_task_storage:
            try:
                success = cmt_gr_pst(
                    cookie=cookie,
                    grid=group_id,
                    postIDD=post_id,
                    ctn=full_content,
                    user_id=user_id,
                    fb_dtsg=fb_dtsg,
                    rev=rev,
                    req=req,
                    a=a,
                    jazoest=jazoest
                )
                    
                await asyncio.sleep(delay)
            except Exception as e:
                print(f"Lỗi: {str(e)}")
                await asyncio.sleep(10)

    running_task_storage[task_id] = asyncio.create_task(spam_task())
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'post_id': post_id,
        'group_id': group_id,
        'file_path': file_path,
        'content_preview': full_content[:100] + '...' if len(full_content) > 100 else full_content,
        'type': 'treotop_full'
    }
    
    await ctx.send(
        f"Đã Bắt Đầu Treo Top\n"
        f"├ File Ngôn: {filename}\n"
        f"├ Post: {post_id}\n"
        f"├ Delay: {delay}s\n"
        f"└ Dừng: .stoptask {len(running_task_storage)}"
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

class PaginationView(View):
    def __init__(self, data, author, title, color, items_per_page=10):
        super().__init__(timeout=60)
        self.data = data
        self.author = author
        self.title = title
        self.color = color
        self.page = 0
        self.items_per_page = items_per_page
        self.max_page = max(0, math.ceil(len(data) / items_per_page) - 1)
        self.update_buttons()
        
    def update_buttons(self):
        self.clear_items()
        
        # Previous Button
        prev_btn = Button(style=discord.ButtonStyle.blurple, emoji="⬅️", disabled=self.page <= 0)
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)
        
        # Next Button
        next_btn = Button(style=discord.ButtonStyle.blurple, emoji="➡️", disabled=self.page >= self.max_page)
        next_btn.callback = self.next_page
        self.add_item(next_btn)
        
        # Close Button
        close_btn = Button(style=discord.ButtonStyle.red, emoji="⛔")
        close_btn.callback = self.close
        self.add_item(close_btn)
    
    def create_embed(self):
        embed = discord.Embed(title=self.title, color=self.color)
        
        start = self.page * self.items_per_page
        for item in self.data[start:start+self.items_per_page]:
            embed.add_field(
                name=item.get('name', 'No Name'),
                value=item.get('value', 'No Value'),
                inline=False
            )
        
        embed.set_footer(text=f"Trang {self.page + 1}/{self.max_page + 1} | Tổng {len(self.data)} mục")
        return embed
    
    async def prev_page(self, interaction):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    async def next_page(self, interaction):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    async def close(self, interaction):
        await interaction.message.delete()
        self.stop()
    
    async def interaction_check(self, interaction):
        return interaction.user == self.author

@bot.command()
async def listbox(ctx, cookie: str):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền!")
    
    msg = await ctx.send("Đang tải danh sách box...")
    
    try:
        extractor = FacebookThreadExtractor(cookie)
        result = extractor.get_thread_list()
        
        if "error" in result:
            return await msg.edit(content=f"Lỗi: {result['error']}")
            
        boxes = result.get('threads', [])
        if not boxes:
            return await msg.edit(content="Không tìm thấy box nào!")
        
        # Format data for pagination
        box_data = [
            {
                "name": f"{box['thread_name']}",
                "value": f"**ID:** `{box['thread_id']}`"
            }
            for box in boxes
        ]
        
        view = PaginationView(
            data=box_data,
            author=ctx.author,
            title="Danh sách Box",
            color=0xB8F0FF
        )
        
        await msg.delete()
        view.message = await ctx.send(embed=view.create_embed(), view=view)
        
    except Exception as e:
        await msg.edit(content=f"Lỗi: {str(e)}")

@bot.command()
async def nhaynamebox(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này")

    try:
        with open('nhaynamebox.txt', 'r', encoding='utf-8') as f:
            names = [line.strip() for line in f if line.strip()]
            if not names:
                return await ctx.send("File nhaynamebox.txt trống hoặc không có nội dung")
    except Exception as e:
        return await ctx.send(f"Lỗi khi đọc file nhaynamebox.txt: {str(e)}")

    try:
        dataFB = dataGetHome(cookie)
        if "FacebookID" not in dataFB or not dataFB.get("fb_dtsg"):
            return await ctx.send("Cookie không hợp lệ hoặc thiếu thông tin đăng nhập")
    except Exception as e:
        return await ctx.send(f"Lỗi khi xử lý cookie: {str(e)}")

    print(f"[+] Bắt Đầu Nhây Name Box Mỗi {speed} giây.")	

    task_id = f"nhaynamebox_{id_box}_{int(time.time())}"
    
    async def name_change_task():
        index = 0
        while task_id in running_task_storage:
            try:
                current_name = names[index]
                result = tenbox(current_name, id_box, dataFB)
                index = (index + 1) % len(names)
                await asyncio.sleep(speed)
                
            except Exception as e:
                error_msg = f"Có lỗi xảy ra: {str(e)}"
                print(error_msg)
                await asyncio.sleep(10)

    running_task_storage[task_id] = asyncio.create_task(name_change_task())
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'thread_id': id_box,
        'names': names,
        'current_index': 0,
        'type': 'nhaynamebox'
    }
    
    embed = discord.Embed(
        title="Bắt Đầu Nhây Name Box",
        description=f"ID Box {id_box}",
        color=0xB8F0FF
    )
    embed.add_field(name="Delay", value=f"{speed} giây", inline=True)
    embed.add_field(name="Dừng task", value=f"Dùng lệnh .stoptask {len(running_task_storage)}", inline=False)
    
    await ctx.send(embed=embed)

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
async def reostr(ctx, cookie: str, mention: str, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này")

    user_id, fb_dtsg, rev, req, a, jazoest = get_uid_fbdtsg(cookie)
    if not all([user_id, fb_dtsg, jazoest]):
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin")

    await ctx.send("Vui lòng gửi ảnh đính kèm hoặc nhập link ảnh")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and (
            m.attachments or 
            (m.content.startswith('http://') or m.content.startswith('https://')) or
            m.content.lower() == 'cancel'
        )

    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        
        if msg.content.lower() == 'cancel':
            return await ctx.send("Đã hủy lệnh")
            
        if msg.attachments:
            image_url = msg.attachments[0].url
        else:
            image_url = msg.content.strip()

    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ upload ảnh")

    print(f"[+] Bắt Đầu Réo Story Mỗi {delay} giây.")	

    task_id = f"reostr_{user_id}_{int(time.time())}"

    async def post_story_loop():
        while task_id in running_task_storage:
            try:
                # Upload ảnh và lấy FBID
                fbid = upload_image_get_fbid(image_url, cookie)
                
                if not fbid or not fbid.isdigit():
                    print(f"Lỗi upload ảnh: {fbid}")
                    await asyncio.sleep(10)
                    continue

                # Tạo payload story
                payload = {
                    "av": user_id,
                    "__user": user_id,
                    "__a": "1",
                    "__req": "1b",
                    "__rev": rev,
                    "fb_dtsg": fb_dtsg,
                    "jazoest": jazoest,
                    "variables": json.dumps({
                        "input": {
                            "audiences": [{"stories": {"self": {"target_id": user_id}}}],
                            "audiences_is_complete": True,
                            "logging": {"composer_session_id": ""},
                            "navigation_data": {
                                "attribution_id_v2": "StoriesCreateRoot.react,comet.stories.create,..."
                            },
                            "source": "WWW",
                            "attachments": [{
                                "photo": {
                                    "id": fbid,
                                    "overlays": [
                                        {
                                            "tag_sticker": {
                                                "bounds": {
                                                    "height": 0.0356,
                                                    "rotation": 0,
                                                    "width": 0.3764,
                                                    "x": 0.3944,
                                                    "y": 0.4582
                                                },
                                                "creation_source": "TEXT_TOOL_MENTION",
                                                "tag_id": mention,
                                                "type": "PEOPLE"
                                            }
                                        }
                                    ]
                                }
                            }],
                            "tracking": [None],
                            "actor_id": user_id,
                            "client_mutation_id": str(time.time())
                        }
                    }),
                    "doc_id": "7490607150987409"
                }

                headers = {
                    'authority': 'www.facebook.com',
                    'accept': '*/*',
                    'accept-language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
                    'content-type': 'application/x-www-form-urlencoded',
                    'cookie': cookie,
                    'origin': 'https://www.facebook.com',
                    'referer': 'https://www.facebook.com/stories/create',
                    'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
                    'x-fb-friendly-name': 'StoriesCreateMutation',
                    'x-fb-lsd': fb_dtsg
                }

                # Gửi request
                response = requests.post(
                    'https://www.facebook.com/api/graphql/',
                    headers=headers,
                    data=payload
                )

                if response.status_code == 200:
                    print(f"Réo Story Thành Công")
                else:
                    print(f"Lỗi réo story: {response.text}")

                await asyncio.sleep(delay)

            except Exception as e:
                print(f"Lỗi nghiêm trọng: {str(e)}")
                await asyncio.sleep(10)

    # Bắt đầu task
    running_task_storage[task_id] = asyncio.create_task(post_story_loop())
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'target_id': mention,
        'image': image_url,
        'type': 'reostr'
    }

    embed = discord.Embed(
        title="Bắt Réo Story",
        description=f"Tag: {mention} mỗi {delay} giây",
        color=0xB8F0FF
    )
    embed.add_field(name="Ảnh", value=image_url[:100] + "..." if len(image_url) > 100 else image_url, inline=False)
    embed.add_field(name="Dừng task", value=f"Dùng lệnh: .stoptask {len(running_task_storage)}", inline=False)
    embed.set_thumbnail(url=image_url if image_url.startswith('http') else None)
    
    await ctx.send(embed=embed)

def upload_image_get_fbid(image_path_or_url: str, ck: str) -> str:
  user_id, fb_dtsg, rev, req, a, jazoest = get_uid_fbdtsg(ck)
  if not all([user_id, fb_dtsg, jazoest]):
    return "Không thể lấy thông tin từ cookie. Vui lòng kiểm tra lại."

  # Tải ảnh nếu là URL
  is_url = image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://")
  try:
    if is_url:
      resp = requests.get(image_path_or_url)
      if resp.status_code != 200:
        return "Không thể tải ảnh từ URL."
      img_data = BytesIO(resp.content)
      img_data.name = "image.jpg"
    else:
      if not os.path.isfile(image_path_or_url):
        return "File không tồn tại. Hãy nhập đúng đường dẫn tới ảnh."
      img_data = open(image_path_or_url, 'rb')
  except Exception as e:
    return f"Lỗi khi đọc ảnh: {e}"

  headers = {
    'cookie': ck,
    'origin': 'https://www.facebook.com',
    'referer': 'https://www.facebook.com/',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64)',
    'x-fb-lsd': fb_dtsg,
  }

  params = {
    'av': user_id,
    'profile_id': user_id,
    'source': '19',
    'target_id': user_id,
    '__user': user_id,
    '__a': a,
    '__req': req,
    '__rev': rev,
    'fb_dtsg': fb_dtsg,
    'jazoest': jazoest,
  }

  try:
    files = {
      'file': (img_data.name, img_data, 'image/jpeg')
    }

    response = requests.post(
      'https://www.facebook.com/ajax/ufi/upload/',
      headers=headers,
      params=params,
      files=files
    )

    if is_url:
      img_data.close()

    text = response.text.strip()
    if text.startswith("for(;;);"):
      text = text[8:]

    try:
      data = json.loads(text)
      fbid = data.get("payload", {}).get("fbid")
      if fbid:
        return fbid
      return "Không tìm thấy fbid trong JSON."

    except json.JSONDecodeError:
      match = re.search(r'"fbid"\s*:\s*"(\d+)"', text)
      if match:
        return match.group(1)
      return "Không tìm thấy fbid trong text."

  except Exception as e:
    return f"Lỗi khi upload: {e}"

@bot.command()
async def setfilev2(ctx):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    if not ctx.message.attachments:
        return await ctx.send("Vui lòng đính kèm file txt!")
    attachment = ctx.message.attachments[0]
    if not attachment.filename.endswith('.txt'):
        return await ctx.send("File phải có đuôi .txt!")
    save_path = os.path.join(DATA_FOLDER, attachment.filename)
    await attachment.save(save_path)
    await ctx.send(f"Đã lưu file thành công: {attachment.filename}")
    
def send_message_user_token(channel_id, user_token, message):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": user_token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    json_data = {"content": message}
    try:
        r = requests.post(url, headers=headers, json=json_data)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

async def loop_ngondisc(channel_id, user_token, message, delay, ctx):
    stop_flags[channel_id] = False
    while not stop_flags.get(channel_id, True):
        status, resp = send_message_user_token(channel_id, user_token, message)
        if status not in (200, 201):
            await ctx.send(f"Lỗi gửi tin: {status} - {resp}")
            break
        await asyncio.sleep(delay)
    await ctx.send(f"Đã dừng gửi treo vào channel Discord {channel_id}")

async def send_typing_indicator(channel_id: str, user_token: str):
    url = f"https://discord.com/api/v10/channels/{channel_id}/typing"
    headers = {
        "Authorization": user_token,
        "User-Agent": "Mozilla/5.0"
    }
    try:
        requests.post(url, headers=headers)
    except Exception as e:
        print(f"Error sending typing indicator: {e}")

async def loop_nhaydisc(channel_id, user_token, lines, delay, ctx):
    stop_flags[channel_id] = False
    while not stop_flags.get(channel_id, True):
        for line in lines:
            if stop_flags.get(channel_id, True):
                break
                
            # Gửi typing indicator và đợi một khoảng thời gian ngắn
            await send_typing_indicator(channel_id, user_token)
            await asyncio.sleep(min(2, delay * 0.3))  # Delay fake soạn bằng 30% của delay gửi tin, tối đa 2s
            
            message = f"# {line}"
            
            status, resp = send_message_user_token(channel_id, user_token, message)
            if status not in (200, 201):
                await ctx.send(f"Lỗi gửi tin: {status} - {resp}")
                stop_flags[channel_id] = True
                break
            await asyncio.sleep(delay)
    await ctx.send(f"Đã dừng nhây Discord vào kênh {channel_id}")

async def loop_nhaytagdis(channel_id: str, user_token: str, user_ids: str, lines: list, delay: float, ctx):
    user_id_list = [uid.strip() for uid in user_ids.split(',') if uid.strip()]
    if not user_id_list:
        await ctx.send("Không có ID người dùng hợp lệ!")
        return

    task_id = f"nhaytagdis_{channel_id}_{'_'.join(user_id_list)}_{int(time.time())}"
    stop_flags[task_id] = False
    
    discord_threads[task_id] = {
        'channel_id': channel_id,
        'user_ids': user_id_list,
        'start_time': time.time(),
        'admin_id': ctx.author.id,
        'status': 'running'
    }
    
    index = 0
    while not stop_flags.get(task_id, False):
        try:
            await send_typing_indicator(channel_id, user_token)
            await asyncio.sleep(delay)
            
            tags = ' '.join([f'<@{user_id}>' for user_id in user_id_list])
            message = f"# {lines[index]} {tags}"
            
            status, resp = send_message_user_token(channel_id, user_token, message)
            
            if status not in (200, 201):
                error_msg = f"Lỗi gửi tin: {status} - {resp}"
                print(error_msg)
                
                if status == 403:
                    await ctx.send("Token không có quyền gửi tin nhắn!")
                    break
                if status == 404:
                    await ctx.send("Không tìm thấy kênh hoặc người dùng!")
                    break
                if status == 429:
                    await ctx.send("Bị rate limit, đợi 10s thử lại...")
                    await asyncio.sleep(10)
                    continue
            
            index = (index + 1) % len(lines)
            await asyncio.sleep(delay)
            
        except Exception as e:
            error_msg = f"Lỗi trong loop_nhaytagdis: {str(e)}"
            print(error_msg)
            await asyncio.sleep(10)
    
    if task_id in discord_threads:
        discord_threads[task_id]['status'] = 'stopped'
        discord_threads[task_id]['end_time'] = time.time()
    
    await ctx.send(f"Đã dừng nhây tag Discord vào kênh {channel_id}")

async def loop_nhaydisc(channel_id, user_token, lines, delay, ctx):
    stop_flags[channel_id] = False
    while not stop_flags.get(channel_id, True):
        for line in lines:
            if stop_flags.get(channel_id, True):
                break
                
            await send_typing_indicator(channel_id, user_token)
            await asyncio.sleep(delay)
            
            message = f"# {line}"
            
            status, resp = send_message_user_token(channel_id, user_token, message)
            if status not in (200, 201):
                await ctx.send(f"Lỗi gửi tin: {status} - {resp}")
                stop_flags[channel_id] = True
                break
            await asyncio.sleep(delay)
    await ctx.send(f"Đã dừng nhây Discord vào kênh {channel_id}")

@bot.command()
async def ngondis(ctx, channel_id, user_token, filename, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    file_path = os.path.join(DATA_FOLDER, filename)
    if not os.path.exists(file_path):
        return await ctx.send(f"File {filename} không tồn tại!")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    except Exception as e:
        return await ctx.send(f"Lỗi đọc file: {e}")
    if not content:
        return await ctx.send("File rỗng, không có nội dung để gửi")
    task = asyncio.create_task(loop_ngondisc(channel_id, user_token, content, delay, ctx))
    task_storage[channel_id] = task
    
    print(f"[+] Bắt Đầu Treo Discord Kênh Mỗi {delay} giây.")	    
    
    await ctx.send(f"Bắt Đầu Treo Dis Kênh {channel_id}")

@bot.command()
async def nhaydis(ctx, channel_id, user_token, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    
    filename = "nhay.txt"
    file_path = os.path.join(DATA_FOLDER, filename)
    
    if not os.path.exists(file_path):
        return await ctx.send(f"File {filename} không tồn tại!")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return await ctx.send(f"Lỗi đọc file: {e}")
    
    if not lines:
        return await ctx.send("File rỗng hoặc không có dòng nào để gửi")
    
    task = asyncio.create_task(loop_nhaydisc(channel_id, user_token, lines, delay, ctx))
    task_storage[channel_id] = task
    
    print(f"[+] Bắt Đầu Nhây Discord Kênh Mỗi {delay} giây.")
  
    await ctx.send(f"Bắt đầu nhây dis vào kênh {channel_id}")

@bot.command()
async def nhaytagdis(ctx, channel_id: str, user_token: str, user_ids: str, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    filename = "nhay.txt"
    file_path = os.path.join(DATA_FOLDER, filename)
    
    if not os.path.exists(file_path):
        return await ctx.send(f"File {filename} không tồn tại!")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return await ctx.send(f"Lỗi đọc file: {e}")
    
    if not lines:
        return await ctx.send("File rỗng hoặc không có dòng nào để gửi")

    if delay < 1:
        return await ctx.send("Delay phải lớn hơn hoặc bằng 1 giây")

    asyncio.create_task(loop_nhaytagdis(channel_id, user_token, user_ids, lines, delay, ctx))

    print(f"[+] Bắt Đầu Nhây Tag Discord Kênh Mỗi {delay} giây.")
    
    await ctx.send(
        f"Đã bắt đầu nhây tag dis:\n"
        f"• Kênh: {channel_id}\n"
        f"• Tag: {user_ids}\n"
        f"• Delay: {delay}s\n"
        f"Dùng lệnh `.stopnhaytagdis` để dừng"
    )

@bot.command()
async def tabnhaytagdis(ctx):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    active_task_storage = []
    for task_id, task_data in discord_threads.items():
        if task_id.startswith("nhaytagdis_") and not stop_flags.get(task_id, True):
            duration = str(datetime.now() - datetime.fromtimestamp(task_data['start_time'])).split('.')[0]
            active_task_storage.append({
                'channel_id': task_data['channel_id'],
                'user_ids': ', '.join(task_data['user_ids']),
                'duration': duration,
                'task_id': task_id
            })

    if not active_task_storage:
        return await ctx.send("Không có task nhaytagdis nào đang chạy.")

    embed = discord.Embed(
        title="Danh Sách Task Nhây Tag Discord Đang Chạy",
        color=0xB8F0FF
    )
    
    for i, task in enumerate(active_task_storage, 1):
        embed.add_field(
            name=f"{i}. Kênh: {task['channel_id']}",
            value=f"Tag: {task['user_ids']}\nĐã chạy: {task['duration']}",
            inline=False
        )

    embed.set_footer(text="Dùng .stopnhaytagdis [số] để dừng task")
    await ctx.send(embed=embed)

@bot.command()
async def stopnhaytagdis(ctx, channel_id: str = None):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    if channel_id is None:
        return await tabnhaytagdis(ctx)

    if channel_id.lower() == 'all':
        stopped_count = 0
        for task_id, task_data in discord_threads.items():
            if task_id.startswith("nhaytagdis_") and not stop_flags.get(task_id, True):
                if ctx.author.id == IDADMIN_GOC or task_data['admin_id'] == ctx.author.id:
                    stop_flags[task_id] = True
                    if task_id in discord_threads:
                        discord_threads[task_id]['status'] = 'stopped'
                        discord_threads[task_id]['end_time'] = time.time()
                    stopped_count += 1
        return await ctx.send(f"Đã dừng {stopped_count} task nhaytagdis.")

    stopped = False
    for task_id, task_data in discord_threads.items():
        if (task_id.startswith("nhaytagdis_") and 
            not stop_flags.get(task_id, True) and 
            task_data['channel_id'] == channel_id):
            
            if ctx.author.id != IDADMIN_GOC and task_data['admin_id'] != ctx.author.id:
                continue
                
            stop_flags[task_id] = True
            if task_id in discord_threads:
                discord_threads[task_id]['status'] = 'stopped'
                discord_threads[task_id]['end_time'] = time.time()
            stopped = True

    if stopped:
        await ctx.send(f"Đã dừng task nhaytagdis tại kênh {channel_id}")
    else:
        await ctx.send(f"Không tìm thấy task nhaytagdis nào đang chạy tại kênh {channel_id}")


@bot.command()
async def stopngondis(ctx, channel_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    stop_flags[channel_id] = True
    task = task_storage.get(channel_id)
    if task:
        task.cancel()
    await ctx.send(f"Đã dừng channel Discord {channel_id}")

@bot.command()
async def stopnhaydis(ctx, channel_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    stop_flags[channel_id] = True
    task = task_storage.get(channel_id)
    if task:
        task.cancel()
    await ctx.send(f"Đã dừng channel Discord {channel_id}")

@bot.command()
async def tabngondis(ctx, channel_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    running = not stop_flags.get(channel_id, True)
    await ctx.send(f"Channel Discord {channel_id} đang {'chạy' if running else 'dừng'}")

@bot.command()
async def tabnhaydis(ctx, channel_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    running = not stop_flags.get(channel_id, True)
    await ctx.send(f"Channel Discord {channel_id} đang {'chạy' if running else 'dừng'}")

async def send_telegram_message(token, chat_id, text, image_url=None):
    async with aiohttp.ClientSession() as session:
        if image_url:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            data = {
                'chat_id': chat_id,
                'caption': text,
                'photo': image_url
            }
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
        async with session.post(url, data=data) as resp:
            if resp.status != 200:
                raise Exception(await resp.text())

async def loop_ngontele(chat_id, token, content, delay, ctx):
    while not stop_flags.get(chat_id, False):
        try:
            await send_telegram_message(token, chat_id, content)
        except Exception as e:
            await ctx.send(f"Lỗi gửi tin nhắn ngontele: {e}")
        await asyncio.sleep(delay)
    await ctx.send(f"Đã dừng ngontele {chat_id}")

async def loop_nhaytele(chat_id, token, lines, delay, ctx):
    while not stop_flags.get(chat_id, False):
        for line in lines:
            if stop_flags.get(chat_id, False):
                break
            try:
                await send_telegram_message(token, chat_id, line)
            except Exception as e:
                await ctx.send(f"Lỗi nhaytele: {e}")
            await asyncio.sleep(delay)
    await ctx.send(f"Đã dừng nhaytele {chat_id}")

async def loop_nhaytagtele(chat_id, token, user_id, lines, delay, ctx):
    while not stop_flags.get(chat_id, False):
        for line in lines:
            if stop_flags.get(chat_id, False):
                break
            text = f'<a href="tg://user?id={user_id}">{line}</a>'
            try:
                await send_telegram_message(token, chat_id, text)
            except Exception as e:
                await ctx.send(f"Lỗi nhaytagtele: {e}")
            await asyncio.sleep(delay)
    await ctx.send(f"Đã dừng nhaytagtele {chat_id}")

async def loop_nhayanhtele(chat_id, token, lines, image_url, delay, ctx):
    while not stop_flags.get(chat_id, False):
        for line in lines:
            if stop_flags.get(chat_id, False):
                break
            try:
                await send_telegram_message(token, chat_id, line, image_url)
            except Exception as e:
                await ctx.send(f"Lỗi nhayanhtele: {e}")
            await asyncio.sleep(delay)
    await ctx.send(f"Đã dừng nhayanhtele {chat_id}")

@bot.command()
async def ngontele(ctx, chat_id, token, filename, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    path = os.path.join(DATA_FOLDER, filename)
    if not os.path.exists(path):
        return await ctx.send("File không tồn tại!")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    stop_flags[chat_id] = False
    task_storage[chat_id] = asyncio.create_task(loop_ngontele(chat_id, token, content, delay, ctx))
    await ctx.send(f"Đã bắt đầu ngontele {chat_id}")

@bot.command()
async def nhaytele(ctx, chat_id, token, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    
    filename = "nhay.txt"
    path = os.path.join(DATA_FOLDER, filename)
    
    if not os.path.exists(path):
        return await ctx.send("File nhay.txt không tồn tại!")
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    stop_flags[chat_id] = False
    task_storage[chat_id] = asyncio.create_task(loop_nhaytele(chat_id, token, lines, delay, ctx))
    await ctx.send(f"Đã bắt đầu nhaytele {chat_id}")

@bot.command()
async def nhaytagtele(ctx, chat_id, token, user_id, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    
    filename = "nhay.txt"
    path = os.path.join(DATA_FOLDER, filename)
    
    if not os.path.exists(path):
        return await ctx.send("File nhay.txt không tồn tại!")
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    stop_flags[chat_id] = False
    task_storage[chat_id] = asyncio.create_task(loop_nhaytagtele(chat_id, token, user_id, lines, delay, ctx))
    await ctx.send(f"Đã bắt đầu nhaytagtele {chat_id}")

@bot.command()
async def nhayanhtele(ctx, chat_id, token, image_url, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    
    filename = "nhay.txt"
    path = os.path.join(DATA_FOLDER, filename)
    
    if not os.path.exists(path):
        return await ctx.send("File nhay.txt không tồn tại!")
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    stop_flags[chat_id] = False
    task_storage[chat_id] = asyncio.create_task(loop_nhayanhtele(chat_id, token, lines, image_url, delay, ctx))
    await ctx.send(f"Đã bắt đầu nhayanhtele {chat_id}")

@bot.command()
async def stopngontele(ctx, chat_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    stop_flags[chat_id] = True
    task = task_storage.get(chat_id)
    if task:
        task.cancel()
    await ctx.send(f"Đã dừng ngontele {chat_id}")

@bot.command()
async def stopnhaytele(ctx, chat_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    stop_flags[chat_id] = True
    task = task_storage.get(chat_id)
    if task:
        task.cancel()
    await ctx.send(f"Đã dừng nhaytele {chat_id}")

@bot.command()
async def stopnhaytagtele(ctx, chat_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    stop_flags[chat_id] = True
    task = task_storage.get(chat_id)
    if task:
        task.cancel()
    await ctx.send(f"Đã dừng nhaytagtele {chat_id}")

@bot.command()
async def stopnhayanhtele(ctx, chat_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    stop_flags[chat_id] = True
    task = task_storage.get(chat_id)
    if task:
        task.cancel()
    await ctx.send(f"Đã dừng nhayanhtele {chat_id}")

@bot.command()
async def tabngontele(ctx, chat_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    running = not stop_flags.get(chat_id, True)
    await ctx.send(f"ngontele {chat_id} đang {'chạy' if running else 'dừng'}")

@bot.command()
async def tabnhaytele(ctx, chat_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    running = not stop_flags.get(chat_id, True)
    await ctx.send(f"nhaytele {chat_id} đang {'chạy' if running else 'dừng'}")

@bot.command()
async def tabnhaytagtele(ctx, chat_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    running = not stop_flags.get(chat_id, True)
    await ctx.send(f"nhaytagtele {chat_id} đang {'chạy' if running else 'dừng'}")

@bot.command()
async def tabnhayanhtele(ctx, chat_id):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    running = not stop_flags.get(chat_id, True)
    await ctx.send(f"nhayanhtele {chat_id} đang {'chạy' if running else 'dừng'}")

class GmailAccount:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.active = True

@bot.command()
async def treogmail(ctx, delay: float):
    """Bắt đầu gửi email spam"""
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    
    await ctx.send("Nhập danh sách tài khoản Gmail (định dạng: email1|password1,email2|password2,...):")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        accounts_input = msg.content.strip()
    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ nhập tài khoản.")
    
    accounts = []
    account_entries = [entry.strip() for entry in accounts_input.split(',') if entry.strip()]
    for entry in account_entries:
        if '|' in entry:
            email, password = entry.split('|', 1)
            email = email.strip()
            password = password.strip()
            if email and password:
                accounts.append(GmailAccount(email, password))
    
    if not accounts:
        return await ctx.send("Không có tài khoản Gmail hợp lệ.")
    
    await ctx.send("Nhập email nhận:")
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        to_email = msg.content.strip()
    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ nhập email nhận.")
    
    if not to_email:
        return await ctx.send("Email nhận không được để trống.")
    
    await ctx.send("Nhập nội dung email:")
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        content = msg.content.strip()
    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ nhập nội dung.")
    
    if not content:
        return await ctx.send("Nội dung không được để trống.")

    print(f"[+] Bắt Đầu Treo Gmail với {len(accounts)} tài khoản đến {to_email} mỗi {delay} giây.")
    
    task_id = f"treogmail_{to_email}_{int(time.time())}"
    
    async def send_email_loop():
        idx = 0
        while task_id in running_task_storage:
            active_accounts = [acc for acc in accounts if acc.active]
            if not active_accounts:
                for acc in accounts:
                    acc.active = True
                active_accounts = accounts
            
            account = active_accounts[idx % len(active_accounts)]
            
            try:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                    server.login(account.email, account.password)
                    msg = MIMEText(content)
                    msg["From"] = account.email
                    msg["To"] = to_email
                    msg["Subject"] = " "
                    server.sendmail(account.email, to_email, msg.as_string())
            except Exception as e:
                print(f"[!] Lỗi khi gửi email từ {account.email}: {str(e)}")
                account.active = False
            
            idx += 1
            line_idx += 1
            await asyncio.sleep(delay)
    
    task = asyncio.create_task(send_email_loop())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'to_email': to_email,
        'account_count': len(accounts),
        'type': 'treogmail'
    }
    
    embed = discord.Embed(
        title="Bắt Đầu Treo Gmail",
        description=f"Đang gửi email tới {to_email}",
        color=0xB8F0FF
    )
    embed.add_field(name="Số tài khoản", value=str(len(accounts)), inline=True)
    embed.add_field(name="Delay", value=f"{delay} giây", inline=True)
    embed.add_field(name="Dừng task", value=f"Dùng lệnh .stoptask {len(running_task_storage)}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def nhaygmail(ctx, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    
    filename = "nhay.txt"
    path = os.path.join(DATA_FOLDER, filename)
    
    if not os.path.exists(path):
        return await ctx.send(f"File {filename} không tồn tại!")
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return await ctx.send(f"Lỗi đọc file: {e}")
    
    if not lines:
        return await ctx.send("File nhay.txt rỗng, không có nội dung để gửi")
    
    await ctx.send("Nhập danh sách tài khoản Gmail (định dạng: email1|password1,email2|password2,...):")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        accounts_input = msg.content.strip()
    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ nhập tài khoản.")
    
    accounts = []
    account_entries = [entry.strip() for entry in accounts_input.split(',') if entry.strip()]
    for entry in account_entries:
        if '|' in entry:
            email, password = entry.split('|', 1)
            email = email.strip()
            password = password.strip()
            if email and password:
                accounts.append(GmailAccount(email, password))
    
    if not accounts:
        return await ctx.send("Không có tài khoản Gmail hợp lệ.")
    
    await ctx.send("Nhập email nhận:")
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        to_email = msg.content.strip()
    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ nhập email nhận.")
    
    if not to_email:
        return await ctx.send("Email nhận không được để trống.")
 
    print(f"[+] Bắt Đầu Nhây Gmail với {len(accounts)} tài khoản đến {to_email} mỗi {delay} giây.")
   
    task_id = f"nhaygmail_{to_email}_{int(time.time())}"
    
    async def send_email_loop():
        idx = 0
        line_idx = 0
        while task_id in running_task_storage:
            active_accounts = [acc for acc in accounts if acc.active]
            if not active_accounts:
                for acc in accounts:
                    acc.active = True
                active_accounts = accounts
            
            account = active_accounts[idx % len(active_accounts)]
            content = lines[line_idx % len(lines)]
            
            try:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                    server.login(account.email, account.password)
                    msg = MIMEText(content)
                    msg["From"] = account.email
                    msg["To"] = to_email
                    msg["Subject"] = " "
                    server.sendmail(account.email, to_email, msg.as_string())
            except Exception as e:
                print(f"[!] Lỗi khi gửi email từ {account.email}: {str(e)}")
                account.active = False
            
            idx += 1
            line_idx += 1
            await asyncio.sleep(delay)
    
    task = asyncio.create_task(send_email_loop())
    running_task_storage[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'to_email': to_email,
        'account_count': len(accounts),
        'content_lines': len(lines),
        'type': 'nhaygmail'
    }
    
    embed = discord.Embed(
        title="Bắt Đầu Nhây Gmail",
        description=f"Đang Nhây email tới {to_email}",
        color=0xB8F0FF
    )
    embed.add_field(name="Số Lượng tài khoản", value=str(len(accounts)), inline=True)
    embed.add_field(name="Delay", value=f"{delay} giây", inline=True)
    embed.add_field(name="Dừng task", value=f"Dùng lệnh .stoptask {len(running_task_storage)}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def menu(ctx):
    embed = discord.Embed(
        title="『Menu Bot 4 App | Trọng Nhân』",
        description=f"""
[Facebook Admin](https://www.facebook.com/share/198swaLh2e/)
Admin: Trọng Nhân💔
Ngày Update Bot Này: 25/6/2025

Owner VIP Commands
💤 • .add
💤 • .xoa
💤 • .list

Messenger

🎭 • .setfile
🎭 • .xemfileset
🎭 • .danhsachtask
🎭 • .stoptask
🎭 • .treo
🎭 • .nhay — Fake Soạn
🎭 • .treoso — Fake Soạn
🎭 • .nhayicon — Fake Soạn
🎭 • .nhaytag — Fake Soạn
🎭 • .nhaytagfaketen — Fake Soạn
🎭 • .nhay2c — Fake Soạn
🎭 • .sotagfaketen — Fake Soạn
🎭 • .sotag — Fake Soạn
🎭 • .ideamess — Fake Soạn
🎭 • .codelag — Fake Soạn
🎭 • .nhaynamebox


Facebook

🌐 • .setfile
🌐 • .xemfileset
🌐 • .danhsachtask
🌐 • .stoptask
🌐 • .nhaytop
🌐 • .sotop
🌐 • .treotop
🌐 • .reostr
🌐 • .treoso
🌐 • .listbox

Discord

⚡ • .setfilev2
⚡ • .ngondis
⚡ • .nhaydis — Fake Soạn
⚡ • .nhaytagdis — Fake Soạn
⚡ • .tabngondis
⚡ • .tabnhaydis
⚡ • .tabnhaytagdis
⚡ • .stopngondis
⚡ • .stopnhaydis
⚡ • .stopnhaytagdis

Telegram

💢 • .setfilev2
💢 • .ngontele
💢 • .nhaytele
💢 • .nhaytagtele
💢 • .nhayanhtele
💢 • .tabngontele
💢 • .tabnhaytele"
💢 • .tabnhaytagtele
💢 • .tabnhayanhtele
💢 • .stopngontele
💢 • .stopnhaytele
💢 • .stopnhaytagtele
💢 • .stopnhayanhtele

Gmail

✉️ • .treogmail
✉️ • .nhaygmail

Hướng Dẫn Dùng Bot*
🔥 • .hdan
""",
        color=0xB8F0FF
    )

    await ctx.send(embed=embed)

@bot.command()
async def hdan(ctx):
    embed = discord.Embed(
        title="『Hướng Dẫn Dùng Lệnh』",
        description=f"""  
Hướng Dẫn

.treo idbox cookie> file delay — Treo Mess
.nhay idbox cookie delay — Nhây Mess Fake Soạn
.nhayicon idbox cookie icon delay — Nhây Icon Fake Soạn
.nhaytag idbox cookie id delay — Nhây Tag Fake Soạn
.nhaytagfakten idbox cookie "tên fake" id delay — Nhây Tag Fake Tên Fake Soạn
.sotagfakten idbox cookie "tên fake" id delay — Sớ Tag Fake Tên Fake Soạn
.nhay2c idbox cookie delay — Nhây 2 Chữ Fake Soạn
.treoso idbox cookie delay — Treo Sớ Super Múp Fake Soạn
.sotag idbox cookie id delay — Thả Sớ Tag Fake Soạn
.ideamess idbox cookie delay  — Ideamess Fake Soạn
.codelag idbox cookie delay  — Code Lag Fake Soạn
.nhaynamebox idbox cookie delay  — Nhây Name Box
.nhaytop cookie delay — Nhây Top
.sotop cookie> delay — Thả Sớ Top
.treotop cookie delay file.txt — Treo Top
.reostr cookie id delay — Réo Story
.listbox cookie — Show Box Bằng Cookie

Telegram:
.ngontele idkenh token file delay — Treo Telegram
.nhaytele idkenh token delay — Nhây Telegram
.nhaytagtele idkenh token id delay — Nhây tag Telegram
.nhayanhtele idkenh token urhanh delay — Nhây ảnh Telegram
.stopngontele idkenh — Stop Treo Telegram
.stopnhaytele idkenh — Stop Nhây Telegram
.stopnhaytagtele idkenh — Stop Nhây tag Telegram
.stopnhayanhtele idkenh — Stop Nhây ảnh Telegram

Discord:
.ngondis idkenh token file delay — Treo Discord
.nhaydis idkenh token delay — Nhây Discord Có Fake Soạn
.nhaytagdis idkenh token id delay — Nhây Tag Discord Có Fake Soạn 
.stopnhaydis idkenh — Stop Nhây Discord
.stopngondis idkenh — Stop Treo Discord
.stopnhaytagdis idkenh — Stop Nhây Tag Discord

Gmail:
.treogmail delay — Treo Gmail
.nhaygmail delay — Nhây Gmail

Chức Năng Phụ
.setfilev2 — Gửi Kèm File Dùng Cho Chức Năng Dis Và Tele
.setfile — Gửi Kèm File
.xemfileset — Xem File
.danhsachtask — Xem Danh Sách Task
.stoptask [số của task] — Xoá Task
""",
        color=0xB8F0FF
    )

    await ctx.send(embed=embed)

@tasks.loop(seconds=1)
async def heartbeat():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Trọng Nhân"))

@bot.event
async def on_ready():
    print(f'\033[35m{bot.user} đã kết nối thành công')
    if not heartbeat.is_running():
        heartbeat.start()    


if __name__ == "__main__":
    bot.run(TOKEN)