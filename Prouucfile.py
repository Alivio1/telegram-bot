# telegram_bot.py
import logging
import sqlite3
import json
import hashlib
import time
import random
import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import NetworkError, TimedOut, RetryAfter
import requests
import base64
import urllib.parse
import os
import zipfile
import tempfile
import shutil
import xml.etree.ElementTree as ET
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad

# ==================== 配置 ====================
TOKEN = "8578271412:AAEVeaeMnwSOwFT8aXIMLOYN-ewtR5Hdt9A"
ADMIN_IDS = [7410111825]
BASE_URL = "http://www.gxdlys.com"
MY_PHONE = "19395814828"
PASSWORD = "11111Qq."

# ==================== 欢迎图片配置 ====================
WELCOME_IMAGE_URL = "https://i.ibb.co/j9rHcWFt/IMG-20260703-145418-enhanced.jpg"

# ==================== 引用语列表 ====================
QUOTE_MESSAGES = [
    "我變得如此鋒利究竟是為了刺穿什麼",
    "人和人之间除了骗就是演 就连天气也会骗人",
    "旺财快回来不要打扰到这位美女 我为我家旺财的行为感到抱歉 能不能加个wx给你道歉呢",
    "缝缝补补太多次了 直到有一天我忽然觉得不太体面 算了 我不要了",
    "左边画个虫虫🐛右边画个龙龙🐲不要对我凶凶🥰我的心会痛痛❤️",
    "似乎一切都是短暂的",
    "难吃的东西你不会吃第二次 让你难过的人却原谅了很多次",
    "时间永远是消除记忆的最好办法",
    "一辈子很短 要爱对的人",
    "遇见你那天起 这把刀我就亲手交给了你 怎么捅都好 我都愿意",
    "时间是个好词 能代替所有的一言难尽",
    "同在一片天空下 为何好久不见",
    "人与人之间有过那一瞬就足够了",
    "当你在读这句话的时候 这一刻你属于我",
    "我们是对方 特别的人",
    "再见这个词 是告别 还是约定",
    "或许你也偷看过我 但你并不喜欢我",
    "是时间不对 又或许是我不对",
    "抱歉 是我让你失望了",
]

# ==================== 日志 ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== 查询API ====================
class GovQueryAPI:
    def __init__(self):
        self.base_url = "https://chaxun.govsvip.com/yuan-zhou-si-ma/"
        self.ak = "ak_fbb63a44da42eceb64cbf2e397d2f19bd70116cc_20f02ccc"

    def query(self, content: str) -> Optional[Dict]:
        """查询数据 - 过滤公告"""
        try:
            args = urllib.parse.urlencode({"key": self.ak, "cx": content})
            url = f"{self.base_url}?{args}"
            print(f"[查询] 请求URL: {url}")
            
            req = urllib.request.urlopen(url, timeout=15)
            raw_content = req.read().decode("utf-8")
            print(f"[查询] 响应内容长度: {len(raw_content)}")
            
            # ===== 过滤公告行 =====
            skip_keywords = ['公告', '刀盟', '斩龙殿', '烂梗', '虚圈', '甘雨社', 'Key公告', '系统公告', '公益查询', '可用服务', '没有KEY']
            lines = raw_content.split('\n')
            filtered_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                
                should_skip = False
                for keyword in skip_keywords:
                    if keyword in line_stripped:
                        should_skip = True
                        break
                
                if not should_skip:
                    filtered_lines.append(line_stripped)
            
            filtered_content = '\n'.join(filtered_lines)
            
            # 如果过滤后没有内容，返回原始数据（让上层处理）
            if not filtered_content:
                return {"raw": raw_content, "success": True}
            
            try:
                return json.loads(filtered_content)
            except:
                return {"raw": filtered_content, "success": True}
                
        except Exception as e:
            print(f"[查询失败] 异常: {e}")
            return {"error": str(e), "success": False}

