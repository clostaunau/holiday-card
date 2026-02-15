#!/bin/bash

# Agent Creation Helper Script
# Usage: ./create-agent.sh <agent-name> <agent-type>
# Types: analyzer, generator, specialist, process-guide

AGENT_NAME=$1
AGENT_TYPE=${2:-"analyzer"}

if [ -z "$AGENT_NAME" ]; then
  echo "Usage: $0 <agent-name> [agent-type]"
  echo "Types: analyzer, generator, specialist, process-guide"
  exit 1
fi

AGENT_FILE=".claude/agents/${AGENT_NAME}.md"

mkdir -p .claude/agents

case $AGENT_TYPE in
  "analyzer")
    TOOLS="Read, Grep, Glob, Bash"
    ROLE="analyzer"
    ;;
  "generator")
    TOOLS="Read, Write, Edit, Bash"
    ROLE="generator"
    ;;
  "specialist")
    TOOLS="Read, Grep, Glob"
    ROLE="specialist"
    ;;
  "process-guide")
    TOOLS="Read, Bash"
    ROLE="process guide"
    ;;
  *)
    echo "Unknown type: $AGENT_TYPE"
    exit 1
    ;;
esac

cat > "$AGENT_FILE" <<EOF
---
name: $AGENT_NAME
description: [FILL IN: Clear description of when to use this agent]
tools: $TOOLS
proactive: false
---

# ${AGENT_NAME^} Agent

You are a $ROLE specializing in [FILL IN: domain].

## Your Responsibilities

1. **[FILL IN: Primary Responsibility]**
   - [Task 1]
   - [Task 2]

## Guidelines

1. [FILL IN: Guideline]

## Output Format

[FILL IN: Define output structure]

## Constraints

- Do NOT [FILL IN: constraints]
EOF

echo "Created agent: $AGENT_FILE"
echo "Please edit and fill in the [FILL IN: ...] placeholders"
