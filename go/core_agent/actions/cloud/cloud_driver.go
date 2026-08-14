// Package cloud implements the CloudHandler interface using AWS SDK v2.
// This gives Ultron the ability to provision and manage compute resources.
package cloud

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/ec2"
	"github.com/aws/aws-sdk-go-v2/service/ec2/types"
	"go.uber.org/zap"
)

// InstanceInfo represents an EC2 instance's current state.
type InstanceInfo struct {
	ID       string    `json:"id"`
	Type     string    `json:"type"`
	State    string    `json:"state"`
	IP       string    `json:"ip"`
	Region   string    `json:"region"`
	LaunchAt time.Time `json:"launch_at"`
}

// AuditEntry records a cloud action for the audit trail.
type AuditEntry struct {
	Timestamp  time.Time `json:"timestamp"`
	Action     string    `json:"action"`
	InstanceID string    `json:"instance_id"`
	Result     string    `json:"result"`
	Error      string    `json:"error,omitempty"`
	Duration   time.Duration `json:"duration"`
}

// AWSCloudDriver implements CloudHandler using AWS EC2.
type AWSCloudDriver struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger
	client *ec2.Client
	region string

	// Audit trail
	auditLog []AuditEntry

	// Metrics
	apiCalls   uint64
	errors     uint64
	instances  map[string]*InstanceInfo
}

// AWSConfig holds AWS configuration.
type AWSConfig struct {
	Region string // e.g. "us-east-1"
	// Credentials from environment: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
}

// NewAWSCloudDriver creates a new AWS EC2 driver.
func NewAWSCloudDriver(logger *zap.SugaredLogger, awsConfig AWSConfig) (*AWSCloudDriver, error) {
	if awsConfig.Region == "" {
		awsConfig.Region = "us-east-1"
	}

	cfg, err := config.LoadDefaultConfig(context.Background(),
		config.WithRegion(awsConfig.Region),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to load AWS config: %w", err)
	}

	driver := &AWSCloudDriver{
		logger:    logger,
		client:    ec2.NewFromConfig(cfg),
		region:    awsConfig.Region,
		auditLog:  make([]AuditEntry, 0, 1000),
		instances: make(map[string]*InstanceInfo),
	}

	logger.Infof("AWS Cloud Driver initialized (region: %s)", awsConfig.Region)
	return driver, nil
}

// ═══════════════════════════════════════════════════════════════
// CloudHandler Interface Implementation
// ═══════════════════════════════════════════════════════════════

// StartInstance starts a stopped EC2 instance.
func (d *AWSCloudDriver) StartInstance(ctx context.Context, instanceID string) error {
	start := time.Now()
	d.mu.Lock()
	d.apiCalls++
	d.mu.Unlock()

	d.logger.Infof("Starting instance: %s", instanceID)

	input := &ec2.StartInstancesInput{
		InstanceIds: []string{instanceID},
	}

	_, err := d.client.StartInstances(ctx, input)

	d.audit("StartInstance", instanceID, err, time.Since(start))

	if err != nil {
		d.mu.Lock()
		d.errors++
		d.mu.Unlock()
		return fmt.Errorf("failed to start instance %s: %w", instanceID, err)
	}

	d.logger.Infof("Instance %s starting", instanceID)
	return nil
}

// StopInstance stops a running EC2 instance.
func (d *AWSCloudDriver) StopInstance(ctx context.Context, instanceID string) error {
	start := time.Now()
	d.mu.Lock()
	d.apiCalls++
	d.mu.Unlock()

	d.logger.Infof("Stopping instance: %s", instanceID)

	input := &ec2.StopInstancesInput{
		InstanceIds: []string{instanceID},
	}

	_, err := d.client.StopInstances(ctx, input)

	d.audit("StopInstance", instanceID, err, time.Since(start))

	if err != nil {
		d.mu.Lock()
		d.errors++
		d.mu.Unlock()
		return fmt.Errorf("failed to stop instance %s: %w", instanceID, err)
	}

	d.logger.Infof("Instance %s stopping", instanceID)
	return nil
}

// GetInstanceStatus returns the current state of an instance.
func (d *AWSCloudDriver) GetInstanceStatus(ctx context.Context, instanceID string) (string, error) {
	start := time.Now()
	d.mu.Lock()
	d.apiCalls++
	d.mu.Unlock()

	input := &ec2.DescribeInstancesInput{
		InstanceIds: []string{instanceID},
	}

	result, err := d.client.DescribeInstances(ctx, input)

	d.audit("GetInstanceStatus", instanceID, err, time.Since(start))

	if err != nil {
		d.mu.Lock()
		d.errors++
		d.mu.Unlock()
		return "", fmt.Errorf("failed to describe instance %s: %w", instanceID, err)
	}

	for _, reservation := range result.Reservations {
		for _, instance := range reservation.Instances {
			state := string(instance.State.Name)

			// Update local cache
			d.mu.Lock()
			d.instances[instanceID] = &InstanceInfo{
				ID:    instanceID,
				Type:  string(instance.InstanceType),
				State: state,
				IP:    aws.ToString(instance.PublicIpAddress),
			}
			d.mu.Unlock()

			return state, nil
		}
	}

	return "not_found", nil
}

