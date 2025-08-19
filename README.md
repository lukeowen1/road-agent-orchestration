# ROAD: Rapid Onboarding Agent for Developers

## Project Structure

```
codebase-evaluator/
├── codebase_analyser.py     # Analyses Python code 
├── codebase_evaluator.py    # LLM evaluation logic 
├── workflow.py     # LangGraph orchestration 
└── main.py         # Entry point 
```

## Installation

- **Clone the repository via terminal**
    ```sh
    git clone https://github.com/lukeowen1/road-agent-orchestration.git
    cd road-agent-orchestration
    ```
- **Use the terminal to create a virtual environment called venv**
    ```sh
    python -m venv venv
    ```
- **Activate the virtual environment**
    ```sh
    source venv/bin/activate 
    ``` 
- **Install pip / check the latest version is running**
    ```sh
    python3 -m pip install --upgrade pip`
    python3 -m pip --version
    ```
- **Install external packages and libraries**
    ```sh
    pip install -r requirements.txt
    ```
- **Set OpenAI_API_KEY**
    ```sh
    export OPENAI_API_KEY="sk-..."
    ```
- **Run Evaluation**
     ```sh
     python3 main.py /path/to/your/codebase
     ```

## Step 1: Evaluate whether a codebase is simple enough to be visualised by an LLM adhering to C4 Architecture diagram standards.

Initial metrics gathered about the codebase using [AST](https://docs.python.org/3/library/ast.html) then an LLM call to evaluate whether the codebase is simple enough to be visualised.

## How It Works

```mermaid
graph LR
    A[Your Codebase] --> B[Analyzer]
    B --> C[Metrics & Structure]
    C --> D[LLM Evaluator]
    D --> E[Decision]
    E --> F[Summary]
```

### Components

1. **Analyzer** (`codebase_analyser.py`)
   - Counts files, lines, classes, functions
   - Detects frameworks and patterns
   - Extracts code samples

2. **Evaluator** (`codebase_evaluator.py`)
   - Sends analysis to LLM
   - Gets structured decision
   - Handles response parsing

3. **Workflow** (`workflow.py`)
   - Orchestrates the pipeline
   - Manages state between steps
   - Creates summary

4. **Main** (`main.py`)
   - Command-line interface
   - Input validation
   - Result formatting

## Example Output

```
🔍 Evaluating: /path/to/project
============================================================

═══════════════════════════════════════════════════════════════
                    EVALUATION COMPLETE
═══════════════════════════════════════════════════════════════

Codebase: /path/to/project

Metrics:
• Files: 25
• Lines: 2,500
• Frameworks: FastAPI, SQLAlchemy

Decision:
• Complexity: SIMPLE
• Score: 3.5/10
• Can Generate C4: YES

Reasoning:
This is a well-structured FastAPI application with clear boundaries.
Single service architecture with standard patterns makes it suitable
for automated C4 diagram generation.
```

## Customization

### Use Different LLM Model

Edit `workflow.py`, line 24:
```python
llm = ChatOpenAI(model="gpt-4", temperature=0.1) 
```

### Adjust Complexity Thresholds

Edit `codebase_evaluator.py`, system message:
```python
- Simple: < 100 files  # Change these numbers
- Moderate: 100-300 files
- Complex: > 300 files
```

### Add More Metrics

Extend `codebase_analyser.py`:
```python
# Add new metrics to analyze_file()
if isinstance(node, ast.AsyncFunctionDef):
    result['async_functions'] += 1
```

## Use Cases

**Good for:**
- Single service APIs
- Small to medium libraries
- Monolithic applications < 10k lines
- Clear architectural patterns

**Not suitable for:**
- Large microservice systems
- Highly coupled legacy code
- Multi-language projects
- > 50k lines of code

## Integration

### Use in Python Code

```python
from workflow import create_workflow

# Create workflow
workflow = create_workflow()

# Run evaluation
result = workflow.invoke({
    "codebase_path": "./my_project",
    "analysis": {},
    "decision": {},
    "summary": ""
})

# Check decision
if result['decision']['can_use_llm']:
    print("Ready for C4 generation!")
else:
    print("Too complex for automated C4")
```

### Next Steps

If evaluation is successful, feed the analysis to a C4 generation agent:

```python
if decision['can_use_llm']:
    # Your C4 generator would use the same analysis
    c4_diagrams = generate_c4_diagrams(result['analysis'])
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API Key Error | Set `OPENAI_API_KEY` environment variable |
| Rate Limit | Use `gpt-4` or add delays |
| No Python Files | Check path and ensure `.py` files exist |
| JSON Parse Error | LLM response format issue, check prompt |

## Performance

- **Analysis Time**: 1-3 seconds
- **LLM Call**: 2-5 seconds  
- **Total**: 3-8 seconds
- **Cost**: $0.002-$0.005 per evaluation (GPT-4)

## License

MIT
