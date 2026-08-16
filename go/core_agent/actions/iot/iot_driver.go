// Package iot implements the IoTHandler interface using Eclipse Paho MQTT.
// This gives Ultron the ability to sense and control physical devices.
package iot

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"ultron/core_agent/actions"
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"go.uber.org/zap"
)

// DeviceInfo — alias to canonical type
type DeviceInfo = actions.DeviceInfo

// MQTTDriver implements IoTHandler using the Paho MQTT client.
type MQTTDriver struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger
	client mqtt.Client
	opts   *mqtt.ClientOptions

	// Configuration
	broker   string
	clientID string
	username string
	password string

	// State
	connected    bool
	subscriptions map[string]chan []byte

	// Device registry
	devices map[string]*DeviceInfo

	// Metrics
	messagesPublished uint64
	messagesReceived  uint64
	errors            uint64
	reconnects        uint64
}

// MQTTConfig holds MQTT connection configuration.
type MQTTConfig struct {
	Broker   string // e.g. "tcp://localhost:1883"
	ClientID string
	Username string
	Password string
}

// NewMQTTDriver creates and connects an MQTT client.
func NewMQTTDriver(logger *zap.SugaredLogger, config MQTTConfig) (*MQTTDriver, error) {
	if config.Broker == "" {
		config.Broker = "tcp://localhost:1883"
	}
	if config.ClientID == "" {
		config.ClientID = fmt.Sprintf("ultron-iot-%d", time.Now().UnixNano()%10000)
	}

	driver := &MQTTDriver{
		logger:        logger,
		broker:        config.Broker,
		clientID:      config.ClientID,
		username:      config.Username,
		password:      config.Password,
		subscriptions: make(map[string]chan []byte),
		devices:       make(map[string]*DeviceInfo),
	}

	if err := driver.connect(); err != nil {
		return nil, err
	}

	return driver, nil
}

func (d *MQTTDriver) connect() error {
	opts := mqtt.NewClientOptions().
		AddBroker(d.broker).
		SetClientID(d.clientID).
		SetAutoReconnect(true).
		SetMaxReconnectInterval(30 * time.Second).
		SetKeepAlive(60 * time.Second).
		SetCleanSession(true).
		SetConnectionLostHandler(d.onConnectionLost).
		SetOnConnectHandler(d.onConnect).
		SetReconnectingHandler(d.onReconnecting)

	if d.username != "" {
		opts.SetUsername(d.username)
		opts.SetPassword(d.password)
	}

	d.opts = opts
	d.client = mqtt.NewClient(opts)

	token := d.client.Connect()
	if token.Wait() && token.Error() != nil {
		return fmt.Errorf("MQTT connect failed: %w", token.Error())
	}

	d.mu.Lock()
	d.connected = true
	d.mu.Unlock()

	d.logger.Infof("MQTT connected to %s (client: %s)", d.broker, d.clientID)
	return nil
}

// ═══════════════════════════════════════════════════════════════
// IoTHandler Interface Implementation
// ═══════════════════════════════════════════════════════════════

// MQTTPublish publishes a message to a topic.
func (d *MQTTDriver) MQTTPublish(ctx context.Context, topic string, payload []byte, qos int) error {
	if !d.isConnected() {
		return fmt.Errorf("MQTT not connected")
	}

	token := d.client.Publish(topic, byte(qos), false, payload)
	if token.Wait() && token.Error() != nil {
		d.mu.Lock()
		d.errors++
		d.mu.Unlock()
		return fmt.Errorf("publish failed: %w", token.Error())
	}

	d.mu.Lock()
	d.messagesPublished++
	d.mu.Unlock()

	d.logger.Debugf("Published to %s (%d bytes)", topic, len(payload))
	return nil
}

// MQTTSubscribe subscribes to a topic and returns a channel for messages.
func (d *MQTTDriver) MQTTSubscribe(ctx context.Context, topic string) (<-chan []byte, error) {
	if !d.isConnected() {
		return nil, fmt.Errorf("MQTT not connected")
	}

	msgCh := make(chan []byte, 100)

	handler := func(client mqtt.Client, msg mqtt.Message) {
		d.mu.Lock()
		d.messagesReceived++
		d.mu.Unlock()

		select {
		case msgCh <- msg.Payload():
		default:
			d.logger.Warn("Message channel full, dropping message")
		}
	}

	token := d.client.Subscribe(topic, 1, handler)
	if token.Wait() && token.Error() != nil {
		close(msgCh)
		return nil, fmt.Errorf("subscribe failed: %w", token.Error())
	}

	d.mu.Lock()
	d.subscriptions[topic] = msgCh
	d.mu.Unlock()

	d.logger.Infof("Subscribed to: %s", topic)
	return msgCh, nil
}

// MQTTUnsubscribe removes a topic subscription.
func (d *MQTTDriver) MQTTUnsubscribe(ctx context.Context, topic string) error {
	token := d.client.Unsubscribe(topic)
	if token.Wait() && token.Error() != nil {
		return fmt.Errorf("unsubscribe failed: %w", token.Error())
	}

	d.mu.Lock()
	if ch, ok := d.subscriptions[topic]; ok {
		close(ch)
		delete(d.subscriptions, topic)
	}
	d.mu.Unlock()

	d.logger.Infof("Unsubscribed from: %s", topic)
	return nil
}

// ListDevices returns all known IoT devices.
func (d *MQTTDriver) ListDevices(ctx context.Context) ([]DeviceInfo, error) {
	d.mu.RLock()
	defer d.mu.RUnlock()

	devices := make([]DeviceInfo, 0, len(d.devices))
	for _, dev := range d.devices {
		devices = append(devices, *dev)
	}
	return devices, nil
}

