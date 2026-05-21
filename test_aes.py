#!/usr/bin/env python3
import json
import base64
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

def aes_encrypt():
    json_data = '{"method":"checkin"}'
    print(f"原始 JSON 数据: {json_data}")
    print(f"原始 JSON 数据类型: {type(json_data)}")
    
    aes_key = datetime.now().strftime("%Y%m%d")
    aes_key = aes_key + aes_key[::-1]
    print(f"AES 密钥: {aes_key}")
    print(f"AES 密钥长度: {len(aes_key)}")
    
    aes_iv = "ZZWBKJ_ZHIHUAWEI"
    print(f"AES IV: {aes_iv}")
    
    cipher = Cipher(
        algorithms.AES(aes_key.encode("utf-8")),
        modes.CBC(aes_iv.encode("utf-8")),
        backend=default_backend(),
    )
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    
    padded_data = padder.update(json_data.encode("utf-8")) + padder.finalize()
    print(f"填充后的数据: {padded_data}")
    
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    print(f"加密后的数据: {ciphertext}")
    
    result = base64.b64encode(ciphertext).decode()
    print(f"Base64 编码后: {result}")
    
    return result

if __name__ == "__main__":
    print("=== 测试 AES 加密 ===")
    encrypted = aes_encrypt()
    print(f"\n最终结果: {encrypted}")