# ==================== OFD身份证提取器 ====================
class OFDIDCardExtractor:
    def __init__(self, ofd_content):
        self.ofd_content = ofd_content
        self.temp_dir = None
        self.namespace = {'ofd': 'http://www.ofdspec.org/2016'}
        self.id_card_info = {
            '姓名': '',
            '性别': '',
            '民族': '',
            '出生日期': '',
            '住址': '',
            '身份证号': '',
            '签发机关': '',
            '有效期限': ''
        }
        self.photo_content = None

    def extract_ofd(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ofd_extract_")
        temp_ofd_path = os.path.join(self.temp_dir, "temp.ofd")
        with open(temp_ofd_path, 'wb') as f:
            f.write(self.ofd_content)
        extract_dir = os.path.join(self.temp_dir, "extracted")
        with zipfile.ZipFile(temp_ofd_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        self.temp_dir = extract_dir

    def get_resource_mapping(self):
        resource_map = {}
        doc_res_path = os.path.join(self.temp_dir, 'Doc_0', 'DocumentRes.xml')
        if os.path.exists(doc_res_path):
            tree = ET.parse(doc_res_path)
            root = tree.getroot()
            for media in root.findall('.//ofd:MultiMedia', self.namespace):
                media_id = media.get('ID')
                media_file = media.find('ofd:MediaFile', self.namespace)
                if media_file is not None:
                    resource_map[media_id] = media_file.text
        return resource_map

    def extract_page_content(self, page_num):
        page_path = os.path.join(self.temp_dir, 'Doc_0', 'Pages', f'Page_{page_num}', 'Content.xml')
        if not os.path.exists(page_path):
            return [], []
        tree = ET.parse(page_path)
        root = tree.getroot()
        texts = []
        for text_obj in root.findall('.//ofd:TextObject', self.namespace):
            text_code = text_obj.find('.//ofd:TextCode', self.namespace)
            if text_code is not None and text_code.text:
                texts.append(text_code.text.strip())
        image_ids = []
        for img_obj in root.findall('.//ofd:ImageObject', self.namespace):
            resource_id = img_obj.get('ResourceID')
            if resource_id:
                image_ids.append(resource_id)
        return texts, image_ids

    def parse_id_card_info(self):
        resource_map = self.get_resource_mapping()
        texts_page0, image_ids_page0 = self.extract_page_content(0)
        if image_ids_page0 and image_ids_page0[0] in resource_map:
            photo_file = resource_map[image_ids_page0[0]]
            photo_src = os.path.join(self.temp_dir, 'Doc_0', 'Res', photo_file)
            if os.path.exists(photo_src):
                with open(photo_src, 'rb') as f:
                    self.photo_content = f.read()
        name_found = False
        birth_parts = []
        for i, text in enumerate(texts_page0):
            if not name_found and len(text) <= 10 and not any(char.isdigit() for char in text) and text not in ['男', '女']:
                if len(text) >= 2 and all('一' <= char <= '鿿' for char in text):
                    self.id_card_info['姓名'] = text
                    name_found = True
                    continue
            if text in ['男', '女']:
                self.id_card_info['性别'] = text
                continue
            if len(text) <= 3 and text not in ['男', '女'] and not text.isdigit() and all('一' <= char <= '鿿' for char in text):
                if not self.id_card_info['民族']:
                    self.id_card_info['民族'] = text
                    continue
            if text.isdigit():
                if len(text) == 4 and (text.startswith('19') or text.startswith('20')):
                    birth_parts.append(text)
                elif len(text) == 2 and len(birth_parts) > 0:
                    birth_parts.append(text)
                elif len(text) == 18:
                    self.id_card_info['身份证号'] = text
            if len(text) > 10 and any(keyword in text for keyword in ['省', '市', '县', '区', '镇', '村', '路', '街']):
                self.id_card_info['住址'] = text
        if len(birth_parts) >= 3:
            self.id_card_info['出生日期'] = f"{birth_parts[0]}年{birth_parts[1]}月{birth_parts[2]}日"
        texts_page1, _ = self.extract_page_content(1)
        date_parts = []
        for text in texts_page1:
            if '公安局' in text or '公安分局' in text:
                self.id_card_info['签发机关'] = text
            elif '.' in text and len(text) >= 8:
                date_parts.append(text)
            elif text in ['长期', '长久', '永久']:
                date_parts.append(text)
        if len(date_parts) >= 2:
            self.id_card_info['有效期限'] = f"{date_parts[0]}-{date_parts[1]}"
        elif len(date_parts) == 1:
            self.id_card_info['有效期限'] = date_parts[0]

    def cleanup(self):
        if self.temp_dir:
            parent_dir = os.path.dirname(self.temp_dir)
            if os.path.exists(parent_dir) and parent_dir.startswith(tempfile.gettempdir()):
                shutil.rmtree(parent_dir, ignore_errors=True)

    def extract(self):
        try:
            self.extract_ofd()
            self.parse_id_card_info()
            return {
                'info': self.id_card_info,
                'photo': self.photo_content
            }
        except Exception as e:
            print(f"[OFD提取失败] {str(e)}")
            return None
        finally:
            self.cleanup()
# ==================== 湖南省政务配置 ====================
HUNAN_CLIENT_ID = "sXK6HBx3QwuJqaMXqmx2fQ"
HUNAN_LOGIN_AES_KEY = HUNAN_CLIENT_ID[:16].encode()
HUNAN_LOGIN_AES_IV = HUNAN_LOGIN_AES_KEY
HUNAN_RSA_PUB_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDC8/aNjKJzZTNdjUvIZeu8sTrd\n"
    "IDdb2uAk/OtWm4jpn1dPYwIiwfmlf+KCnr9jwhwluLEFw+fSUFbz4a56fuOMllVD\n"
    "DvsS5forqB/y+koZfZcdeDQNumgbbFMvJQuSXEpe00nMBzJjK1tRY3zDbDkrWV7H\n"
    "P2jzeIIHKFhxHq1c6QIDAQAB\n"
    "-----END PUBLIC KEY-----\n"
)
HUNAN_AUTH_HOST = "https://auth.zwfw.hunan.gov.cn"
HUNAN_ZW_HOST = "https://zwfw-new.hunan.gov.cn"
HUNAN_ONETHING_CODE = "43PCP0021"
HUNAN_DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"

# ==================== 湖南省政务客户端 ====================
class HunanZwfwClient:
    def __init__(self, account: str, password: str, user_cert_num: str):
        self.account = account
        self.password = password
        self.user_cert_num = user_cert_num
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers["User-Agent"] = HUNAN_DEFAULT_UA
        self.aes_key_c = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-', k=16)).encode()
        self.aes_iv_c = self.aes_key_c[::-1]
        self.zw_key = self._rsa_encrypt(self.aes_key_c.decode())
        self.captcha_key = 0
        self.onething_approve_version_id = ""
        self.guide_process_id = ""
        self.onething_checklist_id = ""
        self.onething_instance_id = ""

    def _rsa_encrypt(self, plaintext: str) -> str:
        key = RSA.import_key(HUNAN_RSA_PUB_PEM)
        return base64.b64encode(PKCS1_v1_5.new(key).encrypt(plaintext.encode("utf-8"))).decode()

    def _aes_encrypt(self, plaintext: str) -> str:
        cipher = AES.new(self.aes_key_c, AES.MODE_CBC, self.aes_iv_c)
        return base64.b64encode(cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))).decode()

    def _aes_decrypt(self, b64_ct: str) -> str:
        raw = base64.b64decode(b64_ct.replace("-", "+").replace("_", "/") + "==")
        return unpad(AES.new(self.aes_key_c, AES.MODE_CBC, self.aes_iv_c).decrypt(raw), AES.block_size).decode("utf-8")

    def _login_encrypt(self, text: str) -> str:
        cipher = AES.new(HUNAN_LOGIN_AES_KEY, AES.MODE_CBC, HUNAN_LOGIN_AES_IV)
        return base64.b64encode(cipher.encrypt(pad(text.encode("utf-8"), AES.block_size))).decode()

    def _gw_headers(self, with_zwkey: bool = True) -> dict:
        h = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": HUNAN_ZW_HOST,
            "Referer": f"{HUNAN_ZW_HOST}/hnywtb/onething/html/situationGuideForm.html",
        }
        if with_zwkey:
            h["ZW-KEY"] = self.zw_key
        return h

    def _gateway_post(self, biz_url: str, body: Optional[dict] = None, encrypt_body: bool = True) -> dict:
        form = {"url": biz_url}
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
            form["data"] = self._aes_encrypt(payload) if encrypt_body else payload
        try:
            r = self.session.post(
                f"{HUNAN_ZW_HOST}/hnywtb/login?action=toHttpPost",
                data=form,
                headers=self._gw_headers(with_zwkey=True),
                timeout=60,
            )
            r.raise_for_status()
            if not r.text or r.text.strip() == "":
                print(f"[_gateway_post] 空响应: {biz_url}")
                return {"code": -1, "msg": "空响应", "success": False}
            try:
                return r.json()
            except Exception as e:
                print(f"[_gateway_post] JSON解析失败: {e}, 响应内容: {r.text[:200]}")
                return {"code": -1, "msg": f"JSON解析失败", "success": False, "raw": r.text}
        except Exception as e:
            print(f"[_gateway_post] 请求异常: {e}")
            return {"code": -1, "msg": str(e), "success": False}

    def _gateway_get(self, biz_url: str) -> dict:
        try:
            r = self.session.post(
                f"{HUNAN_ZW_HOST}/hnywtb/login?action=toHttpGet",
                data={"url": biz_url},
                headers=self._gw_headers(with_zwkey=True),
                timeout=30,
            )
            r.raise_for_status()
            if not r.text or r.text.strip() == "":
                print(f"[_gateway_get] 空响应: {biz_url}")
                return {"code": -1, "msg": "空响应", "success": False}
            try:
                return r.json()
            except Exception as e:
                print(f"[_gateway_get] JSON解析失败: {e}, 响应内容: {r.text[:200]}")
                return {"code": -1, "msg": f"JSON解析失败", "success": False, "raw": r.text}
        except Exception as e:
            print(f"[_gateway_get] 请求异常: {e}")
            return {"code": -1, "msg": str(e), "success": False}

    def login(self) -> bool:
        try:
            login_url = (
                f"{HUNAN_AUTH_HOST}/oauth2/appGovLogin.jsp?client_id={HUNAN_CLIENT_ID}"
                f"&response_type=gov"
                f"&redirect_uri={HUNAN_ZW_HOST}/hnywtb/oauth2-login"
                f"?backUrl=/onething/html/userNeedKnow.html?onethingCode={HUNAN_ONETHING_CODE}"
            )
            self.session.get(login_url, timeout=30)
            self.captcha_key = random.randint(1, 10**8)
            cap = self.session.get(
                f"{HUNAN_AUTH_HOST}/c2ssocaptcha/{self.captcha_key}/captchanumber",
                headers={"Referer": login_url}, timeout=15,
            )
            cap.raise_for_status()
            captcha_text = cap.text.strip()
            print(f"[湖南登录] captcha={captcha_text}")
            body = {
                "loginType": "gov",
                "verifyCode": self._login_encrypt(""),
                "userType": "1",
                "account": self._login_encrypt(self.account),
                "password": self._login_encrypt(self.password),
                "captchaKey": self.captcha_key,
                "captchaText": self._login_encrypt(captcha_text),
                "clientId": HUNAN_CLIENT_ID,
                "isencrypt": True,
            }
            r = self.session.post(
                f"{HUNAN_AUTH_HOST}/oauth2/login", json=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": HUNAN_AUTH_HOST,
                    "Referer": login_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=30,
            )
            r.raise_for_status()
            self.session.get(
                login_url.replace("appGovLogin.jsp", "authorize"),
                headers={"Referer": f"{HUNAN_AUTH_HOST}/"},
                timeout=30, allow_redirects=True,
            )
            cookies = [c.name for c in self.session.cookies]
            if "hnywtbC2AT" not in cookies:
                print(f"[湖南登录] 失败，cookies={cookies}")
                return False
            print(f"[湖南登录] 成功")
            return True
        except Exception as e:
            print(f"[湖南登录] 异常: {e}")
            return False

    def get_ofd(self, cert_num: str) -> Optional[bytes]:
        """获取OFD身份证文件"""
        try:
            # 1. 获取版本ID
            r = self._gateway_post(f"/unify_accept/v1/onethings/{HUNAN_ONETHING_CODE}/version_id", body=None)
            if not r.get("success"):
                print("[OFD] 获取版本ID失败")
                return None
            d = r.get("data") or {}
            version_id = d.get("onethingVersionId") or d.get("singlethingVersionId") or d.get("versionId") or ""
            if not version_id:
                print("[OFD] 版本ID为空")
                return None
            print(f"[OFD] version_id={version_id}")

            # 2. 智能导办
            form_params = {
                "blddxz": ["430102000000"],
                "blcjssx": "3",
                "blcjsx": "3",
                "blcjssxxz": "3",
                "lhjycbyjs": ["1"],
                "ldryrsdajshzd": ["1"],
                "INSU_ADMDVS": "430102",
            }
            r = self._gateway_post(f"/unify_accept/v1/onethings/{version_id}/smart_guidance_check", body=form_params)
            if r.get("code") != 0:
                print(f"[OFD] 智能导办失败: {r}")
                return None
            guide_process_id = (r.get("data") or {}).get("guideProcessId") or ""
            if not guide_process_id:
                print("[OFD] guide_process_id为空")
                return None
            print(f"[OFD] guide_process_id={guide_process_id}")

            # 3. 获取材料清单（使用固定值）
            checklist_id = "FD9E5AB3332D48B59E618AF090620390"
            print(f"[OFD] 使用固定checklist_id: {checklist_id}")

            # 4. 初始化实例
            r = self._gateway_post(
                f"/unify_accept/v1/onethings/{version_id}/implemetation/{checklist_id}/instance_init"
                f"?processGuidanceId={guide_process_id}",
                body=None
            )
            if r.get("code") != 0:
                print(f"[OFD] 初始化实例失败: {r}")
                r = self._gateway_post(
                    f"/unify_accept/v1/onethings/{version_id}/implemetation/{checklist_id}/instance_init",
                    body=None
                )
                if r.get("code") != 0:
                    print(f"[OFD] 初始化实例第二次失败: {r}")
                    return None
            instance_id = r.get("data") or ""
            if not instance_id:
                print("[OFD] instance_id为空")
                return None
            print(f"[OFD] instance_id={instance_id}")

            # 5. 保存表单
            try:
                r = self._gateway_get("/unify_accept/v1/user_info_wt")
                user_info = {}
                if r.get("data"):
                    try:
                        plain = self._aes_decrypt(r["data"])
                        user_info = json.loads(plain)
                    except:
                        pass
                
                now_ms = int(datetime.now().timestamp() * 1000)
                form_values = {
                    "certificateNum": self.user_cert_num,
                    "name": user_info.get("name") or "测试用户",
                    "certificateType": "111",
                    "sex": user_info.get("sex", "1"),
                    "phone": user_info.get("phone") or "18024094679",
                    "agent": user_info.get("name") or "测试用户",
                    "agentType": "111",
                    "agentCertNum": self.user_cert_num,
                    "agentPhone": user_info.get("phone") or "18024094679",
                    "lhjycbyjs": ["1"],
                    "ldryrsdajshzd": ["1"],
                    "blcjsx": "3",
                    "blcjssx": "3",
                    "blddxz": ["430102000000"],
                    "SQRQ": now_ms,
                    "INSU_ADMDVS": "430102",
                }
                
                url = f"/unify_accept/v1/onething_instances/{instance_id}/accept_infos/save"
                body = {"formData": json.dumps(form_values, ensure_ascii=False), "onethingInstanceId": instance_id}
                r = self._gateway_post(url, body=body, encrypt_body=True)
                print(f"[OFD] 保存表单: {r.get('msg')}")
            except Exception as e:
                print(f"[OFD] 保存表单失败（继续）: {e}")

            # 6. 获取待生成材料
            r = self._gateway_get(f"/unify_accept/v1/onething_instances/tobegen/{instance_id}/materials")
            tobegen = r.get("data") or []
            print(f"[OFD] tobegen数量: {len(tobegen)}")
            
            target_mid = None
            for it in tobegen:
                if "身份证" in (it.get("materialName") or ""):
                    target_mid = it.get("onethingMaterialId")
                    break
            if not target_mid and tobegen:
                target_mid = tobegen[0].get("onethingMaterialId")
            if not target_mid:
                print("[OFD] 没有待生成的材料")
                return None
            print(f"[OFD] target_mid={target_mid}")

            # 7. 生成模板
            print(f"[OFD] 开始生成模板...")
            gen_success = False
            for i in range(5):
                try:
                    r = self._gateway_post(
                        f"/unify_accept/v1/onething_instance/{instance_id}/material/{target_mid}/generate_template",
                        body=None
                    )
                    print(f"[OFD] 生成模板第{i+1}次: code={r.get('code')}, msg={r.get('msg')}")
                    if r.get("code") == 0 or "成功" in str(r.get("msg", "")):
                        gen_success = True
                        break
                    time.sleep(3)
                except Exception as e:
                    print(f"[OFD] 生成模板异常: {e}")
                    time.sleep(3)
            
            if not gen_success:
                print("[OFD] 生成模板最终失败")
                return None

            # 8. 获取材料列表
            time.sleep(2)
            r = self._gateway_get(f"/unify_accept/v1/onething_instances/mp/{instance_id}/materials")
            materials = r.get("data") or {}
            if isinstance(materials, dict):
                materials = materials.get("materials") or []
            print(f"[OFD] materials数量: {len(materials)}")
            
            id_card_item = None
            for m in materials:
                if "身份证" in (m.get("materialName") or ""):
                    id_card_item = m
                    break
            if not id_card_item:
                print("[OFD] 未找到身份证材料")
                return None

            # 9. 获取附件
            attach_list = id_card_item.get("attachList") or []
            chosen = None
            for a in attach_list:
                if "身份证" in (a.get("attachName") or ""):
                    chosen = a
                    break
            if not chosen and attach_list:
                chosen = attach_list[0]
            if not chosen:
                print("[OFD] 没有附件")
                return None
            print(f"[OFD] 找到附件: {chosen.get('attachName')}")

            # 10. 下载OFD
            r = self.session.get(
                f"{HUNAN_ZW_HOST}/picPathMapping",
                params={"picPath": chosen["attachUrl"], "bucketName": chosen["bucketName"]},
                timeout=60,
            )
            r.raise_for_status()
            print(f"[OFD] 下载成功，大小: {len(r.content)} bytes")
            return r.content
        except Exception as e:
            print(f"[湖南OFD获取] 异常: {e}")
            import traceback
            traceback.print_exc()
            return None                    # ==================== 数据库 ====================
