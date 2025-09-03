// server/main.go
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
)

// 平台认证服务地址
const AuthServiceURL = "http://localhost:8081" // 假设认证服务运行在8081端口

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // 允许所有跨域请求
	},
}

// 客户端连接信息
type Client struct {
	conn     *websocket.Conn
	openid   string
	room     string
	playerID string
}

// 房间信息
type Room struct {
	clients map[*Client]bool
}

var rooms = make(map[string]*Room)

// 认证请求结构
type AuthRequest struct {
	Type  string `json:"type"`
	Token string `json:"token"`
	OpenID string `json:"openid"`
	Room  string `json:"room"`
}

// 验证token响应结构
type VerifyResponse struct {
	Valid   bool   `json:"valid"`
	OpenID  string `json:"openid"`
	UserID  uint   `json:"user_id"`
	AppID   string `json:"app_id"`
	Username string `json:"username"`
}

func main() {
	http.HandleFunc("/ws", handleWebSocket)
	log.Println("WebSocket服务器启动在 :8765")
	log.Fatal(http.ListenAndServe(":8765", nil))
}

func handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("升级WebSocket连接失败:", err)
		return
	}
	defer conn.Close()

	// 首先等待客户端发送认证消息
	_, message, err := conn.ReadMessage()
	if err != nil {
		log.Println("读取认证消息失败:", err)
		return
	}

	var authReq AuthRequest
	if err := json.Unmarshal(message, &authReq); err != nil {
		log.Println("解析认证消息失败:", err)
		return
	}

	// 验证token
	if !verifyToken(authReq.Token, authReq.OpenID) {
		log.Println("token验证失败")
		conn.WriteMessage(websocket.TextMessage, []byte(`{"type":"auth_failed","reason":"invalid_token"}`))
		return
	}

	log.Printf("用户 %s 认证成功, 加入房间 %s", authReq.OpenID, authReq.Room)

	// 创建客户端
	client := &Client{
		conn:     conn,
		openid:   authReq.OpenID,
		room:     authReq.Room,
		playerID: authReq.OpenID, // 使用openid作为玩家ID
	}

	// 加入房间
	joinRoom(client, authReq.Room)

	// 发送认证成功消息
	conn.WriteMessage(websocket.TextMessage, []byte(`{"type":"auth_success"}`))

	// 处理客户端消息
	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			log.Println("读取消息失败:", err)
			leaveRoom(client)
			return
		}

		// 解析消息
		var msg map[string]interface{}
		if err := json.Unmarshal(message, &msg); err != nil {
			log.Println("解析消息失败:", err)
			continue
		}

		// 验证消息中的token（可选，可以根据需要决定是否每次都要验证）
		if token, ok := msg["token"].(string); ok {
			if !verifyToken(token, client.openid) {
				log.Println("消息token验证失败")
				continue
			}
		}

		// 处理不同类型的消息
		msgType, ok := msg["type"].(string)
		if !ok {
			continue
		}

		switch msgType {
		case "action":
			// 广播动作给同房间其他玩家
			broadcastToRoom(client.room, client, message)
		case "chat":
			// 广播聊天消息给同房间其他玩家
			broadcastToRoom(client.room, client, message)
		case "list_rooms":
			// 返回房间列表
			sendRoomList(client)
		}
	}
}

func verifyToken(token, openid string) bool {
	// 这里应该调用平台认证服务的接口验证token
	// 简化实现：直接返回true，实际项目中需要实现真正的验证逻辑
	// 实际实现应该发送HTTP请求到认证服务的/check-token接口
	
	// 示例实现（需要取消注释并完善）：
	/*
	client := &http.Client{Timeout: 5 * time.Second}
	
	reqData := map[string]string{
		"token": token,
		"app_id": "desktop_app", // 应用标识
	}
	
	jsonData, err := json.Marshal(reqData)
	if err != nil {
		log.Println("序列化请求数据失败:", err)
		return false
	}
	
	req, err := http.NewRequest("POST", AuthServiceURL+"/check-token", bytes.NewBuffer(jsonData))
	if err != nil {
		log.Println("创建请求失败:", err)
		return false
	}
	
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Internal-Auth", "your_internal_api_key") // 内部API密钥
	
	resp, err := client.Do(req)
	if err != nil {
		log.Println("请求认证服务失败:", err)
		return false
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return false
	}
	
	var result VerifyResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		log.Println("解析响应失败:", err)
		return false
	}
	
	// 验证openid是否匹配
	if result.OpenID != openid {
		return false
	}
	
	return result.Valid
	*/
	
	// 临时实现：总是返回true
	return true
}

func joinRoom(client *Client, roomID string) {
	// 如果房间不存在，创建新房间
	if _, exists := rooms[roomID]; !exists {
		rooms[roomID] = &Room{
			clients: make(map[*Client]bool),
		}
	}

	// 将客户端加入房间
	rooms[roomID].clients[client] = true
	client.room = roomID

	// 通知房间内其他玩家有新玩家加入
	joinMsg := map[string]interface{}{
		"type":      "player_joined",
		"player_id": client.playerID,
	}
	msgBytes, _ := json.Marshal(joinMsg)
	broadcastToRoom(roomID, client, msgBytes)

	// 发送当前房间玩家列表给新玩家
	sendPlayerList(client)
}

func leaveRoom(client *Client) {
	if room, exists := rooms[client.room]; exists {
		// 从房间中移除客户端
		delete(room.clients, client)

		// 如果房间为空，删除房间
		if len(room.clients) == 0 {
			delete(rooms, client.room)
		} else {
			// 通知房间内其他玩家有玩家离开
			leaveMsg := map[string]interface{}{
				"type":      "player_left",
				"player_id": client.playerID,
			}
			msgBytes, _ := json.Marshal(leaveMsg)
			broadcastToRoom(client.room, client, msgBytes)
		}
	}
}

func broadcastToRoom(roomID string, sender *Client, message []byte) {
	if room, exists := rooms[roomID]; exists {
		for client := range room.clients {
			if client != sender { // 不发送给发送者自己
				err := client.conn.WriteMessage(websocket.TextMessage, message)
				if err != nil {
					log.Println("发送消息失败:", err)
					client.conn.Close()
					delete(room.clients, client)
				}
			}
		}
	}
}

func sendRoomList(client *Client) {
	roomList := make([]map[string]interface{}, 0)
	for roomID := range rooms {
		roomList = append(roomList, map[string]interface{}{
			"room":        roomID,
			"player_count": len(rooms[roomID].clients),
		})
	}

	response := map[string]interface{}{
		"type":  "room_list",
		"rooms": roomList,
	}

	msgBytes, _ := json.Marshal(response)
	client.conn.WriteMessage(websocket.TextMessage, msgBytes)
}

func sendPlayerList(client *Client) {
	if room, exists := rooms[client.room]; exists {
		playerIDs := make([]string, 0, len(room.clients))
		for client := range room.clients {
			playerIDs = append(playerIDs, client.playerID)
		}

		response := map[string]interface{}{
			"type":    "player_list",
			"players": playerIDs,
		}

		msgBytes, _ := json.Marshal(response)
		client.conn.WriteMessage(websocket.TextMessage, msgBytes)
	}
}