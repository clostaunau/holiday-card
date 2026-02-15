#!/bin/bash

# Skill Creation Helper Script
# Usage: ./create-skill.sh <skill-name> <skill-type>
# Types: conventions, process, domain-knowledge

SKILL_NAME=$1
SKILL_TYPE=${2:-"conventions"}

if [ -z "$SKILL_NAME" ]; then
  echo "Usage: $0 <skill-name> [skill-type]"
  echo "Types: conventions, process, domain-knowledge"
  exit 1
fi

SKILL_DIR=".claude/skills/${SKILL_NAME}"
SKILL_FILE="${SKILL_DIR}/SKILL.md"

mkdir -p "$SKILL_DIR"
mkdir -p "${SKILL_DIR}/templates"
mkdir -p "${SKILL_DIR}/examples"

cat > "$SKILL_FILE" <<EOF
---
name: $SKILL_NAME
description: [FILL IN: Clear description with keywords]
---

# ${SKILL_NAME^} Skill

## Purpose

[FILL IN: What this skill teaches and when to use it]

## Instructions

1. **[FILL IN: Step 1]**
   - [Detail]

## Examples

### Example 1: [FILL IN: Scenario]

❌ **Bad:**
\`\`\`
[Bad example]
\`\`\`

✅ **Good:**
\`\`\`
[Good example]
\`\`\`

## Best Practices

1. **[FILL IN: Practice]**
   - [Why it matters]

## Common Pitfalls

### Pitfall 1: [FILL IN: Name]
**How to avoid:** [Solution]

## Related Skills

- **[related-skill]**: [Relationship]
EOF

echo "Created skill: $SKILL_FILE"
echo "Created directories:"
echo "  - ${SKILL_DIR}/templates/"
echo "  - ${SKILL_DIR}/examples/"
echo ""
echo "Please edit and fill in the [FILL IN: ...] placeholders"