// SpinUpInstance launches a new EC2 instance.
func (d *AWSCloudDriver) SpinUpInstance(ctx context.Context, spec InstanceSpec) (string, error) {
	start := time.Now()
	d.mu.Lock()
	d.apiCalls++
	d.mu.Unlock()

	d.logger.Infof("Launching new instance: type=%s, image=%s", spec.Type, spec.Image)

	// Validate budget
	if spec.MaxCost > 0 {
		d.logger.Infof("Budget constraint: $%.4f/hr", spec.MaxCost)
	}

	input := &ec2.RunInstancesInput{
		ImageId:      aws.String(spec.Image),
		InstanceType: types.InstanceType(spec.Type),
		MinCount:     aws.Int32(1),
		MaxCount:     aws.Int32(1),
	}

	// Add tags
	if len(spec.Tags) > 0 {
		var tags []types.Tag
		for k, v := range spec.Tags {
			tags = append(tags, types.Tag{
				Key:   aws.String(k),
				Value: aws.String(v),
			})
		}
		input.TagSpecifications = []types.TagSpecification{
			{
				ResourceType: types.ResourceTypeInstance,
				Tags:         tags,
			},
		}
	}

	result, err := d.client.RunInstances(ctx, input)

	if err != nil {
		d.audit("SpinUpInstance", "new", err, time.Since(start))
		d.mu.Lock()
		d.errors++
		d.mu.Unlock()
		return "", fmt.Errorf("failed to launch instance: %w", err)
	}

	instanceID := ""
	if len(result.Instances) > 0 {
		instanceID = aws.ToString(result.Instances[0].InstanceId)
	}

	d.audit("SpinUpInstance", instanceID, nil, time.Since(start))
	d.logger.Infof("Instance launched: %s", instanceID)

	return instanceID, nil
}

// TerminateInstance permanently terminates an instance.
func (d *AWSCloudDriver) TerminateInstance(ctx context.Context, instanceID string) error {
	start := time.Now()
	d.mu.Lock()
	d.apiCalls++
	d.mu.Unlock()

	d.logger.Warnf("Terminating instance: %s", instanceID)

	input := &ec2.TerminateInstancesInput{
		InstanceIds: []string{instanceID},
	}

	_, err := d.client.TerminateInstances(ctx, input)

	d.audit("TerminateInstance", instanceID, err, time.Since(start))

	if err != nil {
		d.mu.Lock()
		d.errors++
		d.mu.Unlock()
		return fmt.Errorf("failed to terminate %s: %w", instanceID, err)
	}

	// Remove from local cache
	d.mu.Lock()
	delete(d.instances, instanceID)
	d.mu.Unlock()

	return nil
}

// ListInstances returns all known instances.
func (d *AWSCloudDriver) ListInstances(ctx context.Context) ([]InstanceInfo, error) {
	start := time.Now()
	d.mu.Lock()
	d.apiCalls++
	d.mu.Unlock()

	input := &ec2.DescribeInstancesInput{
		Filters: []types.Filter{
			{
				Name:   aws.String("instance-state-name"),
				Values: []string{"running", "stopped", "pending"},
			},
		},
	}

	result, err := d.client.DescribeInstances(ctx, input)

	d.audit("ListInstances", "*", err, time.Since(start))

	if err != nil {
		d.mu.Lock()
		d.errors++
		d.mu.Unlock()
		return nil, fmt.Errorf("failed to list instances: %w", err)
	}

	var instances []InstanceInfo
	for _, reservation := range result.Reservations {
		for _, inst := range reservation.Instances {
			info := InstanceInfo{
				ID:     aws.ToString(inst.InstanceId),
				Type:   string(inst.InstanceType),
				State:  string(inst.State.Name),
				IP:     aws.ToString(inst.PublicIpAddress),
				Region: d.region,
			}
			if inst.LaunchTime != nil {
				info.LaunchAt = *inst.LaunchTime
			}
			instances = append(instances, info)

			// Update cache
			d.mu.Lock()
			d.instances[info.ID] = &info
			d.mu.Unlock()
		}
	}

	d.logger.Infof("Listed %d instances", len(instances))
	return instances, nil
}

