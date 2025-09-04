// server/main.go
package main

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
)

// 平台认证服务地址
const AuthServiceURL = "http://localhost:8080/auth" // 通过API网关访问认证服务

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
	userID   uint
	username string
}

// 房间信息
type Room struct {
	clients map[*Client]bool
}

var rooms = make(map[string]*Room)

// 认证请求结构
type AuthRequest struct {
	Type   string `json:"type"`
	Token  string `json:"token"`
	OpenID string `json:"openid"`
	Room   string `json:"room"`
}

// 验证token响应结构
type VerifyResponse struct {
	Valid     bool   `json:"valid"`
	OpenID    string `json:"openid"`
	UserID    uint   `json:"user_id"`
	AppID     string `json:"app_id"`
	Username  string `json:"username"`
	SessionID string `json:"session_id"`
	Exp       int64  `json:"exp"`
	Iat       int64  `json:"iat"`
	Jti       string `json:"jti"`
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
	userInfo, valid := verifyToken(authReq.Token, authReq.OpenID)
	if !valid {
		log.Println("token验证失败")
		conn.WriteMessage(websocket.TextMessage, []byte(`{"type":"auth_failed","reason":"invalid_token"}`))
		return
	}

	log.Printf("用户 %s (ID: %d) 认证成功, 加入房间 %s", userInfo.Username, userInfo.UserID, authReq.Room)

	// 创建客户端
	client := &Client{
		conn:     conn,
		openid:   authReq.OpenID,
		room:     authReq.Room,
		playerID: authReq.OpenID, // 使用openid作为玩家ID
		userID:   userInfo.UserID,
		username: userInfo.Username,
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
		case "get_backpack":
			// 获取用户背包信息
			sendBackpackInfo(client)
		case "get_market":
			// 获取商城信息
			sendMarketInfo(client)
		}
	}
}

func verifyToken(token, openid string) (*VerifyResponse, bool) {
	// 调用平台认证服务的接口验证token
	client := &http.Client{Timeout: 5 * time.Second}

	reqData := map[string]string{
		"token":  token,
		"app_id": "desktop_app", // 应用标识
	}

	jsonData, err := json.Marshal(reqData)
	if err != nil {
		log.Println("序列化请求数据失败:", err)
		return nil, false
	}

	req, err := http.NewRequest("POST", AuthServiceURL+"/check-token", bytes.NewBuffer(jsonData))
	if err != nil {
		log.Println("创建请求失败:", err)
		return nil, false
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Internal-Auth", "your_internal_api_key") // 内部API密钥

	resp, err := client.Do(req)
	if err != nil {
		log.Println("请求认证服务失败:", err)
		return nil, false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, false
	}

	var result VerifyResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		log.Println("解析响应失败:", err)
		return nil, false
	}

	// 验证openid是否匹配
	if result.OpenID != openid {
		return nil, false
	}

	return &result, result.Valid
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
		"username":  client.username,
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
				"username":  client.username,
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
	for roomID, room := range rooms {
		roomList = append(roomList, map[string]interface{}{
			"room":         roomID,
			"player_count": len(room.clients),
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
		players := make([]map[string]interface{}, 0, len(room.clients))
		for client := range room.clients {
			players = append(players, map[string]interface{}{
				"player_id": client.playerID,
				"username":  client.username,
				"user_id":   client.userID,
			})
		}

		response := map[string]interface{}{
			"type":    "player_list",
			"players": players,
		}

		msgBytes, _ := json.Marshal(response)
		client.conn.WriteMessage(websocket.TextMessage, msgBytes)
	}
}

func sendBackpackInfo(client *Client) {
	// 模拟背包数据 - 实际应该从数据库获取
	backpackItems := []map[string]interface{}{
		{
			"id":            1,
			"name":          "可爱小猫皮肤",
			"type":          "skin",
			"acquired_time": "2023-01-15 10:30:00",
			"equipped":      true,
		},
		{
			"id":            2,
			"name":          "炫酷小狗皮肤",
			"type":          "skin",
			"acquired_time": "2023-02-20 14:45:00",
			"equipped":      false,
		},
		{
			"id":            3,
			"name":          "金色边框",
			"type":          "decoration",
			"acquired_time": "2023-03-05 09:15:00",
			"equipped":      true,
		},
	}

	response := map[string]interface{}{
		"type":    "backpack_info",
		"items":   backpackItems,
		"count":   len(backpackItems),
		"user_id": client.userID,
	}

	msgBytes, _ := json.Marshal(response)
	client.conn.WriteMessage(websocket.TextMessage, msgBytes)
}

func sendMarketInfo(client *Client) {
	// 模拟商城数据 - 实际应该从数据库获取
	marketItems := []map[string]interface{}{
		{
			"id":          101,
			"name":        "可爱小猫皮肤",
			"type":        "skin",
			"price":       100,
			"description": "一只可爱的小猫皮肤，让你的宠物更加萌动",
			"image_url":   "/images/cat_skin.png",
		},
		{
			"id":          102,
			"name":        "炫酷小狗皮肤",
			"type":        "skin",
			"price":       150,
			"description": "一只炫酷的小狗皮肤，让你的宠物更加帅气",
			"image_url":   "/images/dog_skin.png",
		},
		{
			"id":          201,
			"name":        "金色边框",
			"type":        "decoration",
			"price":       50,
			"description": "金色边框装饰，让你的宠物更加耀眼",
			"image_url":   "/images/gold_frame.png",
		},
		{
			"id":          202,
			"name":        "银色边框",
			"type":        "decoration",
			"price":       30,
			"description": "银色边框装饰，简约而不失优雅",
			"image_url":   "/images/silver_frame.png",
		},
	}

	response := map[string]interface{}{
		"type":  "market_info",
		"items": marketItems,
		"count": len(marketItems),
	}

	msgBytes, _ := json.Marshal(response)
	client.conn.WriteMessage(websocket.TextMessage, msgBytes)
}
