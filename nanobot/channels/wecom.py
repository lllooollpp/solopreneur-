"""
企业微信渠道实现
支持企业微信群机器人 Webhook 模式
"""
from dataclasses import dataclass
from typing import Optional
import hashlib
import base64
import struct
from Crypto.Cipher import AES

try:
    from defusedxml import ElementTree as ET
    XML_PARSER_SAFE = True
except ImportError:
    # 如果没有安装defusedxml，使用标准库但禁用危险特性
    import xml.etree.ElementTree as ET
    XML_PARSER_SAFE = False
    import warnings
    warnings.warn(
        "defusedxml not installed. Install it for better XML security: pip install defusedxml",
        UserWarning
    )

from loguru import logger


@dataclass
class WeComConfig:
    """企业微信配置"""
    corp_id: str  # 企业 ID
    agent_id: str  # 应用 ID
    secret: str  # 应用密钥（用于发送消息）
    token: str  # 接口验证 Token（用于接收消息）
    aes_key: str  # 消息加密密钥（Base64 编码）


@dataclass
class WeComMessage:
    """企业微信消息格式"""
    msg_id: str
    from_user: str  # 发送者 UserID
    to_user: str  # 接收者（通常是应用）
    msg_type: str  # text, image, voice 等
    content: str  # 消息内容
    create_time: int  # 时间戳
    agent_id: str  # 应用 ID


class WeComCrypto:
    """企业微信消息加密解密工具"""
    
    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        """
        初始化加密工具
        
        Args:
            token: 接口验证 Token
            encoding_aes_key: 消息加密密钥（Base64 编码，43位）
            corp_id: 企业 ID
        """
        self.token = token
        self.corp_id = corp_id
        
        # 解码 AES Key
        self.aes_key = base64.b64decode(encoding_aes_key + '=')
        if len(self.aes_key) != 32:
            raise ValueError(f"Invalid AES key length: {len(self.aes_key)}")
    
    def decrypt_message(self, encrypt_msg: str) -> str:
        """
        解密企业微信消息
        
        Args:
            encrypt_msg: 加密的消息内容（Base64）
            
        Returns:
            str: 解密后的 XML 字符串
        """
        try:
            # Base64 解码
            cipher_text = base64.b64decode(encrypt_msg)
            
            # AES 解密
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
            plain_text = cipher.decrypt(cipher_text)
            
            # 去除补位字符
            pad = plain_text[-1]
            plain_text = plain_text[:-pad]
            
            # 提取消息内容（去除随机字符串和长度字段）
            content_length = struct.unpack('!I', plain_text[16:20])[0]
            content = plain_text[20:20 + content_length].decode('utf-8')
            
            # 验证 corp_id
            from_corp_id = plain_text[20 + content_length:].decode('utf-8')
            if from_corp_id != self.corp_id:
                logger.warning(f"Corp ID mismatch: expected {self.corp_id}, got {from_corp_id}")
            
            return content
            
        except Exception as e:
            logger.error(f"解密消息失败: {e}")
            raise
    
    def encrypt_message(self, reply_msg: str, nonce: str) -> str:
        """
        加密企业微信回复消息
        
        Args:
            reply_msg: 回复消息的 XML 字符串
            nonce: 随机字符串
            
        Returns:
            str: 加密后的消息（Base64）
        """
        try:
            # 生成随机字符串（16字节）
            import os
            random_str = os.urandom(16)
            
            # 消息内容编码
            msg_bytes = reply_msg.encode('utf-8')
            msg_length = struct.pack('!I', len(msg_bytes))
            corp_id_bytes = self.corp_id.encode('utf-8')
            
            # 拼接内容
            plain_text = random_str + msg_length + msg_bytes + corp_id_bytes
            
            # PKCS7 补位
            block_size = 32
            padding_length = block_size - (len(plain_text) % block_size)
            plain_text += bytes([padding_length] * padding_length)
            
            # AES 加密
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
            cipher_text = cipher.encrypt(plain_text)
            
            # Base64 编码
            return base64.b64encode(cipher_text).decode('utf-8')
            
        except Exception as e:
            logger.error(f"加密消息失败: {e}")
            raise
    
    def generate_signature(self, timestamp: str, nonce: str, encrypt_msg: str) -> str:
        """
        生成消息签名
        
        Args:
            timestamp: 时间戳
            nonce: 随机字符串
            encrypt_msg: 加密消息
            
        Returns:
            str: SHA1 签名
        """
        items = sorted([self.token, timestamp, nonce, encrypt_msg])
        signature = hashlib.sha1(''.join(items).encode('utf-8')).hexdigest()
        return signature
    
    def verify_signature(self, signature: str, timestamp: str, nonce: str, encrypt_msg: str) -> bool:
        """
        验证消息签名
        
        Args:
            signature: 待验证的签名
            timestamp: 时间戳
            nonce: 随机字符串
            encrypt_msg: 加密消息
            
        Returns:
            bool: 签名是否有效
        """
        expected_signature = self.generate_signature(timestamp, nonce, encrypt_msg)
        return signature == expected_signature


def parse_wecom_message(xml_content: str) -> WeComMessage:
    """
    解析企业微信 XML 消息
    
    Args:
        xml_content: XML 字符串
        
    Returns:
        WeComMessage: 解析后的消息对象
    """
    root = ET.fromstring(xml_content)
    
    return WeComMessage(
        msg_id=root.find('MsgId').text if root.find('MsgId') is not None else '',
        from_user=root.find('FromUserName').text,
        to_user=root.find('ToUserName').text,
        msg_type=root.find('MsgType').text,
        content=root.find('Content').text if root.find('Content') is not None else '',
        create_time=int(root.find('CreateTime').text),
        agent_id=root.find('AgentID').text
    )


def build_text_reply(to_user: str, from_user: str, content: str) -> str:
    """
    构建文本回复消息 XML
    
    Args:
        to_user: 接收者 UserID
        from_user: 发送者（应用）
        content: 文本内容
        
    Returns:
        str: XML 字符串
    """
    import time
    
    xml_template = f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""
    
    return xml_template
