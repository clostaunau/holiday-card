# Agent & Skill Templates

This directory contains reusable templates for creating Claude Code agents and skills.

## Templates

### Test Templates

- **unit-test.template** - Template for creating unit tests following AAA pattern
- **integration-test.template** - Template for creating integration tests with database setup

### Creation Scripts

- **create-agent.sh** - Helper script to create new agents with proper structure
- **create-skill.sh** - Helper script to create new skills with proper structure

## Usage

### Creating an Agent

```bash
# Basic usage
./templates/create-agent.sh my-agent analyzer

# Types available:
# - analyzer: Read-only analysis agents (Read, Grep, Glob, Bash)
# - generator: Content generation agents (Read, Write, Edit, Bash)
# - specialist: Domain expert agents (Read, Grep, Glob)
# - process-guide: Process execution guides (Read, Bash)
```

### Creating a Skill

```bash
# Basic usage
./templates/create-skill.sh my-skill conventions

# Types available:
# - conventions: Standards and conventions documentation
# - process: Process and procedure documentation
# - domain-knowledge: Technical domain knowledge
```

### Using Test Templates

Copy the appropriate template and replace the placeholders:

```bash
# For unit tests
cp templates/unit-test.template tests/unit/my-module.test.js
# Edit and replace [placeholders]

# For integration tests
cp templates/integration-test.template tests/integration/my-feature.integration.test.js
# Edit and replace [placeholders]
```

## Placeholders

Templates use `[PLACEHOLDER]` syntax for values you need to fill in:

- `[module-name]` - Name of the module being tested
- `[ClassOrFunction]` - The class or function name
- `[methodName]` - Method name being tested
- `[FILL IN: ...]` - Instructions for what to add

## See Also

- Main skill: `.claude/skills/agent-skill-templates/SKILL.md`
- Agent builder: `.claude/agents/agent-builder.md`
- Skill builder: `.claude/agents/skill-builder.md`
