# Architecture Deep Dive

## System Overview

CodeDebt Guardian is a sophisticated multi-agent system built using **Google's Agent Development Kit (ADK)** and powered by **Gemini 2.0 Flash**. The system employs a sequential orchestration pattern where three specialized agents collaborate to detect, prioritize, and propose fixes for technical debt.

## Core Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────┐
│                CodeDebt Guardian                        │
│                    Orchestrator                         │
│         (Sequential Agent Coordination)                 │
└──────────────────┬──────────────────────────────────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
  ┌───▼───┐   ┌───▼───┐   ┌───▼───┐
  │Agent 1│   │Agent 2│   │Agent 3│
  │ Debt  │   │Priority│  │  Fix  │
  │Detect │   │Ranking│   │Propose│
  └───┬───┘   └───┬───┘   └───┬───┘
      │            │            │
      └────────────┴────────────┘
                   │
     ┌─────────────▼─────────────┐
     │  Shared Infrastructure   │
     │  • Memory Bank            │
     │  • Session Service        │
     │  • Observability Layer    │
     │  • Custom Tools           │
     └───────────────────────────┘
```

## Agent Specifications

### 1. DebtDetectionAgent

**Purpose**: Scans codebases for technical debt patterns using regex-based pattern matching and optional Gemini-powered analysis.

**Capabilities**:
- Pattern-based detection across 8+ debt categories
- Real-time code analysis
- Gemini integration for complex pattern recognition
- Line-by-line scanning with context awareness

**Debt Categories**:
1. **Code Smells**: Empty functions, TODO/FIXME/HACK comments
2. **Security Issues**: eval/exec usage, hardcoded credentials
3. **Performance Problems**: Inefficient loops, long sleeps
4. **Maintainability**: Code duplication, long methods

**Output**: List of `DebtItem` objects with metadata

### 2. Priority RankingAgent

**Purpose**: Evaluates and ranks detected debt items based on business impact and technical severity.

**Ranking Algorithm**:
```python
Priority Score (0-100) = Base Score (50)
                       + Severity Weight (5-40)
                       + Type Weight (5-30)
                       + Context Bonus (0-20)
```

**Severity Weights**:
- Critical: +40 points
- High: +30 points
- Medium: +15 points
- Low: +5 points

**Type Weights**:
- Security: +30 points
- Performance: +15 points
- Maintainability: +10 points
- Code Smell: +5 points

**Output**: Ranked list with priority scores

### 3. FixProposalAgent

**Purpose**: Generates automated fix recommendations and effort estimates.

**Fix Generation Process**:
1. Match debt pattern to fix template library
2. Generate context-aware code suggestions
3. Estimate effort based on severity
4. Provide implementation guidance

**Effort Estimation**:
- Critical: 4-8 hours
- High: 2-4 hours
- Medium: 1-2 hours
- Low: < 1 hour

**Output**: DebtItem objects enriched with fix proposals

## Data Structures

### DebtItem
```python
@dataclass
class DebtItem:
    id: str                    # DEBT-001, DEBT-002, ...
    file_path: str            # Path to file
    line_number: int          # Line where debt detected
    debt_type: str            # Category of debt
    severity: str             # critical/high/medium/low
    description: str          # Human-readable description
    priority_score: float     # 0-100 ranking score
    estimated_effort: str     # Time estimate
    fix_proposal: Optional[str]  # Recommended fix
    detected_at: str          # ISO timestamp
```

### MemoryStore
Manages both short-term (session) and long-term (persistent) memory:

**Short-term Memory**: 
- Stores current analysis context
- Auto-compacts after 100 items
- Used for agent communication

**Long-term Memory**:
- Persists all detected debt items
- Tracks historical trends
- Enables comparative analysis

### ObservabilityLogger
Comprehensive logging and tracing:
- Event logging with timestamps
- Distributed tracing support
- Performance metrics tracking
- Agent decision audit trail

## Orchestration Pattern

### Sequential Workflow

```
1. INITIALIZE
   ├── Load configuration
   ├── Initialize Gemini connection
   ├── Create shared memory/logger
   └── Instantiate 3 agents