class Database:
    def __init__(self, db_path="users.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                real_name TEXT,
                id_card TEXT,
                points INTEGER DEFAULT 0,
                vip_level INTEGER DEFAULT 0,
                vip_expiry TEXT,
                joined_date TEXT,
                last_checkin TEXT,
                total_checkins INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                register_data TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS point_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                admin_id INTEGER,
                timestamp TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                checkin_date TEXT,
                points_earned INTEGER
            )
        ''')
        self.conn.commit()

    def get_user(self, user_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    def add_user(self, user_id: int, username: str, first_name: str, last_name: str = ""):
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, joined_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, now))
        self.conn.commit()

    def update_user_info(self, user_id: int, real_name: str, id_card: str, phone: str = ""):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET real_name = ?, id_card = ?, phone = ? WHERE user_id = ?
        ''', (real_name, id_card, phone, user_id))
        self.conn.commit()

    def add_points(self, user_id: int, amount: int, reason: str = "", admin_id: int = 0):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        cursor.execute('''
            INSERT INTO point_logs (user_id, amount, reason, admin_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, reason, admin_id, datetime.now().isoformat()))
        self.conn.commit()
        return self.get_user(user_id)

    def set_vip(self, user_id: int, level: int, days: int = 30):
        cursor = self.conn.cursor()
        expiry = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None
        cursor.execute("UPDATE users SET vip_level = ?, vip_expiry = ? WHERE user_id = ?", 
                       (level, expiry, user_id))
        self.conn.commit()

    def checkin(self, user_id: int) -> Dict:
        cursor = self.conn.cursor()
        today = datetime.now().date().isoformat()
        user = self.get_user(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        last_checkin = user.get("last_checkin", "")
        if last_checkin == today:
            return {"success": False, "message": "今日已签到"}

        base_points = 5
        vip_bonus = user.get("vip_level", 0) * 2
        total_points = base_points + vip_bonus

        cursor.execute("UPDATE users SET points = points + ?, last_checkin = ?, total_checkins = total_checkins + 1 WHERE user_id = ?",
                       (total_points, today, user_id))
        cursor.execute('''
            INSERT INTO checkin_logs (user_id, checkin_date, points_earned)
            VALUES (?, ?, ?)
        ''', (user_id, today, total_points))
        self.conn.commit()
        return {
            "success": True,
            "points": total_points,
            "total_checkins": user.get("total_checkins", 0) + 1,
            "vip_bonus": vip_bonus
        }

    def get_top_users(self, limit: int = 10):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name, points, vip_level 
            FROM users 
            ORDER BY points DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

    def is_admin(self, user_id: int) -> bool:
        return user_id in ADMIN_IDS    
# ==================== SM4加密 ====================
SM4_KEY = "CatsPK0WWWRRhjkw"
SboxTable = [
    0xd6, 0x90, 0xe9, 0xfe, 0xcc, 0xe1, 0x3d, 0xb7, 0x16, 0xb6, 0x14, 0xc2, 0x28, 0xfb, 0x2c, 0x05,
    0x2b, 0x67, 0x9a, 0x76, 0x2a, 0xbe, 0x04, 0xc3, 0xaa, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99,
    0x9c, 0x42, 0x50, 0xf4, 0x91, 0xef, 0x98, 0x7a, 0x33, 0x54, 0x0b, 0x43, 0xed, 0xcf, 0xac, 0x62,
    0xe4, 0xb3, 0x1c, 0xa9, 0xc9, 0x08, 0xe8, 0x95, 0x80, 0xdf, 0x94, 0xfa, 0x75, 0x8f, 0x3f, 0xa6,
    0x47, 0x07, 0xa7, 0xfc, 0xf3, 0x73, 0x17, 0xba, 0x83, 0x59, 0x3c, 0x19, 0xe6, 0x85, 0x4f, 0xa8,
    0x68, 0x6b, 0x81, 0xb2, 0x71, 0x64, 0xda, 0x8b, 0xf8, 0xeb, 0x0f, 0x4b, 0x70, 0x56, 0x9d, 0x35,
    0x1e, 0x24, 0x0e, 0x5e, 0x63, 0x58, 0xd1, 0xa2, 0x25, 0x22, 0x7c, 0x3b, 0x01, 0x21, 0x78, 0x87,
    0xd4, 0x00, 0x46, 0x57, 0x9f, 0xd3, 0x27, 0x52, 0x4c, 0x36, 0x02, 0xe7, 0xa0, 0xc4, 0xc8, 0x9e,
    0xea, 0xbf, 0x8a, 0xd2, 0x40, 0xc7, 0x38, 0xb5, 0xa3, 0xf7, 0xf2, 0xce, 0xf9, 0x61, 0x15, 0xa1,
    0xe0, 0xae, 0x5d, 0xa4, 0x9b, 0x34, 0x1a, 0x55, 0xad, 0x93, 0x32, 0x30, 0xf5, 0x8c, 0xb1, 0xe3,
    0x1d, 0xf6, 0xe2, 0x2e, 0x82, 0x66, 0xca, 0x60, 0xc0, 0x29, 0x23, 0xab, 0x0d, 0x53, 0x4e, 0x6f,
    0xd5, 0xdb, 0x37, 0x45, 0xde, 0xfd, 0x8e, 0x2f, 0x03, 0xff, 0x6a, 0x72, 0x6d, 0x6c, 0x5b, 0x51,
    0x8d, 0x1b, 0xaf, 0x92, 0xbb, 0xdd, 0xbc, 0x7f, 0x11, 0xd9, 0x5c, 0x41, 0x1f, 0x10, 0x5a, 0xd8,
    0x0a, 0xc1, 0x31, 0x88, 0xa5, 0xcd, 0x7b, 0xbd, 0x2d, 0x74, 0xd0, 0x12, 0xb8, 0xe5, 0xb4, 0xb0,
    0x89, 0x69, 0x97, 0x4a, 0x0c, 0x96, 0x77, 0x7e, 0x65, 0xb9, 0xf1, 0x09, 0xc5, 0x6e, 0xc6, 0x84,
    0x18, 0xf0, 0x7d, 0xec, 0x3a, 0xdc, 0x4d, 0x20, 0x79, 0xee, 0x5f, 0x3e, 0xd7, 0xcb, 0x39, 0x48
]
FK = [0xa3b1bac6, 0x56aa3350, 0x677d9197, 0xb27022dc]
CK = [
    0x00070e15, 0x1c232a31, 0x383f464d, 0x545b6269,
    0x70777e85, 0x8c939aa1, 0xa8afb6bd, 0xc4cbd2d9,
    0xe0e7eef5, 0xfc030a11, 0x181f262d, 0x343b4249,
    0x50575e65, 0x6c737a81, 0x888f969d, 0xa4abb2b9,
    0xc0c7ced5, 0xdce3eaf1, 0xf8ff060d, 0x141b2229,
    0x30373e45, 0x4c535a61, 0x686f767d, 0x848b9299,
    0xa0a7aeb5, 0xbcc3cad1, 0xd8dfe6ed, 0xf4fb0209,
    0x10171e25, 0x2c333a41, 0x484f565d, 0x646b7279
]

def rotl(x, n):
    left = (x << n) & 0xffffffff
    signed_x = x - 0x100000000 if (x & 0x80000000) else x
    right = (signed_x >> (32 - n)) & 0xffffffff
    return left | right

def sm4_sbox(a):
    return (SboxTable[(a >> 24) & 0xFF] << 24) | \
           (SboxTable[(a >> 16) & 0xFF] << 16) | \
           (SboxTable[(a >> 8) & 0xFF] << 8) | \
           SboxTable[a & 0xFF]

def sm4_lt(ka):
    bb = sm4_sbox(ka)
    return bb ^ rotl(bb, 2) ^ rotl(bb, 10) ^ rotl(bb, 18) ^ rotl(bb, 24)

def sm4_calci_rk(ka):
    bb = sm4_sbox(ka)
    return bb ^ rotl(bb, 13) ^ rotl(bb, 23)

def sm4_f(x0, x1, x2, x3, rk):
    return x0 ^ sm4_lt(x1 ^ x2 ^ x3 ^ rk)

def pkcs7_pad(data: bytes, block_size=16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len]) * pad_len

def sm4_encrypt_ecb(plain_text: str) -> str:
    data = plain_text.encode('utf-8')
    padded = pkcs7_pad(data, 16)
    key_bytes = SM4_KEY.encode('utf-8')
    mk = [0] * 4
    for i in range(4):
        mk[i] = (key_bytes[i*4] << 24) | (key_bytes[i*4+1] << 16) | (key_bytes[i*4+2] << 8) | key_bytes[i*4+3]
    k = [0] * 36
    for i in range(4):
        k[i] = mk[i] ^ FK[i]
    sk = [0] * 32
    for i in range(32):
        k[i+4] = k[i] ^ sm4_calci_rk(k[i+1] ^ k[i+2] ^ k[i+3] ^ CK[i])
        sk[i] = k[i+4]
    result = bytearray()
    for offset in range(0, len(padded), 16):
        block = padded[offset:offset+16]
        x = [0] * 36
        for i in range(4):
            x[i] = (block[i*4] << 24) | (block[i*4+1] << 16) | (block[i*4+2] << 8) | block[i*4+3]
        for i in range(32):
            x[i+4] = sm4_f(x[i], x[i+1], x[i+2], x[i+3], sk[i])
        out = bytearray(16)
        for i in range(4):
            val = x[35-i]
            out[i*4] = (val >> 24) & 0xFF
            out[i*4+1] = (val >> 16) & 0xFF
            out[i*4+2] = (val >> 8) & 0xFF
            out[i*4+3] = val & 0xFF
        result.extend(out)
    return base64.b64encode(result).decode('utf-8')
# ==================== 广西API接口 ====================
class GuangXiAPI:
    def __init__(self):
        self.session = requests.Session()
        self.base_headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive"
        }
        self.user_agents = [
            "Mozilla/5.0 (Linux; Android 14; Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.119 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.7680.118 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.7680.117 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.119 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; Xiaomi 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.7680.118 Mobile Safari/537.36"
        ]

    def _get_headers(self):
        headers = self.base_headers.copy()
        ua = random.choice(self.user_agents)
        headers["User-Agent"] = ua
        return headers

    def _random_delay(self, min_sec=0.5, max_sec=2.0):
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def login(self, id_card: str, pwd: str) -> bool:
        enc_name = urllib.parse.quote(sm4_encrypt_ecb(id_card))
        enc_pwd = urllib.parse.quote(sm4_encrypt_ecb(pwd))
        post_data = f"loginName={enc_name}&password={enc_pwd}&wechatUid="
        
        self._random_delay(1.0, 2.5)
        headers = self._get_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        resp = self.session.post(
            f"{BASE_URL}/Wechat/Home/PostLogin",
            data=post_data,
            headers=headers
        )
        print(f"[登录] 响应: {resp.text}")
        try:
            return resp.json().get("statusCode") == 200
        except:
            return False

    def query_id_photo(self, name: str, id_card: str):
        url = f"{BASE_URL}/Wechat/FaceDetect/GetGAIDCardPhotoNew?idCard={id_card}&name={urllib.parse.quote(name)}"
        
        self._random_delay(2.0, 4.0)
        headers = self._get_headers()
        resp = self.session.get(url, headers=headers)
        print(f"[查询] 响应: {resp.text}")
        return resp.json()

    def download_photo(self, file_id: str) -> Optional[bytes]:
        try:
            url = f"{BASE_URL}/System/FileService/ShowFile?fileId={file_id}"
            
            self._random_delay(1.0, 2.0)
            headers = self._get_headers()
            resp = self.session.get(url, headers=headers, timeout=30)
            if resp.status_code == 200 and resp.content:
                print(f"[下载照片] 成功，大小: {len(resp.content)} 字节")
                return resp.content
            return None
        except Exception as e:
            print(f"[下载照片] 异常: {e}")
            return None

    def get_captcha(self):
        print("[验证码] 开始获取...")
        try:
            self._random_delay(0.5, 1.5)
            headers = self._get_headers()
            resp = self.session.get(
                f"{BASE_URL}/Wechat/FaceDetect/GetVerifyCode", 
                headers=headers, 
                timeout=10
            )
            if resp.status_code != 200:
                return None, None
            res_json = resp.json()
            if res_json.get("statusCode") == 200:
                data = res_json.get("data", {})
                uuid = data.get("uuid")
                img = data.get("img")
                if uuid and img:
                    return uuid, img
            return None, None
        except Exception as e:
            print(f"[验证码] 异常: {e}")
            return None, None

    def send_sms(self, phone: str, captcha_code: str, uuid: str) -> bool:
        data = {
            "phoneId": phone,
            "type": "10001",
            "IsEncryptPhoneId": "false",
            "verifyCode": captcha_code,
            "uuid": uuid
        }
        self._random_delay(0.5, 1.5)
        headers = self._get_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        resp = self.session.post(
            f"{BASE_URL}/System/SmsService/PostVerifyCode",
            data=data,
            headers=headers
        )
        try:
            return resp.json().get("statusCode") == 200
        except:
            return False

    def register(self, phone: str, sms_code: str, captcha_code: str, real_name: str, 
                 id_card: str, password: str, uuid: str = "") -> bool:
        data = {
            "zipArea": "",
            "userType": "-1",
            "wechatUid": "",
            "realName": real_name,
            "iDCard": id_card,
            "loginName": id_card,
            "password": password,
            "idcardImg1Url": "218,8a785f252c8518",
            "idcardImg2Url": "216,8a7860c46589f3",
            "idcardImg3Url": "214,8a78664776227f",
            "idcardImg4Url": "",
            "ownerId": "",
            "tel": phone,
            "isTelEncrypted": "false",
            "validCode": sms_code,
            "verifyCode": captcha_code
        }
        if uuid:
            data["uuid"] = uuid
        self._random_delay(0.5, 1.5)
        headers = self._get_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        resp = self.session.post(
            f"{BASE_URL}/Wechat/User/RegistAdd",
            data=data,
            headers=headers
        )
        try:
            return resp.json().get("statusCode") == 200
        except:
            return False

# ==================== 全局变量 ====================
db = Database()
gov_api = GovQueryAPI()

USER_QUERY_COOLDOWN = {}
GLOBAL_QUERY_COOLDOWN = {"last_query": None}
REGISTER_STATES = {}
# ==================== 发送带动画的欢迎消息 ====================
async def send_animated_welcome(update: Update, caption: str):
    """发送真正的🎉庆祝动画效果"""
    try:
        await update.message.reply_dice(emoji="🎰")
        await asyncio.sleep(1.5)
        
        empty_keyboard = ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            input_field_placeholder="💡 试试输入 /gx 张三 450101199001011234"
        )
        
        try:
            await update.message.reply_photo(
                photo=WELCOME_IMAGE_URL,
                caption=caption,
                reply_markup=empty_keyboard
            )
        except:
            await update.message.reply_text(
                caption,
                reply_markup=empty_keyboard
            )
    except Exception as e:
        print(f"[发送动画失败] {e}")
        await update.message.reply_text(caption)

# ==================== 主页 ====================
async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("请先使用 /start 注册")
        return
    
    vip_status = "❌ 无"
    if user_data.get("vip_level", 0) > 0:
        expiry = user_data.get("vip_expiry")
        if expiry and datetime.fromisoformat(expiry) > datetime.now():
            vip_status = f"👑 VIP {user_data['vip_level']} 级"
    
    caption = f"""
❤️‍🔥 爱 {user_data.get('first_name', '未知')} 无处不在 ❤️‍🔥

🆔 ID: {user_data['user_id']}
💎 积分: {user_data.get('points', 0)}
{vip_status}
📅 已签到: {user_data.get('total_checkins', 0)} 天

💡 使用以下指令操作：

🔍 /gx 姓名 身份证号 - 查询身份证信息
🏛️ /hunan 身份证号 - 获取湖南政务OFD身份证
🔎 /cx 查询内容 - 查询数据(消耗1积分)
✅ /checkin - 每日签到
👤 /profile - 查看个人信息
📊 /rank - 积分排行榜
    """
    await send_animated_welcome(update, caption)

# ==================== 命令处理 ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name or "")
    
    caption = f"""
❤️‍🔥 爱 {user.first_name or '未知'} 无处不在 ❤️‍🔥

💯 你是我的My Only 💯
💡 查询即自动注册，无需手动操作！

📌 可用指令：

🔍 /gx 姓名 身份证号 - 查询身份证信息
🏛️ /hunan 身份证号 - 获取湖南政务OFD身份证
🔎 /cx 查询综合内容 - (消耗1积分)
✅ /checkin - 每日签到
👤 /profile - 查看个人信息
📊 /rank - 积分排行榜
📖 /help - 查看帮助

🌟 试试输入 /gx 张三 450101199001011234 🌟
    """
    await send_animated_welcome(update, caption)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 使用帮助

🔍 /gx <姓名> <身份证号> - 查询广西身份证信息（含照片）
🏛️ /hunan <身份证号> - 获取湖南政务OFD身份证文件
🔎 /cx <查询内容> - 查询综合数据（消耗1积分）
✅ /checkin - 每日签到
👤 /profile - 查看个人信息
📊 /rank - 积分排行榜

⏳ 查询冷却：30秒/次（管理员无限制）

💡 查询即自动注册，无需手动注册！

👑 VIP特权：
• 签到双倍积分
• 免费查询（不消耗积分）
• 专属标识

⚙️ 管理员命令：
• /admin - 打开管理面板
• 管理员无查询限制
"""
    await update.message.reply_text(help_text)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    if not user_data:
        await update.message.reply_text("请先使用 /start 注册")
        return

    vip_status = "❌ 无VIP"
    if user_data.get("vip_level", 0) > 0:
        expiry = user_data.get("vip_expiry")
        if expiry and datetime.fromisoformat(expiry) > datetime.now():
            vip_status = f"👑 VIP {user_data['vip_level']} 级 (到期: {expiry[:10]}) ✅ 免费查询"
        else:
            vip_status = "❌ VIP已过期"

    is_admin = db.is_admin(user.id)
    admin_tag = " 👑 管理员" if is_admin else ""

    profile_text = f"""
👤 个人信息

🆔 ID: {user_data['user_id']}
📛 用户名: @{user_data.get('username', '未设置')}
👤 姓名: {user_data.get('first_name', '未知')}{admin_tag}

💎 积分: {user_data.get('points', 0)}
{vip_status}
📅 注册日期: {user_data.get('joined_date', '未知')[:10]}
✅ 累计签到: {user_data.get('total_checkins', 0)} 天
📱 手机号: {user_data.get('phone', '未绑定')}
🪪 身份证: {user_data.get('id_card', '未绑定')}
"""
    await update.message.reply_text(profile_text)

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    result = db.checkin(user.id)
    
    if result["success"]:
        msg = f"""
✅ 签到成功！

🎉 获得 {result['points']} 积分
📅 连续签到: {result['total_checkins']} 天
✨ VIP加成: +{result.get('vip_bonus', 0)} 积分
"""
    else:
        msg = f"⚠️ {result['message']}"
    
    await update.message.reply_text(msg)

async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = db.get_top_users(10)
    if not top_users:
        await update.message.reply_text("暂无用户数据")
        return

    rank_text = "🏆 积分排行榜\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, username, first_name, points, vip_level) in enumerate(top_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        vip_icon = "👑" if vip_level > 0 else ""
        name = username or first_name or str(user_id)
        rank_text += f"{medal} {name} {vip_icon} - {points} 积分\n"
    
    await update.message.reply_text(rank_text)
# ==================== 综合数据查询 (/cx) - 最终美化版 ====================
async def gov_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询综合数据 - 美化输出"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("请先使用 /start 注册")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "请输入要查询的内容\n"
            "格式: /cx 查询内容\n"
            "例如: /cx 18888888888\n"
            "例如: /cx 张三 450101199001011234"
        )
        return
    
    query_content = " ".join(args).strip()
    
    # 检查VIP状态
    vip_level = user_data.get("vip_level", 0)
    vip_expiry = user_data.get("vip_expiry")
    is_vip_valid = False
    if vip_level > 0 and vip_expiry:
        try:
            if datetime.fromisoformat(vip_expiry) > datetime.now():
                is_vip_valid = True
        except:
            pass
    
    is_admin = db.is_admin(user.id)
    
    # 检查积分（管理员和VIP免费）
    if not is_admin and not is_vip_valid and user_data.get("points", 0) < 1:
        await update.message.reply_text(
            "⚠️ 积分不足！查询综合数据消耗1积分，请签到获取积分。\n\n"
            "💡 开通VIP可免费查询！"
        )
        return
    
    wait_msg = await update.message.reply_text("⏳ 正在查询，请稍候...")
    
    try:
        result = gov_api.query(query_content)
        
        if result is None:
            await wait_msg.edit_text("❌ 查询失败：未收到响应")
            return
        
        if not result.get("success", False):
            error_msg = result.get("error", "查询失败，请稍后重试")
            await wait_msg.edit_text(f"❌ {error_msg}")
            return
        
        # 扣积分（管理员和VIP免费）
        if not is_admin and not is_vip_valid:
            db.add_points(user.id, -1, "综合数据查询", 0)
            cost_text = "消耗 1 积分"
        else:
            if is_admin:
                cost_text = "👑 管理员免费查询，不消耗积分"
            else:
                cost_text = "✅ VIP免费查询，不消耗积分"
        
        raw_text = result.get("raw", "")
        
        if not raw_text:
            await wait_msg.edit_text("❌ 查询结果为空")
            return
        
        # ===== 过滤公告 =====
        skip_keywords = [
            '公告', '刀盟', '斩龙殿', '烂梗', '虚圈', '甘雨社',
            'Key公告', '系统公告', '公益查询', '可用服务', '没有KEY',
            '其他接口', '打开网页', '里面有示例', '作者', '转载使用',
            '必须标注', '来源', '欢迎各位加入', '一人一句', '示列',
            '已用次数', '查询关键词'
        ]
        lines = raw_text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            should_skip = False
            for keyword in skip_keywords:
                if keyword in line_stripped:
                    should_skip = True
                    break
            
            if not should_skip:
                filtered_lines.append(line_stripped)
        
        if not filtered_lines:
            await wait_msg.edit_text("❌ 查询结果为空")
            return
        
        filtered_text = '\n'.join(filtered_lines)
        
        # ===== 替换基础字段Emoji =====
        emoji_replacements = {
            '姓名：': '👤 姓名: ',
            '身份证号码：': '🆔 身份证号码: ',
            '身份证号码_归属地：': '🆔 身份证号码_归属地: ',
            '手机号码：': '📱 手机号码: ',
            '手机号码_运营商：': '📱 手机号码_运营商: ',
            '手机号码_归属地：': '📱 手机号码_归属地: ',
            '地址：': '🏠 地址: ',
            '户籍编号：': '🔢 户籍编号: ',
            '公司名称：': '👤 公司名称: ',
            '学校名称：': '👤 学校名称: ',
            '微信名：': '💬 微信名: ',
            '用户ID：': '🔢 用户ID: ',
            '开放平台ID：': '🔸 开放平台ID: ',
            '用户名：': '👤 用户名: ',
            '学号：': '🔸 学号: ',
            '创建时间：': '🔸 创建时间: ',
            '上线时间：': '🔸 上线时间: ',
            '关系类型：': '🔸 _关系类型: ',
            '_关系类型：': '🔸 _关系类型: ',
            '头像：': '🔸 头像: ',
            'wx_id：': '🔸 wx_id: ',
        }
        
        for old, new in emoji_replacements.items():
            filtered_text = filtered_text.replace(old, new)
        
        # ===== 提取并美化关联人员 =====
        related_text = ""
        related_match = re.search(r'关联人员\s*\n([\s\S]*?)(?=\n家庭成员|\n查询时间|\Z)', filtered_text)
        if related_match:
            related_lines = related_match.group(1).strip().split('\n')
            formatted_related = []
            for line in related_lines:
                line = line.strip()
                if not line:
                    continue
                if '，' in line:
                    parts = line.split('，')
                    formatted_parts = []
                    for i, p in enumerate(parts):
                        p = p.strip()
                        if not p:
                            continue
                        if i == 0:
                            formatted_parts.append(f"👤 {p}")
                        elif i == 1:
                            if re.match(r'^\d{18}|\d{17}[Xx]', p):
                                formatted_parts.append(f"🆔 {p}")
                            else:
                                formatted_parts.append(f"📱 {p}")
                        elif i == 2:
                            if re.match(r'^\d{11}|\d{3}\*{5}\d{3}', p):
                                formatted_parts.append(f"📱 {p}")
                            else:
                                formatted_parts.append(f"📍 {p}")
                        elif i == 3:
                            formatted_parts.append(f"📍 {p}")
                        elif i == 4:
                            formatted_parts.append(f"📡 {p}")
                        elif i == 5:
                            formatted_parts.append(f"📍 {p}")
                        else:
                            formatted_parts.append(p)
                    formatted_related.append(f"📌 {'  '.join(formatted_parts)}")
                else:
                    formatted_related.append(f"📌 {line}")
            related_text = '\n'.join(formatted_related)
        
        # ===== 提取并美化家庭成员 =====
        family_text = ""
        family_match = re.search(r'家庭成员\s*\n([\s\S]*?)(?=\n查询时间|\Z)', filtered_text)
        if family_match:
            family_lines = family_match.group(1).strip().split('\n')
            formatted_family = []
            for line in family_lines:
                line = line.strip()
                if not line:
                    continue
                if '，' in line:
                    parts = line.split('，')
                    formatted_parts = []
                    for i, p in enumerate(parts):
                        p = p.strip()
                        if not p:
                            continue
                        if i == 0:
                            formatted_parts.append(f"👤 {p}")
                        elif i == 1:
                            if re.match(r'^\d{18}|\d{17}[Xx]', p):
                                formatted_parts.append(f"🆔 {p}")
                            else:
                                formatted_parts.append(f"📱 {p}")
                        elif i == 2:
                            if re.match(r'^\d{11}|\d{3}\*{5}\d{3}', p):
                                formatted_parts.append(f"📱 {p}")
                            else:
                                formatted_parts.append(f"📍 {p}")
                        elif i == 3:
                            formatted_parts.append(f"📍 {p}")
                        elif i == 4:
                            formatted_parts.append(f"📡 {p}")
                        elif i == 5:
                            formatted_parts.append(f"📍 {p}")
                        else:
                            formatted_parts.append(p)
                    formatted_family.append(f"📌 {'  '.join(formatted_parts)}")
                else:
                    formatted_family.append(f"📌 {line}")
            family_text = '\n'.join(formatted_family)
        
        # ===== 移除原始关联人员和家庭成员，插入美化后的 =====
        lines = filtered_text.split('\n')
        new_lines = []
        skip_until_family = False
        skip_until_query_time = False
        related_inserted = False
        family_inserted = False
        
        for line in lines:
            line_stripped = line.strip()
            
            if '关联人员' in line_stripped:
                skip_until_family = True
                if not related_inserted and related_text:
                    new_lines.append('🏷️ 关联人员')
                    new_lines.append(related_text)
                    related_inserted = True
                continue
            
            if '家庭成员' in line_stripped:
                skip_until_family = False
                skip_until_query_time = True
                if not family_inserted and family_text:
                    new_lines.append('🏷️ 家庭成员')
                    new_lines.append(family_text)
                    family_inserted = True
                continue
            
            if skip_until_family or skip_until_query_time:
                if '查询时间' in line_stripped:
                    skip_until_query_time = False
                    new_lines.append(line)
                continue
            
            new_lines.append(line)
        
        filtered_text = '\n'.join(new_lines)
        
        # ===== 组装最终输出 =====
        info = f"""
🔎 综合数据查询结果

📋 查询内容: {query_content}

{filtered_text}

💎 {cost_text}
"""
        
        await wait_msg.delete()
        
        if len(info) > 4096:
            parts = []
            current_part = ""
            for line in info.split('\n'):
                if len(current_part) + len(line) + 1 > 3900:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            if current_part:
                parts.append(current_part)
            
            for i, part in enumerate(parts):
                if i == 0:
                    await update.message.reply_text(part)
                else:
                    await update.message.reply_text(f"📄 续 {i+1}/{len(parts)}:\n{part}")
        else:
            await update.message.reply_text(info)
        
    except requests.exceptions.Timeout:
        await wait_msg.edit_text("⏰ 查询超时，请稍后重试")
    except requests.exceptions.ConnectionError:
        await wait_msg.edit_text("🌐 网络连接失败，请检查网络后重试")
    except Exception as e:
        print(f"[综合查询异常] {e}")
        import traceback
        traceback.print_exc()
        await wait_msg.edit_text(f"❌ 查询异常: {str(e)[:100]}")
# ==================== 湖南政务OFD查询 ====================
def _hunan_ofd_query_sync(cert_num: str) -> Optional[Dict]:
    """同步执行湖南OFD查询"""
    try:
        account = "431024200805230056"
        password = "Zouo8866"
        
        client = HunanZwfwClient(account, password, cert_num)
        
        if not client.login():
            print("[湖南OFD] 登录失败")
            return {"error": "登录失败"}
        
        ofd_data = client.get_ofd(cert_num)
        if not ofd_data:
            print("[湖南OFD] 获取OFD失败")
            return {"error": "获取OFD失败，可能该身份证未在湖南政务系统注册或系统暂无数据"}
        
        try:
            extractor = OFDIDCardExtractor(ofd_data)
            result = extractor.extract()
            id_info = {}
            if result:
                id_info = result.get("info", {})
        except Exception as e:
            print(f"[OFD提取异常] {e}")
            id_info = {}
        
        print(f"[湖南OFD] 成功获取OFD，大小: {len(ofd_data)} bytes")
        
        return {
            "ofd_data": ofd_data,
            "id_info": id_info
        }
    except Exception as e:
        print(f"[湖南OFD同步] 异常: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

async def hunan_ofd_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询湖南政务OFD身份证"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("请先使用 /start 注册")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "请输入身份证号\n"
            "格式: /hunan 身份证号\n"
            "例如: /hunan 431024200805230056"
        )
        return
    
    cert_num = args[0].strip()
    
    if len(cert_num) != 18 or not cert_num[:-1].isdigit():
        await update.message.reply_text("❌ 身份证号格式错误，请输入18位身份证号")
        return
    
    # 检查积分
    if user_data.get("points", 0) < 2:
        await update.message.reply_text("⚠️ 积分不足！查询湖南OFD需要2积分，请签到获取积分。")
        return
    
    # 扣积分
    db.add_points(user.id, -2, "湖南OFD查询", 0)
    
    await update.message.reply_text("⏳ 正在查询湖南政务OFD，请稍候...")
    
    try:
        result = await asyncio.to_thread(_hunan_ofd_query_sync, cert_num)
        
        if result and result.get("error"):
            await update.message.reply_text(
                f"❌ 查询失败: {result['error']}\n\n💡 积分已退还"
            )
            db.add_points(user.id, 2, "湖南OFD查询失败退还", 0)
            return
        
        if result and result.get("ofd_data"):
            ofd_data = result["ofd_data"]
            id_info = result.get("id_info", {})
            
            filename = f"身份证_{cert_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ofd"
            
            info_text = "🏛️ 湖南政务OFD身份证\n\n"
            if id_info:
                info_text += "📋 提取的身份证信息：\n"
                for key, value in id_info.items():
                    if value:
                        info_text += f"  {key}: {value}\n"
            else:
                info_text += "⚠️ 未能提取身份证信息\n"
            
            info_text += f"\n💎 消耗 2 积分"
            
            try:
                await update.message.reply_document(
                    document=ofd_data,
                    filename=filename,
                    caption=info_text
                )
                print(f"[湖南OFD] 成功发送: {cert_num}")
            except Exception as e:
                print(f"[湖南OFD] 发送失败: {e}")
                with open(filename, "wb") as f:
                    f.write(ofd_data)
                with open(filename, "rb") as f:
                    await update.message.reply_document(
                        document=f,
                        caption=info_text
                    )
                os.remove(filename)
        else:
            await update.message.reply_text(
                "❌ 查询失败，请检查身份证号是否正确\n"
                "可能原因：\n"
                "• 该身份证未在湖南政务系统注册\n"
                "• 系统暂时不可用\n"
                "• 身份证号输入错误\n\n"
                "💡 积分已退还"
            )
            db.add_points(user.id, 2, "湖南OFD查询失败退还", 0)
            
    except Exception as e:
        print(f"[湖南OFD] 异常: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ 查询异常: {str(e)}\n\n💡 积分已退还")
        db.add_points(user.id, 2, "湖南OFD查询异常退还", 0)
# ==================== 广西身份证查询 (/gx) ====================
async def query_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_data = db.get_user(user_id)
    
    if not user_data:
        await update.message.reply_text("请先使用 /start 注册")
        return
    
    is_admin = db.is_admin(user_id)
    
    if not is_admin:
        current_time = datetime.now()
        
        if user_id in USER_QUERY_COOLDOWN:
            last_query = USER_QUERY_COOLDOWN[user_id]
            time_diff = (current_time - last_query).total_seconds()
            if time_diff < 30:
                remaining = int(30 - time_diff)
                await update.message.reply_text(
                    f"⏳ 请等待 {remaining} 秒后再查询\n\n"
                    "💡 为了防止被服务器限制，每个用户30秒只能查询一次"
                )
                return
        
        if GLOBAL_QUERY_COOLDOWN["last_query"]:
            last_global = GLOBAL_QUERY_COOLDOWN["last_query"]
            time_diff = (current_time - last_global).total_seconds()
            if time_diff < 30:
                remaining = int(30 - time_diff)
                await update.message.reply_text(
                    f"⏳ 系统冷却中，请等待 {remaining} 秒后再查询\n\n"
                    "💡 为了防止被服务器限制，全局30秒只能查询一次"
                )
                return
        
        USER_QUERY_COOLDOWN[user_id] = current_time
        GLOBAL_QUERY_COOLDOWN["last_query"] = current_time
    
    vip_level = user_data.get("vip_level", 0)
    vip_expiry = user_data.get("vip_expiry")
    is_vip_valid = False
    if vip_level > 0 and vip_expiry:
        try:
            if datetime.fromisoformat(vip_expiry) > datetime.now():
                is_vip_valid = True
        except:
            pass
    
    if not is_admin and not is_vip_valid and user_data.get("points", 0) < 1:
        await update.message.reply_text(
            "⚠️ 积分不足！每次查询消耗1积分，请签到获取积分。\n\n"
            "💡 开通VIP可免费查询！"
        )
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "请输入姓名和身份证号\n"
            "格式: /gx 姓名 身份证号\n"
            "例如: /gx 张三 450101199001011234"
        )
        return

    name = args[0]
    id_card = args[1]
    
    if len(id_card) != 18 or not id_card[:-1].isdigit():
        await update.message.reply_text("❌ 身份证号格式错误，请输入18位身份证号")
        return

    if user_data.get('id_card'):
        await update.message.reply_text("⏳ 正在查询，请稍候...")
        
        api = GuangXiAPI()
        max_retries = 3
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"[查询] 第 {attempt+1} 次重试...")
                await update.message.reply_text(f"⏳ 第 {attempt+1} 次重试...")
                api = GuangXiAPI()
                
            if api.login(id_card, PASSWORD):
                print("[查询] 登录成功")
                result = api.query_id_photo(name, id_card)
                
                if result.get("statusCode") == 200:
                    data = result.get("data", {})
                    item = data.get("item2", {})
                    file_id = data.get("item1")
                    
                    if not is_admin and not is_vip_valid:
                        db.add_points(user_id, -1, "身份证查询", 0)
                        cost_text = "消耗 1 积分"
                    else:
                        if is_admin:
                            cost_text = "👑 管理员免费查询，不消耗积分"
                        else:
                            cost_text = "✅ VIP免费查询，不消耗积分"
                    
                    info = f"""
📋 身份证信息查询结果

👤 姓名: {item.get('xm', '未知')}
🆔 身份证号: {item.get('gmsfhm', '未知')}
🏳️ 民族: {item.get('mz', '未知')}
🏠 住址: {item.get('fulladdr', '未知')}
📋 签发机关: {item.get('issueD_UNIT', '未知')}
📅 有效期: {item.get('uL_FROM_DATE', '未知')} 至 {item.get('uL_END_DATE', '未知')}

💎 {cost_text}
"""
                    if not is_admin:
                        info += "\n⏳ 下次查询请等待30秒"
                    
                    if file_id:
                        photo_data = api.download_photo(file_id)
                        if photo_data:
                            try:
                                await update.message.reply_photo(
                                    photo=photo_data,
                                    caption=info
                                )
                                return
                            except Exception as e:
                                print(f"[查询] 发送照片失败: {e}")
                                await update.message.reply_text(info)
                                return
                        else:
                            await update.message.reply_text(info)
                            return
                    else:
                        await update.message.reply_text(info)
                        return
                        
                elif result.get("info") == "限制访问":
                    print(f"[查询] 被限制访问 (尝试 {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        wait_time = random.uniform(5, 10)
                        print(f"[查询] 等待 {wait_time:.1f} 秒后重试...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        await update.message.reply_text(
                            "❌ 服务器限制访问，请稍后再试\n\n"
                            "💡 提示：请等待1-2分钟后再查询"
                        )
                        return
                else:
                    print(f"[查询] 查询失败: {result}")
                    await update.message.reply_text("❌ 查询失败，请确认姓名和身份证号是否正确")
                    return
            else:
                print("[查询] 登录失败")
                await update.message.reply_text("❌ 登录失败，请稍后重试或联系管理员")
                return
    else:
        # 自动注册流程
        await update.message.reply_text(
            f"📝 检测到您尚未注册，正在为您自动注册...\n\n"
            f"👤 姓名: {name}\n"
            f"🆔 身份证: {id_card}\n\n"
            f"⏳ 请稍候，正在获取验证码..."
        )
        
        phone = user_data.get('phone') or MY_PHONE
        
        REGISTER_STATES[user_id] = {
            "step": "auto_register",
            "name": name,
            "id_card": id_card,
            "phone": phone,
            "query_name": name,
            "query_id": id_card
        }
        
        api = GuangXiAPI()
        uuid, img_b64 = api.get_captcha()
        
        if uuid and img_b64:
            REGISTER_STATES[user_id]["uuid"] = uuid
            REGISTER_STATES[user_id]["step"] = "captcha"
            img_data = base64.b64decode(img_b64)
            await update.message.reply_photo(
                photo=img_data,
                caption=f"📷 请输入图片中的验证码：\n\n"
                        f"📱 将向手机号 {phone} 发送短信验证码"
            )
        else:
            await update.message.reply_text("❌ 获取验证码失败，请稍后重试")
            del REGISTER_STATES[user_id]
# ==================== 注册流程处理 ====================
async def handle_register_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    if user.id not in REGISTER_STATES:
        return
    
    state = REGISTER_STATES[user.id]
    step = state.get("step")
    
    if step == "captcha":
        captcha_code = text.upper()
        uuid = state.get("uuid")
        phone = state.get("phone")
        name = state.get("name")
        id_card = state.get("id_card")
        
        await update.message.reply_text("⏳ 正在发送短信验证码...")
        
        api = GuangXiAPI()
        if api.send_sms(phone, captcha_code, uuid):
            state["captcha_code"] = captcha_code
            state["step"] = "sms_code"
            await update.message.reply_text(f"📱 短信验证码已发送到手机 {phone}，请输入：")
        else:
            await update.message.reply_text("❌ 发送短信失败，请检查图形验证码是否正确")
            uuid, img_b64 = api.get_captcha()
            if uuid and img_b64:
                state["uuid"] = uuid
                img_data = base64.b64decode(img_b64)
                await update.message.reply_photo(
                    photo=img_data,
                    caption="📷 请输入新的图片验证码："
                )
            else:
                await update.message.reply_text("❌ 获取验证码失败，请稍后重试")
                del REGISTER_STATES[user.id]
    
    elif step == "sms_code":
        sms_code = text
        name = state.get("name")
        id_card = state.get("id_card")
        phone = state.get("phone")
        captcha_code = state.get("captcha_code")
        uuid = state.get("uuid")
        
        await update.message.reply_text("⏳ 正在注册并查询，请稍候...")
        
        api = GuangXiAPI()
        
        if api.register(phone, sms_code, captcha_code, name, id_card, PASSWORD, uuid):
            db.update_user_info(user.id, name, id_card, phone)
            db.add_points(user.id, 10, "注册奖励", 0)
            
            if api.login(id_card, PASSWORD):
                result = api.query_id_photo(name, id_card)
                if result.get("statusCode") == 200:
                    data = result.get("data", {})
                    item = data.get("item2", {})
                    file_id = data.get("item1")
                    
                    info = f"""
✅ 注册成功！获得 10 积分奖励

📋 身份证信息查询结果

👤 姓名: {item.get('xm', '未知')}
🆔 身份证号: {item.get('gmsfhm', '未知')}
🏳️ 民族: {item.get('mz', '未知')}
🏠 住址: {item.get('fulladdr', '未知')}
📋 签发机关: {item.get('issueD_UNIT', '未知')}
📅 有效期: {item.get('uL_FROM_DATE', '未知')} 至 {item.get('uL_END_DATE', '未知')}

💎 本次查询免费（注册福利）
"""
                    if not db.is_admin(user.id):
                        info += "\n⏳ 下次查询请等待30秒"
                    
                    del REGISTER_STATES[user.id]
                    
                    if file_id:
                        photo_data = api.download_photo(file_id)
                        if photo_data:
                            try:
                                await update.message.reply_photo(
                                    photo=photo_data,
                                    caption=info
                                )
                                return
                            except Exception as e:
                                print(f"[注册查询] 发送照片失败: {e}")
                                await update.message.reply_text(info)
                                return
                        else:
                            await update.message.reply_text(info)
                            return
                    else:
                        await update.message.reply_text(info)
                        return
                else:
                    await update.message.reply_text(
                        "✅ 注册成功！但查询失败，请稍后使用 /gx 手动查询"
                    )
                    del REGISTER_STATES[user.id]
                    return
            else:
                await update.message.reply_text(
                    "✅ 注册成功！但登录失败，请稍后使用 /gx 手动查询"
                )
                del REGISTER_STATES[user.id]
                return
        else:
            await update.message.reply_text(
                "❌ 注册失败，请检查验证码是否正确或稍后重试"
            )
            del REGISTER_STATES[user.id]

# ==================== 引用回复功能 ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有消息 - 引用并随机回复"""
    user = update.effective_user
    text = update.message.text
    
    # 检查是否在注册流程中
    if user.id in REGISTER_STATES:
        await handle_register_input(update, context)
        return
    
    # 检查是否在管理员操作中
    if context.user_data.get("admin_action"):
        await handle_admin_input(update, context)
        return
    
    # 忽略命令
    if text and text.startswith("/"):
        return
    
    # 随机选择一条引用语
    quote = random.choice(QUOTE_MESSAGES)
    
    try:
        await update.message.reply_text(
            quote,
            reply_to_message_id=update.message.message_id
        )
    except Exception as e:
        print(f"[引用回复失败] {e}")

# ==================== 管理员功能 ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.is_admin(user.id):
        await update.message.reply_text("⛔ 您没有管理员权限")
        return
    
    await update.message.reply_text(
        "⚙️ 管理员控制面板\n\n"
        "请选择操作：",
        reply_markup=get_admin_keyboard()
    )

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ 加分", callback_data="admin_add_points"),
         InlineKeyboardButton("➖ 减分", callback_data="admin_sub_points")],
        [InlineKeyboardButton("👑 设置VIP", callback_data="admin_set_vip"),
         InlineKeyboardButton("📊 用户统计", callback_data="admin_stats")],
        [InlineKeyboardButton("📋 积分日志", callback_data="admin_logs"),
         InlineKeyboardButton("🚫 封禁用户", callback_data="admin_ban")],
        [InlineKeyboardButton("🔙 返回", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    if not db.is_admin(user.id):
        await query.edit_message_text("⛔ 您没有管理员权限")
        return
    
    data = query.data
    
    if data == "admin_back":
        await query.edit_message_text("⚙️ 管理面板已关闭")
        return
    
    elif data == "admin_stats":
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(points) FROM users")
        total_points = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM users WHERE vip_level > 0")
        vip_users = cursor.fetchone()[0]
        
        stats = f"""
📊 用户统计

👥 总用户: {total_users}
💎 总积分: {total_points}
👑 VIP用户: {vip_users}
"""
        await query.edit_message_text(stats, reply_markup=get_admin_keyboard())
    
    elif data == "admin_add_points":
        context.user_data["admin_action"] = "add_points"
        await query.edit_message_text(
            "➕ 请输入要加分的用户ID和积分数\n"
            "格式: 用户ID 积分数\n"
            "例如: 123456789 10",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data="admin_back")]])
        )
    
    elif data == "admin_sub_points":
        context.user_data["admin_action"] = "sub_points"
        await query.edit_message_text(
            "➖ 请输入要减分的用户ID和积分数\n"
            "格式: 用户ID 积分数\n"
            "例如: 123456789 5",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data="admin_back")]])
        )
    
    elif data == "admin_set_vip":
        context.user_data["admin_action"] = "set_vip"
        await query.edit_message_text(
            "👑 请输入要设置VIP的用户ID、等级和天数\n"
            "格式: 用户ID 等级 天数\n"
            "例如: 123456789 1 30\n\n"
            "等级说明: 1-普通VIP, 2-高级VIP, 3-超级VIP",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data="admin_back")]])
        )
    
    elif data == "admin_logs":
        cursor = db.conn.cursor()
        cursor.execute('''
            SELECT user_id, amount, reason, timestamp 
            FROM point_logs 
            ORDER BY id DESC 
            LIMIT 20
        ''')
        logs = cursor.fetchall()
        if not logs:
            await query.edit_message_text("暂无积分日志", reply_markup=get_admin_keyboard())
            return
        
        log_text = "📋 最近积分变动日志\n\n"
        for user_id, amount, reason, timestamp in logs:
            sign = "+" if amount > 0 else ""
            log_text += f"🆔 {user_id}: {sign}{amount} 积分 ({reason or '无'}) - {timestamp[:10]}\n"
        
        await query.edit_message_text(log_text, reply_markup=get_admin_keyboard())
    
    elif data == "admin_ban":
        context.user_data["admin_action"] = "ban"
        await query.edit_message_text(
            "🚫 请输入要封禁的用户ID\n"
            "格式: 用户ID\n"
            "例如: 123456789",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data="admin_back")]])
        )

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.is_admin(user.id):
        return
    
    text = update.message.text.strip()
    action = context.user_data.get("admin_action")
    
    if not action:
        return
    
    if action == "add_points" or action == "sub_points":
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await update.message.reply_text("❌ 格式错误，请使用: 用户ID 积分数")
            return
        
        target_id = int(parts[0])
        amount = int(parts[1])
        if action == "sub_points":
            amount = -amount
        
        target_user = db.get_user(target_id)
        if not target_user:
            await update.message.reply_text("❌ 用户不存在")
            return
        
        db.add_points(target_id, amount, f"管理员{'加' if amount > 0 else '减'}分", user.id)
        new_user = db.get_user(target_id)
        await update.message.reply_text(
            f"✅ 操作成功！\n"
            f"🆔 {target_id} 当前积分: {new_user['points']}"
        )
        context.user_data["admin_action"] = None
    
    elif action == "set_vip":
        parts = text.split()
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            await update.message.reply_text("❌ 格式错误，请使用: 用户ID 等级 天数")
            return
        
        target_id = int(parts[0])
        level = int(parts[1])
        days = int(parts[2])
        
        if level < 0 or level > 3:
            await update.message.reply_text("❌ 等级必须为 0-3")
            return
        
        target_user = db.get_user(target_id)
        if not target_user:
            await update.message.reply_text("❌ 用户不存在")
            return
        
        db.set_vip(target_id, level, days)
        await update.message.reply_text(
            f"✅ VIP设置成功！\n"
            f"🆔 {target_id} VIP等级: {level}\n"
            f"📅 有效期: {days} 天"
        )
        context.user_data["admin_action"] = None
    
    elif action == "ban":
        if not text.isdigit():
            await update.message.reply_text("❌ 请输入有效的用户ID")
            return
        
        target_id = int(text)
        target_user = db.get_user(target_id)
        if not target_user:
            await update.message.reply_text("❌ 用户不存在")
            return
        
        cursor = db.conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        db.conn.commit()
        await update.message.reply_text(f"✅ 用户 {target_id} 已被封禁")
        context.user_data["admin_action"] = None                                 # ==================== 健壮机器人封装（手动轮询版） ====================
class RobustBot:
    def __init__(self, token):
        self.token = token
        self.app = None
        self.is_running = False
        self.retry_count = 0
        self.max_retries = 10
        self.base_delay = 5
        self.max_delay = 120
        self.polling_errors = 0

    def create_application(self):
        """创建带超时配置的 Application - 移动端优化"""
        return (
            Application.builder()
            .token(self.token)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .get_updates_connect_timeout(25)
            .get_updates_read_timeout(25)
            .get_updates_write_timeout(25)
            .base_file_url("https://api.telegram.org/file/bot")
            .base_url("https://api.telegram.org/bot")
            .build()
        )

    def setup_handlers(self, app):
        """注册所有处理器"""
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("profile", profile))
        app.add_handler(CommandHandler("checkin", checkin))
        app.add_handler(CommandHandler("rank", rank))
        app.add_handler(CommandHandler("gx", query_id))
        app.add_handler(CommandHandler("hunan", hunan_ofd_query))
        app.add_handler(CommandHandler("cx", gov_query))  # ✅ 综合查询改为 /cx
        app.add_handler(CommandHandler("admin", admin_panel))
        
        app.add_handler(CallbackQueryHandler(admin_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        return app

    async def run_with_retry(self):
        """主运行循环 - 使用手动轮询代替 Updater"""
        while True:
            try:
                # 创建并配置应用
                self.app = self.create_application()
                self.app = self.setup_handlers(self.app)
                
                logger.info("🚀 正在启动 Bot...")
                await self.app.initialize()
                await self.app.start()
                
                self.is_running = True
                self.retry_count = 0
                self.polling_errors = 0
                
                # 打印启动信息
                print("=" * 50)
                print("🤖 机器人已成功启动！")
                print(f"👑 管理员ID: {ADMIN_IDS}")
                print(f"📝 已加载 {len(QUOTE_MESSAGES)} 条引用语")
                print("🏛️ 湖南政务OFD查询已加载")
                print("🔎 综合数据查询已加载 (/cx)")
                print("🔄 手动轮询模式（更稳定）")
                print("=" * 50)
                
                # 手动轮询 - 不依赖 Updater
                last_update_id = 0
                error_count = 0
                health_check_count = 0
                
                while True:
                    try:
                        # 使用更短的超时，避免在移动网络上长时间挂起
                        updates = await asyncio.wait_for(
                            self.app.bot.get_updates(
                                offset=last_update_id + 1,
                                timeout=20,
                                allowed_updates=Update.ALL_TYPES
                            ),
                            timeout=25
                        )
                        
                        # 重置错误计数（成功获取更新）
                        error_count = 0
                        self.polling_errors = 0
                        
                        # 处理更新
                        for update in updates:
                            last_update_id = max(last_update_id, update.update_id)
                            try:
                                await self.app.process_update(update)
                            except Exception as e:
                                logger.error(f"处理更新失败: {e}")
                        
                        # 健康检查（每10次轮询检查一次）
                        health_check_count += 1
                        if health_check_count % 10 == 0:
                            try:
                                await self.app.bot.get_me()
                                logger.info(f"💚 Bot 运行正常 (已处理 {health_check_count} 轮询)")
                            except Exception as e:
                                logger.warning(f"⚠️ 健康检查失败: {e}")
                                if health_check_count % 30 == 0:
                                    logger.warning("🔄 主动重启...")
                                    break
                        
                    except asyncio.TimeoutError:
                        # 轮询超时是正常的，继续
                        error_count = 0
                        continue
                        
                    except NetworkError as e:
                        error_count += 1
                        self.polling_errors += 1
                        logger.warning(f"🌐 网络错误 ({error_count}次): {e}")
                        
                        if error_count >= 5:
                            logger.warning("🔄 连续网络错误，主动重启...")
                            break
                            
                        await asyncio.sleep(5)
                        
                    except Exception as e:
                        error_count += 1
                        logger.error(f"❌ 轮询错误: {e}")
                        
                        if error_count >= 3:
                            logger.warning("🔄 连续错误，主动重启...")
                            break
                            
                        await asyncio.sleep(2)
                        
            except Exception as e:
                logger.error(f"❌ 启动失败: {e}", exc_info=True)
                
            finally:
                # 清理资源
                try:
                    if self.app and self.app.running:
                        await self.app.stop()
                        await self.app.shutdown()
                except:
                    pass
                self.is_running = False
                logger.info("🛑 Bot 已停止")
                
            # 重连等待
            wait_time = min(
                self.base_delay * (2 ** min(self.retry_count, 5)),
                self.max_delay
            )
            self.retry_count += 1
            logger.info(f"⏳ {wait_time:.0f} 秒后重新连接... (尝试 {self.retry_count})")
            await asyncio.sleep(wait_time)
# ==================== 主函数 ====================
async def main():
    """程序入口"""
    logger.info("=" * 50)
    logger.info("🤖 Telegram Bot (移动端优化版 - 手动轮询)")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    bot = RobustBot(TOKEN)
    
    try:
        await bot.run_with_retry()
    except KeyboardInterrupt:
        logger.info("👋 用户中断，正在退出...")
    except Exception as e:
        logger.error(f"💥 致命错误: {e}", exc_info=True)
    finally:
        logger.info("✅ Bot 已完全退出")

# ==================== 程序入口 ====================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        print(f"❌ 程序异常退出: {e}")           