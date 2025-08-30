# debug_server.py
import socket
import ssl

# 创建一个简单的原始 TCP socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 8765))

# 手工发送一个格式错误的 HTTP 请求
# 或者一个非 WebSocket 的请求，看服务器如何响应
s.sendall(b'GET / HTTP/1.1\r\nHost: localhost:8765\r\n\r\n')

# 接收服务器的响应
response = s.recv(1024)
print("Server raw response:", repr(response))
s.close()