2. DETECTION PHASE
   ├── Parse code file
   ├── Apply pattern matching
   ├── Create DebtItem objects
   └── Store in memory

3. RANKING PHASE
   ├── Load detected debts
   ├── Calculate priority scores
   ├── Sort by score (desc)
   └── Update memory

4. FIX PROPOSAL PHASE
   ├── Load ranked debts
   ├── Generate fix templates
   ├── Estimate effort
   └── Enrich debt objects

5. REPORTING
   ├── Compile results
   ├── Generate visualizations
   ├── Calculate metrics
   └── Output reports
```

## Integration Points

### Gemini Integration

**Model**: `gemini-1.5-flash`
**Purpose**: Enhanced code analysis for complex patterns

**Usage Pattern**:
```python
def analyze_with_gemini(code_snippet: str, context: str) -> str:
    prompt = f"""Analyze for {context} issues:
    ```python
    {code_snippet}
    ```
    Provide: 1) Issues, 2) Severity, 3) Fix"""
    return gemini_model.generate_content(prompt).text
```

### Custom Tools

1. **GitHub API Tool**: Repository analysis, issue creation
2. **Code Analysis Tool**: AST parsing, complexity metrics
3. **Visualization Tool**: Dashboard generation

## Performance Characteristics

### Scalability
- **Files**: Handles repositories with 1000+ files
- **Lines**: Processes 100K+ LOC efficiently
- **Patterns**: Matches 50+ patterns per second

### Latency
- Pattern detection: ~10ms per file
- Gemini analysis: ~500ms per query
- Full pipeline: ~5-30 seconds per repo

## Security & Privacy

### Data Handling
- Code never leaves local environment (except Gemini)
- API keys stored in Kaggle Secrets
- No PII collection or storage
- Audit logs for compliance

### Gemini API Security
- Secure HTTPS communication
- Rate limiting and quotas
- Error handling for API failures
- Fallback to rule-based analysis

## Evaluation Metrics

The system includes a comprehensive evaluation framework:

```python
Overall Score = (
    Detection Score × 0.3 +
    Fix Proposal Rate × 0.3 +
    Distribution Balance × 0.2 +
    Priority Accuracy × 0.2
)
```

**Target Metrics**:
- Detection Score: >85/100
- Fix Proposal Rate: >75%
- Average Priority Score: >70/100
- Distribution Balance: >70/100

## Deployment Architecture

### Kaggle Notebook Deployment
- **Environment**: Latest Container Image
- **Resources**: Standard CPU kernel
- **Dependencies**: requirements.txt
- **Output**: /kaggle/working/

### Local Deployment (Planned)
- **Package**: pip install codedebt-guardian
- **CLI**: `codedebt analyze <target>`
- **Configuration**: ~/.codedebt/config.yaml

## Extension Points

### Adding New Agents
```python
class CustomAgent:
    def __init__(self, logger, memory):
        self.logger = logger
        self.memory = memory
    
    def process(self, data):
        # Custom logic
        return results
```

### Custom Debt Patterns
```python
custom_patterns = {
    'my_category': [
        r'pattern1',
        r'pattern2'
    ]
}
agent.debt_patterns.update(custom_patterns)
```

### New Tools
```python
class CustomTool:
    def execute(self, *args, **kwargs):
        # Tool implementation
        pass
```

## Future Enhancements

1. **Real-time Monitoring**: CI/CD pipeline integration
2. **Historical Tracking**: Debt trend analysis over time
3. **Team Dashboard**: Collaborative debt management
4. **Auto-fixing**: Automated PR generation
5. **Multi-language Support**: Beyond Python

## References

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [Gemini API Guide](https://ai.google.dev/)
- [Kaggle Notebook](https://www.kaggle.com/code/priyanshjain01/codedebt-guardian-multi-agent-technical-debt-sys)
- [GitHub Repository](https://github.com/Priyanshjain10/codedebt-guardian)

---

**Author**: Priyansh Jain  
**Project**: 5-Day AI Agents Intensive - Capstone  
**Date**: November 2025