// SendCommand sends a command to a specific device.
func (d *MQTTDriver) SendCommand(ctx context.Context, deviceID string, command string, params map[string]interface{}) error {
	// Build command payload
	payload := map[string]interface{}{
		"device_id": deviceID,
		"command":   command,
		"params":    params,
		"timestamp": time.Now().Unix(),
		"source":    "ultron",
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal command: %w", err)
	}

	// Publish to device command topic
	topic := fmt.Sprintf("devices/%s/commands", deviceID)
	return d.MQTTPublish(ctx, topic, data, 1)
}

// GetDeviceState returns the current state of a device.
func (d *MQTTDriver) GetDeviceState(ctx context.Context, deviceID string) (map[string]interface{}, error) {
	d.mu.RLock()
	dev, exists := d.devices[deviceID]
	d.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("device %s not found", deviceID)
	}

	return map[string]interface{}{
		"id":        dev.ID,
		"name":      dev.Name,
		"type":      dev.Type,
		"online":    dev.Online,
		"last_seen": dev.LastSeen,
	}, nil
}

// ModbusRead reads from a Modbus device (stub — needs modbus library).
func (d *MQTTDriver) ModbusRead(ctx context.Context, address int, count int) ([]byte, error) {
	// In production: use goburrow/modbus
	return nil, fmt.Errorf("Modbus not configured — requires physical serial/TCP connection")
}

// ModbusWrite writes to a Modbus device (stub).
func (d *MQTTDriver) ModbusWrite(ctx context.Context, address int, data []byte) error {
	return fmt.Errorf("Modbus not configured — requires physical serial/TCP connection")
}

// ═══════════════════════════════════════════════════════════════
// CONVENIENCE METHODS
// ═══════════════════════════════════════════════════════════════

// ToggleLight sends a toggle command to a light actuator.
func (d *MQTTDriver) ToggleLight(ctx context.Context, lightID string, state bool) error {
	stateStr := "OFF"
	if state {
		stateStr = "ON"
	}

	topic := fmt.Sprintf("home/actuators/%s/set", lightID)
	payload := []byte(stateStr)

	d.logger.Infof("Toggling light %s → %s", lightID, stateStr)
	return d.MQTTPublish(ctx, topic, payload, 1)
}

// ReadTemperature subscribes to a temperature sensor and reads one value.
func (d *MQTTDriver) ReadTemperature(ctx context.Context, sensorID string, timeout time.Duration) (float64, error) {
	topic := fmt.Sprintf("home/sensors/%s/temp", sensorID)

	msgCh, err := d.MQTTSubscribe(ctx, topic)
	if err != nil {
		return 0, err
	}
	defer d.MQTTUnsubscribe(ctx, topic)

	select {
	case msg := <-msgCh:
		var reading struct {
			Temperature float64 `json:"temperature"`
		}
		if err := json.Unmarshal(msg, &reading); err != nil {
			// Try plain float
			var temp float64
			if err2 := json.Unmarshal(msg, &temp); err2 != nil {
				return 0, fmt.Errorf("failed to parse temperature: %w", err)
			}
			return temp, nil
		}
		return reading.Temperature, nil

	case <-time.After(timeout):
		return 0, fmt.Errorf("timeout waiting for temperature reading")

	case <-ctx.Done():
		return 0, ctx.Err()
	}
}

// RegisterDevice adds a device to the known device registry.
func (d *MQTTDriver) RegisterDevice(device DeviceInfo) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.devices[device.ID] = &device
}

// Disconnect cleanly disconnects from the MQTT broker.
func (d *MQTTDriver) Disconnect() {
	d.client.Disconnect(5000) // 5s grace period
	d.mu.Lock()
	d.connected = false
	d.mu.Unlock()
	d.logger.Info("MQTT disconnected")
}

// GetMetrics returns IoT driver metrics.
func (d *MQTTDriver) GetMetrics() map[string]interface{} {
	d.mu.RLock()
	defer d.mu.RUnlock()

	return map[string]interface{}{
		"connected":          d.connected,
		"broker":             d.broker,
		"messages_published": d.messagesPublished,
		"messages_received":  d.messagesReceived,
		"errors":             d.errors,
		"reconnects":         d.reconnects,
		"subscriptions":      len(d.subscriptions),
		"known_devices":      len(d.devices),
	}
}

// ═══════════════════════════════════════════════════════════════
// CALLBACKS
// ═══════════════════════════════════════════════════════════════

func (d *MQTTDriver) onConnect(client mqtt.Client) {
	d.mu.Lock()
	d.connected = true
	d.mu.Unlock()
	d.logger.Info("MQTT connected")

	// Re-subscribe to all topics after reconnect
	d.mu.RLock()
	topics := make([]string, 0, len(d.subscriptions))
	for topic := range d.subscriptions {
		topics = append(topics, topic)
	}
	d.mu.RUnlock()

	for _, topic := range topics {
		d.client.Subscribe(topic, 1, nil)
	}
}

func (d *MQTTDriver) onConnectionLost(client mqtt.Client, err error) {
	d.mu.Lock()
	d.connected = false
	d.errors++
	d.mu.Unlock()
	d.logger.Warnf("MQTT connection lost: %v", err)
}

func (d *MQTTDriver) onReconnecting(client mqtt.Client, opts *mqtt.ClientOptions) {
	d.mu.Lock()
	d.reconnects++
	d.mu.Unlock()
	d.logger.Info("MQTT reconnecting...")
}

func (d *MQTTDriver) isConnected() bool {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return d.connected
}