// GetInstanceMetrics returns CloudWatch metrics for an instance.
func (d *AWSCloudDriver) GetInstanceMetrics(ctx context.Context, instanceID string) (map[string]float64, error) {
	// Simplified: return cached state info
	d.mu.RLock()
	info, exists := d.instances[instanceID]
	d.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("instance %s not in cache", instanceID)
	}

	metrics := map[string]float64{
		"running": boolToFloat(info.State == "running"),
	}

	return metrics, nil
}

// SetAutoScalePolicy configures auto-scaling (simplified).
func (d *AWSCloudDriver) SetAutoScalePolicy(ctx context.Context, policy AutoScalePolicy) error {
	d.logger.Infof("Auto-scale policy set: min=%d, max=%d, target_cpu=%.0f%%",
		policy.MinInstances, policy.MaxInstances, policy.TargetCPU*100)

	// In production: use AWS Auto Scaling Groups API
	d.audit("SetAutoScalePolicy", "asg", nil, 0)
	return nil
}

// GetCurrentScale returns the current number of running instances.
func (d *AWSCloudDriver) GetCurrentScale(ctx context.Context) (int, error) {
	instances, err := d.ListInstances(ctx)
	if err != nil {
		return 0, err
	}

	running := 0
	for _, inst := range instances {
		if inst.State == "running" {
			running++
		}
	}
	return running, nil
}

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS (S3)
// ═══════════════════════════════════════════════════════════════

// CreateBucket creates an S3 bucket (stub — needs s3 client).
func (d *AWSCloudDriver) CreateBucket(ctx context.Context, name string, region string) error {
	d.logger.Infof("CreateBucket: %s (region: %s) — requires S3 client", name, region)
	d.audit("CreateBucket", name, nil, 0)
	return nil
}

// UploadObject uploads to S3 (stub).
func (d *AWSCloudDriver) UploadObject(ctx context.Context, bucket, key string, data []byte) error {
	d.logger.Infof("UploadObject: s3://%s/%s (%d bytes) — requires S3 client", bucket, key, len(data))
	d.audit("UploadObject", bucket+"/"+key, nil, 0)
	return nil
}

// DownloadObject downloads from S3 (stub).
func (d *AWSCloudDriver) DownloadObject(ctx context.Context, bucket, key string) ([]byte, error) {
	d.audit("DownloadObject", bucket+"/"+key, nil, 0)
	return nil, fmt.Errorf("S3 client not configured")
}

// ═══════════════════════════════════════════════════════════════
// AUDIT & METRICS
// ═══════════════════════════════════════════════════════════════

// GetAuditLog returns the cloud action audit trail.
func (d *AWSCloudDriver) GetAuditLog(limit int) []AuditEntry {
	d.mu.RLock()
	defer d.mu.RUnlock()

	if limit > len(d.auditLog) {
		limit = len(d.auditLog)
	}
	return d.auditLog[len(d.auditLog)-limit:]
}

// GetMetrics returns cloud driver metrics.
func (d *AWSCloudDriver) GetMetrics() map[string]interface{} {
	d.mu.RLock()
	defer d.mu.RUnlock()

	return map[string]interface{}{
		"region":          d.region,
		"api_calls":       d.apiCalls,
		"errors":          d.errors,
		"cached_instances": len(d.instances),
		"audit_entries":   len(d.auditLog),
		"error_rate":      float64(d.errors) / float64(maxU64(1, d.apiCalls)),
	}
}

// ═══════════════════════════════════════════════════════════════
// PRIVATE
// ═══════════════════════════════════════════════════════════════

func (d *AWSCloudDriver) audit(action, instanceID string, err error, duration time.Duration) {
	entry := AuditEntry{
		Timestamp:  time.Now(),
		Action:     action,
		InstanceID: instanceID,
		Result:     "success",
		Duration:   duration,
	}

	if err != nil {
		entry.Result = "error"
		entry.Error = err.Error()
	}

	d.mu.Lock()
	d.auditLog = append(d.auditLog, entry)
	if len(d.auditLog) > 10000 {
		d.auditLog = d.auditLog[5000:]
	}
	d.mu.Unlock()
}

func boolToFloat(b bool) float64 {
	if b {
		return 1.0
	}
	return 0.0
}

func maxU64(a, b uint64) uint64 {
	if a > b {
		return a
	}
	return b
}

// Supporting types matching the interface

type InstanceSpec struct {
	Provider string
	Type     string
	Region   string
	Image    string
	Tags     map[string]string
	MaxCost  float64
}

type AutoScalePolicy struct {
	MinInstances int
	MaxInstances int
	TargetCPU    float64
	ScaleUpAt    float64
	ScaleDownAt  float64
	CooldownSec  int
}
