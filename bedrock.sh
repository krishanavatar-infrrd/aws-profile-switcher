#!/bin/bash

# Claude Code AWS Bedrock Configuration
# This script sets up environment variables for Claude Code to use AWS Bedrock
# Your AWS credentials from ~/.aws/credentials will be used automatically

# Required: Enable Bedrock integration
export CLAUDE_CODE_USE_BEDROCK=1

# Required: Set your AWS region (change to your preferred region)
export AWS_REGION=us-west-2

# Optional: If you want to use a specific AWS profile from ~/.aws/config
# Uncomment and set your profile name:
# export AWS_PROFILE=your-profile-name

# Optional: Override the region for the small/fast model (Haiku)
# export ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION=us-west-2

# Optional: Pin specific model versions (recommended for production)
# This prevents breaking when new models are released
# export ANTHROPIC_DEFAULT_OPUS_MODEL='us.anthropic.claude-opus-4-6-v1'
# export ANTHROPIC_DEFAULT_SONNET_MODEL='us.anthropic.claude-sonnet-4-6'
# export ANTHROPIC_DEFAULT_HAIKU_MODEL='us.anthropic.claude-haiku-4-5-20251001-v1:0'

# export ANTHROPIC_BEDROCK_BASE_URL=https://bedrock-runtime.us-east-1.amazonaws.com

# Optional: Disable prompt caching if needed
# export DISABLE_PROMPT_CACHING=1
